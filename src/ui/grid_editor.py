"""Interactive grid editor overlaid on a PDF viewer.

Modes
-----
idle     – arrow cursor; drag existing lines by clicking near the line or its
           handle; right-click near a line to remove it.
add_h    – crosshair cursor; click-drag to place a horizontal line.
add_v    – crosshair cursor; click-drag to place a vertical line.
grouping – click cells in the field recipe order to create a group;
           right-click on a cell to remove any group that contains it.
omit     – click-drag to mark a page-specific area that should be skipped
           during extraction; right-click an omitted region to remove it.

Grid line coordinates are stored in 150-DPI pixel space so they match the
coordinate system used by the Extractor.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.extraction.grid import (
    CellGroup,
    FieldDefinition,
    Grid,
    GridSegment,
    OmitRegion,
    cells_form_rectangle,
)
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

_GROUP_FILLS: list[QColor] = [
    QColor(56, 189, 248, 48),
    QColor(34, 197, 94, 44),
    QColor(168, 85, 247, 45),
    QColor(251, 146, 60, 48),
    QColor(250, 204, 21, 38),
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

        # --- Cell fills: grouped cells ---
        for idx, group in enumerate(e._groups):
            fill = _GROUP_FILLS[idx % len(_GROUP_FILLS)]
            for cell in group.cells():
                r = _cell_rect_display(cell, h_d, v_d)
                if r:
                    painter.fillRect(r, fill)

        # --- Pending group cells ---
        for cell in e._pending_group_cells:
            r = _cell_rect_display(cell, h_d, v_d)
            if r:
                painter.fillRect(r, _PENDING_FILL)

        # --- Hovered cell (grouping mode only) ---
        hc = e._hovered_cell
        is_ungrouped = hc is not None and not any(hc in group.cells() for group in e._groups)
        if e._mode == "grouping" and is_ungrouped and hc not in e._pending_group_cells:
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

        # --- Group badges ---
        for idx, group in enumerate(e._groups):
            badge = str(idx + 1)
            for cell in group.cells():
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

    def wheelEvent(self, event) -> None:  # noqa: ANN001
        self._e._on_wheel(event)


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
# Glowing icon button
# ------------------------------------------------------------------


class GlowIconButton(QToolButton):
    """Icon-only action button with an animated outer glow.

    The button has no label; identification is purely via tooltip. A drop
    shadow effect provides the glow, with the blur radius animated on
    hover/press/checked transitions so the affordance feels responsive
    without resorting to bright background fills.
    """

    _IDLE_BLUR = 0.0
    _HOVER_BLUR = 18.0
    _PRESS_BLUR = 28.0
    _CHECKED_BLUR = 14.0

    def __init__(
        self,
        icon_name: str,
        tooltip: str,
        glow_color: QColor | None = None,
        checkable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setIcon(QIcon(theme.icon_path(icon_name)))
        self.setIconSize(QSize(18, 18))
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setCheckable(checkable)
        self.setProperty("class", "iconAction")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        base = QColor(glow_color) if glow_color is not None else QColor(theme.ACCENT)
        base.setAlpha(220)
        self._glow_color = base

        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setColor(self._glow_color)
        self._glow.setBlurRadius(self._IDLE_BLUR)
        self._glow.setOffset(0, 0)
        self.setGraphicsEffect(self._glow)

        self._anim = QPropertyAnimation(self._glow, b"blurRadius", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._hovered = False
        self._pressed = False

        if checkable:
            self.toggled.connect(self._on_toggled)

    # -- glow state ----------------------------------------------------
    def _target_blur(self) -> float:
        if not self.isEnabled():
            return self._IDLE_BLUR
        if self._pressed:
            return self._PRESS_BLUR
        if self._hovered:
            return self._HOVER_BLUR
        if self.isChecked():
            return self._CHECKED_BLUR
        return self._IDLE_BLUR

    def _animate_to(self, target: float, duration: int = 180) -> None:
        self._anim.stop()
        self._anim.setDuration(duration)
        self._anim.setStartValue(self._glow.blurRadius())
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_toggled(self, _checked: bool) -> None:
        self._animate_to(self._target_blur())

    # -- events --------------------------------------------------------
    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._hovered = True
        self._animate_to(self._target_blur())
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._hovered = False
        self._animate_to(self._target_blur())
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._animate_to(self._target_blur(), duration=80)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            self._animate_to(self._target_blur(), duration=140)
        super().mouseReleaseEvent(event)

    def changeEvent(self, event) -> None:  # noqa: ANN001
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange:
            if not self.isEnabled():
                self._hovered = False
                self._pressed = False
            self._animate_to(self._target_blur(), duration=120)


def _make_separator() -> QFrame:
    sep = QFrame()
    sep.setObjectName("toolbarSeparator")
    sep.setFrameShape(QFrame.Shape.NoFrame)
    sep.setFixedWidth(1)
    sep.setFixedHeight(22)
    return sep


def _make_status_chip(initial: str = "") -> QLabel:
    label = QLabel(initial)
    label.setProperty("class", "statusChip")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class _FieldRecipeDialog(QDialog):
    """Dialog for editing the ordered extraction field recipe."""

    def __init__(self, fields: list[FieldDefinition], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fields")
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Type", "Clicks"])
        header = self._table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        for field_def in fields:
            self._append_row(field_def)

        add_text = QPushButton("Add Text")
        add_text.clicked.connect(lambda: self._append_row(FieldDefinition("field", "text", 1)))
        add_image = QPushButton("Add Image")
        add_image.clicked.connect(lambda: self._append_row(FieldDefinition("image", "image", 1)))
        remove = QPushButton("Remove")
        remove.clicked.connect(self._remove_selected)
        up = QPushButton("Up")
        up.clicked.connect(lambda: self._move_selected(-1))
        down = QPushButton("Down")
        down.clicked.connect(lambda: self._move_selected(1))

        tools = QHBoxLayout()
        tools.addWidget(add_text)
        tools.addWidget(add_image)
        tools.addWidget(remove)
        tools.addStretch()
        tools.addWidget(up)
        tools.addWidget(down)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(tools)
        layout.addWidget(buttons)
        self.resize(520, 320)

    def fields(self) -> list[FieldDefinition]:
        result: list[FieldDefinition] = []
        seen: set[str] = set()
        for row in range(self._table.rowCount()):
            name_item = self._table.item(row, 0)
            name = name_item.text().strip() if name_item else ""
            if not name or name in seen:
                continue
            type_widget = self._table.cellWidget(row, 1)
            click_widget = self._table.cellWidget(row, 2)
            field_type = "text"
            if isinstance(type_widget, QComboBox):
                field_type = type_widget.currentText().lower()
            click_count = 1
            if isinstance(click_widget, QSpinBox):
                click_count = click_widget.value()
            seen.add(name)
            result.append(FieldDefinition(name=name, field_type=field_type, click_count=click_count))  # type: ignore[arg-type]
        return result

    def _append_row(self, field_def: FieldDefinition) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(field_def.name))

        type_box = QComboBox()
        type_box.addItems(["text", "image"])
        type_box.setCurrentText(field_def.field_type)
        self._table.setCellWidget(row, 1, type_box)

        clicks = QSpinBox()
        clicks.setRange(1, 20)
        clicks.setValue(max(1, field_def.click_count))
        self._table.setCellWidget(row, 2, clicks)
        self._table.selectRow(row)

    def _remove_selected(self) -> None:
        row = self._selected_row()
        if row is not None:
            self._table.removeRow(row)

    def _move_selected(self, delta: int) -> None:
        row = self._selected_row()
        if row is None:
            return
        target = row + delta
        if target < 0 or target >= self._table.rowCount():
            return
        current = self.fields()
        current[row], current[target] = current[target], current[row]
        self._table.setRowCount(0)
        for field_def in current:
            self._append_row(field_def)
        self._table.selectRow(target)

    def _selected_row(self) -> int | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return indexes[0].row()


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
        self._fields: list[FieldDefinition] = [
            FieldDefinition("swatch", "image", 1),
            FieldDefinition("material_id", "text", 1),
        ]
        self._groups: list[CellGroup] = []
        self._omitted_pages: set[int] = set()
        self._omit_regions: list[OmitRegion] = []

        # Per-page layout history for this session.  Cleared on PDF open / clear.
        # Each GridSegment records the grid config in effect from its start_page
        # onward.  The entry with the highest start_page <= current page wins.
        self._segments: list[GridSegment] = []

        # Interaction state
        self._mode: str = "idle"
        self._preview: int | None = None
        self._placing: bool = False
        self._dragging: tuple[str, int] | None = None
        self._hovered_line: tuple[str, int] | None = None
        self._pending_group_cells: list[tuple[int, int]] = []
        self._hovered_cell: tuple[int, int] | None = None
        self._omit_start: tuple[int, int] | None = None
        self._omit_preview: tuple[int, int, int, int] | None = None
        self._pan_last: QPoint | None = None

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
        bar.setContentsMargins(18, 0, 18, 0)
        bar.setSpacing(10)

        warn_color = QColor(theme.WARNING)
        danger_color = QColor(theme.ERROR)

        # --- Tool group: row / column / group / ignore area ---
        modes = [
            ("h-line.svg", "add_h", "Add a horizontal row boundary. Click-drag across the page."),
            ("v-line.svg", "add_v", "Add a vertical column boundary. Click-drag across the page."),
            ("link.svg", "grouping", "Create a group by clicking cells in field order."),
            ("omit-area.svg", "omit", "Ignore an area on this page. Click-drag the region to skip."),
        ]
        for icon_name, mode, tooltip in modes:
            glow = QColor(warn_color) if mode == "omit" else None
            btn = GlowIconButton(icon_name, tooltip, glow_color=glow, checkable=True)
            if mode == "omit":
                btn.setProperty("warn", True)
            btn.clicked.connect(lambda _checked, m=mode, b=btn: self._set_mode(m, b))
            setattr(self, f"_btn_{mode}", btn)
            bar.addWidget(btn)

        bar.addSpacing(6)
        bar.addWidget(_make_separator())
        bar.addSpacing(6)

        self._fields_btn = GlowIconButton(
            "layers.svg",
            "Define extraction fields, types, click counts, and column order.",
        )
        self._fields_btn.clicked.connect(self._edit_fields)
        bar.addWidget(self._fields_btn)

        bar.addSpacing(6)
        bar.addWidget(_make_separator())
        bar.addSpacing(6)

        # --- Page navigation: prev / [page chip] / next ---
        self._prev_page_btn = GlowIconButton(
            "chevron-left.svg",
            "Previous page",
        )
        self._prev_page_btn.clicked.connect(
            lambda: self._go_to_page(self.current_page_index() - 1)
        )
        bar.addWidget(self._prev_page_btn)

        self._page_label = _make_status_chip("—/—")
        self._page_label.setToolTip("Current page")
        bar.addWidget(self._page_label)

        self._next_page_btn = GlowIconButton(
            "chevron-right.svg",
            "Next page",
        )
        self._next_page_btn.clicked.connect(
            lambda: self._go_to_page(self.current_page_index() + 1)
        )
        bar.addWidget(self._next_page_btn)

        bar.addSpacing(8)

        # --- Layout segment navigation ---
        self._seg_prev_btn = GlowIconButton(
            "chevrons-left.svg",
            "Previous layout segment",
        )
        self._seg_prev_btn.setEnabled(False)
        self._seg_prev_btn.clicked.connect(self._on_nav_prev_segment)
        bar.addWidget(self._seg_prev_btn)

        self._seg_label = _make_status_chip("—")
        self._seg_label.setToolTip("Current layout segment")
        bar.addWidget(self._seg_label)

        self._seg_next_btn = GlowIconButton(
            "chevrons-right.svg",
            "Next layout segment",
        )
        self._seg_next_btn.setEnabled(False)
        self._seg_next_btn.clicked.connect(self._on_nav_next_segment)
        bar.addWidget(self._seg_next_btn)

        bar.addSpacing(8)

        self._zoom_label = _make_status_chip("100%")
        self._zoom_label.setToolTip("Zoom level — scroll over the page to zoom")
        bar.addWidget(self._zoom_label)

        bar.addStretch(1)

        # --- Page omission group ---
        bar.addWidget(_make_separator())
        bar.addSpacing(6)

        self._omit_page_btn = GlowIconButton(
            "page-omit.svg",
            "Omit this page from extraction.",
            glow_color=warn_color,
            checkable=True,
        )
        self._omit_page_btn.setProperty("warn", True)
        self._omit_page_btn.clicked.connect(self._toggle_current_page_omitted)
        bar.addWidget(self._omit_page_btn)

        omit_all_btn = GlowIconButton(
            "pages-omit.svg",
            "Omit every page so none are extracted.",
            glow_color=warn_color,
        )
        omit_all_btn.setProperty("warn", True)
        omit_all_btn.clicked.connect(self._omit_all_pages)
        bar.addWidget(omit_all_btn)

        bar.addSpacing(6)
        bar.addWidget(_make_separator())
        bar.addSpacing(6)

        # --- Destructive ---
        clear_btn = GlowIconButton(
            "trash.svg",
            "Clear all lines, groups, and omissions for this PDF.",
            glow_color=danger_color,
        )
        clear_btn.setProperty("danger", True)
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

        subtitle = QLabel("Define reusable row and column boundaries, then group fields for export.")
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

    @property
    def ctrl_bar(self) -> QWidget:
        """The toolbar widget; owned by GridEditor but placed by the parent layout."""
        return self._ctrl_bar

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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
        self._zoom_label.setText("100%")
        self._stack.setCurrentIndex(1)
        self._set_hint("Use Rows or Columns to place boundaries on any page. Changes apply to this page and forward.")
        # Reset layout history; current grid applies to all pages until edited.
        self._segments = [GridSegment(
            start_page=0,
            horizontal_lines=list(self._h_lines),
            vertical_lines=list(self._v_lines),
            groups=list(self._groups),
        )]
        self._update_page_controls()
        self._update_segment_nav()
        self._reposition_overlay()

    def current_profile(self) -> Grid | None:
        if not self._h_lines and not self._v_lines:
            return None
        return Grid(
            horizontal_lines=sorted(self._h_lines),
            vertical_lines=sorted(self._v_lines),
            fields=list(self._fields),
            groups=list(self._groups),
            omitted_pages=sorted(self._omitted_pages),
            omit_regions=list(self._omit_regions),
        )

    def current_segments(self) -> list[GridSegment]:
        """Return the per-page layout history for the current session."""
        return list(self._segments)

    def apply_profile(self, grid: Grid) -> None:
        self._h_lines = sorted(grid.horizontal_lines)
        self._v_lines = sorted(grid.vertical_lines)
        self._fields = list(grid.fields)
        self._groups = list(grid.groups)
        self._omitted_pages = set(grid.omitted_pages)
        self._omit_regions = list(grid.omit_regions)
        self._pending_group_cells = []
        self._hovered_cell = None
        self._hovered_line = None
        self._omit_start = None
        self._omit_preview = None
        # Treat the applied profile as the baseline layout for all pages.
        self._segments = [GridSegment(
            start_page=0,
            horizontal_lines=list(self._h_lines),
            vertical_lines=list(self._v_lines),
            groups=list(self._groups),
        )]
        self._set_hint("Profile applied. Navigate pages to review page/section omissions.")
        self._update_page_controls()
        self._update_segment_nav()
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
        self._page_label.setText(f"{page_index + 1}/{page_count}" if has_pages else "—/—")
        self._omit_page_btn.setChecked(page_index in self._omitted_pages)

    def _go_to_page(self, index: int) -> None:
        if index < 0 or index >= self._viewer.page_count:
            return
        self._viewer.load_page(index)
        self._zoom_label.setText("100%")
        self._pending_group_cells = []
        self._hovered_cell = None
        self._hovered_line = None
        self._omit_start = None
        self._omit_preview = None
        self._update_page_controls()
        self._load_segment_for_page(index)
        self._update_segment_nav()
        self._set_hint(f"Viewing page {index + 1}. Edits apply to this page and forward.")
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

    def _omit_all_pages(self) -> None:
        page_count = self._viewer.page_count
        if page_count == 0:
            return
        self._omitted_pages = set(range(page_count))
        self._update_page_controls()
        self._overlay.update()
        self._set_hint(f"All {page_count} pages marked as omitted.")

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

    def _set_mode(self, mode: str, active_btn: QToolButton) -> None:
        self._mode = mode if active_btn.isChecked() else "idle"
        for attr in ("_btn_add_h", "_btn_add_v", "_btn_grouping", "_btn_omit"):
            btn = getattr(self, attr, None)
            if btn and btn is not active_btn:
                btn.setChecked(False)
        self._pending_group_cells = []
        self._hovered_cell = None
        self._omit_start = None
        self._omit_preview = None
        self._overlay.update()
        self._update_cursor(None, None)

        hints = {
            "idle": "Drag existing handles to move lines. Right-click a line to remove it.",
            "add_h": "Click-drag across the PDF to place a horizontal row boundary.",
            "add_v": "Click-drag across the PDF to place a vertical column boundary.",
            "grouping": "Click cells in field order until the group is complete.",
            "omit": "Click-drag a section on this page to ignore during extraction. Right-click an ignored section to remove it.",
        }
        self._set_hint(hints.get(self._mode, hints["idle"]))

    def _set_hint(self, _text: str) -> None:
        # Hint label was removed in favor of static button tooltips; call sites
        # remain so transient feedback could be re-introduced later without
        # touching the editor's interaction logic.
        return

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

        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_last = pos
            self._overlay.setCursor(Qt.CursorShape.ClosedHandCursor)
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
        elif self._mode == "grouping":
            self._on_group_click(ox, oy)
        elif self._mode == "omit":
            start = self._clamped_orig_point(ox, oy)
            self._omit_start = start
            self._omit_preview = (*start, *start)
            self._set_hint("Dragging ignored area. Release to save it for this page.")
            self._overlay.update()

    def _on_move(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        dx, dy = pos.x(), pos.y()

        if self._pan_last is not None:
            ddx = dx - self._pan_last.x()
            ddy = dy - self._pan_last.y()
            self._viewer.pan_by(ddx, ddy)
            self._pan_last = pos
            self._overlay.update()
            return

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

        if self._mode == "grouping":
            self._hovered_cell = self._cell_at_orig(ox, oy)
        else:
            self._hovered_cell = None
        self._overlay.update()

    def _on_release(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_last = None
            self._update_cursor(None, None)
            return

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
            self._record_segment_change()
            return

        if self._placing:
            if self._preview is not None:
                if self._mode == "add_h":
                    if self._can_place_line("h", self._preview):
                        self._h_lines.append(self._preview)
                        self._h_lines.sort()
                        self._clear_groups_for_grid_change()
                        self._set_hint("Row boundary added. Drag its handle to adjust.")
                    else:
                        self._set_hint("Row boundary is too close to another line or page edge.")
                elif self._mode == "add_v":
                    if self._can_place_line("v", self._preview):
                        self._v_lines.append(self._preview)
                        self._v_lines.sort()
                        self._clear_groups_for_grid_change()
                        self._set_hint("Column boundary added. Drag its handle to adjust.")
                    else:
                        self._set_hint("Column boundary is too close to another line or page edge.")
            self._placing = False
            self._preview = None
            self._overlay.update()
            self._record_segment_change()

    def _on_wheel(self, event: QWheelEvent) -> None:
        """Zoom on mouse wheel. Cancels any in-progress placement first."""
        if self._placing or self._omit_start is not None:
            self._placing = False
            self._preview = None
            self._omit_start = None
            self._omit_preview = None

        delta = event.angleDelta().y()
        if delta == 0:
            event.accept()
            return

        factor = 1.15 if delta > 0 else 1.0 / 1.15
        new_zoom = self._viewer.zoom_level * factor
        pos = event.position().toPoint()
        self._viewer.zoom_at(pos.x(), pos.y(), new_zoom)
        self._zoom_label.setText(f"{round(self._viewer.zoom_level * 100)}%")
        self._overlay.update()
        event.accept()

    def _on_right_click(self, dx: int, dy: int) -> None:
        ox, oy = self._d2o(dx, dy)

        if self._mode == "omit":
            region_idx = self._omit_region_at_orig(ox, oy)
            if region_idx is not None:
                del self._omit_regions[region_idx]
                self._set_hint("Ignored section removed.")
                self._overlay.update()
            return

        if self._mode == "grouping":
            if self._pending_group_cells:
                self._pending_group_cells = []
                self._set_hint("Group selection cancelled.")
                self._overlay.update()
                return
            cell = self._cell_at_orig(ox, oy)
            if cell:
                before = len(self._groups)
                self._groups = [group for group in self._groups if cell not in group.cells()]
                if len(self._groups) != before:
                    self._set_hint("Group removed.")
                    self._record_segment_change()
                self._overlay.update()
            return

        hit_h, hit_v = self._line_hit(dx, dy)
        if hit_h is not None:
            del self._h_lines[hit_h]
            self._clear_groups_for_grid_change()
            self._set_hint("Row boundary removed. Groups were cleared because the grid changed.")
            self._overlay.update()
            self._record_segment_change()
        elif hit_v is not None:
            del self._v_lines[hit_v]
            self._clear_groups_for_grid_change()
            self._set_hint("Column boundary removed. Groups were cleared because the grid changed.")
            self._overlay.update()
            self._record_segment_change()

    def _on_group_click(self, ox: int, oy: int) -> None:
        cell = self._cell_at_orig(ox, oy)
        if cell is None:
            return
        if not self._fields:
            self._set_hint("Define fields before creating groups.")
            return
        if cell in self._pending_group_cells:
            self._set_hint("That cell is already selected for the pending group.")
            return

        candidate = [*self._pending_group_cells, cell]
        field_def = self._field_for_click_index(len(candidate) - 1)
        if field_def is None:
            self._pending_group_cells = []
            return
        current_cells = self._pending_cells_for_field(candidate, field_def)
        if len(current_cells) == field_def.click_count and not cells_form_rectangle(current_cells):
            self._set_hint("Field cells must form one adjacent rectangle.")
            return

        self._pending_group_cells = candidate
        if len(self._pending_group_cells) < self._recipe_click_count():
            self._set_hint(f"Group selection {len(self._pending_group_cells)}/{self._recipe_click_count()}.")
        else:
            group = CellGroup(field_cells=self._field_cells_from_pending())
            self._groups.append(group)
            self._pending_group_cells = []
            self._set_hint("Group created. Continue grouping cells or right-click a group to remove it.")
            self._record_segment_change()
        self._overlay.update()

    # ------------------------------------------------------------------
    # Grid management
    # ------------------------------------------------------------------

    def _edit_fields(self) -> None:
        if self._groups:
            confirm = QMessageBox(self)
            confirm.setWindowTitle("Change fields")
            confirm.setIcon(QMessageBox.Icon.Warning)
            confirm.setText("Changing fields will clear existing groups.")
            confirm.setInformativeText("Continue?")
            confirm.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
            )
            confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if confirm.exec() != QMessageBox.StandardButton.Yes:
                return

        dialog = _FieldRecipeDialog(list(self._fields), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        fields = dialog.fields()
        if not fields:
            self._set_hint("Keep at least one field in the recipe.")
            return
        self._fields = fields
        self._groups.clear()
        self._pending_group_cells = []
        self._record_segment_change()
        self._overlay.update()

    def _recipe_click_count(self) -> int:
        return sum(field_def.click_count for field_def in self._fields)

    def _field_for_click_index(self, click_index: int) -> FieldDefinition | None:
        start = 0
        for field_def in self._fields:
            end = start + field_def.click_count
            if start <= click_index < end:
                return field_def
            start = end
        return None

    def _pending_cells_for_field(
        self,
        pending: list[tuple[int, int]],
        field_def: FieldDefinition,
    ) -> list[tuple[int, int]]:
        start = 0
        for candidate in self._fields:
            end = start + candidate.click_count
            if candidate.name == field_def.name:
                return pending[start:end]
            start = end
        return []

    def _field_cells_from_pending(self) -> dict[str, list[tuple[int, int]]]:
        result: dict[str, list[tuple[int, int]]] = {}
        start = 0
        for field_def in self._fields:
            end = start + field_def.click_count
            result[field_def.name] = self._pending_group_cells[start:end]
            start = end
        return result

    def _clear_groups_for_grid_change(self) -> None:
        self._groups.clear()
        self._pending_group_cells = []

    def _clear_grid(self) -> None:
        self._h_lines.clear()
        self._v_lines.clear()
        self._groups.clear()
        self._omitted_pages.clear()
        self._omit_regions.clear()
        self._pending_group_cells = []
        self._hovered_cell = None
        self._hovered_line = None
        self._omit_start = None
        self._omit_preview = None
        self._segments = [GridSegment(start_page=0)]
        self._update_page_controls()
        self._update_segment_nav()
        self._set_hint("Grid and omissions cleared. Add row and column boundaries to start again.")
        self._overlay.update()

    # ------------------------------------------------------------------
    # Layout segment management
    # ------------------------------------------------------------------

    def _segment_index_for_page(self, page_index: int) -> int:
        """Return the index of the segment whose layout applies to ``page_index``."""
        best = 0
        for i, seg in enumerate(self._segments):
            if seg.start_page <= page_index:
                best = i
            else:
                break
        return best

    def _record_segment_change(self) -> None:
        """Snapshot the current grid state into _segments for the active page."""
        if not self._segments:
            return
        page_index = self.current_page_index()
        seg_idx = self._segment_index_for_page(page_index)
        new_seg = GridSegment(
            start_page=page_index,
            horizontal_lines=list(self._h_lines),
            vertical_lines=list(self._v_lines),
            groups=list(self._groups),
        )
        if self._segments[seg_idx].start_page == page_index:
            self._segments[seg_idx] = new_seg
        else:
            self._segments.insert(seg_idx + 1, new_seg)
        self._update_segment_nav()

    def _load_segment_for_page(self, page_index: int) -> None:
        """Load the layout applicable to ``page_index`` into the editor state."""
        if not self._segments:
            return
        seg = self._segments[self._segment_index_for_page(page_index)]
        self._h_lines = sorted(seg.horizontal_lines)
        self._v_lines = sorted(seg.vertical_lines)
        self._groups = list(seg.groups)
        self._pending_group_cells = []
        self._overlay.update()

    def _update_segment_nav(self) -> None:
        """Refresh the segment navigator label and button enabled states."""
        total = len(self._segments)
        if total == 0:
            self._seg_label.setText("—")
            self._seg_prev_btn.setEnabled(False)
            self._seg_next_btn.setEnabled(False)
            return
        idx = self._segment_index_for_page(self.current_page_index())
        self._seg_label.setText(f"{idx + 1}/{total}")
        self._seg_prev_btn.setEnabled(idx > 0)
        self._seg_next_btn.setEnabled(idx < total - 1)

    def _on_nav_prev_segment(self) -> None:
        idx = self._segment_index_for_page(self.current_page_index())
        if idx > 0:
            self._go_to_page(self._segments[idx - 1].start_page)

    def _on_nav_next_segment(self) -> None:
        idx = self._segment_index_for_page(self.current_page_index())
        if idx < len(self._segments) - 1:
            self._go_to_page(self._segments[idx + 1].start_page)






