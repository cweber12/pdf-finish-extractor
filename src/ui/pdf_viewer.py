from __future__ import annotations

import fitz  # PyMuPDF
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PDFViewer(QWidget):
    """Renders a single PDF page as a QPixmap.

    The rendered pixmap is available through :attr:`pixmap` for coordinate
    mapping by :class:`GridEditor`. The displayed image is scaled to fit the
    viewer while preserving aspect ratio.
    """

    RENDER_DPI: int = 150

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pdfViewer")

        self._doc: fitz.Document | None = None
        self._page_index: int = 0
        self._original_pixmap: QPixmap | None = None

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

    def open(self, path: str) -> None:
        if self._doc is not None:
            self._doc.close()
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

    def display_to_original_coords(self, x: int, y: int) -> tuple[int, int]:
        """Map viewer/display coordinates to 150-DPI PDF pixel coordinates."""
        pm = self._label.pixmap()
        if pm is None or self._original_pixmap is None or pm.width() == 0:
            return x, y

        label_rect = self._label.geometry()
        local_x = x - label_rect.x()
        local_y = y - label_rect.y()
        page_x = (self._label.width() - pm.width()) // 2
        page_y = (self._label.height() - pm.height()) // 2
        scale = pm.width() / self._original_pixmap.width()
        return round((local_x - page_x) / scale), round((local_y - page_y) / scale)

    def original_to_display_coords(self, x: int, y: int) -> tuple[int, int]:
        """Map 150-DPI PDF pixel coordinates to viewer/display coordinates."""
        pm = self._label.pixmap()
        if pm is None or self._original_pixmap is None or self._original_pixmap.width() == 0:
            return x, y

        label_rect = self._label.geometry()
        page_x = (self._label.width() - pm.width()) // 2
        page_y = (self._label.height() - pm.height()) // 2
        scale = pm.width() / self._original_pixmap.width()
        return (
            label_rect.x() + round(x * scale) + page_x,
            label_rect.y() + round(y * scale) + page_y,
        )

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._fit_pixmap()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _render(self) -> None:
        if not self._doc:
            return

        page = self._doc[self._page_index]
        mat = fitz.Matrix(self.render_dpi_scale(), self.render_dpi_scale())
        pix = page.get_pixmap(matrix=mat, alpha=False)
        image = QImage(
            pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888
        )
        self._original_pixmap = QPixmap.fromImage(image)
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


