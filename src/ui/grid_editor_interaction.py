from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MouseButtonName = Literal["left", "middle", "right", "other"]
MoveAction = Literal["pan", "drag_line", "omit_drag", "placing_preview", "hover"]
ReleaseAction = Literal["end_pan", "ignore", "omit_release", "finalize_drag", "finalize_placing", "none"]


@dataclass(frozen=True)
class MoveDecision:
    action: MoveAction


@dataclass(frozen=True)
class ReleaseDecision:
    action: ReleaseAction


def decide_move_action(
    *,
    has_pan_anchor: bool,
    has_dragging: bool,
    has_omit_drag: bool,
    is_placing: bool,
) -> MoveDecision:
    if has_pan_anchor:
        return MoveDecision(action="pan")
    if has_dragging:
        return MoveDecision(action="drag_line")
    if has_omit_drag:
        return MoveDecision(action="omit_drag")
    if is_placing:
        return MoveDecision(action="placing_preview")
    return MoveDecision(action="hover")


def decide_release_action(
    *,
    mouse_button: MouseButtonName,
    mode: str,
    has_omit_start: bool,
    has_dragging: bool,
    is_placing: bool,
) -> ReleaseDecision:
    if mouse_button == "middle":
        return ReleaseDecision(action="end_pan")
    if mouse_button != "left":
        return ReleaseDecision(action="ignore")
    if has_omit_start and mode == "omit":
        return ReleaseDecision(action="omit_release")
    if has_dragging:
        return ReleaseDecision(action="finalize_drag")
    if is_placing:
        return ReleaseDecision(action="finalize_placing")
    return ReleaseDecision(action="none")
