from __future__ import annotations

from src.extraction.grid import CellGroup, FieldDefinition
from src.ui.grid_editor_grouping import (
    apply_group_click,
    field_cells_from_pending,
    field_for_click_index,
    pending_cells_for_field,
    recipe_click_count,
)


def _fields() -> list[FieldDefinition]:
    return [
        FieldDefinition("swatch", "image", 2),
        FieldDefinition("material_id", "text", 1),
    ]


def test_recipe_click_count_sums_clicks() -> None:
    assert recipe_click_count(_fields()) == 3


def test_field_for_click_index_maps_recipe_order() -> None:
    fields = _fields()
    assert field_for_click_index(fields, 0) == fields[0]
    assert field_for_click_index(fields, 1) == fields[0]
    assert field_for_click_index(fields, 2) == fields[1]
    assert field_for_click_index(fields, 3) is None


def test_pending_cells_for_field_slices_cells_for_field() -> None:
    fields = _fields()
    pending = [(0, 0), (0, 1), (1, 0)]
    assert pending_cells_for_field(fields, pending, fields[0]) == [(0, 0), (0, 1)]
    assert pending_cells_for_field(fields, pending, fields[1]) == [(1, 0)]


def test_field_cells_from_pending_builds_group_mapping() -> None:
    fields = _fields()
    pending = [(0, 0), (0, 1), (1, 0)]
    assert field_cells_from_pending(fields, pending) == {
        "swatch": [(0, 0), (0, 1)],
        "material_id": [(1, 0)],
    }


def test_apply_group_click_requires_fields() -> None:
    decision = apply_group_click(fields=[], pending_cells=[], clicked_cell=(0, 0))
    assert decision.pending_cells == []
    assert decision.hint == "Define fields before creating groups."
    assert decision.created_group is None


def test_apply_group_click_rejects_duplicate_pending_cell() -> None:
    decision = apply_group_click(
        fields=_fields(),
        pending_cells=[(0, 0)],
        clicked_cell=(0, 0),
    )
    assert decision.pending_cells == [(0, 0)]
    assert decision.hint == "That cell is already selected for the pending group."
    assert decision.created_group is None


def test_apply_group_click_rejects_non_rectangular_field_selection() -> None:
    fields = [FieldDefinition("swatch", "image", 3)]
    decision = apply_group_click(
        fields=fields,
        pending_cells=[(0, 0), (0, 1)],
        clicked_cell=(1, 0),
    )
    assert decision.pending_cells == [(0, 0), (0, 1)]
    assert decision.hint == "Field cells must form one adjacent rectangle."
    assert decision.created_group is None


def test_apply_group_click_updates_progress_hint_until_complete() -> None:
    decision = apply_group_click(
        fields=_fields(),
        pending_cells=[],
        clicked_cell=(0, 0),
    )
    assert decision.pending_cells == [(0, 0)]
    assert decision.hint == "Group selection 1/3."
    assert decision.created_group is None


def test_apply_group_click_creates_group_on_final_click() -> None:
    fields = _fields()
    decision = apply_group_click(
        fields=fields,
        pending_cells=[(0, 0), (0, 1)],
        clicked_cell=(1, 0),
    )
    assert decision.pending_cells == []
    assert decision.created_group == CellGroup(
        field_cells={"swatch": [(0, 0), (0, 1)], "material_id": [(1, 0)]}
    )
    assert decision.hint == "Group created. Continue grouping cells or right-click a group to remove it."
    assert decision.record_segment_change is True
