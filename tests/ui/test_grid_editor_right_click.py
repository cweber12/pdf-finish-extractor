from __future__ import annotations

from src.ui.grid_editor_right_click import decide_right_click


def test_omit_mode_removes_region_when_hit() -> None:
    decision = decide_right_click(
        mode="omit",
        omit_region_index=2,
        pending_group_cells=[],
        clicked_cell=None,
        hit_h_index=None,
        hit_v_index=None,
    )
    assert decision.consumed is True
    assert decision.omit_region_index_to_remove == 2
    assert decision.hint == "Ignored section removed."


def test_omit_mode_consumes_even_without_hit() -> None:
    decision = decide_right_click(
        mode="omit",
        omit_region_index=None,
        pending_group_cells=[],
        clicked_cell=None,
        hit_h_index=None,
        hit_v_index=None,
    )
    assert decision.consumed is True
    assert decision.omit_region_index_to_remove is None


def test_grouping_mode_cancels_pending_selection() -> None:
    decision = decide_right_click(
        mode="grouping",
        omit_region_index=None,
        pending_group_cells=[(0, 0)],
        clicked_cell=(0, 1),
        hit_h_index=None,
        hit_v_index=None,
    )
    assert decision.consumed is True
    assert decision.clear_pending_group_selection is True
    assert decision.hint == "Group selection cancelled."


def test_grouping_mode_selects_group_removal_by_cell() -> None:
    decision = decide_right_click(
        mode="grouping",
        omit_region_index=None,
        pending_group_cells=[],
        clicked_cell=(1, 2),
        hit_h_index=None,
        hit_v_index=None,
    )
    assert decision.consumed is True
    assert decision.remove_groups_containing_cell == (1, 2)


def test_line_mode_removes_horizontal_line() -> None:
    decision = decide_right_click(
        mode="idle",
        omit_region_index=None,
        pending_group_cells=[],
        clicked_cell=None,
        hit_h_index=3,
        hit_v_index=None,
    )
    assert decision.consumed is True
    assert decision.remove_h_line_index == 3
    assert decision.clear_groups_for_grid_change is True
    assert decision.record_segment_change is True
    assert "Row boundary removed" in (decision.hint or "")


def test_line_mode_removes_vertical_line() -> None:
    decision = decide_right_click(
        mode="idle",
        omit_region_index=None,
        pending_group_cells=[],
        clicked_cell=None,
        hit_h_index=None,
        hit_v_index=4,
    )
    assert decision.consumed is True
    assert decision.remove_v_line_index == 4
    assert decision.clear_groups_for_grid_change is True
    assert decision.record_segment_change is True
    assert "Column boundary removed" in (decision.hint or "")


def test_no_action_returns_not_consumed() -> None:
    decision = decide_right_click(
        mode="idle",
        omit_region_index=None,
        pending_group_cells=[],
        clicked_cell=None,
        hit_h_index=None,
        hit_v_index=None,
    )
    assert decision.consumed is False
