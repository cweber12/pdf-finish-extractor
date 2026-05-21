"""Interactive grid editor overlaid on a PDF viewer.

Modes
-----
idle     – arrow cursor; drag existing lines by clicking near the line or its
           handle; right-click near a line to remove it.
add_h    – crosshair cursor; click-drag to place a horizontal line.
add_v    – crosshair cursor; click-drag to place a vertical line.
pairing  – click an image cell then a text cell to create a pair;
           right-click on a cell to remove any pair that contains it.
omit     – click-drag to mark a page-specific area that should be skipped
           during extraction; right-click an omitted region to remove it.

Grid line coordinates are stored in 150-DPI pixel space so they match the
coordinate system used by the Extractor.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.extraction.grid import CellPair, Grid, OmitRegion
from src.ui import theme
from src.ui.pdf_viewer import PDFViewer

# ------------------------------------------------------------------
# Visual constants
# ------------------------------------------------------------------

_LINE_COLOR = QColor(theme.GRID_LINE)
_LINE_ACTIVE = QColor(theme.GRID_LINE_ACTIVE)
_PREVIEW_COLOR = QColor(0, 0, 0, 155)
# Dark rail tabs intentionally match the surrounding control-panel chrome.
# They stay fixed on the line center; overlapped handles no longer jump into
# alternate lanes. Hovered/active handles are drawn last so the target remains
# discoverable without visual shifting.
_HANDLE_COLOR = QColor(theme.BG_ELEVATED)
_HANDLE_HOVER = QColor(theme.BG_ACTIVE)
_HANDLE_INNER = QColor(theme.ACCENT)
_HANDLE_RAIL = QColor(82, 105, 135, 105)
_HANDLE_BORDER = QColor(theme.BORDER_LIGHT)
_HANDLE_ACTIVE_BORDER = QColor(theme.ACCENT)
_PAGE_BORDER = QColor(15, 23, 42, 185)
_PAGE_SHADOW = QColor(0, 0, 0, 55)
_HANDLE_OUTSET = 14
_HANDLE_LENGTH = 22
_HANDLE_THICKNESS = 9
_LINE_HIT_DIST = 5
_MIN_LINE_GAP_ORIG = 3

_PENDING_FILL = QColor(245, 158, 11, 64)
_HOVER_FILL = QColor(148, 163, 184, 42)
_OMIT_FILL = QColor(15, 23, 42, 96)
_OMIT_BORDER = QColor(theme.WARNING)
_OMIT_PREVIEW_FILL = QColor(245, 158, 11, 48)
_OMITTED_PAGE_FILL = QColor(15, 23, 42, 122)

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
    rect: QRectF,
    orientation: str,
    active: bool = False,
) -> None:
    """Draw a compact dark drag tab anchored to the outside rail.

    The tab is intentionally squared-off instead of pill-shaped so it feels
    more like part of the app chrome. Handles do not shift into alternate
    lanes; when two are close together, hover/drag state determines which one
    is drawn on top.
    """
    radius = 3.0

    shadow = rect.translated(0, 1.2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(0, 0, 0, 86)))
    painter.drawRoundedRect(shadow, radius, radius)

    painter.setPen(QPen(_HANDLE_ACTIVE_BORDER if active else _HANDLE_BORDER, 1.0))
    painter.setBrush(QBrush(_HANDLE_HOVER if active else _HANDLE_COLOR))
    painter.drawRoundedRect(rect, radius, radius)

    # Small accent strip visually connects the tab to the editable boundary
    # without using a bright white control surface.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(_HANDLE_ACTIVE_BORDER if active else QColor(theme.BORDER_STRONG)))
    if orientation == "h":
        accent = QRectF(rect.right() - 2.2, rect.top() + 2.0, 1.4, rect.height() - 4.0)
    else:
        accent = QRectF(rect.left() + 2.0, rect.bottom() - 2.2, rect.width() - 4.0, 1.4)
    painter.drawRoundedRect(accent, 0.7, 0.7)

    center = rect.center()
    painter.setBrush(QBrush(_HANDLE_INNER if active else QColor(148, 163, 184, 210)))
    if orientation == "h":
        for offset in (-2.6, 0, 2.6):
            grip = QRectF(center.x() - 5.0, center.y() + offset - 0.55, 8.5, 1.1)
            painter.drawRoundedRect(grip, 0.55, 0.55)
    else:
        for offset in (-2.6, 0, 2.6):
            grip = QRectF(center.x() + offset - 0.55, center.y() - 5.0, 1.1, 8.5)
            painter.drawRoundedRect(grip, 0.55, 0.55)


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

        current_page = e.current_page_index()

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

        # --- Page/region omission overlays ---
        for region in e._regions_for_current_page():
            r = _omit_region_rect_display(region, e)
            if r and r.isValid():
                painter.fillRect(r, _OMIT_FILL)
                pen = QPen(_OMIT_BORDER, 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawRect(r.adjusted(0, 0, -1, -1))

        if current_page in e._omitted_pages:
            painter.fillRect(page_rect, _OMITTED_PAGE_FILL)
            _draw_center_label(painter, page_rect, "Page omitted")

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

        # --- Drag rails and handles ---
        handle_rects = _handle_rects_display(page_rect, h_d, v_d)
        painter.setPen(QPen(_HANDLE_RAIL, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if h_d[1:-1]:
            rail_x = min(rect.left() for key, rect in handle_rects.items() if key[0] == "h") - 3
            painter.drawLine(int(rail_x), page_rect.top(), int(rail_x), page_rect.bottom())
        if v_d[1:-1]:
            rail_y = min(rect.top() for key, rect in handle_rects.items() if key[0] == "v") - 3
            painter.drawLine(page_rect.left(), int(rail_y), page_rect.right(), int(rail_y))

        # Draw inactive handles first, then hovered/dragged handles. This keeps
        # close handles stable without shifting them into extra lanes.
        active_handles: list[tuple[str, int, QRectF]] = []
        for (kind, idx), rect in handle_rects.items():
            active = hovered == (kind, idx) or dragging == (kind, idx)
            if active:
                active_handles.append((kind, idx, rect))
            else:
                _draw_handle(painter, rect, kind, False)
        for kind, _idx, rect in active_handles:
            _draw_handle(painter, rect, kind, True)

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

        if e._omit_preview is not None:
            r = _rect_orig_to_display(e._omit_preview, e)
            if r and r.isValid():
                painter.fillRect(r, _OMIT_PREVIEW_FILL)
                pen = QPen(_OMIT_BORDER, 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawRect(r.adjusted(0, 0, -1, -1))

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


def _draw_center_label(painter: QPainter, rect: QRect, text: str) -> None:
    label_rect = QRectF(rect.center().x() - 86, rect.center().y() - 18, 172, 36)
    painter.setPen(QPen(QColor(15, 23, 42, 180), 1))
    painter.setBrush(QBrush(QColor(248, 250, 252, 224)))
    painter.drawRoundedRect(label_rect, 6, 6)

    f = QFont()
    f.setPointSize(9)
    f.setBold(True)
    painter.setFont(f)
    painter.setPen(QColor(15, 23, 42))
    painter.drawText(label_rect.toRect(), Qt.AlignmentFlag.AlignCenter, text)


def _rect_orig_to_display(rect: tuple[int, int, int, int], editor: GridEditor) -> QRect | None:
    x0, y0, x1, y1 = rect
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    dx0, dy0 = editor._o2d(left, top)
    dx1, dy1 = editor._o2d(right, bottom)
    return QRect(dx0, dy0, dx1 - dx0, dy1 - dy0).normalized()


def _omit_region_rect_display(region: OmitRegion, editor: GridEditor) -> QRect | None:
    return _rect_orig_to_display(region.rect, editor)


def _handle_rects_display(
    page_rect: QRect, h_d: list[int], v_d: list[int]
) -> dict[tuple[str, int], QRectF]:
    """Return stable outside-rail drag handle rects in display space.

    Handles are always centered on their associated line and never move into
    alternate lanes. Compact tab dimensions reduce visual overlap, while the
    hit-test code selects the nearest candidate if two handles are close.
    """
    rects: dict[tuple[str, int], QRectF] = {}

    h_tab_x = page_rect.left() - _HANDLE_OUTSET
    for idx, cy in enumerate(h_d[1:-1]):
        rects[("h", idx)] = QRectF(
            h_tab_x - (_HANDLE_LENGTH / 2),
            cy - (_HANDLE_THICKNESS / 2),
            _HANDLE_LENGTH,
            _HANDLE_THICKNESS,
        )

    v_tab_y = page_rect.top() - _HANDLE_OUTSET
    for idx, cx in enumerate(v_d[1:-1]):
        rects[("v", idx)] = QRectF(
            cx - (_HANDLE_THICKNESS / 2),
            v_tab_y - (_HANDLE_LENGTH / 2),
            _HANDLE_THICKNESS,
            _HANDLE_LENGTH,
        )

    return rects


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
        self._omitted_pages: set[int] = set()
        self._omit_regions: list[OmitRegion] = []

        # Interaction state
        self._mode: str = "idle"
        self._preview: int | None = None
        self._placing: bool = False
        self._dragging: tuple[str, int] | None = None
        self._hovered_line: tuple[str, int] | None = None
        self._pending_image: tuple[int, int] | None = None
        self._hovered_cell: tuple[int, int] | None = None
        self._omit_start: tuple[int, int] | None = None
        self._omit_preview: tuple[int, int, int, int] | None = None

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
            (QIcon(), "Ignore Area", "omit", "Click-drag a page-specific area to skip during extraction."),
        ]
        for icon, label, mode, tooltip in modes:
            btn = QPushButton(icon, f"  {label}")
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda _checked, m=mode, b=btn: self._set_mode(m, b))
            setattr(self, f"_btn_{mode}", btn)
            seg_layout.addWidget(btn)

        bar.addWidget(seg)

        self._prev_page_btn = QPushButton("‹")
        self._prev_page_btn.setObjectName("pageNavButton")
        self._prev_page_btn.setToolTip("Previous page")
        self._prev_page_btn.clicked.connect(lambda: self._go_to_page(self.current_page_index() - 1))
        bar.addWidget(self._prev_page_btn)

        self._page_label = QLabel("Page —/—")
        self._page_label.setObjectName("pageStatus")
        bar.addWidget(self._page_label)

        self._next_page_btn = QPushButton("›")
        self._next_page_btn.setObjectName("pageNavButton")
        self._next_page_btn.setToolTip("Next page")
        self._next_page_btn.clicked.connect(lambda: self._go_to_page(self.current_page_index() + 1))
        bar.addWidget(self._next_page_btn)

        self._omit_page_btn = QPushButton("Omit Page")
        self._omit_page_btn.setCheckable(True)
        self._omit_page_btn.setObjectName("omitPageButton")
        self._omit_page_btn.setToolTip("Skip this entire page during extraction.")
        self._omit_page_btn.clicked.connect(self._toggle_current_page_omitted)
        bar.addWidget(self._omit_page_btn)

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
        self._set_hint("Use Rows or Columns to place boundaries on any page. The grid applies to all pages.")
        self._update_page_controls()
        self._reposition_overlay()

    def current_profile(self) -> Grid | None:
        if not self._h_lines and not self._v_lines:
            return None
        return Grid(
            horizontal_lines=sorted(self._h_lines),
            vertical_lines=sorted(self._v_lines),
            pairs=list(self._pairs),
            omitted_pages=sorted(self._omitted_pages),
            omit_regions=list(self._omit_regions),
        )

    def apply_profile(self, grid: Grid) -> None:
        self._h_lines = sorted(grid.horizontal_lines)
        self._v_lines = sorted(grid.vertical_lines)
        self._pairs = list(grid.pairs)
        self._omitted_pages = set(grid.omitted_pages)
        self._omit_regions = list(grid.omit_regions)
        self._pending_image = None
        self._hovered_cell = None
        self._hovered_line = None
        self._omit_start = None
        self._omit_preview = None
        self._set_hint("Profile applied. Navigate pages to review page/section omissions.")
        self._update_page_controls()
        self._overlay.update()

    def current_page_index(self) -> int:
        return self._viewer.page_index

    def _regions_for_current_page(self) -> list[OmitRegion]:
        page_index = self.current_page_index()
        return [region for region in self._omit_regions if region.page_index == page_index]

    def _update_page_controls(self) -> None:
        page_count = self._viewer.page_count
        page_index = self.current_page_index()
        has_pages = page_count > 0
        self._prev_page_btn.setEnabled(has_pages and page_index > 0)
        self._next_page_btn.setEnabled(has_pages and page_index < page_count - 1)
        self._omit_page_btn.setEnabled(has_pages)
        self._page_label.setText(f"Page {page_index + 1}/{page_count}" if has_pages else "Page —/—")
        self._omit_page_btn.setChecked(page_index in self._omitted_pages)

    def _go_to_page(self, index: int) -> None:
        if index < 0 or index >= self._viewer.page_count:
            return
        self._viewer.load_page(index)
        self._pending_image = None
        self._hovered_cell = None
        self._hovered_line = None
        self._omit_start = None
        self._omit_preview = None
        self._update_page_controls()
        self._set_hint("Viewing page %d. Grid edits here still apply to every page." % (index + 1))
        self._reposition_overlay()

    def _toggle_current_page_omitted(self) -> None:
        page_index = self.current_page_index()
        if page_index in self._omitted_pages:
            self._omitted_pages.remove(page_index)
            self._set_hint("Current page will be included during extraction.")
        else:
            self._omitted_pages.add(page_index)
            self._set_hint("Current page will be skipped during extraction.")
        self._update_page_controls()
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

    def _omit_region_at_orig(self, ox: int, oy: int) -> int | None:
        for idx in range(len(self._omit_regions) - 1, -1, -1):
            region = self._omit_regions[idx]
            if region.page_index != self.current_page_index():
                continue
            x0, y0, x1, y1 = region.rect
            if x0 <= ox <= x1 and y0 <= oy <= y1:
                return idx
        return None

    def _clamped_orig_point(self, ox: int, oy: int) -> tuple[int, int]:
        orig = self._viewer.pixmap
        if orig is None:
            return max(0, ox), max(0, oy)
        return (
            max(0, min(orig.width(), ox)),
            max(0, min(orig.height(), oy)),
        )

    def _normalized_omit_rect(self, start: tuple[int, int], end: tuple[int, int]) -> tuple[int, int, int, int] | None:
        x0, y0 = start
        x1, y1 = end
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))
        if right - left < 8 or bottom - top < 8:
            return None
        return left, top, right, bottom

    def _line_hit(self, dx: int, dy: int) -> tuple[int | None, int | None]:
        """Return (h_index, None) or (None, v_index) if near a line/handle."""
        h_d, v_d = self._grid_display_boundaries()
        page_rect = _page_rect_display(h_d, v_d)
        point = QPointF(dx, dy)

        # Handles are the most intentional drag target, so they take priority.
        # If compact handles visually overlap, choose the nearest line instead
        # of moving handles into alternate lanes.
        handle_candidates: list[tuple[float, str, int]] = []
        for (kind, idx), rect in _handle_rects_display(page_rect, h_d, v_d).items():
            if rect.adjusted(-5, -5, 5, 5).contains(point):
                distance = abs(dy - rect.center().y()) if kind == "h" else abs(dx - rect.center().x())
                handle_candidates.append((distance, kind, idx))
        if handle_candidates:
            _distance, kind, idx = min(handle_candidates, key=lambda item: item[0])
            return (idx, None) if kind == "h" else (None, idx)

        # Lines remain draggable, but only across the visible page area.
        if not page_rect.adjusted(-2, -2, 2, 2).contains(QPoint(dx, dy)):
            return None, None

        for i, y_d in enumerate(h_d[1:-1]):
            if abs(dy - y_d) <= _LINE_HIT_DIST:
                return i, None
        for i, x_d in enumerate(v_d[1:-1]):
            if abs(dx - x_d) <= _LINE_HIT_DIST:
                return None, i
        return None, None

    def _bounded_line_value(self, dtype: str, idx: int, value: int) -> int:
        """Clamp a dragged line so it cannot cross adjacent boundaries."""
        orig = self._viewer.pixmap
        if orig is None:
            return max(0, value)

        lines = self._h_lines if dtype == "h" else self._v_lines
        max_value = orig.height() if dtype == "h" else orig.width()
        if idx < 0 or idx >= len(lines):
            return max(0, min(max_value, value))

        lower = 0 if idx == 0 else lines[idx - 1] + _MIN_LINE_GAP_ORIG
        upper = max_value if idx == len(lines) - 1 else lines[idx + 1] - _MIN_LINE_GAP_ORIG
        if lower > upper:
            return lines[idx]
        return max(lower, min(upper, value))

    def _can_place_line(self, dtype: str, value: int) -> bool:
        """Prevent duplicate/stacked lines that create ambiguous drag handles."""
        orig = self._viewer.pixmap
        if orig is None:
            return False
        max_value = orig.height() if dtype == "h" else orig.width()
        if value <= 0 or value >= max_value:
            return False
        lines = self._h_lines if dtype == "h" else self._v_lines
        return all(abs(existing - value) >= _MIN_LINE_GAP_ORIG for existing in lines)

    # ------------------------------------------------------------------
    # Mode / cursor management
    # ------------------------------------------------------------------

    def _set_mode(self, mode: str, active_btn: QPushButton) -> None:
        self._mode = mode if active_btn.isChecked() else "idle"
        for attr in ("_btn_add_h", "_btn_add_v", "_btn_pairing", "_btn_omit"):
            btn = getattr(self, attr, None)
            if btn and btn is not active_btn:
                btn.setChecked(False)
        self._pending_image = None
        self._hovered_cell = None
        self._omit_start = None
        self._omit_preview = None
        self._overlay.update()
        self._update_cursor(None, None)

        hints = {
            "idle": "Drag existing handles to move lines. Right-click a line to remove it.",
            "add_h": "Click-drag across the PDF to place a horizontal row boundary.",
            "add_v": "Click-drag across the PDF to place a vertical column boundary.",
            "pairing": "Click the image cell first, then click the matching ID/text cell.",
            "omit": "Click-drag a section on this page to ignore during extraction. Right-click an ignored section to remove it.",
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
        if self._mode in ("add_h", "add_v", "omit"):
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
        elif self._mode == "omit":
            start = self._clamped_orig_point(ox, oy)
            self._omit_start = start
            self._omit_preview = (*start, *start)
            self._set_hint("Dragging ignored area. Release to save it for this page.")
            self._overlay.update()

    def _on_move(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        dx, dy = pos.x(), pos.y()
        ox, oy = self._d2o(dx, dy)

        if self._dragging:
            dtype, idx = self._dragging
            if dtype == "h":
                self._h_lines[idx] = self._bounded_line_value("h", idx, oy)
            else:
                self._v_lines[idx] = self._bounded_line_value("v", idx, ox)
            self._overlay.update()
            return

        if self._omit_start is not None and self._mode == "omit":
            end = self._clamped_orig_point(ox, oy)
            self._omit_preview = (*self._omit_start, *end)
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

        if self._mode == "omit":
            region_idx = self._omit_region_at_orig(ox, oy)
            if region_idx is not None:
                del self._omit_regions[region_idx]
                self._set_hint("Ignored section removed.")
                self._overlay.update()
            return

        if self._mode == "pairing":
            self._hovered_cell = self._cell_at_orig(ox, oy)
        else:
            self._hovered_cell = None
        self._overlay.update()

    def _on_release(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._omit_start is not None and self._mode == "omit":
            end = self._clamped_orig_point(*self._d2o(
                event.position().toPoint().x(),
                event.position().toPoint().y(),
            ))
            rect = self._normalized_omit_rect(self._omit_start, end)
            if rect is not None:
                self._omit_regions.append(OmitRegion(page_index=self.current_page_index(), rect=rect))
                self._set_hint("Ignored section added for this page. Right-click it in Ignore Area mode to remove it.")
            else:
                self._set_hint("Ignored section was too small to save.")
            self._omit_start = None
            self._omit_preview = None
            self._overlay.update()
            return

        if self._dragging:
            self._h_lines.sort()
            self._v_lines.sort()
            self._dragging = None
            self._set_hint("Line moved. Right-click any line to delete it.")
            self._overlay.update()
            return

        if self._placing:
            if self._preview is not None:
                if self._mode == "add_h":
                    if self._can_place_line("h", self._preview):
                        self._h_lines.append(self._preview)
                        self._h_lines.sort()
                        self._set_hint("Row boundary added. Drag its handle to adjust.")
                    else:
                        self._set_hint("Row boundary is too close to another line or page edge.")
                elif self._mode == "add_v":
                    if self._can_place_line("v", self._preview):
                        self._v_lines.append(self._preview)
                        self._v_lines.sort()
                        self._set_hint("Column boundary added. Drag its handle to adjust.")
                    else:
                        self._set_hint("Column boundary is too close to another line or page edge.")
            self._placing = False
            self._preview = None
            self._overlay.update()

    def _on_right_click(self, dx: int, dy: int) -> None:
        ox, oy = self._d2o(dx, dy)

        if self._mode == "omit":
            region_idx = self._omit_region_at_orig(ox, oy)
            if region_idx is not None:
                del self._omit_regions[region_idx]
                self._set_hint("Ignored section removed.")
                self._overlay.update()
            return

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
        self._omitted_pages.clear()
        self._omit_regions.clear()
        self._pending_image = None
        self._hovered_cell = None
        self._hovered_line = None
        self._omit_start = None
        self._omit_preview = None
        self._update_page_controls()
        self._set_hint("Grid and omissions cleared. Add row and column boundaries to start again.")
        self._overlay.update()






