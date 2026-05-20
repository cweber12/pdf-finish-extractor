"""Interactive grid editor overlaid on a PDF viewer.

Modes
-----
idle     – arrow cursor; drag existing lines by clicking near the line or its
           handle; right-click near a line to remove it.
add_h    – crosshair cursor; click-drag to place a horizontal line.
add_v    – crosshair cursor; click-drag to place a vertical line.
pairing  – click an image cell then a text cell to create a pair;
           right-click on a cell to remove any pair that contains it.

Grid line coordinates are stored in 150-DPI pixel space so they match the
coordinate system used by the Extractor.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
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

_LINE_COLOR = QColor(theme.GRID_LINE)
_LINE_ACTIVE = QColor(theme.GRID_LINE_ACTIVE)
_PREVIEW_COLOR = QColor(0, 0, 0, 150)
_HANDLE_COLOR = QColor(theme.GRID_HANDLE)
_HANDLE_INNER = QColor(theme.GRID_HANDLE_INNER)
_HANDLE_BORDER = QColor(15, 23, 42, 120)
_PAGE_BORDER = QColor(15, 23, 42, 160)
_PAGE_SHADOW = QColor(0, 0, 0, 70)
_HANDLE_OFFSET = 12
_LINE_HIT_DIST = 6

_PENDING_FILL = QColor(245, 158, 11, 64)
_HOVER_FILL = QColor(148, 163, 184, 42)

# Per-pair fill colours: (image_cell_fill, text_cell_fill)
_PAIR_FILLS: list[tuple[QColor, QColor]] = [
    (QColor(56, 189, 248, 48), QColor(34, 197, 94, 44)),
    (QColor(168, 85, 247, 45), QColor(20, 184, 166, 45)),
    (QColor(251, 146, 60, 48), QColor(244, 63, 94, 42)),
    (QColor(96, 165, 250, 46), QColor(250, 204, 21, 38)),
]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _draw_handle(
    painter: QPainter,
    cx: int,
    cy: int,
    orientation: str,
    active: bool = False,
) -> None:
    """Draw a compact drag tab outside the PDF page edge.

    Horizontal-line handles sit just outside the left page border.
    Vertical-line handles sit just outside the top page border. The handles are
    intentionally narrow so adjacent grid lines do not visually overlap.
    """
    if orientation == "h":
        rect = QRectF(cx - 12, cy - 5, 24, 10)
        grip_rects = [QRectF(cx - 6, cy - 3 + offset, 12, 1.4) for offset in (0, 3, 6)]
        radius = 5
    else:
        rect = QRectF(cx - 5, cy - 12, 10, 24)
        grip_rects = [QRectF(cx - 3 + offset, cy - 6, 1.4, 12) for offset in (0, 3, 6)]
        radius = 5

    painter.setPen(QPen(_HANDLE_BORDER, 0.8))
    painter.setBrush(QBrush(QColor(255, 255, 255, 250) if active else _HANDLE_COLOR))
    painter.drawRoundedRect(rect, radius, radius)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(_LINE_ACTIVE if active else _HANDLE_INNER))
    for grip in grip_rects:
        painter.drawRoundedRect(grip, 0.7, 0.7)


def _draw_badge(painter: QPainter, cx: int, cy: int, text: str) -> None:
    r = 12
    painter.setBrush(QBrush(QColor(15, 23, 42, 225)))
    painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
    painter.drawEllipse(QPoint(cx, cy), r, r)

    f = QFont()
    f.setPointSize(7)
    f.setBold(True)
    painter.setFont(f)
    painter.setPen(QColor(248, 250, 252))
    painter.drawText(QRect(cx - r, cy - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, text)


def _draw_page_frame(painter: QPainter, page_rect: QRect) -> None:
    if page_rect.isNull() or page_rect.width() <= 0 or page_rect.height() <= 0:
        return

    shadow_rect = page_rect.adjusted(2, 2, 2, 2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(_PAGE_SHADOW))
    painter.drawRect(shadow_rect)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(_PAGE_BORDER, 1))
    painter.drawRect(page_rect.adjusted(0, 0, -1, -1))


# ------------------------------------------------------------------
# Overlay widget
# ------------------------------------------------------------------


class _OverlayWidget(QWidget):
    """Transparent overlay that renders the grid and handles mouse events."""

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

        h_d, v_d = e._grid_display_boundaries()
        page_rect = _page_rect_display(h_d, v_d)
        _draw_page_frame(painter, page_rect)

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
        line_pen = QPen(_LINE_COLOR, 1)
        line_pen.setCosmetic(True)
        active_pen = QPen(_LINE_ACTIVE, 1)
        active_pen.setCosmetic(True)
        hovered = e._hovered_line
        dragging = e._dragging

        for idx, y_d in enumerate(h_d[1:-1]):
            active = hovered == ("h", idx) or dragging == ("h", idx)
            painter.setPen(active_pen if active else line_pen)
            painter.drawLine(page_rect.left(), y_d, page_rect.right(), y_d)

        for idx, x_d in enumerate(v_d[1:-1]):
            active = hovered == ("v", idx) or dragging == ("v", idx)
            painter.setPen(active_pen if active else line_pen)
            painter.drawLine(x_d, page_rect.top(), x_d, page_rect.bottom())

        # --- Drag handles ---
        handle_left_x = page_rect.left() - _HANDLE_OFFSET
        handle_top_y = page_rect.top() - _HANDLE_OFFSET
        for idx, y_d in enumerate(h_d[1:-1]):
            active = hovered == ("h", idx) or dragging == ("h", idx)
            _draw_handle(painter, handle_left_x, y_d, "h", active)
        for idx, x_d in enumerate(v_d[1:-1]):
            active = hovered == ("v", idx) or dragging == ("v", idx)
            _draw_handle(painter, x_d, handle_top_y, "v", active)

        # --- Preview line (while placing) ---
        if e._preview is not None:
            prev_pen = QPen(_PREVIEW_COLOR, 1, Qt.PenStyle.DashLine)
            prev_pen.setCosmetic(True)
            painter.setPen(prev_pen)
            if e._mode == "add_h":
                y_d = e._o2d(0, e._preview)[1]
                painter.drawLine(page_rect.left(), y_d, page_rect.right(), y_d)
            elif e._mode == "add_v":
                x_d = e._o2d(e._preview, 0)[0]
                painter.drawLine(x_d, page_rect.top(), x_d, page_rect.bottom())

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
        self._e._hovered_line = None
        self.update()


# ------------------------------------------------------------------
# Display-space helpers
# ------------------------------------------------------------------


def _cell_rect_display(
    cell: tuple[int, int], h_d: list[int], v_d: list[int]
) -> QRect | None:
    ri, ci = cell
    if ri >= len(h_d) - 1 or ci >= len(v_d) - 1:
        return None
    return QRect(v_d[ci], h_d[ri], v_d[ci + 1] - v_d[ci], h_d[ri + 1] - h_d[ri])


def _page_rect_display(h_d: list[int], v_d: list[int]) -> QRect:
    if len(h_d) < 2 or len(v_d) < 2:
        return QRect()
    return QRect(v_d[0], h_d[0], v_d[-1] - v_d[0], h_d[-1] - h_d[0])


# ------------------------------------------------------------------
# Grid editor
# ------------------------------------------------------------------


class GridEditor(QWidget):
    """PDF viewer with an interactive grid overlay."""

    open_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Grid state (150 DPI pixel space)
        self._h_lines: list[int] = []
        self._v_lines: list[int] = []
        self._pairs: list[CellPair] = []

        # Interaction state
        self._mode: str = "idle"
        self._preview: int | None = None
        self._placing: bool = False
        self._dragging: tuple[str, int] | None = None
        self._hovered_line: tuple[str, int] | None = None
        self._pending_image: tuple[int, int] | None = None
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
        bar.setContentsMargins(16, 0, 16, 0)
        bar.setSpacing(12)

        tool_label = QLabel("Grid tools")
        tool_label.setObjectName("toolLabel")
        bar.addWidget(tool_label)

        seg = QWidget()
        seg.setObjectName("segmentedControl")
        seg_layout = QHBoxLayout(seg)
        seg_layout.setContentsMargins(0, 0, 0, 0)
        seg_layout.setSpacing(6)

        modes = [
            (QIcon(theme.icon_path("h-line.svg")), "Rows", "add_h", "Click-drag to add a horizontal row boundary."),
            (QIcon(theme.icon_path("v-line.svg")), "Columns", "add_v", "Click-drag to add a vertical column boundary."),
            (QIcon(theme.icon_path("link.svg")), "Pair", "pairing", "Click an image cell, then its matching ID/text cell."),
        ]
        for icon, label, mode, tooltip in modes:
            btn = QPushButton(icon, f"  {label}")
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda _checked, m=mode, b=btn: self._set_mode(m, b))
            setattr(self, f"_btn_{mode}", btn)
            seg_layout.addWidget(btn)

        bar.addWidget(seg)

        self._hint = QLabel("Drag existing handles to move lines. Right-click a line to remove it.")
        self._hint.setObjectName("toolbarHint")
        bar.addWidget(self._hint, stretch=1)

        clear_btn = QPushButton("Clear Grid")
        clear_btn.setProperty("ghost", True)
        clear_btn.setToolTip("Remove all lines and pairings from the current PDF.")
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
                pix.scaled(
                    72,
                    72,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(icon_label)
        inner.addSpacing(22)

        title = QLabel("Open a PDF to begin")
        title.setProperty("heading", True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(title)
        inner.addSpacing(8)

        subtitle = QLabel("Define reusable row and column boundaries, then pair swatches with IDs.")
        subtitle.setProperty("body", True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(subtitle)
        inner.addSpacing(28)

        open_btn = QPushButton(QIcon(theme.icon_path("folder-open.svg")), "  Open PDF")
        open_btn.setProperty("primary", True)
        open_btn.setFixedWidth(170)
        open_btn.clicked.connect(self.open_requested)
        inner.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return w

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._ctrl_bar)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_empty_state())
        self._stack.addWidget(self._viewer)
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
        self._set_hint("Use Rows or Columns to place boundaries. Drag handles to adjust.")
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
        self._hovered_cell = None
        self._hovered_line = None
        self._set_hint("Profile applied. Fine-tune lines by dragging their handles.")
        self._overlay.update()

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _d2o(self, x: int, y: int) -> tuple[int, int]:
        """Display coords → 150-DPI pixel coords."""
        return self._viewer.display_to_original_coords(x, y)

    def _o2d(self, x: int, y: int) -> tuple[int, int]:
        """150-DPI pixel coords → display coords."""
        return self._viewer.original_to_display_coords(x, y)

    def _grid_display_boundaries(self) -> tuple[list[int], list[int]]:
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
        orig = self._viewer.pixmap
        if orig is None:
            return None
        ph, pw = orig.height(), orig.width()
        if ox < 0 or oy < 0 or ox >= pw or oy >= ph:
            return None
        h = [0] + sorted(self._h_lines) + [ph]
        v = [0] + sorted(self._v_lines) + [pw]
        for ri in range(len(h) - 1):
            if h[ri] <= oy < h[ri + 1]:
                for ci in range(len(v) - 1):
                    if v[ci] <= ox < v[ci + 1]:
                        return (ri, ci)
        return None

    def _line_hit(self, dx: int, dy: int) -> tuple[int | None, int | None]:
        """Return (h_index, None) or (None, v_index) if within hit distance."""
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
        self._hovered_cell = None
        self._overlay.update()
        self._update_cursor(None, None)

        hints = {
            "idle": "Drag existing handles to move lines. Right-click a line to remove it.",
            "add_h": "Click-drag across the PDF to place a horizontal row boundary.",
            "add_v": "Click-drag across the PDF to place a vertical column boundary.",
            "pairing": "Click the image cell first, then click the matching ID/text cell.",
        }
        self._set_hint(hints.get(self._mode, hints["idle"]))

    def _set_hint(self, text: str) -> None:
        self._hint.setText(text)

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

        hit_h, hit_v = self._line_hit(dx, dy)
        if hit_h is not None:
            self._dragging = ("h", hit_h)
            self._set_hint("Dragging row boundary. Release to set position.")
            self._overlay.update()
            return
        if hit_v is not None:
            self._dragging = ("v", hit_v)
            self._set_hint("Dragging column boundary. Release to set position.")
            self._overlay.update()
            return

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

        hit_h, hit_v = self._line_hit(dx, dy)
        if hit_h is not None:
            self._hovered_line = ("h", hit_h)
        elif hit_v is not None:
            self._hovered_line = ("v", hit_v)
        else:
            self._hovered_line = None
        self._update_cursor(dx, dy)

        if self._mode == "pairing":
            self._hovered_cell = self._cell_at_orig(ox, oy)
        else:
            self._hovered_cell = None
        self._overlay.update()

    def _on_release(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._dragging:
            self._dragging = None
            self._set_hint("Line moved. Right-click any line to delete it.")
            self._overlay.update()
            return

        if self._placing:
            if self._preview is not None:
                if self._mode == "add_h":
                    self._h_lines.append(self._preview)
                    self._set_hint("Row boundary added. Drag its handle to adjust.")
                elif self._mode == "add_v":
                    self._v_lines.append(self._preview)
                    self._set_hint("Column boundary added. Drag its handle to adjust.")
            self._placing = False
            self._preview = None
            self._overlay.update()

    def _on_right_click(self, dx: int, dy: int) -> None:
        ox, oy = self._d2o(dx, dy)

        if self._mode == "pairing":
            if self._pending_image is not None:
                self._pending_image = None
                self._set_hint("Pair selection cancelled.")
                self._overlay.update()
                return
            cell = self._cell_at_orig(ox, oy)
            if cell:
                before = len(self._pairs)
                self._pairs = [
                    p for p in self._pairs
                    if p.image_cell != cell and p.text_cell != cell
                ]
                if len(self._pairs) != before:
                    self._set_hint("Cell pair removed.")
                self._overlay.update()
            return

        hit_h, hit_v = self._line_hit(dx, dy)
        if hit_h is not None:
            del self._h_lines[hit_h]
            self._pairs = []
            self._set_hint("Row boundary removed. Pairings were cleared because the grid changed.")
            self._overlay.update()
        elif hit_v is not None:
            del self._v_lines[hit_v]
            self._pairs = []
            self._set_hint("Column boundary removed. Pairings were cleared because the grid changed.")
            self._overlay.update()

    def _on_pair_click(self, ox: int, oy: int) -> None:
        cell = self._cell_at_orig(ox, oy)
        if cell is None:
            return
        if self._pending_image is None:
            self._pending_image = cell
            self._set_hint("Image cell selected. Now click the matching ID/text cell.")
        elif cell == self._pending_image:
            self._pending_image = None
            self._set_hint("Pair selection cancelled.")
        else:
            self._pairs.append(CellPair(image_cell=self._pending_image, text_cell=cell))
            self._pending_image = None
            self._set_hint("Pair created. Continue pairing cells or right-click a pair to remove it.")
        self._overlay.update()

    # ------------------------------------------------------------------
    # Grid management
    # ------------------------------------------------------------------

    def _clear_grid(self) -> None:
        self._h_lines.clear()
        self._v_lines.clear()
        self._pairs.clear()
        self._pending_image = None
        self._hovered_cell = None
        self._hovered_line = None
        self._set_hint("Grid cleared. Add row and column boundaries to start again.")
        self._overlay.update()

