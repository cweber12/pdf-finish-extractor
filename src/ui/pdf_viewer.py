from __future__ import annotations

import fitz  # PyMuPDF
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PDFViewer(QWidget):
    """Renders a single PDF page as a QPixmap.

    Consumers call :meth:`load_page` to display a specific page.
    The rendered pixmap is available via :attr:`pixmap` for coordinate
    mapping by :class:`GridEditor`. The displayed image is always scaled
    to fit the widget while preserving aspect ratio.
    """

    RENDER_DPI: int = 150  # resolution for display rendering

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doc: fitz.Document | None = None
        self._page_index: int = 0
        self._original_pixmap: QPixmap | None = None

        self._label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._label.setScaledContents(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def page_count(self) -> int:
        return len(self._doc) if self._doc else 0

    @property
    def pixmap(self) -> QPixmap | None:
        """Full-resolution pixmap (unscaled) for coordinate mapping."""
        return self._original_pixmap

    def open(self, path: str) -> None:
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
