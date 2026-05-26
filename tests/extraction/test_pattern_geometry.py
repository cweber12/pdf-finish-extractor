from __future__ import annotations

from src.extraction.pattern import RectPx, RelativeRect, resolve_relative_rect
from src.ui.editor.pattern_editor_state import _generate_section_rects
from src.ui.editor.pattern_geometry import (
    _MIN_SIZE,
    clamp_rect_to_page,
    clamp_section_divider,
    default_text_region,
    normalize_rect,
)


# ---------------------------------------------------------------------------
# resolve_relative_rect — all four sides
# ---------------------------------------------------------------------------


def test_resolve_relative_rect_below() -> None:
    image = RectPx(x0=10, y0=10, x1=90, y1=90)  # 80x80
    rel = RelativeRect(x0=0.0, y0=1.0, x1=1.0, y1=1.25)
    result = resolve_relative_rect(rel, image)
    assert result.x0 == 10
    assert result.y0 == 90   # 10 + 1.0*80
    assert result.x1 == 90
    assert result.y1 == 110  # 10 + 1.25*80


def test_resolve_relative_rect_above() -> None:
    image = RectPx(x0=10, y0=80, x1=90, y1=160)  # 80x80 starting at y=80
    rel = RelativeRect(x0=0.0, y0=-0.25, x1=1.0, y1=0.0)
    result = resolve_relative_rect(rel, image)
    assert result.x0 == 10
    assert result.y0 == 60   # 80 + (-0.25)*80 = 60
    assert result.x1 == 90
    assert result.y1 == 80   # 80 + 0*80 = top of image


def test_resolve_relative_rect_right() -> None:
    image = RectPx(x0=10, y0=10, x1=90, y1=90)  # 80x80
    rel = RelativeRect(x0=1.0, y0=0.0, x1=1.25, y1=1.0)
    result = resolve_relative_rect(rel, image)
    assert result.x0 == 90   # 10 + 1.0*80 = right edge
    assert result.y0 == 10
    assert result.x1 == 110  # 10 + 1.25*80
    assert result.y1 == 90


def test_resolve_relative_rect_left() -> None:
    image = RectPx(x0=80, y0=10, x1=160, y1=90)  # 80x80 starting at x=80
    rel = RelativeRect(x0=-0.25, y0=0.0, x1=0.0, y1=1.0)
    result = resolve_relative_rect(rel, image)
    assert result.x0 == 60   # 80 + (-0.25)*80 = 60
    assert result.y0 == 10
    assert result.x1 == 80   # 80 + 0*80 = left edge of image
    assert result.y1 == 90


def test_resolve_relative_rect_identity() -> None:
    image = RectPx(x0=0, y0=0, x1=100, y1=100)
    rel = RelativeRect(x0=0.0, y0=0.0, x1=1.0, y1=1.0)
    assert resolve_relative_rect(rel, image) == image


# ---------------------------------------------------------------------------
# Section adjacency — rows and columns share a boundary, no gap
# ---------------------------------------------------------------------------


def test_row_sections_are_adjacent() -> None:
    region = RectPx(x0=0, y0=100, x1=100, y1=160)
    sections = _generate_section_rects(region, 3, "rows")
    assert sections[0].y1 == sections[1].y0
    assert sections[1].y1 == sections[2].y0


def test_column_sections_are_adjacent() -> None:
    region = RectPx(x0=0, y0=0, x1=90, y1=30)
    sections = _generate_section_rects(region, 3, "columns")
    assert sections[0].x1 == sections[1].x0
    assert sections[1].x1 == sections[2].x0


def test_negative_section_count_returns_empty() -> None:
    region = RectPx(x0=0, y0=0, x1=100, y1=100)
    assert _generate_section_rects(region, -1, "rows") == []
    assert _generate_section_rects(region, -1, "columns") == []


# ---------------------------------------------------------------------------
# default_text_region — adjacent to image on each side
# ---------------------------------------------------------------------------


def test_default_text_region_below_is_adjacent() -> None:
    image = RectPx(x0=10, y0=10, x1=90, y1=90)
    region = default_text_region(image, "below")
    assert region.x0 == image.x0
    assert region.x1 == image.x1
    assert region.y0 == image.y1
    assert region.y1 > image.y1


def test_default_text_region_above_is_adjacent() -> None:
    image = RectPx(x0=10, y0=100, x1=90, y1=180)
    region = default_text_region(image, "above")
    assert region.x0 == image.x0
    assert region.x1 == image.x1
    assert region.y1 == image.y0
    assert region.y0 < image.y0


def test_default_text_region_right_is_adjacent() -> None:
    image = RectPx(x0=10, y0=10, x1=90, y1=90)
    region = default_text_region(image, "right")
    assert region.x0 == image.x1
    assert region.x1 > image.x1
    assert region.y0 == image.y0
    assert region.y1 == image.y1


def test_default_text_region_left_is_adjacent() -> None:
    image = RectPx(x0=100, y0=10, x1=180, y1=90)
    region = default_text_region(image, "left")
    assert region.x1 == image.x0
    assert region.x0 < image.x0
    assert region.y0 == image.y0
    assert region.y1 == image.y1


# ---------------------------------------------------------------------------
# clamp_section_divider
# ---------------------------------------------------------------------------


def test_clamp_section_divider_rows_moves_boundary() -> None:
    sections = [
        RectPx(x0=0, y0=0, x1=100, y1=50),
        RectPx(x0=0, y0=50, x1=100, y1=100),
    ]
    result = clamp_section_divider(sections, 0, 40, "rows")
    assert result[0].y1 == 40
    assert result[1].y0 == 40


def test_clamp_section_divider_columns_moves_boundary() -> None:
    sections = [
        RectPx(x0=0, y0=0, x1=50, y1=100),
        RectPx(x0=50, y0=0, x1=100, y1=100),
    ]
    result = clamp_section_divider(sections, 0, 60, "columns")
    assert result[0].x1 == 60
    assert result[1].x0 == 60


def test_clamp_section_divider_prevents_collapse() -> None:
    sections = [
        RectPx(x0=0, y0=0, x1=100, y1=50),
        RectPx(x0=0, y0=50, x1=100, y1=100),
    ]
    # Try to push the divider almost to the top of section 0
    result = clamp_section_divider(sections, 0, 1, "rows")
    assert result[0].y1 >= sections[0].y0 + _MIN_SIZE
    assert result[1].y0 == result[0].y1


def test_clamp_section_divider_out_of_range_index_returns_unchanged() -> None:
    sections = [
        RectPx(x0=0, y0=0, x1=100, y1=50),
        RectPx(x0=0, y0=50, x1=100, y1=100),
    ]
    assert clamp_section_divider(sections, 5, 40, "rows") == sections
    assert clamp_section_divider(sections, -1, 40, "rows") == sections


# ---------------------------------------------------------------------------
# normalize_rect and clamp_rect_to_page
# ---------------------------------------------------------------------------


def test_normalize_rect_swaps_flipped_coords() -> None:
    result = normalize_rect(90, 80, 10, 20)
    assert result == RectPx(x0=10, y0=20, x1=90, y1=80)


def test_normalize_rect_passes_through_valid_coords() -> None:
    result = normalize_rect(10, 20, 90, 80)
    assert result == RectPx(x0=10, y0=20, x1=90, y1=80)


def test_clamp_rect_to_page_clips_negative_origin() -> None:
    rect = RectPx(x0=-10, y0=-10, x1=90, y1=90)
    result = clamp_rect_to_page(rect, 400, 600)
    assert result.x0 == 0
    assert result.y0 == 0


def test_clamp_rect_to_page_clips_far_corner() -> None:
    rect = RectPx(x0=10, y0=10, x1=500, y1=700)
    result = clamp_rect_to_page(rect, 400, 600)
    assert result.x1 == 400
    assert result.y1 == 600


def test_clamp_rect_to_page_passes_through_in_bounds() -> None:
    rect = RectPx(x0=10, y0=10, x1=90, y1=90)
    assert clamp_rect_to_page(rect, 400, 600) == rect
