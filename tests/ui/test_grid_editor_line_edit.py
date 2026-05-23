from __future__ import annotations

from src.ui.grid_editor_line_edit import apply_line_placement, bounded_line_value, can_place_line


def test_bounded_line_value_clamps_when_no_max_value() -> None:
    assert bounded_line_value(
        line_kind="h",
        lines=[10, 20],
        max_value=None,
        index=0,
        value=-5,
        min_gap=3,
    ) == 0


def test_bounded_line_value_clamps_between_neighbors() -> None:
    assert bounded_line_value(
        line_kind="h",
        lines=[10, 30, 60],
        max_value=100,
        index=1,
        value=15,
        min_gap=5,
    ) == 15
    assert bounded_line_value(
        line_kind="h",
        lines=[10, 30, 60],
        max_value=100,
        index=1,
        value=70,
        min_gap=5,
    ) == 55


def test_bounded_line_value_returns_current_when_neighbor_bounds_invert() -> None:
    assert bounded_line_value(
        line_kind="v",
        lines=[10, 12, 13],
        max_value=20,
        index=1,
        value=99,
        min_gap=3,
    ) == 12


def test_can_place_line_requires_bounds_and_min_gap() -> None:
    assert can_place_line(
        line_kind="h",
        lines=[20, 60],
        max_value=100,
        value=40,
        min_gap=5,
    ) is True
    assert can_place_line(
        line_kind="h",
        lines=[20, 60],
        max_value=100,
        value=22,
        min_gap=5,
    ) is False
    assert can_place_line(
        line_kind="h",
        lines=[20, 60],
        max_value=None,
        value=40,
        min_gap=5,
    ) is False


def test_apply_line_placement_rejects_invalid_preview() -> None:
    decision = apply_line_placement(
        line_kind="h",
        lines=[20, 60],
        max_value=100,
        preview_value=22,
        min_gap=5,
    )
    assert decision.lines == [20, 60]
    assert decision.clear_groups_for_grid_change is False
    assert decision.hint == "Row boundary is too close to another line or page edge."


def test_apply_line_placement_accepts_and_sorts_new_line() -> None:
    decision = apply_line_placement(
        line_kind="v",
        lines=[80, 20],
        max_value=120,
        preview_value=50,
        min_gap=5,
    )
    assert decision.lines == [20, 50, 80]
    assert decision.clear_groups_for_grid_change is True
    assert decision.hint == "Column boundary added. Drag its handle to adjust."
