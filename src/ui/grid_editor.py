from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QMouseEvent
from PyQt6.QtCore import Qt, QPoint, QRect

from src.ui.pdf_viewer import PDFViewer
from src.extraction.grid import CellType, Grid, PairDirection

if TYPE_CHECKING:
    pass


_CELL_COLORS: dict[CellType, QColor] = {
    CellType.IMAGE: QColor(0, 120, 215, 60),
    CellType.TEXT: QColor(0, 180, 0, 60),
    CellType.IGNORED: QColor(180, 180, 180, 40),
}

_LINE_COLOR = QColor(220, 50, 50)


class _OverlayWidget(QWidget):
    """Transparent overlay drawn on top of the PDF viewer for grid interaction."""

    def __init__(self, grid_editor: "GridEditor") -> None:
        super().__init__(grid_editor)
        self._editor = grid_editor
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(_LINE_COLOR, 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        for y in self._editor._h_lines:
            painter.drawLine(0, y, self.width(), y)
        for x in self._editor._v_lines:
            painter.drawLine(x, 0, x, self.height())

        # Draw cell type fills
        h = [0] + sorted(self._editor._h_lines) + [self.height()]
        v = [0] + sorted(self._editor._v_lines) + [self.width()]
        for ri in range(len(h) - 1):
            for ci in range(len(v) - 1):
                cell_type = self._editor._cell_types.get((ri, ci), CellType.IGNORED)
                color = _CELL_COLORS[cell_type]
                painter.fillRect(QRect(v[ci], h[ri], v[ci + 1] - v[ci], h[ri + 1] - h[ri]), color)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._editor._on_overlay_click(event)


class GridEditor(QWidget):
    """PDF viewer with an interactive grid overlay.

    The user adds horizontal/vertical lines by clicking toolbar buttons
    then clicking on the overlay. Cells are tagged by clicking on them
    while in 'tag' mode.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._h_lines: list[int] = []
        self._v_lines: list[int] = []
        self._cell_types: dict[tuple[int, int], CellType] = {}
        self._mode: str = "none"  # "add_h" | "add_v" | "tag" | "none"
        self._pair_direction = PairDirection.RIGHT
        self.pdf_path: str | None = None

        self._viewer = PDFViewer()
        self._overlay = _OverlayWidget(self)
        self._build_controls()
        self._build_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_controls(self) -> None:
        self._ctrl_bar = QWidget()
        bar_layout = QHBoxLayout(self._ctrl_bar)
        bar_layout.setContentsMargins(4, 4, 4, 4)

        for label, mode in [("+ H Line", "add_h"), ("+ V Line", "add_v"), ("Tag Cells", "tag")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, m=mode, b=btn: self._set_mode(m, b))
            bar_layout.addWidget(btn)
            setattr(self, f"_btn_{mode}", btn)

        bar_layout.addWidget(QLabel("Pair direction:"))
        self._dir_combo = QComboBox()
        for d in PairDirection:
            self._dir_combo.addItem(d.value, d)
        self._dir_combo.currentIndexChanged.connect(self._on_direction_changed)
        bar_layout.addWidget(self._dir_combo)

        bar_layout.addWidget(QLabel("Tag as:"))
        self._tag_combo = QComboBox()
        for ct in CellType:
            self._tag_combo.addItem(ct.value, ct)
        bar_layout.addWidget(self._tag_combo)

        bar_layout.addStretch()
        clear_btn = QPushButton("Clear Grid")
        clear_btn.clicked.connect(self._clear_grid)
        bar_layout.addWidget(clear_btn)

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._ctrl_bar)
        layout.addWidget(self._viewer, stretch=1)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._reposition_overlay()

    def _reposition_overlay(self) -> None:
        geom = self._viewer.geometry()
        self._overlay.setGeometry(geom)
        self._overlay.raise_()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_pdf(self, path: str) -> None:
        self.pdf_path = path
        self._viewer.open(path)
        self._reposition_overlay()

    def current_profile(self) -> Grid | None:
        if not self._h_lines and not self._v_lines:
            return None
        return Grid(
            horizontal_lines=sorted(self._h_lines),
            vertical_lines=sorted(self._v_lines),
            cell_types=dict(self._cell_types),
            pair_direction=self._pair_direction,
        )

    def apply_profile(self, grid: Grid) -> None:
        self._h_lines = list(grid.horizontal_lines)
        self._v_lines = list(grid.vertical_lines)
        self._cell_types = dict(grid.cell_types)
        self._pair_direction = grid.pair_direction
        idx = self._dir_combo.findData(grid.pair_direction)
        if idx >= 0:
            self._dir_combo.setCurrentIndex(idx)
        self._overlay.update()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _set_mode(self, mode: str, active_btn: QPushButton) -> None:
        self._mode = mode if active_btn.isChecked() else "none"
        for attr in ("_btn_add_h", "_btn_add_v", "_btn_tag"):
            btn = getattr(self, attr, None)
            if btn and btn is not active_btn:
                btn.setChecked(False)

    def _on_overlay_click(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._mode == "add_h":
            self._h_lines.append(pos.y())
            self._overlay.update()
        elif self._mode == "add_v":
            self._v_lines.append(pos.x())
            self._overlay.update()
        elif self._mode == "tag":
            cell = self._cell_at(pos)
            if cell is not None:
                tag = self._tag_combo.currentData()
                self._cell_types[cell] = tag
                self._overlay.update()

    def _cell_at(self, pos: QPoint) -> tuple[int, int] | None:
        h = [0] + sorted(self._h_lines) + [self._overlay.height()]
        v = [0] + sorted(self._v_lines) + [self._overlay.width()]
        for ri in range(len(h) - 1):
            if h[ri] <= pos.y() < h[ri + 1]:
                for ci in range(len(v) - 1):
                    if v[ci] <= pos.x() < v[ci + 1]:
                        return (ri, ci)
        return None

    def _on_direction_changed(self, _index: int) -> None:
        self._pair_direction = self._dir_combo.currentData()

    def _clear_grid(self) -> None:
        self._h_lines.clear()
        self._v_lines.clear()
        self._cell_types.clear()
        self._overlay.update()
