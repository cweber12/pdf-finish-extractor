from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PatternPressAction = Literal[
    "begin_image_crop",
    "begin_drag_image",
    "begin_resize_image",
    "begin_drag_text_region",
    "begin_resize_text_region",
    "begin_drag_section_divider",
    "begin_omit",
    "begin_pan",
    "right_click",
    "none",
]

PatternMoveAction = Literal[
    "pan",
    "resize_image",
    "drag_image",
    "resize_text",
    "drag_text",
    "drag_section_divider",
    "omit_drag",
    "crop_preview",
    "hover",
]

PatternReleaseAction = Literal[
    "end_pan",
    "finalize_image_crop",
    "finalize_drag",
    "finalize_resize",
    "finalize_section_divider",
    "finalize_omit",
    "ignore",
]


@dataclass(frozen=True)
class PressDecision:
    action: PatternPressAction


@dataclass(frozen=True)
class MoveDecision:
    action: PatternMoveAction


@dataclass(frozen=True)
class ReleaseDecision:
    action: PatternReleaseAction


def decide_press_action(
    mouse_button: str,
    mode: str,
    hit_target: str,
) -> PressDecision:
    if mouse_button == "right":
        return PressDecision("right_click")
    if mouse_button == "middle":
        return PressDecision("begin_pan")

    # Left button
    if mode == "crop_image":
        return PressDecision("begin_image_crop")
    if mode == "omit":
        return PressDecision("begin_omit")

    # Idle mode — dispatch by hit
    if hit_target.startswith("image_corner") or hit_target.startswith("image_edge"):
        return PressDecision("begin_resize_image")
    if hit_target == "image_body":
        return PressDecision("begin_drag_image")
    if hit_target.startswith("text_corner") or hit_target.startswith("text_edge"):
        return PressDecision("begin_resize_text_region")
    if hit_target == "text_body":
        return PressDecision("begin_drag_text_region")
    if hit_target.startswith("section_divider"):
        return PressDecision("begin_drag_section_divider")

    return PressDecision("none")


def decide_move_action(
    has_pan_anchor: bool,
    active_resize: str | None,
    active_drag: str | None,
    active_section_divider: int | None,
    is_cropping: bool,
    has_omit_start: bool,
) -> MoveDecision:
    if has_pan_anchor:
        return MoveDecision("pan")
    if has_omit_start:
        return MoveDecision("omit_drag")
    if active_resize is not None:
        if active_resize.startswith("image"):
            return MoveDecision("resize_image")
        return MoveDecision("resize_text")
    if active_drag is not None:
        if active_drag == "image":
            return MoveDecision("drag_image")
        return MoveDecision("drag_text")
    if active_section_divider is not None:
        return MoveDecision("drag_section_divider")
    if is_cropping:
        return MoveDecision("crop_preview")
    return MoveDecision("hover")


def decide_release_action(
    mouse_button: str,
    has_pan_anchor: bool,
    active_resize: str | None,
    active_drag: str | None,
    active_section_divider: int | None,
    is_cropping: bool,
    has_omit_start: bool,
) -> ReleaseDecision:
    if mouse_button == "middle" and has_pan_anchor:
        return ReleaseDecision("end_pan")
    if mouse_button != "left":
        return ReleaseDecision("ignore")
    if is_cropping:
        return ReleaseDecision("finalize_image_crop")
    if has_omit_start:
        return ReleaseDecision("finalize_omit")
    if active_resize is not None:
        return ReleaseDecision("finalize_resize")
    if active_drag is not None:
        return ReleaseDecision("finalize_drag")
    if active_section_divider is not None:
        return ReleaseDecision("finalize_section_divider")
    return ReleaseDecision("ignore")
