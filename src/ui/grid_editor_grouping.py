from __future__ import annotations

from dataclasses import dataclass

from src.extraction.grid import CellGroup, FieldDefinition, cells_form_rectangle

Cell = tuple[int, int]


@dataclass(frozen=True)
class GroupClickDecision:
    pending_cells: list[Cell]
    created_group: CellGroup | None = None
    hint: str | None = None
    record_segment_change: bool = False


def recipe_click_count(fields: list[FieldDefinition]) -> int:
    return sum(field_def.click_count for field_def in fields)


def field_for_click_index(
    fields: list[FieldDefinition],
    click_index: int,
) -> FieldDefinition | None:
    start = 0
    for field_def in fields:
        end = start + field_def.click_count
        if start <= click_index < end:
            return field_def
        start = end
    return None


def pending_cells_for_field(
    fields: list[FieldDefinition],
    pending: list[Cell],
    field_def: FieldDefinition,
) -> list[Cell]:
    start = 0
    for candidate in fields:
        end = start + candidate.click_count
        if candidate.name == field_def.name:
            return pending[start:end]
        start = end
    return []


def field_cells_from_pending(
    fields: list[FieldDefinition],
    pending: list[Cell],
) -> dict[str, list[Cell]]:
    result: dict[str, list[Cell]] = {}
    start = 0
    for field_def in fields:
        end = start + field_def.click_count
        result[field_def.name] = pending[start:end]
        start = end
    return result


def apply_group_click(
    *,
    fields: list[FieldDefinition],
    pending_cells: list[Cell],
    clicked_cell: Cell,
) -> GroupClickDecision:
    if not fields:
        return GroupClickDecision(
            pending_cells=list(pending_cells),
            hint="Define fields before creating groups.",
        )

    if clicked_cell in pending_cells:
        return GroupClickDecision(
            pending_cells=list(pending_cells),
            hint="That cell is already selected for the pending group.",
        )

    candidate = [*pending_cells, clicked_cell]
    field_def = field_for_click_index(fields, len(candidate) - 1)
    if field_def is None:
        return GroupClickDecision(pending_cells=[])

    current_cells = pending_cells_for_field(fields, candidate, field_def)
    if len(current_cells) == field_def.click_count and not cells_form_rectangle(current_cells):
        return GroupClickDecision(
            pending_cells=list(pending_cells),
            hint="Field cells must form one adjacent rectangle.",
        )

    if len(candidate) < recipe_click_count(fields):
        return GroupClickDecision(
            pending_cells=candidate,
            hint=f"Group selection {len(candidate)}/{recipe_click_count(fields)}.",
        )

    group = CellGroup(field_cells=field_cells_from_pending(fields, candidate))
    return GroupClickDecision(
        pending_cells=[],
        created_group=group,
        hint="Group created. Continue grouping cells or right-click a group to remove it.",
        record_segment_change=True,
    )
