from __future__ import annotations

from src.ui.editor.grid_editor_omit import (
    decide_omit_move,
    decide_omit_release,
    normalized_omit_rect,
)


def test_normalized_omit_rect_sorts_coordinates() -> None:
    assert normalized_omit_rect((20, 30), (10, 15)) == (10, 15, 20, 30)


def test_normalized_omit_rect_rejects_small_rectangles() -> None:
    assert normalized_omit_rect((0, 0), (7, 20)) is None
    assert normalized_omit_rect((0, 0), (20, 7)) is None


def test_decide_omit_move_updates_preview_while_dragging() -> None:
    decision = decide_omit_move(
        mode="omit",
        omit_start=(5, 6),
        clamped_point=(20, 30),
        omit_region_index_at_point=None,
    )
    assert decision.consumed is True
    assert decision.preview_rect == (5, 6, 20, 30)
    assert decision.remove_region_index is None


def test_decide_omit_move_removes_region_on_hover_when_not_dragging() -> None:
    decision = decide_omit_move(
        mode="omit",
        omit_start=None,
        clamped_point=(20, 30),
        omit_region_index_at_point=3,
    )
    assert decision.consumed is True
    assert decision.remove_region_index == 3
    assert decision.hint == "Ignored section removed."


def test_decide_omit_move_non_omit_mode_not_consumed() -> None:
    decision = decide_omit_move(
        mode="idle",
        omit_start=None,
        clamped_point=(20, 30),
        omit_region_index_at_point=None,
    )
    assert decision.consumed is False


def test_decide_omit_release_adds_region_when_valid() -> None:
    decision = decide_omit_release(
        mode="omit",
        omit_start=(10, 10),
        clamped_release_point=(30, 35),
    )
    assert decision.consumed is True
    assert decision.normalized_rect == (10, 10, 30, 35)
    assert "Ignored section added" in (decision.hint or "")
    assert decision.clear_start is True
    assert decision.clear_preview is True


def test_decide_omit_release_rejects_small_region() -> None:
    decision = decide_omit_release(
        mode="omit",
        omit_start=(10, 10),
        clamped_release_point=(14, 14),
    )
    assert decision.consumed is True
    assert decision.normalized_rect is None
    assert decision.hint == "Ignored section was too small to save."
    assert decision.clear_start is True
    assert decision.clear_preview is True


def test_decide_omit_release_non_omit_mode_not_consumed() -> None:
    decision = decide_omit_release(
        mode="idle",
        omit_start=(10, 10),
        clamped_release_point=(30, 35),
    )
    assert decision.consumed is False


