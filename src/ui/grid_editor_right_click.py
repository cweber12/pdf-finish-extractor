from __future__ import annotations

from dataclasses import dataclass

Cell = tuple[int, int]


@dataclass(frozen=True)
class RightClickDecision:
    consumed: bool
    omit_region_index_to_remove: int | None = None
    clear_pending_group_selection: bool = False
    remove_groups_containing_cell: Cell | None = None
    remove_h_line_index: int | None = None
    remove_v_line_index: int | None = None
    clear_groups_for_grid_change: bool = False
    record_segment_change: bool = False
    hint: str | None = None


def decide_right_click(
    *,
    mode: str,
    omit_region_index: int | None,
    pending_group_cells: list[Cell],
    clicked_cell: Cell | None,
    hit_h_index: int | None,
    hit_v_index: int | None,
) -> RightClickDecision:
    if mode == "omit":
        if omit_region_index is not None:
            return RightClickDecision(
                consumed=True,
                omit_region_index_to_remove=omit_region_index,
                hint="Ignored section removed.",
            )
        return RightClickDecision(consumed=True)

    if mode == "grouping":
        if pending_group_cells:
            return RightClickDecision(
                consumed=True,
                clear_pending_group_selection=True,
                hint="Group selection cancelled.",
            )
        if clicked_cell is not None:
            return RightClickDecision(
                consumed=True,
                remove_groups_containing_cell=clicked_cell,
            )
        return RightClickDecision(consumed=True)

    if hit_h_index is not None:
        return RightClickDecision(
            consumed=True,
            remove_h_line_index=hit_h_index,
            clear_groups_for_grid_change=True,
            record_segment_change=True,
            hint="Row boundary removed. Groups were cleared because the grid changed.",
        )
    if hit_v_index is not None:
        return RightClickDecision(
            consumed=True,
            remove_v_line_index=hit_v_index,
            clear_groups_for_grid_change=True,
            record_segment_change=True,
            hint="Column boundary removed. Groups were cleared because the grid changed.",
        )

    return RightClickDecision(consumed=False)
