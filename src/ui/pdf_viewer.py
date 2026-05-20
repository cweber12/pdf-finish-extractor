from __future__ import annotations

import fitz  # PyMuPDF
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget


class PDFViewer(QWidget):
    """Renders a single PDF page as a QPixmap.

    Consumers call :meth:`load_page` to display a specific page.
    The rendered pixmap is available via :attr:`pixmap` for coordinate
    mapping by :class:`GridEditor`.
    """

    RENDER_DPI: int = 150  # resolution for display rendering

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doc: fitz.Document | None = None
        self._page_index: int = 0

        self._label = QLabel(alignment=Qt.AlignmentFlag.AlignTop)
        self._label.setScaledContents(False)

        scroll = QScrollArea()
        scroll.setWidget(self._label)
        scroll.setWidgetResizable(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def page_count(self) -> int:
        return len(self._doc) if self._doc else 0

    @property
    def pixmap(self) -> QPixmap | None:
        return self._label.pixmap()

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
        self._label.setPixmap(QPixmap.fromImage(image))
        self._label.resize(pix.width, pix.height)
