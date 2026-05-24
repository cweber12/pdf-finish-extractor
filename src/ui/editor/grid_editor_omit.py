from __future__ import annotations

from dataclasses import dataclass

Point = tuple[int, int]
Rect = tuple[int, int, int, int]

_MIN_OMIT_RECT_SIZE = 8


@dataclass(frozen=True)
class OmitMoveDecision:
    consumed: bool
    preview_rect: Rect | None = None
    remove_region_index: int | None = None
    hint: str | None = None


@dataclass(frozen=True)
class OmitReleaseDecision:
    consumed: bool
    normalized_rect: Rect | None = None
    hint: str | None = None
    clear_start: bool = False
    clear_preview: bool = False


def normalized_omit_rect(start: Point, end: Point) -> Rect | None:
    x0, y0 = start
    x1, y1 = end
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    if right - left < _MIN_OMIT_RECT_SIZE or bottom - top < _MIN_OMIT_RECT_SIZE:
        return None
    return left, top, right, bottom


def decide_omit_move(
    *,
    mode: str,
    omit_start: Point | None,
    clamped_point: Point,
    omit_region_index_at_point: int | None,
) -> OmitMoveDecision:
    if mode != "omit":
        return OmitMoveDecision(consumed=False)

    if omit_start is not None:
        return OmitMoveDecision(
            consumed=True,
            preview_rect=(*omit_start, *clamped_point),
        )

    if omit_region_index_at_point is not None:
        return OmitMoveDecision(
            consumed=True,
            remove_region_index=omit_region_index_at_point,
            hint="Ignored section removed.",
        )

    return OmitMoveDecision(consumed=True)


def decide_omit_release(
    *,
    mode: str,
    omit_start: Point | None,
    clamped_release_point: Point,
) -> OmitReleaseDecision:
    if mode != "omit" or omit_start is None:
        return OmitReleaseDecision(consumed=False)

    rect = normalized_omit_rect(omit_start, clamped_release_point)
    if rect is not None:
        return OmitReleaseDecision(
            consumed=True,
            normalized_rect=rect,
            hint="Ignored section added for this page. Right-click it in Ignore Area mode to remove it.",
            clear_start=True,
            clear_preview=True,
        )

    return OmitReleaseDecision(
        consumed=True,
        normalized_rect=None,
        hint="Ignored section was too small to save.",
        clear_start=True,
        clear_preview=True,
    )

