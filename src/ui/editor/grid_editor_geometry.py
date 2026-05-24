from __future__ import annotations

from src.extraction.grid import OmitRegion


def grid_orig_boundaries(
    horizontal_lines: list[int],
    vertical_lines: list[int],
    *,
    page_height: int,
    page_width: int,
) -> tuple[list[int], list[int]]:
    return (
        [0] + sorted(horizontal_lines) + [page_height],
        [0] + sorted(vertical_lines) + [page_width],
    )


def cell_at_orig_point(
    ox: int,
    oy: int,
    *,
    page_height: int,
    page_width: int,
    horizontal_lines: list[int],
    vertical_lines: list[int],
) -> tuple[int, int] | None:
    if ox < 0 or oy < 0 or ox >= page_width or oy >= page_height:
        return None

    h, v = grid_orig_boundaries(
        horizontal_lines,
        vertical_lines,
        page_height=page_height,
        page_width=page_width,
    )
    for ri in range(len(h) - 1):
        if h[ri] <= oy < h[ri + 1]:
            for ci in range(len(v) - 1):
                if v[ci] <= ox < v[ci + 1]:
                    return ri, ci
    return None


def omit_region_index_at_orig_point(
    ox: int,
    oy: int,
    *,
    regions: list[OmitRegion],
    page_index: int,
) -> int | None:
    for idx in range(len(regions) - 1, -1, -1):
        region = regions[idx]
        if region.page_index != page_index:
            continue
        x0, y0, x1, y1 = region.rect
        if x0 <= ox <= x1 and y0 <= oy <= y1:
            return idx
    return None


def clamped_orig_point(
    ox: int,
    oy: int,
    *,
    page_height: int | None,
    page_width: int | None,
) -> tuple[int, int]:
    if page_height is None or page_width is None:
        return max(0, ox), max(0, oy)
    return (
        max(0, min(page_width, ox)),
        max(0, min(page_height, oy)),
    )

