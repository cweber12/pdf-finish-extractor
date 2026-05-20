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
            image_cell=tuple(data["image_cell"]),  # type: ignore[arg-type]
            text_cell=tuple(data["text_cell"]),    # type: ignore[arg-type]
        )


@dataclass
class Grid:
    """Defines a grid layout and explicit cell pairings for a PDF page.

    ``horizontal_lines`` and ``vertical_lines`` are pixel coordinates in the
    150 DPI rendered image space (the same space used by :class:`~src.extraction.extractor.Extractor`).
    Divide by ``150 / 72 ≈ 2.0833`` to convert to PDF points.

    ``pairs`` explicitly lists which cells go together. Each :class:`CellPair`
    names the image cell and the text cell (which holds the material ID).
    """

    horizontal_lines: list[int] = field(default_factory=list)
    vertical_lines: list[int] = field(default_factory=list)
    pairs: list[CellPair] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "horizontal_lines": self.horizontal_lines,
            "vertical_lines": self.vertical_lines,
            "pairs": [p.to_dict() for p in self.pairs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Grid:
        return cls(
            horizontal_lines=list(data.get("horizontal_lines", [])),
            vertical_lines=list(data.get("vertical_lines", [])),
            pairs=[CellPair.from_dict(p) for p in data.get("pairs", [])],
        )
