from __future__ import annotations

from dataclasses import dataclass, field

from src.extraction.pattern import PatternSide, RectPx, TextSegmentation


def _default_field_names(count: int) -> list[str]:
    return [f"text_{i + 1}" for i in range(count)]


def _pad_field_names(names: list[str], count: int) -> list[str]:
    if len(names) >= count:
        return names[:count]
    result = list(names)
    for i in range(len(names), count):
        result.append(f"text_{i + 1}")
    return result


def _generate_section_rects(
    text_region: RectPx, section_count: int, segmentation: TextSegmentation
) -> list[RectPx]:
    if section_count <= 0:
        return []
    if segmentation == "rows":
        height = text_region.y1 - text_region.y0
        step = height / section_count
        return [
            RectPx(
                x0=text_region.x0,
                y0=text_region.y0 + round(i * step),
                x1=text_region.x1,
                y1=text_region.y0 + round((i + 1) * step),
            )
            for i in range(section_count)
        ]
    else:
        width = text_region.x1 - text_region.x0
        step = width / section_count
        return [
            RectPx(
                x0=text_region.x0 + round(i * step),
                y0=text_region.y0,
                x1=text_region.x0 + round((i + 1) * step),
                y1=text_region.y1,
            )
            for i in range(section_count)
        ]


@dataclass
class PatternEditorState:
    image_rect_px: RectPx | None = None
    text_side: PatternSide = "below"
    segmentation: TextSegmentation = "rows"
    section_count: int = 1
    text_region_rect_px: RectPx | None = None
    text_section_rects_px: list[RectPx] = field(default_factory=list)
    field_names: list[str] = field(default_factory=lambda: ["text_1"])
    selected_handle: str | None = None
    selected_section_index: int | None = None

    @property
    def is_complete(self) -> bool:
        return (
            self.image_rect_px is not None
            and self.text_region_rect_px is not None
            and len(self.text_section_rects_px) == self.section_count
        )

    @property
    def text_region_is_customized(self) -> bool:
        return self.text_region_rect_px is not None

    def with_section_count(self, count: int) -> PatternEditorState:
        new_sections = (
            _generate_section_rects(self.text_region_rect_px, count, self.segmentation)
            if self.text_region_rect_px is not None
            else []
        )
        return PatternEditorState(
            image_rect_px=self.image_rect_px,
            text_side=self.text_side,
            segmentation=self.segmentation,
            section_count=count,
            text_region_rect_px=self.text_region_rect_px,
            text_section_rects_px=new_sections,
            field_names=_pad_field_names(list(self.field_names), count),
            selected_handle=self.selected_handle,
            selected_section_index=self.selected_section_index,
        )

    def with_segmentation(self, seg: TextSegmentation) -> PatternEditorState:
        new_sections = (
            _generate_section_rects(self.text_region_rect_px, self.section_count, seg)
            if self.text_region_rect_px is not None
            else []
        )
        return PatternEditorState(
            image_rect_px=self.image_rect_px,
            text_side=self.text_side,
            segmentation=seg,
            section_count=self.section_count,
            text_region_rect_px=self.text_region_rect_px,
            text_section_rects_px=new_sections,
            field_names=list(self.field_names),
            selected_handle=self.selected_handle,
            selected_section_index=self.selected_section_index,
        )

    def with_text_side(self, side: PatternSide) -> tuple[PatternEditorState, bool]:
        """Returns (new_state, needs_confirmation).

        needs_confirmation is True when the text region was already customized —
        the caller should ask before clearing and repositioning it.
        """
        needs_confirmation = self.text_region_rect_px is not None
        return (
            PatternEditorState(
                image_rect_px=self.image_rect_px,
                text_side=side,
                segmentation=self.segmentation,
                section_count=self.section_count,
                text_region_rect_px=self.text_region_rect_px,
                text_section_rects_px=list(self.text_section_rects_px),
                field_names=list(self.field_names),
                selected_handle=self.selected_handle,
                selected_section_index=self.selected_section_index,
            ),
            needs_confirmation,
        )

    def with_text_region_cleared(self) -> PatternEditorState:
        return PatternEditorState(
            image_rect_px=self.image_rect_px,
            text_side=self.text_side,
            segmentation=self.segmentation,
            section_count=self.section_count,
            text_region_rect_px=None,
            text_section_rects_px=[],
            field_names=list(self.field_names),
            selected_handle=self.selected_handle,
            selected_section_index=self.selected_section_index,
        )

    def with_text_region_rect(self, rect: RectPx) -> PatternEditorState:
        new_sections = _generate_section_rects(rect, self.section_count, self.segmentation)
        return PatternEditorState(
            image_rect_px=self.image_rect_px,
            text_side=self.text_side,
            segmentation=self.segmentation,
            section_count=self.section_count,
            text_region_rect_px=rect,
            text_section_rects_px=new_sections,
            field_names=list(self.field_names),
            selected_handle=self.selected_handle,
            selected_section_index=self.selected_section_index,
        )

    def with_image_rect(self, rect: RectPx, *, auto_text: bool = True) -> PatternEditorState:
        """Set image rect. If auto_text and no text region is set, compute a default text region."""
        from src.ui.editor.pattern_geometry import default_text_region

        text_region = self.text_region_rect_px
        if auto_text and text_region is None:
            text_region = default_text_region(rect, self.text_side)
        new_sections = (
            _generate_section_rects(text_region, self.section_count, self.segmentation)
            if text_region is not None
            else []
        )
        return PatternEditorState(
            image_rect_px=rect,
            text_side=self.text_side,
            segmentation=self.segmentation,
            section_count=self.section_count,
            text_region_rect_px=text_region,
            text_section_rects_px=new_sections,
            field_names=list(self.field_names),
            selected_handle=self.selected_handle,
            selected_section_index=self.selected_section_index,
        )

    def with_field_names(self, names: list[str]) -> PatternEditorState:
        return PatternEditorState(
            image_rect_px=self.image_rect_px,
            text_side=self.text_side,
            segmentation=self.segmentation,
            section_count=self.section_count,
            text_region_rect_px=self.text_region_rect_px,
            text_section_rects_px=list(self.text_section_rects_px),
            field_names=list(names),
            selected_handle=self.selected_handle,
            selected_section_index=self.selected_section_index,
        )

    def with_section_rects(self, rects: list[RectPx]) -> PatternEditorState:
        """Replace section rects directly (used by section divider drags)."""
        return PatternEditorState(
            image_rect_px=self.image_rect_px,
            text_side=self.text_side,
            segmentation=self.segmentation,
            section_count=self.section_count,
            text_region_rect_px=self.text_region_rect_px,
            text_section_rects_px=list(rects),
            field_names=list(self.field_names),
            selected_handle=self.selected_handle,
            selected_section_index=self.selected_section_index,
        )
