from __future__ import annotations

from dataclasses import dataclass

from src.extraction.grid import CellGroup, FieldDefinition, Grid, GridSegment, OmitRegion


@dataclass(frozen=True)
class InteractionResetState:
    pending_group_cells: list[tuple[int, int]]
    hovered_cell: tuple[int, int] | None
    hovered_line: tuple[str, int] | None
    omit_start: tuple[int, int] | None
    omit_preview: tuple[int, int, int, int] | None


@dataclass(frozen=True)
class AppliedProfileState:
    horizontal_lines: list[int]
    vertical_lines: list[int]
    fields: list[FieldDefinition]
    groups: list[CellGroup]
    omitted_pages: set[int]
    omit_regions: list[OmitRegion]


def baseline_segments(
    horizontal_lines: list[int],
    vertical_lines: list[int],
    groups: list[CellGroup],
) -> list[GridSegment]:
    return [
        GridSegment(
            start_page=0,
            horizontal_lines=list(horizontal_lines),
            vertical_lines=list(vertical_lines),
            groups=list(groups),
        )
    ]


def profile_from_editor_state(
    *,
    horizontal_lines: list[int],
    vertical_lines: list[int],
    fields: list[FieldDefinition],
    groups: list[CellGroup],
    omitted_pages: set[int],
    omit_regions: list[OmitRegion],
) -> Grid | None:
    if not horizontal_lines and not vertical_lines:
        return None
    return Grid(
        horizontal_lines=sorted(horizontal_lines),
        vertical_lines=sorted(vertical_lines),
        fields=list(fields),
        groups=list(groups),
        omitted_pages=sorted(omitted_pages),
        omit_regions=list(omit_regions),
    )


def applied_profile_state(grid: Grid) -> AppliedProfileState:
    return AppliedProfileState(
        horizontal_lines=sorted(grid.horizontal_lines),
        vertical_lines=sorted(grid.vertical_lines),
        fields=list(grid.fields),
        groups=list(grid.groups),
        omitted_pages=set(grid.omitted_pages),
        omit_regions=list(grid.omit_regions),
    )


def cleared_grid_collections() -> tuple[list[int], list[int], list[CellGroup], set[int], list[OmitRegion]]:
    return [], [], [], set(), []


def interaction_reset_state() -> InteractionResetState:
    return InteractionResetState(
        pending_group_cells=[],
        hovered_cell=None,
        hovered_line=None,
        omit_start=None,
        omit_preview=None,
    )
