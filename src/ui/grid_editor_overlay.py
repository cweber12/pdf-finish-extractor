from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from src.ui import theme

if TYPE_CHECKING:
    from src.extraction.grid import OmitRegion
    from src.ui.grid_editor import GridEditor

_LINE_COLOR = QColor(theme.GRID_LINE)
_LINE_ACTIVE = QColor(theme.GRID_LINE_ACTIVE)
_PREVIEW_COLOR = QColor(0, 0, 0, 155)
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

_PENDING_FILL = QColor(245, 158, 11, 64)
_HOVER_FILL = QColor(148, 163, 184, 42)
_OMIT_FILL = QColor(15, 23, 42, 96)
_OMIT_BORDER = QColor(theme.WARNING)
_OMIT_PREVIEW_FILL = QColor(245, 158, 11, 48)
_OMITTED_PAGE_FILL = QColor(15, 23, 42, 122)

_GROUP_FILLS: list[QColor] = [
    QColor(56, 189, 248, 48),
    QColor(34, 197, 94, 44),
    QColor(168, 85, 247, 45),
    QColor(251, 146, 60, 48),
    QColor(250, 204, 21, 38),
]


def _draw_handle(
    painter: QPainter,
    rect: QRectF,
    orientation: str,
    active: bool = False,
) -> None:
    radius = 3.0

    shadow = rect.translated(0, 1.2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(0, 0, 0, 86)))
    painter.drawRoundedRect(shadow, radius, radius)

    painter.setPen(QPen(_HANDLE_ACTIVE_BORDER if active else _HANDLE_BORDER, 1.0))
    painter.setBrush(QBrush(_HANDLE_HOVER if active else _HANDLE_COLOR))
    painter.drawRoundedRect(rect, radius, radius)

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


class _OverlayWidget(QWidget):
    """Transparent overlay that renders the grid and handles mouse events."""

    def __init__(self, editor: GridEditor) -> None:
        super().__init__(editor)
        self._e = editor
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

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

        for idx, group in enumerate(e._groups):
            fill = _GROUP_FILLS[idx % len(_GROUP_FILLS)]
            for cell in group.cells():
                r = _cell_rect_display(cell, h_d, v_d)
                if r:
                    painter.fillRect(r, fill)

        for cell in e._pending_group_cells:
            r = _cell_rect_display(cell, h_d, v_d)
            if r:
                painter.fillRect(r, _PENDING_FILL)

        hc = e._hovered_cell
        is_ungrouped = hc is not None and not any(hc in group.cells() for group in e._groups)
        if e._mode == "grouping" and is_ungrouped and hc not in e._pending_group_cells:
            r = _cell_rect_display(hc, h_d, v_d)
            if r:
                painter.fillRect(r, _HOVER_FILL)

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

        handle_rects = _handle_rects_display(page_rect, h_d, v_d)
        painter.setPen(QPen(_HANDLE_RAIL, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if h_d[1:-1]:
            rail_x = min(rect.left() for key, rect in handle_rects.items() if key[0] == "h") - 3
            painter.drawLine(int(rail_x), page_rect.top(), int(rail_x), page_rect.bottom())
        if v_d[1:-1]:
            rail_y = min(rect.top() for key, rect in handle_rects.items() if key[0] == "v") - 3
            painter.drawLine(page_rect.left(), int(rail_y), page_rect.right(), int(rail_y))

        active_handles: list[tuple[str, int, QRectF]] = []
        for (kind, idx), rect in handle_rects.items():
            active = hovered == (kind, idx) or dragging == (kind, idx)
            if active:
                active_handles.append((kind, idx, rect))
            else:
                _draw_handle(painter, rect, kind, False)
        for kind, _idx, rect in active_handles:
            _draw_handle(painter, rect, kind, True)

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

        for idx, group in enumerate(e._groups):
            badge = str(idx + 1)
            for cell in group.cells():
                r = _cell_rect_display(cell, h_d, v_d)
                if r:
                    _draw_badge(painter, r.center().x(), r.center().y(), badge)

        painter.end()

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

    def wheelEvent(self, event) -> None:  # noqa: ANN001
        self._e._on_wheel(event)


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
