from __future__ import annotations

from dataclasses import dataclass

from src.extraction.grid import CellGroup, GridSegment


@dataclass(frozen=True)
class SegmentNavState:
    label: str
    prev_enabled: bool
    next_enabled: bool


@dataclass(frozen=True)
class SegmentLayoutState:
    horizontal_lines: list[int]
    vertical_lines: list[int]
    groups: list[CellGroup]


def segment_index_for_page(segments: list[GridSegment], page_index: int) -> int:
    best = 0
    for i, seg in enumerate(segments):
        if seg.start_page <= page_index:
            best = i
        else:
            break
    return best


def record_segment_change(
    *,
    segments: list[GridSegment],
    page_index: int,
    horizontal_lines: list[int],
    vertical_lines: list[int],
    groups: list[CellGroup],
) -> list[GridSegment]:
    if not segments:
        return []

    next_segments = list(segments)
    seg_idx = segment_index_for_page(next_segments, page_index)
    new_seg = GridSegment(
        start_page=page_index,
        horizontal_lines=list(horizontal_lines),
        vertical_lines=list(vertical_lines),
        groups=list(groups),
    )
    if next_segments[seg_idx].start_page == page_index:
        next_segments[seg_idx] = new_seg
    else:
        next_segments.insert(seg_idx + 1, new_seg)
    return next_segments


def layout_state_for_page(
    segments: list[GridSegment],
    page_index: int,
) -> SegmentLayoutState | None:
    if not segments:
        return None
    seg = segments[segment_index_for_page(segments, page_index)]
    return SegmentLayoutState(
        horizontal_lines=sorted(seg.horizontal_lines),
        vertical_lines=sorted(seg.vertical_lines),
        groups=list(seg.groups),
    )


def segment_nav_state(segments: list[GridSegment], current_page_index: int) -> SegmentNavState:
    total = len(segments)
    if total == 0:
        return SegmentNavState(label="—", prev_enabled=False, next_enabled=False)

    idx = segment_index_for_page(segments, current_page_index)
    return SegmentNavState(
        label=f"{idx + 1}/{total}",
        prev_enabled=idx > 0,
        next_enabled=idx < total - 1,
    )


def adjacent_segment_start_page(
    segments: list[GridSegment],
    current_page_index: int,
    direction: str,
) -> int | None:
    if not segments:
        return None
    idx = segment_index_for_page(segments, current_page_index)
    if direction == "prev":
        if idx > 0:
            return segments[idx - 1].start_page
        return None
    if direction == "next":
        if idx < len(segments) - 1:
            return segments[idx + 1].start_page
        return None
    return None

