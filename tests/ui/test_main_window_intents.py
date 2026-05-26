from src.ui.shell.main_window_intents import (
    apply_pattern_preflight_error,
    busy_guard_message,
    extract_preflight_error,
    named_event_message,
    save_profile_preflight_error,
)


def test_busy_guard_message_maps_each_action() -> None:
    assert busy_guard_message("open_pdf") == "Cancel extraction before opening another PDF."
    assert busy_guard_message("change_profile") == "Cancel extraction before changing profiles."
    assert busy_guard_message("save_profile") == "Cancel extraction before saving a profile."
    assert busy_guard_message("apply_pattern") == "Cancel extraction before applying a pattern."
    assert busy_guard_message("delete_layout") == "Cancel extraction before deleting a layout."
    assert busy_guard_message("change_mode") == "Cancel extraction before switching modes."


def test_save_profile_preflight_error_when_profile_missing() -> None:
    assert save_profile_preflight_error(profile_exists=False) == (
        "Add at least one grid line before saving a profile."
    )
    assert save_profile_preflight_error(profile_exists=True) is None


def test_apply_pattern_preflight_error_when_pattern_missing() -> None:
    assert apply_pattern_preflight_error(profile_exists=False) == (
        "Crop an image and define text sections before applying a pattern."
    )
    assert apply_pattern_preflight_error(profile_exists=True) is None


def test_extract_preflight_error_prefers_missing_pdf() -> None:
    assert extract_preflight_error(pdf_path=None, profile_exists=False) == (
        "Open a PDF before extracting."
    )
    assert extract_preflight_error(pdf_path="", profile_exists=True) == (
        "Open a PDF before extracting."
    )


def test_extract_preflight_error_for_missing_profile_only() -> None:
    assert extract_preflight_error(pdf_path="sample.pdf", profile_exists=False) == (
        "Create or apply a grid profile before extracting."
    )
    assert extract_preflight_error(pdf_path="sample.pdf", profile_exists=True) is None


def test_named_event_message() -> None:
    assert named_event_message("Profile saved", "Acme") == "Profile saved: Acme"


