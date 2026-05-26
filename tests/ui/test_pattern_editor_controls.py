from __future__ import annotations

from src.ui.editor.pattern_editor import PatternEditor


def test_apply_pattern_button_emits_requested_signal(qapp) -> None:
    editor = PatternEditor()
    received: list[bool] = []
    editor.apply_requested.connect(lambda: received.append(True))

    editor._apply_pattern_btn.click()  # noqa: SLF001 - UI seam under test

    assert received == [True]