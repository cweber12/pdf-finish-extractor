from src.ui.grid_editor_interaction_flow import (
    begin_omit_preview,
    hovered_line_from_hit,
    mouse_button_name,
    placing_preview_value,
    should_reset_zoom_interaction,
    wheel_zoom_factor,
)


def test_mouse_button_name_maps_known_buttons() -> None:
    assert mouse_button_name("L", left_button="L", middle_button="M", right_button="R") == "left"
    assert mouse_button_name("M", left_button="L", middle_button="M", right_button="R") == "middle"
    assert mouse_button_name("R", left_button="L", middle_button="M", right_button="R") == "right"
    assert mouse_button_name("X", left_button="L", middle_button="M", right_button="R") == "other"


def test_hovered_line_from_hit_prefers_horizontal_then_vertical() -> None:
    assert hovered_line_from_hit(2, 3) == ("h", 2)
    assert hovered_line_from_hit(None, 3) == ("v", 3)
    assert hovered_line_from_hit(None, None) is None


def test_placing_preview_value_uses_mode_axis() -> None:
    assert placing_preview_value("add_h", 120, 80) == 80
    assert placing_preview_value("add_v", 120, 80) == 120
    assert placing_preview_value("other", -5, 10) == 0


def test_begin_omit_preview_returns_start_and_preview_rect() -> None:
    start, preview = begin_omit_preview((11, 22))
    assert start == (11, 22)
    assert preview == (11, 22, 11, 22)


def test_zoom_interaction_reset_predicate() -> None:
    assert should_reset_zoom_interaction(is_placing=True, has_omit_start=False) is True
    assert should_reset_zoom_interaction(is_placing=False, has_omit_start=True) is True
    assert should_reset_zoom_interaction(is_placing=False, has_omit_start=False) is False


def test_wheel_zoom_factor() -> None:
    assert wheel_zoom_factor(0) is None
    assert wheel_zoom_factor(120) == 1.15
    assert wheel_zoom_factor(-120) == 1.0 / 1.15
