from src.ui.extraction_feedback import (
    coerce_extracted_groups,
    extraction_completion_message,
    extraction_failure_toast,
    extraction_progress_status,
    extraction_progress_value,
    toolbar_state_for_running,
)


def test_toolbar_state_for_running_true_disables_edit_actions() -> None:
    state = toolbar_state_for_running(True)

    assert state.open_enabled is False
    assert state.profile_enabled is False
    assert state.extract_enabled is False
    assert state.grid_enabled is False
    assert state.cancel_visible is True
    assert state.cancel_enabled is True
    assert state.progress_visible is True
    assert state.progress_value == 0


def test_toolbar_state_for_running_false_enables_edit_actions() -> None:
    state = toolbar_state_for_running(False)

    assert state.open_enabled is True
    assert state.profile_enabled is True
    assert state.extract_enabled is True
    assert state.grid_enabled is True
    assert state.cancel_visible is False
    assert state.cancel_enabled is False
    assert state.progress_visible is False
    assert state.progress_value == 0


def test_extraction_progress_value_handles_bounds() -> None:
    assert extraction_progress_value(0, 4) == 25
    assert extraction_progress_value(5, 4) == 100
    assert extraction_progress_value(-5, 4) == 0
    assert extraction_progress_value(1, 0) == 0


def test_extraction_progress_status_formats_expected_text() -> None:
    assert (
        extraction_progress_status(2, 10, 7)
        == "Extracting page 3/10 • 7 groups found"
    )


def test_coerce_extracted_groups_preserves_list_only() -> None:
    assert coerce_extracted_groups([1, 2]) == [1, 2]
    assert coerce_extracted_groups((1, 2)) == []
    assert coerce_extracted_groups("abc") == []


def test_extraction_completion_message_by_mode() -> None:
    assert extraction_completion_message(3, False) == (
        "Extraction complete: 3 groups found.",
        True,
    )
    assert extraction_completion_message(3, True) == (
        "Extraction cancelled: 3 groups found.",
        False,
    )


def test_extraction_failure_toast_truncates_long_detail() -> None:
    long_error = "x" * 130
    assert extraction_failure_toast(long_error) == f"Extraction failed: {'x' * 120}…"
    assert extraction_failure_toast("bad page") == "Extraction failed: bad page"
