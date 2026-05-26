from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal, cast

_PROFILE_TYPE = "manual_grid"
_PROFILE_VERSION = 2

FieldType = Literal["text", "image"]
CellAddress = tuple[int, int]


@dataclass(frozen=True)
class FieldDefinition:
    """A named field in the extraction recipe."""

    name: str
    field_type: FieldType = "text"
    click_count: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.field_type,
            "click_count": self.click_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FieldDefinition:
        field_type = str(data.get("type", "text")).lower()
        if field_type not in ("text", "image"):
            field_type = "text"
        return cls(
            name=str(data.get("name", "")).strip(),
            field_type=cast(FieldType, field_type),
            click_count=max(1, int(data.get("click_count", 1))),
        )


@dataclass(frozen=True)
class CellGroup:
    """Cells assigned to each Field for one extracted row."""

    field_cells: dict[str, list[CellAddress]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "field_cells": {
                name: [list(cell) for cell in cells]
                for name, cells in self.field_cells.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CellGroup:
        raw = data.get("field_cells", {})
        if not isinstance(raw, dict):
            raw = {}
        return cls(
            field_cells={
                str(name): [_coerce_cell(cell) for cell in cells]
                for name, cells in raw.items()
                if isinstance(cells, list)
            }
        )

    def cells(self) -> list[CellAddress]:
        return [cell for cells in self.field_cells.values() for cell in cells]


@dataclass(frozen=True)
class OmitRegion:
    """A page-specific rectangular area to skip during extraction.

    Coordinates are stored in the same 150-DPI rendered-pixel space as grid
    lines. ``page_index`` is zero-based. Regions are page-specific on purpose:
    they are intended for catalog pages that contain diagrams, renderings, ads,
    or other non-swatch areas inside an otherwise reusable layout.
    """

    page_index: int
    rect: tuple[int, int, int, int]  # x0, y0, x1, y1

    def to_dict(self) -> dict[str, object]:
        return {
            "page_index": self.page_index,
            "rect": list(self.rect),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OmitRegion:
        page_index = int(data.get("page_index", 0))
        rect = _coerce_rect(data.get("rect", [0, 0, 0, 0]))
        return cls(page_index=page_index, rect=rect)


@dataclass
class GridSegment:
    """Grid lines and groups that apply from ``start_page`` onward."""

    start_page: int
    horizontal_lines: list[int] = field(default_factory=list)
    vertical_lines: list[int] = field(default_factory=list)
    groups: list[CellGroup] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "start_page": self.start_page,
            "horizontal_lines": sorted(self.horizontal_lines),
            "vertical_lines": sorted(self.vertical_lines),
            "groups": [group.to_dict() for group in self.groups],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GridSegment:
        return cls(
            start_page=int(data.get("start_page", 0)),
            horizontal_lines=[int(v) for v in data.get("horizontal_lines", [])],
            vertical_lines=[int(v) for v in data.get("vertical_lines", [])],
            groups=[CellGroup.from_dict(group) for group in data.get("groups", [])],
        )


@dataclass
class Grid:
    """Defines a grid layout, field recipe, groups, and omit rules.

    ``horizontal_lines`` and ``vertical_lines`` are pixel coordinates in the
    150-DPI rendered image space used by the editor and extractor.

    ``fields`` defines the ordered extraction recipe. ``groups`` records the
    cells selected for each field in each extracted row.
    """

    horizontal_lines: list[int] = field(default_factory=list)
    vertical_lines: list[int] = field(default_factory=list)
    fields: list[FieldDefinition] = field(default_factory=list)
    groups: list[CellGroup] = field(default_factory=list)
    omitted_pages: list[int] = field(default_factory=list)
    omit_regions: list[OmitRegion] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return (
            not self.horizontal_lines
            and not self.vertical_lines
            and not self.fields
            and not self.groups
            and not self.omitted_pages
            and not self.omit_regions
        )

    @property
    def has_groups(self) -> bool:
        return bool(self.groups)

    def normalized(self) -> Grid:
        horizontal = _dedupe_ints(v for v in self.horizontal_lines if v >= 0)
        vertical = _dedupe_ints(v for v in self.vertical_lines if v >= 0)
        omitted_pages = _dedupe_ints(v for v in self.omitted_pages if v >= 0)
        max_row = len(horizontal)
        max_col = len(vertical)

        fields: list[FieldDefinition] = []
        seen_names: set[str] = set()
        for field_def in self.fields:
            name = field_def.name.strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            fields.append(
                FieldDefinition(
                    name=name,
                    field_type=field_def.field_type,
                    click_count=max(1, int(field_def.click_count)),
                )
            )

        field_by_name = {field_def.name: field_def for field_def in fields}
        groups: list[CellGroup] = []
        seen_groups: set[tuple[tuple[str, tuple[CellAddress, ...]], ...]] = set()
        for group in self.groups:
            field_cells: dict[str, list[CellAddress]] = {}
            for field_def in fields:
                cells = list(group.field_cells.get(field_def.name, []))
                if len(cells) != field_def.click_count:
                    continue
                if not all(_cell_is_valid(cell, max_row, max_col) for cell in cells):
                    continue
                if not _cells_form_rectangle(cells):
                    continue
                field_cells[field_def.name] = cells

            if not field_cells:
                continue
            key = tuple(
                (name, tuple(cells))
                for name, cells in field_cells.items()
                if name in field_by_name
            )
            if key in seen_groups:
                continue
            seen_groups.add(key)
            groups.append(CellGroup(field_cells=field_cells))

        regions: list[OmitRegion] = []
        seen_regions: set[tuple[int, tuple[int, int, int, int]]] = set()
        for region in self.omit_regions:
            if region.page_index < 0:
                continue
            rect = _normalize_rect(region.rect)
            if rect is None:
                continue
            region_key = (region.page_index, rect)
            if region_key in seen_regions:
                continue
            seen_regions.add(region_key)
            regions.append(OmitRegion(page_index=region.page_index, rect=rect))

        return Grid(
            horizontal_lines=horizontal,
            vertical_lines=vertical,
            fields=fields,
            groups=groups,
            omitted_pages=omitted_pages,
            omit_regions=regions,
        )

    def to_dict(self) -> dict[str, object]:
        normalized = self.normalized()
        return {
            "horizontal_lines": normalized.horizontal_lines,
            "vertical_lines": normalized.vertical_lines,
            "fields": [field_def.to_dict() for field_def in normalized.fields],
            "groups": [group.to_dict() for group in normalized.groups],
            "omitted_pages": normalized.omitted_pages,
            "omit_regions": [region.to_dict() for region in normalized.omit_regions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Grid:
        grid = cls(
            horizontal_lines=[int(v) for v in data.get("horizontal_lines", [])],
            vertical_lines=[int(v) for v in data.get("vertical_lines", [])],
            fields=[FieldDefinition.from_dict(v) for v in data.get("fields", [])],
            groups=[CellGroup.from_dict(v) for v in data.get("groups", [])],
            omitted_pages=[int(v) for v in data.get("omitted_pages", [])],
            omit_regions=[OmitRegion.from_dict(r) for r in data.get("omit_regions", [])],
        )
        return grid.normalized()


def cells_form_rectangle(cells: list[CellAddress]) -> bool:
    return _cells_form_rectangle(cells)


def _coerce_cell(value: object) -> CellAddress:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Invalid cell address: {value!r}")
    return int(value[0]), int(value[1])


def _coerce_rect(value: object) -> tuple[int, int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"Invalid omit region rect: {value!r}")
    return int(value[0]), int(value[1]), int(value[2]), int(value[3])


def _normalize_rect(rect: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    x0, y0, x1, y1 = rect
    left, right = sorted((int(x0), int(x1)))
    top, bottom = sorted((int(y0), int(y1)))
    if right - left < 2 or bottom - top < 2:
        return None
    return left, top, right, bottom


def _dedupe_ints(values: Iterable[int]) -> list[int]:
    return sorted(set(int(v) for v in values))


def _cell_is_valid(cell: CellAddress, max_row: int, max_col: int) -> bool:
    row, col = cell
    return 0 <= row <= max_row and 0 <= col <= max_col


def _cells_form_rectangle(cells: list[CellAddress]) -> bool:
    if not cells:
        return False
    unique = set(cells)
    if len(unique) != len(cells):
        return False
    rows = {row for row, _col in cells}
    cols = {col for _row, col in cells}
    expected = {(row, col) for row in rows for col in cols}
    return unique == expected


@dataclass
class GridExtractionProfile:
    """Wraps a :class:`Grid` and its per-page layout history for persistence.

    The ``grid`` carries global settings (fields, omitted pages, omit regions).
    The ``segments`` list records the grid lines and groups in effect from each
    segment's ``start_page`` onward.
    """

    grid: Grid = field(default_factory=Grid)
    segments: list[GridSegment] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_type": _PROFILE_TYPE,
            "version": _PROFILE_VERSION,
            "grid": self.grid.to_dict(),
            "segments": [seg.to_dict() for seg in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GridExtractionProfile:
        if "profile_type" not in data:
            # Migrate old Grid-only format: seed a single segment from the baseline.
            grid = Grid.from_dict(data)
            segments = [
                GridSegment(
                    start_page=0,
                    horizontal_lines=list(grid.horizontal_lines),
                    vertical_lines=list(grid.vertical_lines),
                    groups=list(grid.groups),
                )
            ]
            return cls(grid=grid, segments=segments)

        grid = Grid.from_dict(data.get("grid", {}))
        segments = [GridSegment.from_dict(s) for s in data.get("segments", [])]
        if not segments:
            segments = [
                GridSegment(
                    start_page=0,
                    horizontal_lines=list(grid.horizontal_lines),
                    vertical_lines=list(grid.vertical_lines),
                    groups=list(grid.groups),
                )
            ]
        return cls(grid=grid, segments=segments)
