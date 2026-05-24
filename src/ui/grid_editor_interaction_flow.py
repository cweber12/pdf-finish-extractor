from __future__ import annotations

from typing import Literal

MouseButtonName = Literal["left", "middle", "right", "other"]


def mouse_button_name(
    mouse_button: object,
    *,
    left_button: object,
    middle_button: object,
    right_button: object,
) -> MouseButtonName:
    if mouse_button == left_button:
        return "left"
    if mouse_button == middle_button:
        return "middle"
    if mouse_button == right_button:
        return "right"
    return "other"


def hovered_line_from_hit(
    hit_h: int | None,
    hit_v: int | None,
) -> tuple[str, int] | None:
    if hit_h is not None:
        return "h", hit_h
    if hit_v is not None:
        return "v", hit_v
    return None


def placing_preview_value(mode: str, ox: int, oy: int) -> int:
    return max(0, oy if mode == "add_h" else ox)


def begin_omit_preview(start: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int, int, int]]:
    return start, (*start, *start)


def should_reset_zoom_interaction(
    *,
    is_placing: bool,
    has_omit_start: bool,
) -> bool:
    return is_placing or has_omit_start


def wheel_zoom_factor(delta: int, *, step: float = 1.15) -> float | None:
    if delta == 0:
        return None
    return step if delta > 0 else 1.0 / step
