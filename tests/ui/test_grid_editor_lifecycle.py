from src.extraction.grid import CellGroup, FieldDefinition, Grid, OmitRegion
from src.ui.grid_editor_lifecycle import (
    applied_profile_state,
    baseline_segments,
    cleared_grid_collections,
    interaction_reset_state,
    profile_from_editor_state,
)


def test_baseline_segments_builds_single_start_page_zero_segment() -> None:
    groups = [CellGroup(field_cells={"id": [(0, 0)]})]
    segments = baseline_segments([100], [200], groups)

    assert len(segments) == 1
    seg = segments[0]
    assert seg.start_page == 0
    assert seg.horizontal_lines == [100]
    assert seg.vertical_lines == [200]
    assert seg.groups == groups


def test_profile_from_editor_state_returns_none_without_lines() -> None:
    result = profile_from_editor_state(
        horizontal_lines=[],
        vertical_lines=[],
        fields=[FieldDefinition("id", "text", 1)],
        groups=[CellGroup(field_cells={"id": [(0, 0)]})],
        omitted_pages={1},
        omit_regions=[OmitRegion(page_index=1, rect=(0, 0, 10, 10))],
    )

    assert result is None


def test_profile_from_editor_state_returns_sorted_grid() -> None:
    result = profile_from_editor_state(
        horizontal_lines=[300, 100],
        vertical_lines=[400, 200],
        fields=[FieldDefinition("id", "text", 1)],
        groups=[CellGroup(field_cells={"id": [(0, 0)]})],
        omitted_pages={3, 1},
        omit_regions=[OmitRegion(page_index=2, rect=(1, 2, 3, 4))],
    )

    assert result is not None
    assert result.horizontal_lines == [100, 300]
    assert result.vertical_lines == [200, 400]
    assert result.omitted_pages == [1, 3]


def test_applied_profile_state_copies_grid_values() -> None:
    grid = Grid(
        horizontal_lines=[300, 100],
        vertical_lines=[200],
        fields=[FieldDefinition("swatch", "image", 1)],
        groups=[CellGroup(field_cells={"swatch": [(0, 0)]})],
        omitted_pages=[4, 2],
        omit_regions=[OmitRegion(page_index=4, rect=(10, 20, 40, 80))],
    )

    state = applied_profile_state(grid)

    assert state.horizontal_lines == [100, 300]
    assert state.vertical_lines == [200]
    assert state.fields == grid.fields
    assert state.groups == grid.groups
    assert state.omitted_pages == {2, 4}
    assert state.omit_regions == grid.omit_regions


def test_cleared_grid_collections_returns_empty_containers() -> None:
    h_lines, v_lines, groups, omitted_pages, omit_regions = cleared_grid_collections()

    assert h_lines == []
    assert v_lines == []
    assert groups == []
    assert omitted_pages == set()
    assert omit_regions == []


def test_interaction_reset_state_returns_cleared_values() -> None:
    reset = interaction_reset_state()

    assert reset.pending_group_cells == []
    assert reset.hovered_cell is None
    assert reset.hovered_line is None
    assert reset.omit_start is None
    assert reset.omit_preview is None
