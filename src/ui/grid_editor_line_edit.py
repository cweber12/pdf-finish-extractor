from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LineKind = Literal["h", "v"]


@dataclass(frozen=True)
class PlacementDecision:
    lines: list[int]
    clear_groups_for_grid_change: bool
    hint: str


def bounded_line_value(
    *,
    line_kind: LineKind,
    lines: list[int],
    max_value: int | None,
    index: int,
    value: int,
    min_gap: int,
) -> int:
    if max_value is None:
        return max(0, value)

    if index < 0 or index >= len(lines):
        return max(0, min(max_value, value))

    lower = 0 if index == 0 else lines[index - 1] + min_gap
    upper = max_value if index == len(lines) - 1 else lines[index + 1] - min_gap
    if lower > upper:
        return lines[index]
    return max(lower, min(upper, value))


def can_place_line(
    *,
    line_kind: LineKind,
    lines: list[int],
    max_value: int | None,
    value: int,
    min_gap: int,
) -> bool:
    if max_value is None:
        return False
    if value <= 0 or value >= max_value:
        return False
    return all(abs(existing - value) >= min_gap for existing in lines)


def apply_line_placement(
    *,
    line_kind: LineKind,
    lines: list[int],
    max_value: int | None,
    preview_value: int | None,
    min_gap: int,
) -> PlacementDecision:
    if preview_value is None:
        return PlacementDecision(
            lines=list(lines),
            clear_groups_for_grid_change=False,
            hint="",
        )

    if not can_place_line(
        line_kind=line_kind,
        lines=lines,
        max_value=max_value,
        value=preview_value,
        min_gap=min_gap,
    ):
        hint = (
            "Row boundary is too close to another line or page edge."
            if line_kind == "h"
            else "Column boundary is too close to another line or page edge."
        )
        return PlacementDecision(
            lines=list(lines),
            clear_groups_for_grid_change=False,
            hint=hint,
        )

    new_lines = [*lines, preview_value]
    new_lines.sort()
    hint = (
        "Row boundary added. Drag its handle to adjust."
        if line_kind == "h"
        else "Column boundary added. Drag its handle to adjust."
    )
    return PlacementDecision(
        lines=new_lines,
        clear_groups_for_grid_change=True,
        hint=hint,
    )
