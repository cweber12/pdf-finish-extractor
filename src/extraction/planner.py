from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import fitz

from src.extraction.grid import CellAddress, CellGroup, FieldDefinition, Grid, GridSegment

# Grid coordinates are stored in 150-DPI rendered-pixel space.
_GRID_DPI = 150
_GRID_SCALE = _GRID_DPI / 72.0  # grid pixels per PDF point


@dataclass(frozen=True)
class ResolvedField:
    definition: FieldDefinition
    rect: fitz.Rect


@dataclass(frozen=True)
class ResolvedGroup:
    source: CellGroup
    fields: list[ResolvedField]


class ExtractionPlanner:
    """Resolve page-local field rectangles for extraction."""

    def __init__(
        self,
        grid: Grid,
        *,
        segments: list[GridSegment] | None = None,
    ) -> None:
        self._grid = grid.normalized()
        self._segments: list[GridSegment] = (
            sorted(segments, key=lambda s: s.start_page) if segments else []
        )

    def plan_page(self, page: fitz.Page) -> list[ResolvedGroup]:
        h_pts, v_pts = self._page_boundaries(page)
        omit_regions = self._omit_regions_for_page(page)
        _, _, groups = self._layout_for_page(int(page.number))
        fields = self._grid.fields

        resolved: list[ResolvedGroup] = []
        for group in groups:
            resolved_fields: list[ResolvedField] = []
            skip_group = False
            for field_def in fields:
                cells = group.field_cells.get(field_def.name)
                if not cells:
                    continue
                rect = self._field_rect(cells, h_pts, v_pts)
                if rect is None:
                    continue
                rect = page.rect & rect
                if rect.is_empty:
                    continue
                if any(_rects_intersect(rect, omitted) for omitted in omit_regions):
                    skip_group = True
                    break
                resolved_fields.append(ResolvedField(field_def, rect))

            if not skip_group and resolved_fields:
                resolved.append(ResolvedGroup(source=group, fields=resolved_fields))

        return resolved

    def _layout_for_page(
        self, page_index: int
    ) -> tuple[list[int], list[int], list[CellGroup]]:
        if not self._segments:
            return (
                self._grid.horizontal_lines,
                self._grid.vertical_lines,
                self._grid.groups,
            )
        applicable = [s for s in self._segments if s.start_page <= page_index]
        seg = applicable[-1] if applicable else self._segments[0]
        return seg.horizontal_lines, seg.vertical_lines, seg.groups

    def _omit_regions_for_page(self, page: fitz.Page) -> list[fitz.Rect]:
        page_index = int(getattr(page, "number", 0))
        regions: list[fitz.Rect] = []
        for region in self._grid.omit_regions:
            if region.page_index != page_index:
                continue

            x0, y0, x1, y1 = region.rect
            rect = fitz.Rect(
                x0 / _GRID_SCALE,
                y0 / _GRID_SCALE,
                x1 / _GRID_SCALE,
                y1 / _GRID_SCALE,
            )
            rect = page.rect & rect
            if not rect.is_empty:
                regions.append(rect)
        return regions

    def _page_boundaries(self, page: fitz.Page) -> tuple[list[float], list[float]]:
        h_lines, v_lines, _ = self._layout_for_page(int(page.number))

        h_pts = [0.0]
        h_pts.extend(y / _GRID_SCALE for y in h_lines)
        h_pts.append(float(page.rect.height))

        v_pts = [0.0]
        v_pts.extend(x / _GRID_SCALE for x in v_lines)
        v_pts.append(float(page.rect.width))

        h_pts = _dedupe_sorted(_clamp(v, 0.0, float(page.rect.height)) for v in h_pts)
        v_pts = _dedupe_sorted(_clamp(v, 0.0, float(page.rect.width)) for v in v_pts)
        return h_pts, v_pts

    @staticmethod
    def _field_rect(
        cells: list[CellAddress],
        h_pts: list[float],
        v_pts: list[float],
    ) -> fitz.Rect | None:
        rects = [ExtractionPlanner._cell_rect(cell, h_pts, v_pts) for cell in cells]
        valid_rects = [rect for rect in rects if rect is not None]
        if len(valid_rects) != len(cells):
            return None
        result = fitz.Rect(valid_rects[0])
        for rect in valid_rects[1:]:
            result |= rect
        return result

    @staticmethod
    def _cell_rect(
        cell: CellAddress,
        h_pts: list[float],
        v_pts: list[float],
    ) -> fitz.Rect | None:
        row, col = cell
        if row < 0 or col < 0 or row >= len(h_pts) - 1 or col >= len(v_pts) - 1:
            return None
        return fitz.Rect(v_pts[col], h_pts[row], v_pts[col + 1], h_pts[row + 1])


def _rects_intersect(a: fitz.Rect, b: fitz.Rect) -> bool:
    return not (a.x1 <= b.x0 or a.x0 >= b.x1 or a.y1 <= b.y0 or a.y0 >= b.y1)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _dedupe_sorted(values: Iterable[float], *, tolerance: float = 0.01) -> list[float]:
    result: list[float] = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
    return result
