from __future__ import annotations

from src.extraction.grid import CellGroup, GridSegment
from src.ui.grid_editor_segments import (
    adjacent_segment_start_page,
    layout_state_for_page,
    record_segment_change,
    segment_index_for_page,
    segment_nav_state,
)


def _segments() -> list[GridSegment]:
    return [
        GridSegment(
            start_page=0,
            horizontal_lines=[10],
            vertical_lines=[20],
            groups=[CellGroup(field_cells={"a": [(0, 0)]})],
        ),
        GridSegment(
            start_page=3,
            horizontal_lines=[15],
            vertical_lines=[25],
            groups=[CellGroup(field_cells={"b": [(1, 1)]})],
        ),
    ]


def test_segment_index_for_page_selects_latest_applicable_segment() -> None:
    segments = _segments()
    assert segment_index_for_page(segments, 0) == 0
    assert segment_index_for_page(segments, 2) == 0
    assert segment_index_for_page(segments, 3) == 1
    assert segment_index_for_page(segments, 9) == 1


def test_record_segment_change_replaces_existing_segment_at_same_page() -> None:
    segments = _segments()
    updated = record_segment_change(
        segments=segments,
        page_index=3,
        horizontal_lines=[100],
        vertical_lines=[200],
        groups=[],
    )
    assert len(updated) == 2
    assert updated[1].start_page == 3
    assert updated[1].horizontal_lines == [100]
    assert updated[1].vertical_lines == [200]
    assert updated[1].groups == []


def test_record_segment_change_inserts_new_segment_after_current() -> None:
    segments = _segments()
    updated = record_segment_change(
        segments=segments,
        page_index=1,
        horizontal_lines=[100],
        vertical_lines=[200],
        groups=[],
    )
    assert [seg.start_page for seg in updated] == [0, 1, 3]


def test_layout_state_for_page_returns_sorted_lines_and_groups() -> None:
    segments = [
        GridSegment(
            start_page=0,
            horizontal_lines=[50, 10],
            vertical_lines=[40, 20],
            groups=[CellGroup(field_cells={"x": [(0, 0)]})],
        )
    ]
    layout = layout_state_for_page(segments, 0)
    assert layout is not None
    assert layout.horizontal_lines == [10, 50]
    assert layout.vertical_lines == [20, 40]
    assert len(layout.groups) == 1


def test_segment_nav_state_and_adjacent_navigation() -> None:
    segments = _segments()
    nav = segment_nav_state(segments, 0)
    assert nav.label == "1/2"
    assert nav.prev_enabled is False
    assert nav.next_enabled is True

    nav2 = segment_nav_state(segments, 4)
    assert nav2.label == "2/2"
    assert nav2.prev_enabled is True
    assert nav2.next_enabled is False

    assert adjacent_segment_start_page(segments, 4, "prev") == 0
    assert adjacent_segment_start_page(segments, 0, "next") == 3
    assert adjacent_segment_start_page(segments, 0, "prev") is None
    assert adjacent_segment_start_page(segments, 4, "next") is None
