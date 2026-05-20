from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CellType(StrEnum):
    IMAGE = "image"
    TEXT = "text"
    IGNORED = "ignored"


class PairDirection(StrEnum):
    RIGHT = "right"
    LEFT = "left"
    BELOW = "below"
    ABOVE = "above"


@dataclass
class Grid:
    """Defines a grid layout over a PDF page.

    ``horizontal_lines`` and ``vertical_lines`` are pixel coordinates in the
    rendered image space (at the viewer's DPI). They are converted to PDF
    points by :class:`~src.extraction.extractor.Extractor` before use.

    ``cell_types`` maps ``(row_index, col_index)`` to a :class:`CellType`.
    Any cell not in the mapping is treated as :attr:`CellType.IGNORED`.

    ``pair_direction`` describes the spatial relationship from each image cell
    to its associated text cell.
    """

    horizontal_lines: list[int] = field(default_factory=list)
    vertical_lines: list[int] = field(default_factory=list)
    cell_types: dict[tuple[int, int], CellType] = field(default_factory=dict)
    pair_direction: PairDirection = PairDirection.RIGHT

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "horizontal_lines": self.horizontal_lines,
            "vertical_lines": self.vertical_lines,
            "cells": [
                {"row": r, "col": c, "type": t.value}
                for (r, c), t in self.cell_types.items()
            ],
            "pair_direction": self.pair_direction.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Grid:
        cell_types = {
            (entry["row"], entry["col"]): CellType(entry["type"])
            for entry in data.get("cells", [])
        }
        return cls(
            horizontal_lines=data.get("horizontal_lines", []),
            vertical_lines=data.get("vertical_lines", []),
            cell_types=cell_types,
            pair_direction=PairDirection(data.get("pair_direction", "right")),
        )
