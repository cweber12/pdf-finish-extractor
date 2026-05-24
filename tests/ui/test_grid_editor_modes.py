from __future__ import annotations

from src.ui.editor.grid_editor_modes import mode_hint, mode_uses_crosshair, resolved_mode


def test_resolved_mode_uses_requested_mode_when_checked() -> None:
    assert resolved_mode("grouping", is_checked=True) == "grouping"


def test_resolved_mode_falls_back_to_idle_when_unchecked() -> None:
    assert resolved_mode("grouping", is_checked=False) == "idle"


def test_mode_hint_returns_expected_text() -> None:
    assert "right-click a line" in mode_hint("idle").lower()
    assert "click-drag" in mode_hint("add_h").lower()
    assert "ignore" in mode_hint("omit").lower()


def test_mode_hint_unknown_mode_uses_idle_hint() -> None:
    assert mode_hint("unknown") == mode_hint("idle")


def test_mode_uses_crosshair_for_add_and_omit_modes() -> None:
    assert mode_uses_crosshair("add_h") is True
    assert mode_uses_crosshair("add_v") is True
    assert mode_uses_crosshair("omit") is True
    assert mode_uses_crosshair("idle") is False
    assert mode_uses_crosshair("grouping") is False


