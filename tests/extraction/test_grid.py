from src.extraction.grid import CellGroup, FieldDefinition, Grid


class TestGridSerialization:
    def test_round_trip_preserves_fields_and_groups(self) -> None:
        grid = Grid(
            horizontal_lines=[200],
            vertical_lines=[150, 300],
            fields=[
                FieldDefinition("swatch", "image", 2),
                FieldDefinition("material_id", "text", 1),
            ],
            groups=[
                CellGroup(
                    field_cells={
                        "swatch": [(0, 0), (0, 1)],
                        "material_id": [(1, 0)],
                    }
                )
            ],
        )

        restored = Grid.from_dict(grid.to_dict())

        assert restored.horizontal_lines == grid.horizontal_lines
        assert restored.vertical_lines == grid.vertical_lines
        assert restored.fields == grid.fields
        assert restored.groups == grid.groups

    def test_to_dict_uses_new_group_shape_without_pairs(self) -> None:
        grid = Grid(
            fields=[FieldDefinition("id", "text", 1)],
            groups=[CellGroup(field_cells={"id": [(0, 0)]})],
        )

        data = grid.to_dict()

        assert "pairs" not in data
        assert data["fields"] == [{"name": "id", "type": "text", "click_count": 1}]
        assert data["groups"] == [{"field_cells": {"id": [[0, 0]]}}]

    def test_normalized_drops_duplicate_field_names(self) -> None:
        grid = Grid(
            fields=[
                FieldDefinition("id", "text", 1),
                FieldDefinition("id", "image", 1),
            ],
        )

        assert grid.normalized().fields == [FieldDefinition("id", "text", 1)]

    def test_normalized_drops_non_rectangular_field_cells(self) -> None:
        grid = Grid(
            horizontal_lines=[100],
            vertical_lines=[100],
            fields=[FieldDefinition("shape", "text", 3)],
            groups=[CellGroup(field_cells={"shape": [(0, 0), (0, 1), (1, 0)]})],
        )

        assert grid.normalized().groups == []
