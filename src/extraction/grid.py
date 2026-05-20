from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CellPair:
    """An explicit pairing of one image cell with one text cell.

    Cell addresses are ``(row_index, col_index)`` within the grid formed by
    ``horizontal_lines`` and ``vertical_lines``.
    """

    image_cell: tuple[int, int]
    text_cell: tuple[int, int]

    def to_dict(self) -> dict:
        return {
            "image_cell": list(self.image_cell),
            "text_cell": list(self.text_cell),
        }

    @classmethod
    def from_dict(cls, data: dict) -> CellPair:
        return cls(
            image_cell=_coerce_cell(data["image_cell"]),
            text_cell=_coerce_cell(data["text_cell"]),
        )


@dataclass
class Grid:
    """Defines a grid layout and explicit cell pairings for a PDF page.

    ``horizontal_lines`` and ``vertical_lines`` are pixel coordinates in the
    150 DPI rendered image space used by the editor and extractor.

    ``pairs`` explicitly lists which cells go together. Each :class:`CellPair`
    names the image cell and the text cell that contains the material ID.
    """

    horizontal_lines: list[int] = field(default_factory=list)
    vertical_lines: list[int] = field(default_factory=list)
    pairs: list[CellPair] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.horizontal_lines and not self.vertical_lines and not self.pairs

    @property
    def has_pairs(self) -> bool:
        return bool(self.pairs)

    def normalized(self) -> Grid:
        """Return a cleaned copy of the grid.

        This keeps saved profiles tolerant of accidental duplicate lines,
        negative coordinates, or invalid pair data without mutating the original
        object owned by the UI.
        """
        horizontal = _dedupe_ints(v for v in self.horizontal_lines if v >= 0)
        vertical = _dedupe_ints(v for v in self.vertical_lines if v >= 0)

        max_row = len(horizontal)
        max_col = len(vertical)

        pairs: list[CellPair] = []
        seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()

        for pair in self.pairs:
            if not _cell_is_valid(pair.image_cell, max_row, max_col):
                continue
            if not _cell_is_valid(pair.text_cell, max_row, max_col):
                continue

            key = (pair.image_cell, pair.text_cell)
            if key in seen:
                continue
            seen.add(key)
            pairs.append(pair)

        return Grid(
            horizontal_lines=horizontal,
            vertical_lines=vertical,
            pairs=pairs,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        normalized = self.normalized()
        return {
            "horizontal_lines": normalized.horizontal_lines,
            "vertical_lines": normalized.vertical_lines,
            "pairs": [p.to_dict() for p in normalized.pairs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Grid:
        grid = cls(
            horizontal_lines=[int(v) for v in data.get("horizontal_lines", [])],
            vertical_lines=[int(v) for v in data.get("vertical_lines", [])],
            pairs=[CellPair.from_dict(p) for p in data.get("pairs", [])],
        )
        return grid.normalized()


def _coerce_cell(value: object) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Invalid cell address: {value!r}")
    return int(value[0]), int(value[1])


def _dedupe_ints(values) -> list[int]:  # noqa: ANN001
    return sorted(set(int(v) for v in values))


def _cell_is_valid(cell: tuple[int, int], max_row: int, max_col: int) -> bool:
    row, col = cell
    # With N horizontal lines there are N + 1 rows; same for vertical lines.
    return 0 <= row <= max_row and 0 <= col <= max_col
