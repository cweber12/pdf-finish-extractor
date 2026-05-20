import pytest

from src.extraction.grid import CellType, Grid, PairDirection


def make_simple_grid(**kwargs) -> Grid:
    defaults = dict(
        horizontal_lines=[100, 200],
        vertical_lines=[50, 150],
        cell_types={(0, 0): CellType.IMAGE, (0, 1): CellType.TEXT},
        pair_direction=PairDirection.RIGHT,
    )
    defaults.update(kwargs)
    return Grid(**defaults)


class TestGridSerialisation:
    def test_round_trip(self):
        grid = make_simple_grid()
        restored = Grid.from_dict(grid.to_dict())
        assert restored.horizontal_lines == grid.horizontal_lines
        assert restored.vertical_lines == grid.vertical_lines
        assert restored.cell_types == grid.cell_types
        assert restored.pair_direction == grid.pair_direction

    def test_to_dict_cell_keys_are_serialisable(self):
        grid = make_simple_grid()
        data = grid.to_dict()
        # cell_types must be a list of dicts, not tuple keys
        assert isinstance(data["cells"], list)
        for cell in data["cells"]:
            assert "row" in cell
            assert "col" in cell
            assert "type" in cell

    def test_from_dict_defaults_ignored_for_missing_cells(self):
        data = {
            "horizontal_lines": [100],
            "vertical_lines": [50],
            "cells": [],
            "pair_direction": "right",
        }
        grid = Grid.from_dict(data)
        assert grid.cell_types == {}

    def test_from_dict_unknown_direction_raises(self):
        data = {
            "horizontal_lines": [],
            "vertical_lines": [],
            "cells": [],
            "pair_direction": "diagonal",
        }
        with pytest.raises(ValueError):
            Grid.from_dict(data)

    def test_all_directions_round_trip(self):
        for direction in PairDirection:
            grid = make_simple_grid(pair_direction=direction)
            restored = Grid.from_dict(grid.to_dict())
            assert restored.pair_direction == direction
