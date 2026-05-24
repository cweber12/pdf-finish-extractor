from __future__ import annotations

from src.ui.editor.grid_editor_interaction import (
    decide_move_action,
    decide_press_action,
    decide_release_action,
)


def test_decide_press_action_precedence() -> None:
    assert decide_press_action(
        mouse_button="right",
        mode="grouping",
        hit_h_index=1,
        hit_v_index=2,
    ).action == "right_click"
    assert decide_press_action(
        mouse_button="middle",
        mode="grouping",
        hit_h_index=1,
        hit_v_index=2,
    ).action == "begin_pan"
    assert decide_press_action(
        mouse_button="left",
        mode="grouping",
        hit_h_index=1,
        hit_v_index=2,
    ).action == "begin_drag_h"
    assert decide_press_action(
        mouse_button="left",
        mode="grouping",
        hit_h_index=None,
        hit_v_index=2,
    ).action == "begin_drag_v"


def test_decide_press_action_mode_fallbacks_without_hits() -> None:
    assert decide_press_action(
        mouse_button="left",
        mode="add_h",
        hit_h_index=None,
        hit_v_index=None,
    ).action == "begin_place_h"
    assert decide_press_action(
        mouse_button="left",
        mode="add_v",
        hit_h_index=None,
        hit_v_index=None,
    ).action == "begin_place_v"
    assert decide_press_action(
        mouse_button="left",
        mode="grouping",
        hit_h_index=None,
        hit_v_index=None,
    ).action == "group_click"
    assert decide_press_action(
        mouse_button="left",
        mode="omit",
        hit_h_index=None,
        hit_v_index=None,
    ).action == "begin_omit"
    assert decide_press_action(
        mouse_button="left",
        mode="idle",
        hit_h_index=None,
        hit_v_index=None,
    ).action == "none"


def test_decide_move_action_precedence() -> None:
    assert decide_move_action(
        has_pan_anchor=True,
        has_dragging=True,
        has_omit_drag=True,
        is_placing=True,
    ).action == "pan"
    assert decide_move_action(
        has_pan_anchor=False,
        has_dragging=True,
        has_omit_drag=True,
        is_placing=True,
    ).action == "drag_line"
    assert decide_move_action(
        has_pan_anchor=False,
        has_dragging=False,
        has_omit_drag=True,
        is_placing=True,
    ).action == "omit_drag"
    assert decide_move_action(
        has_pan_anchor=False,
        has_dragging=False,
        has_omit_drag=False,
        is_placing=True,
    ).action == "placing_preview"
    assert decide_move_action(
        has_pan_anchor=False,
        has_dragging=False,
        has_omit_drag=False,
        is_placing=False,
    ).action == "hover"


def test_decide_release_action_precedence_and_modes() -> None:
    assert decide_release_action(
        mouse_button="middle",
        mode="omit",
        has_omit_start=True,
        has_dragging=True,
        is_placing=True,
    ).action == "end_pan"
    assert decide_release_action(
        mouse_button="right",
        mode="omit",
        has_omit_start=True,
        has_dragging=True,
        is_placing=True,
    ).action == "ignore"
    assert decide_release_action(
        mouse_button="left",
        mode="omit",
        has_omit_start=True,
        has_dragging=True,
        is_placing=True,
    ).action == "omit_release"
    assert decide_release_action(
        mouse_button="left",
        mode="idle",
        has_omit_start=False,
        has_dragging=True,
        is_placing=True,
    ).action == "finalize_drag"
    assert decide_release_action(
        mouse_button="left",
        mode="idle",
        has_omit_start=False,
        has_dragging=False,
        is_placing=True,
    ).action == "finalize_placing"
    assert decide_release_action(
        mouse_button="left",
        mode="idle",
        has_omit_start=False,
        has_dragging=False,
        is_placing=False,
    ).action == "none"


