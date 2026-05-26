from __future__ import annotations

import pytest

from src.extraction.pattern import RectPx
from src.ui.editor.pattern_editor_state import PatternEditorState, _generate_section_rects


# ------------------------------------------------------------------
# _generate_section_rects — rows segmentation
# ------------------------------------------------------------------


def test_rows_below_splits_vertically() -> None:
    # Text region is below the image (wide, short)
    region = RectPx(x0=10, y0=100, x1=110, y1=160)
    sections = _generate_section_rects(region, 3, "rows")
    assert len(sections) == 3
    assert sections[0] == RectPx(x0=10, y0=100, x1=110, y1=120)
    assert sections[1] == RectPx(x0=10, y0=120, x1=110, y1=140)
    assert sections[2] == RectPx(x0=10, y0=140, x1=110, y1=160)


def test_rows_above_splits_vertically() -> None:
    # Text region is above the image
    region = RectPx(x0=10, y0=40, x1=110, y1=100)
    sections = _generate_section_rects(region, 2, "rows")
    assert len(sections) == 2
    assert sections[0].y0 == 40
    assert sections[0].y1 == 70
    assert sections[1].y0 == 70
    assert sections[1].y1 == 100


def test_rows_right_splits_vertically() -> None:
    # Text region is to the right of the image (tall, narrow)
    region = RectPx(x0=100, y0=0, x1=140, y1=80)
    sections = _generate_section_rects(region, 4, "rows")
    assert len(sections) == 4
    for s in sections:
        assert s.x0 == 100
        assert s.x1 == 140
    assert sections[0].y0 == 0
    assert sections[-1].y1 == 80


def test_rows_left_splits_vertically() -> None:
    # Text region is to the left of the image (tall, narrow)
    region = RectPx(x0=0, y0=0, x1=40, y1=80)
    sections = _generate_section_rects(region, 2, "rows")
    assert len(sections) == 2
    assert sections[0] == RectPx(x0=0, y0=0, x1=40, y1=40)
    assert sections[1] == RectPx(x0=0, y0=40, x1=40, y1=80)


# ------------------------------------------------------------------
# _generate_section_rects — columns segmentation
# ------------------------------------------------------------------


def test_columns_below_splits_horizontally() -> None:
    region = RectPx(x0=10, y0=100, x1=110, y1=130)
    sections = _generate_section_rects(region, 2, "columns")
    assert len(sections) == 2
    assert sections[0] == RectPx(x0=10, y0=100, x1=60, y1=130)
    assert sections[1] == RectPx(x0=60, y0=100, x1=110, y1=130)


def test_columns_above_splits_horizontally() -> None:
    region = RectPx(x0=0, y0=0, x1=90, y1=30)
    sections = _generate_section_rects(region, 3, "columns")
    assert len(sections) == 3
    assert sections[0].x0 == 0
    assert sections[-1].x1 == 90
    for s in sections:
        assert s.y0 == 0
        assert s.y1 == 30


def test_columns_right_splits_horizontally() -> None:
    region = RectPx(x0=100, y0=0, x1=160, y1=80)
    sections = _generate_section_rects(region, 3, "columns")
    assert len(sections) == 3
    assert sections[0].x0 == 100
    assert sections[-1].x1 == 160


def test_columns_left_splits_horizontally() -> None:
    region = RectPx(x0=0, y0=10, x1=60, y1=90)
    sections = _generate_section_rects(region, 2, "columns")
    assert len(sections) == 2
    assert sections[0] == RectPx(x0=0, y0=10, x1=30, y1=90)
    assert sections[1] == RectPx(x0=30, y0=10, x1=60, y1=90)


# ------------------------------------------------------------------
# _generate_section_rects — edge cases
# ------------------------------------------------------------------


def test_section_count_zero_returns_empty() -> None:
    region = RectPx(x0=0, y0=0, x1=100, y1=100)
    assert _generate_section_rects(region, 0, "rows") == []
    assert _generate_section_rects(region, 0, "columns") == []


def test_section_count_one_returns_full_region() -> None:
    region = RectPx(x0=10, y0=20, x1=110, y1=120)
    assert _generate_section_rects(region, 1, "rows") == [region]
    assert _generate_section_rects(region, 1, "columns") == [region]


# ------------------------------------------------------------------
# PatternEditorState — completeness
# ------------------------------------------------------------------


def test_state_is_incomplete_without_image_rect() -> None:
    state = PatternEditorState(
        text_region_rect_px=RectPx(x0=0, y0=100, x1=100, y1=130),
        text_section_rects_px=[RectPx(x0=0, y0=100, x1=100, y1=130)],
    )
    assert not state.is_complete


def test_state_is_incomplete_without_text_region() -> None:
    state = PatternEditorState(
        image_rect_px=RectPx(x0=0, y0=0, x1=100, y1=100),
    )
    assert not state.is_complete


def test_state_is_complete_when_all_set() -> None:
    state = PatternEditorState(
        image_rect_px=RectPx(x0=0, y0=0, x1=100, y1=100),
        section_count=1,
        text_region_rect_px=RectPx(x0=0, y0=100, x1=100, y1=130),
        text_section_rects_px=[RectPx(x0=0, y0=100, x1=100, y1=130)],
    )
    assert state.is_complete


# ------------------------------------------------------------------
# PatternEditorState.with_section_count
# ------------------------------------------------------------------


def test_with_section_count_regenerates_sections() -> None:
    region = RectPx(x0=0, y0=100, x1=100, y1=160)
    state = PatternEditorState(
        image_rect_px=RectPx(x0=0, y0=0, x1=100, y1=100),
        text_region_rect_px=region,
        text_section_rects_px=[region],
        section_count=1,
    )
    new_state = state.with_section_count(3)
    assert new_state.section_count == 3
    assert len(new_state.text_section_rects_px) == 3
    assert new_state.text_region_rect_px == region


def test_with_section_count_without_text_region_clears_sections() -> None:
    state = PatternEditorState(section_count=2)
    new_state = state.with_section_count(4)
    assert new_state.section_count == 4
    assert new_state.text_section_rects_px == []


# ------------------------------------------------------------------
# PatternEditorState.with_text_side
# ------------------------------------------------------------------


def test_with_text_side_no_confirmation_when_text_region_not_set() -> None:
    state = PatternEditorState(text_side="below")
    new_state, needs_confirmation = state.with_text_side("above")
    assert new_state.text_side == "above"
    assert not needs_confirmation


def test_with_text_side_needs_confirmation_when_text_region_set() -> None:
    state = PatternEditorState(
        text_side="below",
        text_region_rect_px=RectPx(x0=0, y0=100, x1=100, y1=130),
    )
    new_state, needs_confirmation = state.with_text_side("right")
    assert new_state.text_side == "right"
    assert needs_confirmation
    assert new_state.text_region_rect_px is not None  # preserved until user confirms


def test_with_text_region_cleared_removes_rect_and_sections() -> None:
    state = PatternEditorState(
        text_region_rect_px=RectPx(x0=0, y0=100, x1=100, y1=130),
        text_section_rects_px=[RectPx(x0=0, y0=100, x1=100, y1=130)],
    )
    cleared = state.with_text_region_cleared()
    assert cleared.text_region_rect_px is None
    assert cleared.text_section_rects_px == []


# ------------------------------------------------------------------
# PatternEditorState.with_text_region_rect
# ------------------------------------------------------------------


def test_with_text_region_rect_sets_region_and_generates_sections() -> None:
    state = PatternEditorState(section_count=2, segmentation="rows")
    region = RectPx(x0=0, y0=100, x1=100, y1=160)
    new_state = state.with_text_region_rect(region)
    assert new_state.text_region_rect_px == region
    assert len(new_state.text_section_rects_px) == 2
    assert new_state.text_section_rects_px[0].y0 == 100
    assert new_state.text_section_rects_px[1].y1 == 160
