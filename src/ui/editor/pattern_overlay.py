from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import QWidget

from src.extraction.pattern import RectPx
from src.ui.style import theme

if TYPE_CHECKING:
    from src.ui.editor.pattern_editor import PatternEditor

# ------------------------------------------------------------------
# Colour palette
# ------------------------------------------------------------------

_IMAGE_BORDER = QColor(theme.ACCENT)
_IMAGE_FILL = QColor(theme.ACCENT)
_IMAGE_FILL.setAlpha(18)

_TEXT_BORDER = QColor(148, 163, 184, 210)
_TEXT_FILL = QColor(148, 163, 184, 10)

_SECTION_FILLS = [
    QColor(56, 189, 248, 32),
    QColor(34, 197, 94, 28),
    QColor(168, 85, 247, 28),
    QColor(251, 146, 60, 32),
    QColor(250, 204, 21, 25),
    QColor(244, 114, 182, 28),
]
_DIVIDER_COLOR = QColor(148, 163, 184, 160)

_HANDLE_BG = QColor(theme.BG_ELEVATED)
_HANDLE_HOVER = QColor(theme.BG_ACTIVE)
_HANDLE_BORDER = QColor(theme.BORDER_LIGHT)
_HANDLE_ACCENT_BORDER = QColor(theme.ACCENT)
_HANDLE_TEXT_BORDER = QColor(148, 163, 184, 200)

_CROP_PREVIEW = QColor(0, 0, 0, 140)
_PAGE_BORDER = QColor(15, 23, 42, 185)
_PAGE_SHADOW = QColor(0, 0, 0, 55)

_OMIT_FILL = QColor(15, 23, 42, 96)
_OMIT_BORDER = QColor(theme.WARNING)
_OMIT_PREVIEW_FILL = QColor(245, 158, 11, 48)
_OMITTED_PAGE_FILL = QColor(15, 23, 42, 122)

_LABEL_BG = QColor(15, 23, 42, 200)
_LABEL_TEXT = QColor(248, 250, 252)

_HANDLE_SIZE = 8   # half-size of a corner/edge handle square


# ------------------------------------------------------------------
# Drawing helpers
# ------------------------------------------------------------------

def _draw_page_frame(painter: QPainter, page_rect: QRect) -> None:
    if page_rect.isNull():
        return
    shadow = page_rect.adjusted(2, 2, 2, 2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(_PAGE_SHADOW))
    painter.drawRect(shadow)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(_PAGE_BORDER, 1))
    painter.drawRect(page_rect.adjusted(0, 0, -1, -1))


def _draw_rect_with_handles(
    painter: QPainter,
    rd: tuple[int, int, int, int],
    border_color: QColor,
    fill_color: QColor,
    hovered_handle: str,
    active_handle: str,
    prefix: str,
) -> None:
    x0, y0, x1, y1 = rd
    qr = QRect(x0, y0, x1 - x0, y1 - y0)

    painter.setBrush(QBrush(fill_color))
    painter.setPen(QPen(border_color, 1.5))
    painter.drawRect(qr)

    # Corner handles
    mx = (x0 + x1) // 2
    my = (y0 + y1) // 2
    handle_points = [
        (f"{prefix}_corner_tl", x0, y0),
        (f"{prefix}_corner_tr", x1, y0),
        (f"{prefix}_corner_bl", x0, y1),
        (f"{prefix}_corner_br", x1, y1),
        (f"{prefix}_edge_t", mx, y0),
        (f"{prefix}_edge_b", mx, y1),
        (f"{prefix}_edge_l", x0, my),
        (f"{prefix}_edge_r", x1, my),
    ]
    hs = _HANDLE_SIZE
    for name, hx, hy in handle_points:
        active = name in (hovered_handle, active_handle)
        painter.setPen(QPen(_HANDLE_ACCENT_BORDER if (active and prefix == "image") else _HANDLE_TEXT_BORDER if not active else border_color, 1))
        painter.setBrush(QBrush(_HANDLE_HOVER if active else _HANDLE_BG))
        painter.drawRoundedRect(QRectF(hx - hs / 2, hy - hs / 2, hs, hs), 2, 2)


def _draw_section_fills_and_dividers(
    painter: QPainter,
    sections: list[RectPx],
    segmentation: str,
    o2d_fn,
    field_names: list[str],
) -> None:
    for i, sect in enumerate(sections):
        x0d, y0d = o2d_fn(sect.x0, sect.y0)
        x1d, y1d = o2d_fn(sect.x1, sect.y1)
        fill = _SECTION_FILLS[i % len(_SECTION_FILLS)]
        painter.fillRect(QRect(x0d, y0d, x1d - x0d, y1d - y0d), fill)

    # Dividers between sections
    divider_pen = QPen(_DIVIDER_COLOR, 1, Qt.PenStyle.DashLine)
    divider_pen.setCosmetic(True)
    painter.setPen(divider_pen)
    for i, sect in enumerate(sections[:-1]):
        if segmentation == "rows":
            dy = o2d_fn(0, sect.y1)[1]
            x0d, _ = o2d_fn(sect.x0, sect.y0)
            x1d, _ = o2d_fn(sect.x1, sect.y0)
            painter.drawLine(x0d, dy, x1d, dy)
        else:
            dx = o2d_fn(sect.x1, 0)[0]
            _, y0d = o2d_fn(sect.x0, sect.y0)
            _, y1d = o2d_fn(sect.x0, sect.y1)
            painter.drawLine(dx, y0d, dx, y1d)

    # Section labels
    f = QFont()
    f.setPointSize(7)
    f.setBold(True)
    painter.setFont(f)
    for i, sect in enumerate(sections):
        x0d, y0d = o2d_fn(sect.x0, sect.y0)
        x1d, y1d = o2d_fn(sect.x1, sect.y1)
        cx = (x0d + x1d) // 2
        cy = (y0d + y1d) // 2
        label = field_names[i] if i < len(field_names) else f"text_{i + 1}"
        text_w = max(len(label) * 6 + 8, 44)
        label_rect = QRect(cx - text_w // 2, cy - 9, text_w, 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_LABEL_BG))
        painter.drawRoundedRect(QRectF(label_rect), 3, 3)
        painter.setPen(_LABEL_TEXT)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)


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


# ------------------------------------------------------------------
# Overlay widget
# ------------------------------------------------------------------

class _PatternOverlayWidget(QWidget):
    """Transparent overlay that renders the pattern state and forwards mouse events."""

    def __init__(self, editor: PatternEditor) -> None:
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

        # Page frame
        pw = orig.width()
        ph = orig.height()
        x0d, y0d = e._o2d(0, 0)
        x1d, y1d = e._o2d(pw, ph)
        page_rect = QRect(x0d, y0d, x1d - x0d, y1d - y0d)
        _draw_page_frame(painter, page_rect)

        current_page = e.current_page_index()

        # Omit regions
        for region in e._omit_regions:
            if region.page_index != current_page:
                continue
            x0, y0, x1, y1 = region.rect
            ax0, ay0 = e._o2d(min(x0, x1), min(y0, y1))
            ax1, ay1 = e._o2d(max(x0, x1), max(y0, y1))
            r = QRect(ax0, ay0, ax1 - ax0, ay1 - ay0)
            painter.fillRect(r, _OMIT_FILL)
            pen = QPen(_OMIT_BORDER, 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawRect(r.adjusted(0, 0, -1, -1))

        # Omit preview while drawing
        if e._omit_preview is not None:
            x0, y0, x1, y1 = e._omit_preview
            ax0, ay0 = e._o2d(min(x0, x1), min(y0, y1))
            ax1, ay1 = e._o2d(max(x0, x1), max(y0, y1))
            r = QRect(ax0, ay0, ax1 - ax0, ay1 - ay0)
            painter.fillRect(r, _OMIT_PREVIEW_FILL)
            pen = QPen(_OMIT_BORDER, 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawRect(r.adjusted(0, 0, -1, -1))

        # Page-omitted overlay
        if current_page in e._omitted_pages:
            painter.fillRect(page_rect, _OMITTED_PAGE_FILL)
            _draw_center_label(painter, page_rect, "Page omitted")

        state = e._state

        # Image crop preview while dragging a new crop
        if e._crop_start_orig is not None and e._crop_preview_orig is not None:
            sx, sy = e._o2d(*e._crop_start_orig)
            ex, ey = e._o2d(*e._crop_preview_orig)
            r = QRect(min(sx, ex), min(sy, ey), abs(ex - sx), abs(ey - sy))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(_CROP_PREVIEW, 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawRect(r)

        # Text region (draw before image so image handles are on top)
        if state.text_region_rect_px is not None:
            tr = state.text_region_rect_px
            x0d, y0d = e._o2d(tr.x0, tr.y0)
            x1d, y1d = e._o2d(tr.x1, tr.y1)
            _draw_rect_with_handles(
                painter,
                (x0d, y0d, x1d, y1d),
                _TEXT_BORDER,
                _TEXT_FILL,
                hovered_handle=e._hovered_handle or "",
                active_handle=e._active_resize or e._active_drag or "",
                prefix="text",
            )

            if state.text_section_rects_px:
                _draw_section_fills_and_dividers(
                    painter,
                    state.text_section_rects_px,
                    state.segmentation,
                    e._o2d,
                    state.field_names,
                )

        # Image crop rectangle
        if state.image_rect_px is not None:
            ir = state.image_rect_px
            x0d, y0d = e._o2d(ir.x0, ir.y0)
            x1d, y1d = e._o2d(ir.x1, ir.y1)
            _draw_rect_with_handles(
                painter,
                (x0d, y0d, x1d, y1d),
                _IMAGE_BORDER,
                _IMAGE_FILL,
                hovered_handle=e._hovered_handle or "",
                active_handle=e._active_resize or "",
                prefix="image",
            )

            # "Image" label
            label_rect = QRect(x0d + 4, y0d + 4, 46, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(_LABEL_BG))
            painter.drawRoundedRect(QRectF(label_rect), 3, 3)
            f = QFont()
            f.setPointSize(7)
            painter.setFont(f)
            painter.setPen(_LABEL_TEXT)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, "image")

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._e._on_press(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._e._on_move(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._e._on_release(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._e._on_wheel(event)

    def leaveEvent(self, _event) -> None:  # noqa: ANN001
        self._e._hovered_handle = None
        self.update()
