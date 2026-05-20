"""Interactive grid editor overlaid on a PDF viewer.

Modes
-----
idle     – arrow cursor; drag existing lines by clicking within 8 px;
           right-click near a line to remove it.
add_h    – crosshair cursor; click-drag to place a horizontal line,
           release to set it.
add_v    – crosshair cursor; click-drag to place a vertical line,
           release to set it.
pairing  – click an image cell then a text cell to create a pair;
           right-click on a cell to remove any pair that contains it.

Grid line coordinates are stored in 150-DPI pixel space so they match the
coordinate system used by the Extractor.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.extraction.grid import CellPair, Grid
from src.ui import theme
from src.ui.pdf_viewer import PDFViewer

# ------------------------------------------------------------------
# Visual constants
# ------------------------------------------------------------------

_LINE_COLOR = QColor(220, 50, 50)
_LINE_SHADOW = QColor(0, 0, 0, 80)
_PREVIEW_COLOR = QColor(220, 50, 50, 120)
_HANDLE_COLOR = QColor(220, 50, 50)
_HANDLE_RADIUS = 7          # px
_LINE_HIT_DIST = 9          # px – distance that triggers drag / remove
_PENDING_FILL = QColor(255, 140, 0, 75)
_HOVER_FILL = QColor(255, 230, 0, 50)

# Per-pair fill colours: (image_cell_fill, text_cell_fill)
_PAIR_FILLS: list[tuple[QColor, QColor]] = [
    (QColor(0, 120, 215, 65),  QColor(0, 160, 50, 65)),
    (QColor(180, 60, 200, 65), QColor(0, 160, 160, 65)),
    (QColor(200, 80, 0, 65),   QColor(150, 0, 0, 65)),
    (QColor(0, 90, 170, 65),   QColor(120, 120, 0, 65)),
]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _draw_handle(painter: QPainter, cx: int, cy: int) -> None:
    painter.setBrush(QBrush(_HANDLE_COLOR))
    painter.setPen(QPen(QColor(255, 255, 255), 1.5))
    painter.drawEllipse(QPoint(cx, cy), _HANDLE_RADIUS, _HANDLE_RADIUS)


def _draw_badge(painter: QPainter, cx: int, cy: int, text: str) -> None:
    r = 11
    painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPoint(cx, cy), r, r)
    f = QFont()
    f.setPointSize(7)
    f.setBold(True)
    painter.setFont(f)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(QRect(cx - r, cy - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, text)


# ------------------------------------------------------------------
# Overlay widget
# ------------------------------------------------------------------

class _OverlayWidget(QWidget):
    """Transparent overlay that renders the grid and handles all mouse events."""

    def __init__(self, editor: GridEditor) -> None:
        super().__init__(editor)
        self._e = editor
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        e = self._e
        orig = e._viewer.pixmap
        if orig is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Compute display-space grid boundaries
        h_d, v_d = e._grid_display_boundaries()

        # --- Cell fills: paired cells ---
        for idx, pair in enumerate(e._pairs):
            fills = _PAIR_FILLS[idx % len(_PAIR_FILLS)]
            for cell, fill in ((pair.image_cell, fills[0]), (pair.text_cell, fills[1])):
                r = _cell_rect_display(cell, h_d, v_d)
                if r:
                    painter.fillRect(r, fill)

        # --- Pending image cell ---
        if e._pending_image is not None:
            r = _cell_rect_display(e._pending_image, h_d, v_d)
            if r:
                painter.fillRect(r, _PENDING_FILL)

        # --- Hovered cell (pairing mode only) ---
        hc = e._hovered_cell
        is_unpaired = hc is not None and not any(
            hc in (p.image_cell, p.text_cell) for p in e._pairs
        )
        if e._mode == "pairing" and is_unpaired and hc != e._pending_image:
            r = _cell_rect_display(hc, h_d, v_d)
            if r:
                painter.fillRect(r, _HOVER_FILL)

        # --- Grid lines ---
        shadow_pen = QPen(_LINE_SHADOW, 4)
        line_pen = QPen(_LINE_COLOR, 2)
        # h_d[1:-1] = user-placed H lines (skip 0 and page-bottom boundary)
        for y_d in h_d[1:-1]:
            painter.setPen(shadow_pen)
            painter.drawLine(0, y_d, self.width(), y_d)
            painter.setPen(line_pen)
            painter.drawLine(0, y_d, self.width(), y_d)
        for x_d in v_d[1:-1]:
            painter.setPen(shadow_pen)
            painter.drawLine(x_d, 0, x_d, self.height())
            painter.setPen(line_pen)
            painter.drawLine(x_d, 0, x_d, self.height())

        # --- Handles ---
        for y_d in h_d[1:-1]:
            _draw_handle(painter, _HANDLE_RADIUS + 2, y_d)
        for x_d in v_d[1:-1]:
            _draw_handle(painter, x_d, _HANDLE_RADIUS + 2)

        # --- Preview line (while placing) ---
        if e._preview is not None:
            prev_pen = QPen(_PREVIEW_COLOR, 2, Qt.PenStyle.DashLine)
            painter.setPen(prev_pen)
            if e._mode == "add_h":
                y_d = e._o2d(0, e._preview)[1]
                painter.drawLine(0, y_d, self.width(), y_d)
            elif e._mode == "add_v":
                x_d = e._o2d(e._preview, 0)[0]
                painter.drawLine(x_d, 0, x_d, self.height())

        # --- Pair badges ---
        for idx, pair in enumerate(e._pairs):
            badge = str(idx + 1)
            for cell in (pair.image_cell, pair.text_cell):
                r = _cell_rect_display(cell, h_d, v_d)
                if r:
                    _draw_badge(painter, r.center().x(), r.center().y(), badge)

        painter.end()

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._e._on_press(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._e._on_move(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._e._on_release(event)

    def leaveEvent(self, _event) -> None:  # noqa: ANN001
        self._e._hovered_cell = None
        self.update()


# ------------------------------------------------------------------
# Cell rect helper (display space)
# ------------------------------------------------------------------

def _cell_rect_display(
    cell: tuple[int, int], h_d: list[int], v_d: list[int]
) -> QRect | None:
    ri, ci = cell
    if ri >= len(h_d) - 1 or ci >= len(v_d) - 1:
        return None
    return QRect(v_d[ci], h_d[ri], v_d[ci + 1] - v_d[ci], h_d[ri + 1] - h_d[ri])


# ------------------------------------------------------------------
# Grid editor
# ------------------------------------------------------------------

class GridEditor(QWidget):
    """PDF viewer with an interactive grid overlay.

    Lines are placed by clicking and dragging in add_h / add_v mode.
    Pairs are formed by clicking two cells sequentially in pairing mode.
    All coordinates are stored in 150-DPI pixel space for extractor compatibility.
    """

    open_requested = pyqtSignal()  # emitted by empty-state "Open PDF" button

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Grid state (150 DPI pixel space)
        self._h_lines: list[int] = []
        self._v_lines: list[int] = []
        self._pairs: list[CellPair] = []

        # Interaction state
        self._mode: str = "idle"
        self._preview: int | None = None        # 150 DPI pos of live preview line
        self._placing: bool = False              # True while dragging to place new line
        self._dragging: tuple[str, int] | None = None  # ("h"|"v", line_index)
        self._pending_image: tuple[int, int] | None = None  # first cell in pair
        self._hovered_cell: tuple[int, int] | None = None

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
        self._ctrl_bar.setObjectName("controlBar")
        bar = QHBoxLayout(self._ctrl_bar)
        bar.setContentsMargins(12, 0, 12, 0)
        bar.setSpacing(8)

        # Segmented control for mutually-exclusive mode buttons
        seg = QWidget()
        seg.setObjectName("segmentedControl")
        seg_layout = QHBoxLayout(seg)
        seg_layout.setContentsMargins(0, 0, 0, 0)
        seg_layout.setSpacing(0)

        modes = [
            (QIcon(theme.icon_path("h-line.svg")), "H Line", "add_h"),
            (QIcon(theme.icon_path("v-line.svg")), "V Line", "add_v"),
            (QIcon(theme.icon_path("link.svg")), "Pair Cells", "pairing"),
        ]
        for icon, label, mode in modes:
            btn = QPushButton(icon, f"  {label}")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked, m=mode, b=btn: self._set_mode(m, b))
            setattr(self, f"_btn_{mode}", btn)
            seg_layout.addWidget(btn)

        bar.addWidget(seg)
        bar.addStretch()

        clear_btn = QPushButton("Clear Grid")
        clear_btn.setProperty("ghost", True)
        clear_btn.clicked.connect(self._clear_grid)
        bar.addWidget(clear_btn)

    def _build_empty_state(self) -> QWidget:
        w = QWidget()
        inner = QVBoxLayout(w)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.setSpacing(0)

        icon_label = QLabel()
        pix = QPixmap(theme.icon_path("document.svg"))
        if not pix.isNull():
            icon_label.setPixmap(
                pix.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(icon_label)
        inner.addSpacing(20)

        title = QLabel("No PDF open")
        title.setProperty("heading", True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(title)
        inner.addSpacing(8)

        subtitle = QLabel("Open a PDF file to define your extraction grid.")
        subtitle.setProperty("body", True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(subtitle)
        inner.addSpacing(28)

        open_btn = QPushButton(QIcon(theme.icon_path("folder-open.svg")), "  Open PDF")
        open_btn.setProperty("primary", True)
        open_btn.setFixedWidth(160)
        open_btn.clicked.connect(self.open_requested)
        inner.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return w

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._ctrl_bar)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_empty_state())  # index 0: no PDF
        self._stack.addWidget(self._viewer)               # index 1: PDF loaded
        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack, stretch=1)

    def resizeEvent(self, _event) -> None:  # noqa: ANN001
        self._reposition_overlay()

    def _reposition_overlay(self) -> None:
        top_left = self._viewer.mapTo(self, QPoint(0, 0))
        self._overlay.setGeometry(QRect(top_left, self._viewer.size()))
        self._overlay.raise_()
        self._overlay.update()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_pdf(self, path: str) -> None:
        self.pdf_path = path
        self._viewer.open(path)
        self._stack.setCurrentIndex(1)
        self._reposition_overlay()

    def current_profile(self) -> Grid | None:
        if not self._h_lines and not self._v_lines:
            return None
        return Grid(
            horizontal_lines=sorted(self._h_lines),
            vertical_lines=sorted(self._v_lines),
            pairs=list(self._pairs),
        )

    def apply_profile(self, grid: Grid) -> None:
        self._h_lines = list(grid.horizontal_lines)
        self._v_lines = list(grid.vertical_lines)
        self._pairs = list(grid.pairs)
        self._pending_image = None
        self._overlay.update()

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _d2o(self, x: int, y: int) -> tuple[int, int]:
        """Display coords → 150 DPI pixel coords."""
        return self._viewer.display_to_original_coords(x, y)

    def _o2d(self, x: int, y: int) -> tuple[int, int]:
        """150 DPI pixel coords → display coords."""
        return self._viewer.original_to_display_coords(x, y)

    def _grid_display_boundaries(self) -> tuple[list[int], list[int]]:
        """Return (h_display, v_display) boundary lists in display/overlay space.

        Each list starts at the page top/left and ends at the page bottom/right,
        with user-placed lines in between.
        """
        orig = self._viewer.pixmap
        if orig is None:
            return [0, self._overlay.height()], [0, self._overlay.width()]
        ph, pw = orig.height(), orig.width()
        h_orig = [0] + sorted(self._h_lines) + [ph]
        v_orig = [0] + sorted(self._v_lines) + [pw]
        h_d = [self._o2d(0, y)[1] for y in h_orig]
        v_d = [self._o2d(x, 0)[0] for x in v_orig]
        return h_d, v_d

    def _cell_at_orig(self, ox: int, oy: int) -> tuple[int, int] | None:
        """Return the (row, col) cell that contains the 150-DPI point (ox, oy)."""
        orig = self._viewer.pixmap
        if orig is None:
            return None
        ph, pw = orig.height(), orig.width()
        h = [0] + sorted(self._h_lines) + [ph]
        v = [0] + sorted(self._v_lines) + [pw]
        for ri in range(len(h) - 1):
            if h[ri] <= oy < h[ri + 1]:
                for ci in range(len(v) - 1):
                    if v[ci] <= ox < v[ci + 1]:
                        return (ri, ci)
        return None

    def _line_hit(self, dx: int, dy: int) -> tuple[int | None, int | None]:
        """Return (h_index, None) or (None, v_index) if within _LINE_HIT_DIST."""
        for i, y_orig in enumerate(self._h_lines):
            y_d = self._o2d(0, y_orig)[1]
            if abs(dy - y_d) <= _LINE_HIT_DIST:
                return i, None
        for i, x_orig in enumerate(self._v_lines):
            x_d = self._o2d(x_orig, 0)[0]
            if abs(dx - x_d) <= _LINE_HIT_DIST:
                return None, i
        return None, None

    # ------------------------------------------------------------------
    # Mode / cursor management
    # ------------------------------------------------------------------

    def _set_mode(self, mode: str, active_btn: QPushButton) -> None:
        self._mode = mode if active_btn.isChecked() else "idle"
        for attr in ("_btn_add_h", "_btn_add_v", "_btn_pairing"):
            btn = getattr(self, attr, None)
            if btn and btn is not active_btn:
                btn.setChecked(False)
        self._pending_image = None
        self._overlay.update()
        self._update_cursor(None, None)

    def _update_cursor(self, dx: int | None, dy: int | None) -> None:
        if dx is not None and dy is not None:
            hit_h, hit_v = self._line_hit(dx, dy)
            if hit_h is not None:
                self._overlay.setCursor(Qt.CursorShape.SizeVerCursor)
                return
            if hit_v is not None:
                self._overlay.setCursor(Qt.CursorShape.SizeHorCursor)
                return
        if self._mode in ("add_h", "add_v"):
            self._overlay.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self._overlay.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------------
    # Mouse event handlers
    # ------------------------------------------------------------------

    def _on_press(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        dx, dy = pos.x(), pos.y()

        if event.button() == Qt.MouseButton.RightButton:
            self._on_right_click(dx, dy)
            return

        # Priority 1: drag existing line if close enough
        hit_h, hit_v = self._line_hit(dx, dy)
        if hit_h is not None:
            self._dragging = ("h", hit_h)
            return
        if hit_v is not None:
            self._dragging = ("v", hit_v)
            return

        # Priority 2: mode action
        ox, oy = self._d2o(dx, dy)
        if self._mode == "add_h":
            self._placing = True
            self._preview = max(0, oy)
            self._overlay.update()
        elif self._mode == "add_v":
            self._placing = True
            self._preview = max(0, ox)
            self._overlay.update()
        elif self._mode == "pairing":
            self._on_pair_click(ox, oy)

    def _on_move(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        dx, dy = pos.x(), pos.y()
        ox, oy = self._d2o(dx, dy)

        if self._dragging:
            dtype, idx = self._dragging
            if dtype == "h":
                self._h_lines[idx] = max(0, oy)
            else:
                self._v_lines[idx] = max(0, ox)
            self._overlay.update()
            return

        if self._placing:
            self._preview = max(0, oy if self._mode == "add_h" else ox)
            self._overlay.update()
            return

        # Update cursor based on proximity to lines
        self._update_cursor(dx, dy)

        # Update hovered cell in pairing mode
        if self._mode == "pairing":
            self._hovered_cell = self._cell_at_orig(ox, oy)
            self._overlay.update()

    def _on_release(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._dragging:
            self._dragging = None
            self._overlay.update()
            return

        if self._placing:
            if self._preview is not None:
                if self._mode == "add_h":
                    self._h_lines.append(self._preview)
                elif self._mode == "add_v":
                    self._v_lines.append(self._preview)
            self._placing = False
            self._preview = None
            self._overlay.update()

    def _on_right_click(self, dx: int, dy: int) -> None:
        ox, oy = self._d2o(dx, dy)

        if self._mode == "pairing":
            if self._pending_image is not None:
                self._pending_image = None
                self._overlay.update()
                return
            cell = self._cell_at_orig(ox, oy)
            if cell:
                self._pairs = [
                    p for p in self._pairs
                    if p.image_cell != cell and p.text_cell != cell
                ]
                self._overlay.update()
            return

        # Any other mode: right-click near a line removes it
        hit_h, hit_v = self._line_hit(dx, dy)
        if hit_h is not None:
            del self._h_lines[hit_h]
            # Remove pairs that reference now-invalid cells
            self._pairs = []
            self._overlay.update()
        elif hit_v is not None:
            del self._v_lines[hit_v]
            self._pairs = []
            self._overlay.update()

    def _on_pair_click(self, ox: int, oy: int) -> None:
        cell = self._cell_at_orig(ox, oy)
        if cell is None:
            return
        if self._pending_image is None:
            self._pending_image = cell
        elif cell == self._pending_image:
            self._pending_image = None      # deselect same cell
        else:
            self._pairs.append(CellPair(image_cell=self._pending_image, text_cell=cell))
            self._pending_image = None
        self._overlay.update()

    # ------------------------------------------------------------------
    # Grid management
    # ------------------------------------------------------------------

    def _clear_grid(self) -> None:
        self._h_lines.clear()
        self._v_lines.clear()
        self._pairs.clear()
        self._pending_image = None
        self._overlay.update()
