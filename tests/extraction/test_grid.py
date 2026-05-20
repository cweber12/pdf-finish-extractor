from src.extraction.grid import CellPair, Grid


def make_simple_grid(**kwargs) -> Grid:
    defaults = dict(
        horizontal_lines=[100, 200],
        vertical_lines=[50, 150],
        pairs=[CellPair(image_cell=(0, 0), text_cell=(0, 1))],
    )
    defaults.update(kwargs)
    return Grid(**defaults)


class TestGridSerialisation:
    def test_round_trip(self) -> None:
        grid = make_simple_grid()
        restored = Grid.from_dict(grid.to_dict())
        assert restored.horizontal_lines == grid.horizontal_lines
        assert restored.vertical_lines == grid.vertical_lines
        assert restored.pairs == grid.pairs

    def test_to_dict_pairs_are_serialisable(self) -> None:
        grid = make_simple_grid()
        data = grid.to_dict()
        assert isinstance(data["pairs"], list)
        for p in data["pairs"]:
            assert isinstance(p["image_cell"], list)
            assert isinstance(p["text_cell"], list)

    def test_from_dict_empty_pairs(self) -> None:
        data = {"horizontal_lines": [100], "vertical_lines": [50], "pairs": []}
        grid = Grid.from_dict(data)
        assert grid.pairs == []

    def test_from_dict_missing_keys_use_defaults(self) -> None:
        grid = Grid.from_dict({})
        assert grid.horizontal_lines == []
        assert grid.vertical_lines == []
        assert grid.pairs == []

    def test_multiple_pairs_round_trip(self) -> None:
        pairs = [
            CellPair(image_cell=(0, 0), text_cell=(0, 1)),
            CellPair(image_cell=(1, 0), text_cell=(1, 1)),
            CellPair(image_cell=(0, 2), text_cell=(1, 2)),
        ]
        grid = Grid(horizontal_lines=[200], vertical_lines=[150, 300], pairs=pairs)
        restored = Grid.from_dict(grid.to_dict())
        assert restored.pairs == pairs
