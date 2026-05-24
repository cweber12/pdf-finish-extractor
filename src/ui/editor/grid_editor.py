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
    QPoint,
    QRect,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QMouseEvent,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QStackedWidget,
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
)
from src.ui.editor.grid_editor_controls import build_controls, build_empty_state
from src.ui.editor.grid_editor_fields import confirm_field_recipe_change, prompt_field_recipe
from src.ui.editor.grid_editor_grouping import apply_group_click
from src.ui.editor.grid_editor_geometry import (
    cell_at_orig_point,
    clamped_orig_point,
    grid_orig_boundaries,
    omit_region_index_at_orig_point,
)
from src.ui.editor.grid_editor_hit_test import resolve_line_hit
from src.ui.editor.grid_editor_interaction_flow import (
    begin_omit_preview,
    hovered_line_from_hit,
    mouse_button_name,
    placing_preview_value,
    should_reset_zoom_interaction,
    wheel_zoom_factor,
)
from src.ui.editor.grid_editor_interaction import (
    decide_move_action,
    decide_press_action,
    decide_release_action,
)
from src.ui.editor.grid_editor_lifecycle import (
    applied_profile_state,
    baseline_segments,
    cleared_grid_collections,
    interaction_reset_state,
    profile_from_editor_state,
)
from src.ui.editor.grid_editor_line_edit import apply_line_placement, bounded_line_value, can_place_line
from src.ui.editor.grid_editor_modes import mode_hint, mode_uses_crosshair, resolved_mode
from src.ui.editor.grid_editor_omit import decide_omit_move, decide_omit_release
from src.ui.editor.grid_editor_overlay import _OverlayWidget
from src.ui.editor.grid_editor_pages import (
    omit_all_pages,
    page_controls_state,
    toggle_omitted_page,
    viewing_page_hint,
)
from src.ui.editor.grid_editor_right_click import decide_right_click
from src.ui.editor.grid_editor_segments import (
    adjacent_segment_start_page,
    layout_state_for_page,
    record_segment_change,
    segment_index_for_page,
    segment_nav_state,
)
from src.ui.editor.grid_editor_widgets import GlowIconButton
from src.ui.editor.pdf_viewer import PDFViewer

_LINE_HIT_DIST = 5
_MIN_LINE_GAP_ORIG = 3

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
        build_controls(self)
        self._build_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    @property
    def ctrl_bar(self) -> QWidget:
        """The toolbar widget; owned by GridEditor but placed by the parent layout."""
        return self._ctrl_bar

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(build_empty_state(self.open_requested.emit))
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
        self._segments = baseline_segments(self._h_lines, self._v_lines, self._groups)
        self._update_page_controls()
        self._update_segment_nav()
        self._reposition_overlay()

    def current_profile(self) -> Grid | None:
        return profile_from_editor_state(
            horizontal_lines=self._h_lines,
            vertical_lines=self._v_lines,
            fields=self._fields,
            groups=self._groups,
            omitted_pages=self._omitted_pages,
            omit_regions=self._omit_regions,
        )

    def current_segments(self) -> list[GridSegment]:
        """Return the per-page layout history for the current session."""
        return list(self._segments)

    def apply_profile(self, grid: Grid) -> None:
        state = applied_profile_state(grid)
        self._h_lines = state.horizontal_lines
        self._v_lines = state.vertical_lines
        self._fields = state.fields
        self._groups = state.groups
        self._omitted_pages = state.omitted_pages
        self._omit_regions = state.omit_regions
        reset = interaction_reset_state()
        self._pending_group_cells = reset.pending_group_cells
        self._hovered_cell = reset.hovered_cell
        self._hovered_line = reset.hovered_line
        self._omit_start = reset.omit_start
        self._omit_preview = reset.omit_preview
        # Treat the applied profile as the baseline layout for all pages.
        self._segments = baseline_segments(self._h_lines, self._v_lines, self._groups)
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
        state = page_controls_state(
            page_count=self._viewer.page_count,
            page_index=self.current_page_index(),
            omitted_pages=self._omitted_pages,
        )
        self._prev_page_btn.setEnabled(state.prev_enabled)
        self._next_page_btn.setEnabled(state.next_enabled)
        self._omit_page_btn.setEnabled(state.omit_enabled)
        self._page_label.setText(state.page_label)
        self._omit_page_btn.setChecked(state.omit_checked)

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
        self._set_hint(viewing_page_hint(index))
        self._reposition_overlay()

    def _toggle_current_page_omitted(self) -> None:
        decision = toggle_omitted_page(self._omitted_pages, self.current_page_index())
        self._omitted_pages = decision.omitted_pages
        self._set_hint(decision.hint)
        self._update_page_controls()
        self._overlay.update()

    def _omit_all_pages(self) -> None:
        decision = omit_all_pages(self._viewer.page_count)
        if decision is None:
            return
        omitted_pages, hint = decision
        self._omitted_pages = omitted_pages
        self._update_page_controls()
        self._overlay.update()
        self._set_hint(hint)

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
        h_orig, v_orig = grid_orig_boundaries(
            self._h_lines,
            self._v_lines,
            page_height=orig.height(),
            page_width=orig.width(),
        )
        h_d = [self._o2d(0, y)[1] for y in h_orig]
        v_d = [self._o2d(x, 0)[0] for x in v_orig]
        return h_d, v_d

    def _cell_at_orig(self, ox: int, oy: int) -> tuple[int, int] | None:
        orig = self._viewer.pixmap
        if orig is None:
            return None
        return cell_at_orig_point(
            ox,
            oy,
            page_height=orig.height(),
            page_width=orig.width(),
            horizontal_lines=self._h_lines,
            vertical_lines=self._v_lines,
        )

    def _omit_region_at_orig(self, ox: int, oy: int) -> int | None:
        return omit_region_index_at_orig_point(
            ox,
            oy,
            regions=self._omit_regions,
            page_index=self.current_page_index(),
        )

    def _clamped_orig_point(self, ox: int, oy: int) -> tuple[int, int]:
        orig = self._viewer.pixmap
        return clamped_orig_point(
            ox,
            oy,
            page_height=None if orig is None else orig.height(),
            page_width=None if orig is None else orig.width(),
        )

    def _line_hit(self, dx: int, dy: int) -> tuple[int | None, int | None]:
        """Return (h_index, None) or (None, v_index) if near a line/handle."""
        h_d, v_d = self._grid_display_boundaries()
        return resolve_line_hit(
            dx=dx,
            dy=dy,
            h_d=h_d,
            v_d=v_d,
            line_hit_dist=_LINE_HIT_DIST,
        )

    def _bounded_line_value(self, dtype: str, idx: int, value: int) -> int:
        """Clamp a dragged line so it cannot cross adjacent boundaries."""
        orig = self._viewer.pixmap
        lines = self._h_lines if dtype == "h" else self._v_lines
        max_value = None if orig is None else (orig.height() if dtype == "h" else orig.width())
        return bounded_line_value(
            line_kind=dtype,
            lines=lines,
            max_value=max_value,
            index=idx,
            value=value,
            min_gap=_MIN_LINE_GAP_ORIG,
        )

    def _can_place_line(self, dtype: str, value: int) -> bool:
        """Prevent duplicate/stacked lines that create ambiguous drag handles."""
        orig = self._viewer.pixmap
        lines = self._h_lines if dtype == "h" else self._v_lines
        max_value = None if orig is None else (orig.height() if dtype == "h" else orig.width())
        return can_place_line(
            line_kind=dtype,
            lines=lines,
            max_value=max_value,
            value=value,
            min_gap=_MIN_LINE_GAP_ORIG,
        )

    # ------------------------------------------------------------------
    # Mode / cursor management
    # ------------------------------------------------------------------

    def _set_mode(self, mode: str, active_btn: QToolButton) -> None:
        self._mode = resolved_mode(mode, is_checked=active_btn.isChecked())
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
        self._set_hint(mode_hint(self._mode))

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
        if mode_uses_crosshair(self._mode):
            self._overlay.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self._overlay.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------------
    # Mouse event handlers
    # ------------------------------------------------------------------

    def _on_press(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        dx, dy = pos.x(), pos.y()
        button_name = mouse_button_name(
            event.button(),
            left_button=Qt.MouseButton.LeftButton,
            middle_button=Qt.MouseButton.MiddleButton,
            right_button=Qt.MouseButton.RightButton,
        )

        hit_h, hit_v = self._line_hit(dx, dy)
        press_decision = decide_press_action(
            mouse_button=button_name,
            mode=self._mode,
            hit_h_index=hit_h,
            hit_v_index=hit_v,
        )

        if press_decision.action == "right_click":
            self._on_right_click(dx, dy)
            return

        if press_decision.action == "begin_pan":
            self._pan_last = pos
            self._overlay.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if press_decision.action == "begin_drag_h":
            if hit_h is None:
                return
            self._dragging = ("h", hit_h)
            self._set_hint("Dragging row boundary. Release to set position.")
            self._overlay.update()
            return
        if press_decision.action == "begin_drag_v":
            if hit_v is None:
                return
            self._dragging = ("v", hit_v)
            self._set_hint("Dragging column boundary. Release to set position.")
            self._overlay.update()
            return

        ox, oy = self._d2o(dx, dy)
        if press_decision.action == "begin_place_h":
            self._placing = True
            self._preview = placing_preview_value("add_h", ox, oy)
            self._overlay.update()
        elif press_decision.action == "begin_place_v":
            self._placing = True
            self._preview = placing_preview_value("add_v", ox, oy)
            self._overlay.update()
        elif press_decision.action == "group_click":
            self._on_group_click(ox, oy)
        elif press_decision.action == "begin_omit":
            self._omit_start, self._omit_preview = begin_omit_preview(
                self._clamped_orig_point(ox, oy)
            )
            self._set_hint("Dragging ignored area. Release to save it for this page.")
            self._overlay.update()

    def _on_move(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        dx, dy = pos.x(), pos.y()
        decision = decide_move_action(
            has_pan_anchor=self._pan_last is not None,
            has_dragging=self._dragging is not None,
            has_omit_drag=self._omit_start is not None and self._mode == "omit",
            is_placing=self._placing,
        )

        if decision.action == "pan":
            ddx = dx - self._pan_last.x()
            ddy = dy - self._pan_last.y()
            self._viewer.pan_by(ddx, ddy)
            self._pan_last = pos
            self._overlay.update()
            return

        ox, oy = self._d2o(dx, dy)

        if decision.action == "drag_line":
            dtype, idx = self._dragging
            if dtype == "h":
                self._h_lines[idx] = self._bounded_line_value("h", idx, oy)
            else:
                self._v_lines[idx] = self._bounded_line_value("v", idx, ox)
            self._overlay.update()
            return

        if decision.action == "omit_drag":
            decision = decide_omit_move(
                mode=self._mode,
                omit_start=self._omit_start,
                clamped_point=self._clamped_orig_point(ox, oy),
                omit_region_index_at_point=None,
            )
            if decision.preview_rect is not None:
                self._omit_preview = decision.preview_rect
            self._overlay.update()
            return

        if decision.action == "placing_preview":
            self._preview = placing_preview_value(self._mode, ox, oy)
            self._overlay.update()
            return

        hit_h, hit_v = self._line_hit(dx, dy)
        self._hovered_line = hovered_line_from_hit(hit_h, hit_v)
        self._update_cursor(dx, dy)

        if self._mode == "omit":
            decision = decide_omit_move(
                mode=self._mode,
                omit_start=None,
                clamped_point=self._clamped_orig_point(ox, oy),
                omit_region_index_at_point=self._omit_region_at_orig(ox, oy),
            )
            if decision.remove_region_index is not None:
                del self._omit_regions[decision.remove_region_index]
                if decision.hint is not None:
                    self._set_hint(decision.hint)
                self._overlay.update()
            return

        if self._mode == "grouping":
            self._hovered_cell = self._cell_at_orig(ox, oy)
        else:
            self._hovered_cell = None
        self._overlay.update()

    def _on_release(self, event: QMouseEvent) -> None:
        button_name = mouse_button_name(
            event.button(),
            left_button=Qt.MouseButton.LeftButton,
            middle_button=Qt.MouseButton.MiddleButton,
            right_button=Qt.MouseButton.RightButton,
        )

        release_decision = decide_release_action(
            mouse_button=button_name,
            mode=self._mode,
            has_omit_start=self._omit_start is not None,
            has_dragging=self._dragging is not None,
            is_placing=self._placing,
        )

        if release_decision.action == "end_pan":
            self._pan_last = None
            self._update_cursor(None, None)
            return

        if release_decision.action == "ignore":
            return

        if release_decision.action == "omit_release":
            decision = decide_omit_release(
                mode=self._mode,
                omit_start=self._omit_start,
                clamped_release_point=self._clamped_orig_point(
                    *self._d2o(
                        event.position().toPoint().x(),
                        event.position().toPoint().y(),
                    )
                ),
            )
            if decision.normalized_rect is not None:
                self._omit_regions.append(
                    OmitRegion(page_index=self.current_page_index(), rect=decision.normalized_rect)
                )
            if decision.hint is not None:
                self._set_hint(decision.hint)
            if decision.clear_start:
                self._omit_start = None
            if decision.clear_preview:
                self._omit_preview = None
            self._overlay.update()
            return

        if release_decision.action == "finalize_drag":
            self._h_lines.sort()
            self._v_lines.sort()
            self._dragging = None
            self._set_hint("Line moved. Right-click any line to delete it.")
            self._overlay.update()
            self._record_segment_change()
            return

        if release_decision.action == "finalize_placing":
            orig = self._viewer.pixmap
            max_height = None if orig is None else orig.height()
            max_width = None if orig is None else orig.width()
            if self._mode == "add_h":
                decision = apply_line_placement(
                    line_kind="h",
                    lines=self._h_lines,
                    max_value=max_height,
                    preview_value=self._preview,
                    min_gap=_MIN_LINE_GAP_ORIG,
                )
                self._h_lines = decision.lines
                if decision.clear_groups_for_grid_change:
                    self._clear_groups_for_grid_change()
                if decision.hint:
                    self._set_hint(decision.hint)
            elif self._mode == "add_v":
                decision = apply_line_placement(
                    line_kind="v",
                    lines=self._v_lines,
                    max_value=max_width,
                    preview_value=self._preview,
                    min_gap=_MIN_LINE_GAP_ORIG,
                )
                self._v_lines = decision.lines
                if decision.clear_groups_for_grid_change:
                    self._clear_groups_for_grid_change()
                if decision.hint:
                    self._set_hint(decision.hint)
            self._placing = False
            self._preview = None
            self._overlay.update()
            self._record_segment_change()

    def _on_wheel(self, event: QWheelEvent) -> None:
        """Zoom on mouse wheel. Cancels any in-progress placement first."""
        if should_reset_zoom_interaction(
            is_placing=self._placing,
            has_omit_start=self._omit_start is not None,
        ):
            self._placing = False
            self._preview = None
            self._omit_start = None
            self._omit_preview = None

        factor = wheel_zoom_factor(event.angleDelta().y())
        if factor is None:
            event.accept()
            return

        new_zoom = self._viewer.zoom_level * factor
        pos = event.position().toPoint()
        self._viewer.zoom_at(pos.x(), pos.y(), new_zoom)
        self._zoom_label.setText(f"{round(self._viewer.zoom_level * 100)}%")
        self._overlay.update()
        event.accept()

    def _on_right_click(self, dx: int, dy: int) -> None:
        ox, oy = self._d2o(dx, dy)
        cell = self._cell_at_orig(ox, oy)
        hit_h, hit_v = self._line_hit(dx, dy)
        decision = decide_right_click(
            mode=self._mode,
            omit_region_index=self._omit_region_at_orig(ox, oy) if self._mode == "omit" else None,
            pending_group_cells=self._pending_group_cells,
            clicked_cell=cell,
            hit_h_index=hit_h,
            hit_v_index=hit_v,
        )
        if not decision.consumed:
            return

        if decision.omit_region_index_to_remove is not None:
            del self._omit_regions[decision.omit_region_index_to_remove]
            if decision.hint is not None:
                self._set_hint(decision.hint)
            self._overlay.update()
            return

        if decision.clear_pending_group_selection:
            self._pending_group_cells = []
            if decision.hint is not None:
                self._set_hint(decision.hint)
            self._overlay.update()
            return

        if decision.remove_groups_containing_cell is not None:
            before = len(self._groups)
            self._groups = [
                group
                for group in self._groups
                if decision.remove_groups_containing_cell not in group.cells()
            ]
            if len(self._groups) != before:
                self._set_hint("Group removed.")
                self._record_segment_change()
            self._overlay.update()
            return

        if decision.remove_h_line_index is not None:
            del self._h_lines[decision.remove_h_line_index]
        elif decision.remove_v_line_index is not None:
            del self._v_lines[decision.remove_v_line_index]
        else:
            return

        if decision.clear_groups_for_grid_change:
            self._clear_groups_for_grid_change()
        if decision.hint is not None:
            self._set_hint(decision.hint)
        self._overlay.update()
        if decision.record_segment_change:
            self._record_segment_change()

    def _on_group_click(self, ox: int, oy: int) -> None:
        cell = self._cell_at_orig(ox, oy)
        if cell is None:
            return
        decision = apply_group_click(
            fields=self._fields,
            pending_cells=self._pending_group_cells,
            clicked_cell=cell,
        )
        self._pending_group_cells = decision.pending_cells
        if decision.created_group is not None:
            self._groups.append(decision.created_group)
        if decision.hint is not None:
            self._set_hint(decision.hint)
        if decision.record_segment_change:
            self._record_segment_change()
        self._overlay.update()

    # ------------------------------------------------------------------
    # Grid management
    # ------------------------------------------------------------------

    def _edit_fields(self) -> None:
        if not confirm_field_recipe_change(self, has_groups=bool(self._groups)):
            return
        fields = prompt_field_recipe(self, list(self._fields))
        if fields is None:
            return
        if not fields:
            self._set_hint("Keep at least one field in the recipe.")
            return
        self._fields = fields
        self._groups.clear()
        self._pending_group_cells = []
        self._record_segment_change()
        self._overlay.update()

    def _clear_groups_for_grid_change(self) -> None:
        self._groups.clear()
        self._pending_group_cells = []

    def _clear_grid(self) -> None:
        (
            self._h_lines,
            self._v_lines,
            self._groups,
            self._omitted_pages,
            self._omit_regions,
        ) = cleared_grid_collections()
        reset = interaction_reset_state()
        self._pending_group_cells = reset.pending_group_cells
        self._hovered_cell = reset.hovered_cell
        self._hovered_line = reset.hovered_line
        self._omit_start = reset.omit_start
        self._omit_preview = reset.omit_preview
        self._segments = baseline_segments(self._h_lines, self._v_lines, self._groups)
        self._update_page_controls()
        self._update_segment_nav()
        self._set_hint("Grid and omissions cleared. Add row and column boundaries to start again.")
        self._overlay.update()

    # ------------------------------------------------------------------
    # Layout segment management
    # ------------------------------------------------------------------

    def _segment_index_for_page(self, page_index: int) -> int:
        return segment_index_for_page(self._segments, page_index)

    def _record_segment_change(self) -> None:
        """Snapshot the current grid state into _segments for the active page."""
        self._segments = record_segment_change(
            segments=self._segments,
            page_index=self.current_page_index(),
            horizontal_lines=self._h_lines,
            vertical_lines=self._v_lines,
            groups=self._groups,
        )
        self._update_segment_nav()

    def _load_segment_for_page(self, page_index: int) -> None:
        """Load the layout applicable to ``page_index`` into the editor state."""
        state = layout_state_for_page(self._segments, page_index)
        if state is None:
            return
        self._h_lines = state.horizontal_lines
        self._v_lines = state.vertical_lines
        self._groups = state.groups
        self._pending_group_cells = []
        self._overlay.update()

    def _update_segment_nav(self) -> None:
        """Refresh the segment navigator label and button enabled states."""
        nav = segment_nav_state(self._segments, self.current_page_index())
        self._seg_label.setText(nav.label)
        self._seg_prev_btn.setEnabled(nav.prev_enabled)
        self._seg_next_btn.setEnabled(nav.next_enabled)

    def _on_nav_prev_segment(self) -> None:
        target = adjacent_segment_start_page(self._segments, self.current_page_index(), "prev")
        if target is not None:
            self._go_to_page(target)

    def _on_nav_next_segment(self) -> None:
        target = adjacent_segment_start_page(self._segments, self.current_page_index(), "next")
        if target is not None:
            self._go_to_page(target)







