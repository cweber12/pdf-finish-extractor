"""Interactive pattern editor overlaid on a PDF viewer.

Modes
-----
idle       – hover; drag handles to resize/move image crop or text region;
             right-click to clear the pattern.
crop_image – crosshair; click-drag to define (or redefine) the image crop rectangle.
omit       – click-drag to mark a page area that should be skipped during detection.

All coordinates are stored in 150-DPI pixel space to match PyMuPDF extraction.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import (
    QInputDialog,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.extraction.grid import OmitRegion
from src.extraction.pattern import (
    ImageSampleDefinition,
    ImageTextPattern,
    ImageTextPatternProfile,
    RectPx,
    RelativeRect,
    TextSectionDefinition,
)
from src.ui.editor.grid_editor_interaction_flow import (
    mouse_button_name,
    wheel_zoom_factor,
)
from src.ui.editor.grid_editor_pages import (
    omit_all_pages,
    page_controls_state,
    toggle_omitted_page,
)
from src.ui.editor.pattern_editor_controls import (
    build_pattern_controls,
    build_pattern_empty_state,
)
from src.ui.editor.pattern_editor_state import PatternEditorState
from src.ui.editor.pattern_geometry import (
    apply_rect_resize,
    clamp_section_divider,
    normalize_rect,
    translate_rect,
)
from src.ui.editor.pattern_hit_test import resolve_pattern_hit
from src.ui.editor.pattern_interaction import (
    decide_move_action,
    decide_press_action,
    decide_release_action,
)
from src.ui.editor.pattern_overlay import _PatternOverlayWidget
from src.ui.editor.pdf_viewer import PDFViewer

_MIN_CROP_SIZE = 8  # minimum side length in 150-DPI pixels


class PatternEditor(QWidget):
    """PDF viewer with an interactive pattern crop and text-section overlay."""

    open_requested = pyqtSignal()
    apply_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Canonical pattern state
        self._state = PatternEditorState()

        # Omit state (issue #29: shared omit behaviour lives here)
        self._omitted_pages: set[int] = set()
        self._omit_regions: list[OmitRegion] = []

        # Interaction state
        self._mode: str = "idle"
        self._crop_start_orig: tuple[int, int] | None = None
        self._crop_preview_orig: tuple[int, int] | None = None
        # resize: stores the handle name ("image_corner_tl", "text_edge_r", ...)
        self._active_resize: str | None = None
        # drag: "image" | "text"
        self._active_drag: str | None = None
        self._drag_start_orig: tuple[int, int] | None = None
        self._drag_start_image: RectPx | None = None
        self._drag_start_text: RectPx | None = None
        # section divider drag
        self._active_divider: int | None = None
        # omit region drag
        self._omit_start_orig: tuple[int, int] | None = None
        self._omit_preview: tuple[int, int, int, int] | None = None
        # pan
        self._pan_last: QPoint | None = None
        # hover
        self._hovered_handle: str | None = None

        self.pdf_path: str | None = None

        self._viewer = PDFViewer()
        self._overlay = _PatternOverlayWidget(self)
        build_pattern_controls(self)
        self._build_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    @property
    def ctrl_bar(self) -> QWidget:
        return self._ctrl_bar

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(build_pattern_empty_state(self.open_requested.emit))
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
    # Public API  (issue #27 acceptance criteria)
    # ------------------------------------------------------------------

    def load_pdf(self, path: str) -> None:
        self.pdf_path = path
        self._viewer.open(path)
        self._zoom_label.setText("100%")
        self._stack.setCurrentIndex(1)
        self._state = PatternEditorState()
        self._omitted_pages = set()
        self._omit_regions = []
        self._reset_interaction()
        self._update_page_controls()
        self._reposition_overlay()

    def current_profile(self) -> ImageTextPatternProfile | None:
        """Return the current pattern as a saveable profile, or None if incomplete."""
        return _state_to_profile(self._state, self._omitted_pages, self._omit_regions)

    def apply_profile(self, profile: ImageTextPatternProfile) -> None:
        self._state = _profile_to_state(profile)
        self._omitted_pages = set(profile.omitted_pages)
        self._omit_regions = list(profile.omit_regions)
        self._reset_interaction()
        self._sync_toolbar_to_state()
        self._update_page_controls()
        self._overlay.update()

    def current_page_index(self) -> int:
        return self._viewer.page_index

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _d2o(self, x: int, y: int) -> tuple[int, int]:
        return self._viewer.display_to_original_coords(x, y)

    def _o2d(self, x: int, y: int) -> tuple[int, int]:
        return self._viewer.original_to_display_coords(x, y)

    def _clamped_orig(self, ox: int, oy: int) -> tuple[int, int]:
        pm = self._viewer.pixmap
        if pm is None:
            return ox, oy
        return max(0, min(ox, pm.width())), max(0, min(oy, pm.height()))

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------

    def _set_mode(self, mode: str, active_btn) -> None:
        import importlib
        from PyQt6.QtWidgets import QToolButton
        self._mode = mode if (hasattr(active_btn, "isChecked") and active_btn.isChecked()) else "idle"
        # Uncheck sibling mode buttons
        for attr in ("_btn_crop", "_btn_omit"):
            btn = getattr(self, attr, None)
            if btn is not None and btn is not active_btn:
                btn.setChecked(False)
        self._reset_interaction()
        self._update_cursor_for_mode()
        self._overlay.update()

    def _update_cursor_for_mode(self) -> None:
        if self._mode == "crop_image":
            self._overlay.setCursor(Qt.CursorShape.CrossCursor)
        elif self._mode == "omit":
            self._overlay.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self._overlay.setCursor(Qt.CursorShape.ArrowCursor)

    def _reset_interaction(self) -> None:
        self._crop_start_orig = None
        self._crop_preview_orig = None
        self._active_resize = None
        self._active_drag = None
        self._drag_start_orig = None
        self._drag_start_image = None
        self._drag_start_text = None
        self._active_divider = None
        self._omit_start_orig = None
        self._omit_preview = None
        self._pan_last = None
        self._hovered_handle = None

    # ------------------------------------------------------------------
    # Mouse event handlers
    # ------------------------------------------------------------------

    def _on_press(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        dx, dy = pos.x(), pos.y()
        button = mouse_button_name(
            event.button(),
            left_button=Qt.MouseButton.LeftButton,
            middle_button=Qt.MouseButton.MiddleButton,
            right_button=Qt.MouseButton.RightButton,
        )

        hit = resolve_pattern_hit(dx, dy, self._state, self._o2d)
        decision = decide_press_action(button, self._mode, hit.target)

        if decision.action == "right_click":
            self._on_right_click(dx, dy)
            return

        if decision.action == "begin_pan":
            self._pan_last = pos
            self._overlay.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        ox, oy = self._d2o(dx, dy)

        if decision.action == "begin_image_crop":
            self._crop_start_orig = self._clamped_orig(ox, oy)
            self._crop_preview_orig = self._crop_start_orig
            self._overlay.update()
            return

        if decision.action == "begin_omit":
            p = self._clamped_orig(ox, oy)
            self._omit_start_orig = p
            self._omit_preview = (p[0], p[1], p[0], p[1])
            self._overlay.update()
            return

        if decision.action == "begin_resize_image":
            self._active_resize = hit.target
            self._overlay.update()
            return

        if decision.action == "begin_resize_text_region":
            self._active_resize = hit.target
            self._overlay.update()
            return

        if decision.action == "begin_drag_image":
            self._active_drag = "image"
            self._drag_start_orig = (ox, oy)
            self._drag_start_image = self._state.image_rect_px
            self._drag_start_text = self._state.text_region_rect_px
            self._overlay.update()
            return

        if decision.action == "begin_drag_text_region":
            self._active_drag = "text"
            self._drag_start_orig = (ox, oy)
            self._drag_start_text = self._state.text_region_rect_px
            self._overlay.update()
            return

        if decision.action == "begin_drag_section_divider":
            # Extract divider index from target name e.g. "section_divider_2"
            try:
                self._active_divider = int(hit.target.split("_")[-1])
            except ValueError:
                self._active_divider = None
            self._overlay.update()
            return

    def _on_move(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        dx, dy = pos.x(), pos.y()

        decision = decide_move_action(
            has_pan_anchor=self._pan_last is not None,
            active_resize=self._active_resize,
            active_drag=self._active_drag,
            active_section_divider=self._active_divider,
            is_cropping=self._crop_start_orig is not None,
            has_omit_start=self._omit_start_orig is not None,
        )

        if decision.action == "pan":
            ddx = dx - self._pan_last.x()
            ddy = dy - self._pan_last.y()
            self._viewer.pan_by(ddx, ddy)
            self._pan_last = pos
            self._overlay.update()
            return

        ox, oy = self._d2o(dx, dy)

        if decision.action == "omit_drag":
            p = self._clamped_orig(ox, oy)
            s = self._omit_start_orig
            self._omit_preview = (s[0], s[1], p[0], p[1])
            self._overlay.update()
            return

        if decision.action == "crop_preview":
            self._crop_preview_orig = self._clamped_orig(ox, oy)
            self._overlay.update()
            return

        if decision.action in ("resize_image", "resize_text"):
            handle = self._active_resize
            if handle is None:
                return
            suffix = handle.split("_")[-1]   # e.g. "tl", "r", "b"
            if decision.action == "resize_image" and self._state.image_rect_px is not None:
                new_rect = apply_rect_resize(self._state.image_rect_px, suffix, ox, oy)
                self._state = PatternEditorState(
                    image_rect_px=new_rect,
                    text_side=self._state.text_side,
                    segmentation=self._state.segmentation,
                    section_count=self._state.section_count,
                    text_region_rect_px=self._state.text_region_rect_px,
                    text_section_rects_px=list(self._state.text_section_rects_px),
                    field_names=list(self._state.field_names),
                )
            elif decision.action == "resize_text" and self._state.text_region_rect_px is not None:
                new_rect = apply_rect_resize(self._state.text_region_rect_px, suffix, ox, oy)
                self._state = self._state.with_text_region_rect(new_rect)
            self._overlay.update()
            return

        if decision.action == "drag_image":
            if self._drag_start_orig is None or self._drag_start_image is None:
                return
            ddx = ox - self._drag_start_orig[0]
            ddy = oy - self._drag_start_orig[1]
            new_image = translate_rect(self._drag_start_image, ddx, ddy)
            new_text = (
                translate_rect(self._drag_start_text, ddx, ddy)
                if self._drag_start_text is not None
                else None
            )
            # Rebuild state preserving text region as-is (no auto-compute)
            self._state = PatternEditorState(
                image_rect_px=new_image,
                text_side=self._state.text_side,
                segmentation=self._state.segmentation,
                section_count=self._state.section_count,
                text_region_rect_px=new_text,
                text_section_rects_px=(
                    self._state.with_text_region_rect(new_text).text_section_rects_px
                    if new_text is not None
                    else []
                ),
                field_names=list(self._state.field_names),
            )
            self._overlay.update()
            return

        if decision.action == "drag_text":
            if self._drag_start_orig is None or self._drag_start_text is None:
                return
            ddx = ox - self._drag_start_orig[0]
            ddy = oy - self._drag_start_orig[1]
            new_text = translate_rect(self._drag_start_text, ddx, ddy)
            self._state = self._state.with_text_region_rect(new_text)
            self._overlay.update()
            return

        if decision.action == "drag_section_divider":
            if self._active_divider is None:
                return
            new_sections = clamp_section_divider(
                self._state.text_section_rects_px,
                self._active_divider,
                oy if self._state.segmentation == "rows" else ox,
                self._state.segmentation,
            )
            self._state = self._state.with_section_rects(new_sections)
            self._overlay.update()
            return

        # Hover — update cursor and hovered handle
        hit = resolve_pattern_hit(dx, dy, self._state, self._o2d)
        self._hovered_handle = hit.target if hit.target else None
        cursor_map = {
            "arrow": Qt.CursorShape.ArrowCursor,
            "move": Qt.CursorShape.SizeAllCursor,
            "size_h": Qt.CursorShape.SizeHorCursor,
            "size_v": Qt.CursorShape.SizeVerCursor,
            "size_fdiag": Qt.CursorShape.SizeFDiagCursor,
            "size_bdiag": Qt.CursorShape.SizeBDiagCursor,
        }
        if self._mode == "idle":
            self._overlay.setCursor(cursor_map.get(hit.cursor, Qt.CursorShape.ArrowCursor))
        self._overlay.update()

    def _on_release(self, event: QMouseEvent) -> None:
        button = mouse_button_name(
            event.button(),
            left_button=Qt.MouseButton.LeftButton,
            middle_button=Qt.MouseButton.MiddleButton,
            right_button=Qt.MouseButton.RightButton,
        )

        decision = decide_release_action(
            mouse_button=button,
            has_pan_anchor=self._pan_last is not None,
            active_resize=self._active_resize,
            active_drag=self._active_drag,
            active_section_divider=self._active_divider,
            is_cropping=self._crop_start_orig is not None,
            has_omit_start=self._omit_start_orig is not None,
        )

        if decision.action == "end_pan":
            self._pan_last = None
            self._update_cursor_for_mode()
            return

        pos = event.position().toPoint()
        ox, oy = self._d2o(pos.x(), pos.y())

        if decision.action == "finalize_image_crop":
            if self._crop_start_orig is not None:
                ex, ey = self._clamped_orig(ox, oy)
                sx, sy = self._crop_start_orig
                if abs(ex - sx) >= _MIN_CROP_SIZE and abs(ey - sy) >= _MIN_CROP_SIZE:
                    new_rect = normalize_rect(sx, sy, ex, ey)
                    # Fresh crop always resets text region
                    self._state = PatternEditorState(
                        image_rect_px=new_rect,
                        text_side=self._state.text_side,
                        segmentation=self._state.segmentation,
                        section_count=self._state.section_count,
                        field_names=list(self._state.field_names),
                    ).with_image_rect(new_rect, auto_text=True)
            self._crop_start_orig = None
            self._crop_preview_orig = None
            self._overlay.update()
            return

        if decision.action == "finalize_omit":
            if self._omit_preview is not None:
                x0, y0, x1, y1 = self._omit_preview
                lx0, ly0, lx1, ly1 = min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
                if (lx1 - lx0) >= _MIN_CROP_SIZE and (ly1 - ly0) >= _MIN_CROP_SIZE:
                    self._omit_regions.append(
                        OmitRegion(
                            page_index=self.current_page_index(),
                            rect=(lx0, ly0, lx1, ly1),
                        )
                    )
            self._omit_start_orig = None
            self._omit_preview = None
            self._overlay.update()
            return

        if decision.action in ("finalize_resize", "finalize_drag", "finalize_section_divider"):
            self._active_resize = None
            self._active_drag = None
            self._drag_start_orig = None
            self._drag_start_image = None
            self._drag_start_text = None
            self._active_divider = None
            self._overlay.update()
            return

    def _on_wheel(self, event: QWheelEvent) -> None:
        # Cancel any in-progress crop or omit drag on zoom
        if self._crop_start_orig is not None or self._omit_start_orig is not None:
            self._crop_start_orig = None
            self._crop_preview_orig = None
            self._omit_start_orig = None
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
        # Remove omit region under cursor if in omit mode
        if self._mode == "omit":
            for i, region in enumerate(self._omit_regions):
                if region.page_index != self.current_page_index():
                    continue
                x0, y0, x1, y1 = region.rect
                lx0, ly0 = min(x0, x1), min(y0, y1)
                lx1, ly1 = max(x0, x1), max(y0, y1)
                if lx0 <= ox <= lx1 and ly0 <= oy <= ly1:
                    del self._omit_regions[i]
                    self._overlay.update()
                    return

    # ------------------------------------------------------------------
    # Pattern management
    # ------------------------------------------------------------------

    def _clear_pattern(self) -> None:
        self._state = PatternEditorState(
            text_side=self._state.text_side,
            segmentation=self._state.segmentation,
            section_count=self._state.section_count,
            field_names=list(self._state.field_names),
        )
        self._omitted_pages = set()
        self._omit_regions = []
        self._reset_interaction()
        self._update_page_controls()
        self._overlay.update()

    # ------------------------------------------------------------------
    # Page / omit management  (issue #29)
    # ------------------------------------------------------------------

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
        self._reset_interaction()
        self._update_page_controls()
        self._reposition_overlay()

    def _toggle_current_page_omitted(self) -> None:
        result = toggle_omitted_page(self._omitted_pages, self.current_page_index())
        self._omitted_pages = result.omitted_pages
        self._update_page_controls()
        self._overlay.update()

    def _omit_all_pages(self) -> None:
        result = omit_all_pages(self._viewer.page_count)
        if result is None:
            return
        self._omitted_pages, _ = result
        self._update_page_controls()
        self._overlay.update()

    # ------------------------------------------------------------------
    # Toolbar callbacks  (issue #13 / #28)
    # ------------------------------------------------------------------

    def _on_text_side_changed(self, side: str) -> None:
        new_state, needs_confirm = self._state.with_text_side(side)
        if needs_confirm and self._state.text_region_rect_px is not None:
            reply = QMessageBox.question(
                self,
                "Change text side",
                "Changing the text side will clear the current text region. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            new_state = new_state.with_text_region_cleared()
            if new_state.image_rect_px is not None:
                new_state = new_state.with_image_rect(new_state.image_rect_px, auto_text=True)
        self._state = new_state
        side_labels = {"below": "Below ▾", "above": "Above ▾", "right": "Right ▾", "left": "Left ▾"}
        self._text_side_btn.setText(side_labels.get(side, side.capitalize() + " ▾"))
        self._overlay.update()

    def _on_section_count_changed(self, count: int) -> None:
        self._state = self._state.with_section_count(count)
        self._overlay.update()

    def _on_segmentation_changed(self, seg: str) -> None:
        self._state = self._state.with_segmentation(seg)
        self._btn_rows.setChecked(seg == "rows")
        self._btn_cols.setChecked(seg == "columns")
        self._overlay.update()

    def _on_edit_field_names(self) -> None:
        count = self._state.section_count
        names = list(self._state.field_names)
        # Pad to current count
        while len(names) < count:
            names.append(f"text_{len(names) + 1}")
        names = names[:count]

        current_text = ", ".join(names)
        new_text, ok = QInputDialog.getText(
            self,
            "Edit field names",
            f"Enter {count} comma-separated field name(s):",
            text=current_text,
        )
        if not ok:
            return

        parts = [p.strip() for p in new_text.split(",")]
        # Pad or truncate
        while len(parts) < count:
            parts.append(f"text_{len(parts) + 1}")
        parts = parts[:count]

        # Dedup: if any name appears more than once, append a numeric suffix
        seen: dict[str, int] = {}
        deduped: list[str] = []
        for name in parts:
            if name in seen:
                seen[name] += 1
                deduped.append(f"{name}_{seen[name]}")
            else:
                seen[name] = 1
                deduped.append(name)

        self._state = self._state.with_field_names(deduped)
        self._overlay.update()

    def _sync_toolbar_to_state(self) -> None:
        """Push current state values into toolbar widgets after apply_profile."""
        side_labels = {"below": "Below ▾", "above": "Above ▾", "right": "Right ▾", "left": "Left ▾"}
        self._text_side_btn.setText(
            side_labels.get(self._state.text_side, self._state.text_side.capitalize() + " ▾")
        )
        self._sections_spin.blockSignals(True)
        self._sections_spin.setValue(self._state.section_count)
        self._sections_spin.blockSignals(False)
        self._btn_rows.setChecked(self._state.segmentation == "rows")
        self._btn_cols.setChecked(self._state.segmentation == "columns")


# ------------------------------------------------------------------
# Profile conversion helpers
# ------------------------------------------------------------------

def _state_to_profile(
    state: PatternEditorState,
    omitted_pages: set[int],
    omit_regions: list[OmitRegion],
) -> ImageTextPatternProfile | None:
    if not state.is_complete or state.image_rect_px is None:
        return None

    ir = state.image_rect_px
    iw = ir.x1 - ir.x0
    ih = ir.y1 - ir.y0
    if iw <= 0 or ih <= 0:
        return None

    sample = ImageSampleDefinition(
        rect=ir,
        width_px=iw,
        height_px=ih,
        aspect_ratio=iw / ih,
    )

    text_sections: list[TextSectionDefinition] = []
    for i, sect in enumerate(state.text_section_rects_px):
        rel = RelativeRect(
            rx0=(sect.x0 - ir.x0) / iw,
            ry0=(sect.y0 - ir.y0) / ih,
            rx1=(sect.x1 - ir.x0) / iw,
            ry1=(sect.y1 - ir.y0) / ih,
        )
        name = state.field_names[i] if i < len(state.field_names) else f"text_{i + 1}"
        text_sections.append(TextSectionDefinition(name=name, index=i, relative_rect=rel))

    pattern = ImageTextPattern(
        sample=sample,
        text_side=state.text_side,
        segmentation=state.segmentation,
        text_sections=text_sections,
        image_field_name="swatch",
    )
    return ImageTextPatternProfile(
        pattern=pattern,
        omitted_pages=sorted(omitted_pages),
        omit_regions=list(omit_regions),
    )


def _profile_to_state(profile: ImageTextPatternProfile) -> PatternEditorState:
    ir = profile.pattern.sample.rect
    iw = ir.x1 - ir.x0
    ih = ir.y1 - ir.y0

    sections_px: list[RectPx] = []
    for sect in profile.pattern.text_sections:
        rel = sect.relative_rect
        sections_px.append(RectPx(
            x0=ir.x0 + round(rel.rx0 * iw),
            y0=ir.y0 + round(rel.ry0 * ih),
            x1=ir.x0 + round(rel.rx1 * iw),
            y1=ir.y0 + round(rel.ry1 * ih),
        ))

    text_region = None
    if sections_px:
        text_region = RectPx(
            x0=min(s.x0 for s in sections_px),
            y0=min(s.y0 for s in sections_px),
            x1=max(s.x1 for s in sections_px),
            y1=max(s.y1 for s in sections_px),
        )

    return PatternEditorState(
        image_rect_px=ir,
        text_side=profile.pattern.text_side,
        segmentation=profile.pattern.segmentation,
        section_count=len(sections_px),
        text_region_rect_px=text_region,
        text_section_rects_px=sections_px,
        field_names=[s.name for s in profile.pattern.text_sections],
    )
