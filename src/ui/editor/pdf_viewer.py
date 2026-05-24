from __future__ import annotations

import contextlib

import fitz  # PyMuPDF
from PyQt6.QtCore import QRect, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

# Matches BG_BASE in theme.py — used to fill the label margins around the page.
_BG_COLOR = QColor("#080E1A")


class _RenderWorker(QThread):
    """Renders a single PDF page at an arbitrary DPI and emits a cropped QPixmap."""

    rendered = pyqtSignal(QPixmap)

    def __init__(
        self,
        doc_path: str,
        page_index: int,
        dpi: float,
        crop_rect: QRect,
    ) -> None:
        super().__init__()
        self._doc_path = doc_path
        self._page_index = page_index
        self._dpi = dpi
        self._crop_rect = crop_rect

    def run(self) -> None:
        doc = fitz.open(self._doc_path)
        try:
            page = doc[self._page_index]
            scale = self._dpi / 72.0
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            image = QImage(
                pix.samples, pix.width, pix.height, pix.stride,
                QImage.Format.Format_RGB888,
            )
            full_pm = QPixmap.fromImage(image)
            cropped = full_pm.copy(self._crop_rect.intersected(full_pm.rect()))
            self.rendered.emit(cropped)
        finally:
            doc.close()


class PDFViewer(QWidget):
    """Renders a single PDF page as a QPixmap.

    The rendered pixmap is available through :attr:`pixmap` for coordinate
    mapping by :class:`GridEditor`. At zoom=1.0 the page is scaled to fit the
    viewer while preserving aspect ratio. At zoom>1.0 a sub-region is rendered
    at higher DPI via a background thread for sharpness.
    """

    RENDER_DPI: int = 150
    _MAX_ZOOM: float = 8.0
    _MIN_ZOOM: float = 1.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pdfViewer")

        self._doc: fitz.Document | None = None
        self._doc_path: str | None = None
        self._page_index: int = 0
        self._original_pixmap: QPixmap | None = None

        # Zoom/pan state. _viewport_cx/cy is the page point (in 150-DPI pixel
        # coords) currently centred in the label.
        self._zoom: float = 1.0
        self._viewport_cx: float = 0.0
        self._viewport_cy: float = 0.0

        # Background re-render support.
        self._render_worker: _RenderWorker | None = None
        self._render_dst_x: int = 0
        self._render_dst_y: int = 0
        self._render_lw: int = 0
        self._render_lh: int = 0
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._start_render)

        self._label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._label.setObjectName("pdfPageLabel")
        self._label.setScaledContents(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(56, 56, 32, 32)
        layout.setSpacing(0)
        layout.addWidget(self._label)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def page_count(self) -> int:
        return len(self._doc) if self._doc else 0

    @property
    def page_index(self) -> int:
        return self._page_index

    @property
    def pixmap(self) -> QPixmap | None:
        """Full-resolution pixmap in 150-DPI pixel space."""
        return self._original_pixmap

    @property
    def zoom_level(self) -> float:
        return self._zoom

    def open(self, path: str) -> None:
        if self._doc is not None:
            self._doc.close()
        self._doc_path = path
        self._doc = fitz.open(path)
        self._page_index = 0
        self._render()

    def load_page(self, index: int) -> None:
        if self._doc and 0 <= index < len(self._doc):
            self._page_index = index
            self._render()

    def render_dpi_scale(self) -> float:
        """Scale factor from PDF points to rendered pixels."""
        return self.RENDER_DPI / 72.0

    def zoom_at(self, display_x: int, display_y: int, new_zoom: float) -> None:
        """Zoom to *new_zoom* keeping the PDF point under the cursor fixed.

        *display_x/y* must be in the viewer widget's coordinate space.
        """
        if self._original_pixmap is None:
            return

        old_ox, old_oy = self.display_to_original_coords(display_x, display_y)
        new_zoom = max(self._MIN_ZOOM, min(self._MAX_ZOOM, new_zoom))
        self._zoom = new_zoom

        if new_zoom <= 1.0:
            self._reset_viewport()
        else:
            label_rect = self._label.geometry()
            local_x = display_x - label_rect.x()
            local_y = display_y - label_rect.y()
            ds = self._fit_scale() * new_zoom
            lw = self._label.width()
            lh = self._label.height()
            new_vx = old_ox - local_x / ds
            new_vy = old_oy - local_y / ds
            self._viewport_cx = new_vx + (lw / ds) / 2.0
            self._viewport_cy = new_vy + (lh / ds) / 2.0

        self._update_display()

    def pan_by(self, ddx: int, ddy: int) -> None:
        """Pan by *ddx/ddy* display pixels. No-op at fit-to-view."""
        if self._zoom <= 1.0 or self._original_pixmap is None:
            return
        ds = self._fit_scale() * self._zoom
        self._viewport_cx -= ddx / ds
        self._viewport_cy -= ddy / ds
        self._update_display()

    def reset_zoom(self) -> None:
        """Return to fit-to-view and cancel any in-flight re-render."""
        self._render_timer.stop()
        self._discard_worker()
        self._zoom = 1.0
        self._reset_viewport()
        self._fit_pixmap()

    def display_to_original_coords(self, x: int, y: int) -> tuple[int, int]:
        """Map viewer/display coordinates to 150-DPI PDF pixel coordinates."""
        if self._original_pixmap is None:
            return x, y

        label_rect = self._label.geometry()
        local_x = x - label_rect.x()
        local_y = y - label_rect.y()

        if self._zoom <= 1.0:
            pm = self._label.pixmap()
            if pm is None or pm.width() == 0:
                return x, y
            page_x = (self._label.width() - pm.width()) // 2
            page_y = (self._label.height() - pm.height()) // 2
            scale = pm.width() / self._original_pixmap.width()
            return round((local_x - page_x) / scale), round((local_y - page_y) / scale)

        ds = self._fit_scale() * self._zoom
        vx, vy = self._viewport_origin()
        return round(local_x / ds + vx), round(local_y / ds + vy)

    def original_to_display_coords(self, x: int, y: int) -> tuple[int, int]:
        """Map 150-DPI PDF pixel coordinates to viewer/display coordinates."""
        if self._original_pixmap is None or self._original_pixmap.width() == 0:
            return x, y

        label_rect = self._label.geometry()

        if self._zoom <= 1.0:
            pm = self._label.pixmap()
            if pm is None:
                return x, y
            page_x = (self._label.width() - pm.width()) // 2
            page_y = (self._label.height() - pm.height()) // 2
            scale = pm.width() / self._original_pixmap.width()
            return (
                label_rect.x() + round(x * scale) + page_x,
                label_rect.y() + round(y * scale) + page_y,
            )

        ds = self._fit_scale() * self._zoom
        vx, vy = self._viewport_origin()
        return (
            label_rect.x() + round((x - vx) * ds),
            label_rect.y() + round((y - vy) * ds),
        )

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        if self._zoom <= 1.0:
            self._fit_pixmap()
        else:
            # Viewport centre is in original coords and stays fixed across resize.
            self._show_placeholder()
            self._render_timer.start(150)

    # ------------------------------------------------------------------
    # Internal — zoom helpers
    # ------------------------------------------------------------------

    def _fit_scale(self) -> float:
        """Uniform scale factor so the page fills the label at zoom=1.0."""
        if self._original_pixmap is None:
            return 1.0
        lw = self._label.width()
        lh = self._label.height()
        if lw == 0 or lh == 0:
            return 1.0
        return min(lw / self._original_pixmap.width(), lh / self._original_pixmap.height())

    def _viewport_origin(self) -> tuple[float, float]:
        """Top-left of the current viewport in original 150-DPI pixel coords.

        Returns a negative value in a dimension when the page is smaller than
        the label in that dimension — this centres the page exactly as
        fit-to-view does, keeping coordinate mapping continuous across the
        zoom=1 boundary.
        """
        if self._original_pixmap is None:
            return 0.0, 0.0
        ds = self._fit_scale() * self._zoom
        if ds == 0:
            return 0.0, 0.0
        lw = self._label.width()
        lh = self._label.height()
        vw = lw / ds
        vh = lh / ds
        ow = self._original_pixmap.width()
        oh = self._original_pixmap.height()

        if vw >= ow:
            # Page fits within the viewport width — centre it.
            vx: float = -(vw - ow) / 2.0
        else:
            cx = max(vw / 2.0, min(ow - vw / 2.0, self._viewport_cx))
            vx = cx - vw / 2.0

        if vh >= oh:
            vy: float = -(vh - oh) / 2.0
        else:
            cy = max(vh / 2.0, min(oh - vh / 2.0, self._viewport_cy))
            vy = cy - vh / 2.0

        return vx, vy

    def _reset_viewport(self) -> None:
        if self._original_pixmap is not None:
            self._viewport_cx = self._original_pixmap.width() / 2.0
            self._viewport_cy = self._original_pixmap.height() / 2.0

    def _update_display(self) -> None:
        self._show_placeholder()
        if self._zoom > 1.0:
            self._render_timer.start(150)

    def _show_placeholder(self) -> None:
        if self._original_pixmap is None:
            return
        if self._zoom <= 1.0:
            self._fit_pixmap()
            return

        ds = self._fit_scale() * self._zoom
        lw = self._label.width()
        lh = self._label.height()
        vx, vy = self._viewport_origin()
        ow = self._original_pixmap.width()
        oh = self._original_pixmap.height()

        # Visible page region in original-pixmap coords (vx may be negative).
        src_x = max(0.0, vx)
        src_y = max(0.0, vy)
        src_x2 = min(float(ow), vx + lw / ds)
        src_y2 = min(float(oh), vy + lh / ds)
        if src_x2 <= src_x or src_y2 <= src_y:
            return

        # Where that region appears inside the label.
        dst_x = round((src_x - vx) * ds)
        dst_y = round((src_y - vy) * ds)
        dst_w = round((src_x2 - src_x) * ds)
        dst_h = round((src_y2 - src_y) * ds)

        src_rect = QRect(
            round(src_x), round(src_y),
            round(src_x2 - src_x), round(src_y2 - src_y),
        )
        crop = self._original_pixmap.copy(src_rect)
        scaled_crop = crop.scaled(
            dst_w, dst_h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        result = QPixmap(lw, lh)
        result.fill(_BG_COLOR)
        painter = QPainter(result)
        painter.drawPixmap(dst_x, dst_y, scaled_crop)
        painter.end()
        self._label.setPixmap(result)

    def _start_render(self) -> None:
        if not self._doc_path or self._original_pixmap is None:
            return
        if self._zoom <= 1.0:
            self._fit_pixmap()
            return

        ds = self._fit_scale() * self._zoom
        dpi = self.RENDER_DPI * ds
        vx, vy = self._viewport_origin()
        lw = self._label.width()
        lh = self._label.height()
        ow = self._original_pixmap.width()
        oh = self._original_pixmap.height()

        # Visible page region in original coords (vx may be negative).
        src_x = max(0.0, vx)
        src_y = max(0.0, vy)
        src_x2 = min(float(ow), vx + lw / ds)
        src_y2 = min(float(oh), vy + lh / ds)
        if src_x2 <= src_x or src_y2 <= src_y:
            return

        # Record where this crop should appear in the label for the callback.
        self._render_dst_x = round((src_x - vx) * ds)
        self._render_dst_y = round((src_y - vy) * ds)
        self._render_lw = lw
        self._render_lh = lh

        crop_rect = QRect(
            round(src_x * ds), round(src_y * ds),
            round((src_x2 - src_x) * ds), round((src_y2 - src_y) * ds),
        )
        self._discard_worker()
        self._render_worker = _RenderWorker(
            self._doc_path, self._page_index, dpi, crop_rect,
        )
        self._render_worker.rendered.connect(self._on_render_complete)
        self._render_worker.start()

    def _on_render_complete(self, pixmap: QPixmap) -> None:
        dst_x = self._render_dst_x
        dst_y = self._render_dst_y
        lw = self._render_lw
        lh = self._render_lh

        if dst_x == 0 and dst_y == 0 and pixmap.width() == lw and pixmap.height() == lh:
            self._label.setPixmap(pixmap)
            return

        result = QPixmap(lw, lh)
        result.fill(_BG_COLOR)
        painter = QPainter(result)
        painter.drawPixmap(dst_x, dst_y, pixmap)
        painter.end()
        self._label.setPixmap(result)

    def _discard_worker(self) -> None:
        if self._render_worker is not None:
            with contextlib.suppress(RuntimeError):
                self._render_worker.rendered.disconnect()
            self._render_worker = None

    # ------------------------------------------------------------------
    # Internal — rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        if not self._doc:
            return

        self._render_timer.stop()
        self._discard_worker()
        self._zoom = 1.0

        page = self._doc[self._page_index]
        mat = fitz.Matrix(self.render_dpi_scale(), self.render_dpi_scale())
        pix = page.get_pixmap(matrix=mat, alpha=False)
        image = QImage(
            pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888
        )
        self._original_pixmap = QPixmap.fromImage(image)
        self._reset_viewport()
        self._fit_pixmap()

    def _fit_pixmap(self) -> None:
        if self._original_pixmap is None:
            return

        scaled = self._original_pixmap.scaled(
            self._label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label.setPixmap(scaled)



