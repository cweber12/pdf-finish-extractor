from __future__ import annotations

from typing import Literal

BusyAction = Literal["open_pdf", "change_profile", "save_profile", "delete_layout"]

_BUSY_MESSAGES: dict[BusyAction, str] = {
    "open_pdf": "Cancel extraction before opening another PDF.",
    "change_profile": "Cancel extraction before changing profiles.",
    "save_profile": "Cancel extraction before saving a profile.",
    "delete_layout": "Cancel extraction before deleting a layout.",
}


def busy_guard_message(action: BusyAction) -> str:
    return _BUSY_MESSAGES[action]


def save_profile_preflight_error(profile_exists: bool) -> str | None:
    if profile_exists:
        return None
    return "Add at least one grid line before saving a profile."


def extract_preflight_error(
    *,
    pdf_path: str | None,
    profile_exists: bool,
) -> str | None:
    if not pdf_path:
        return "Open a PDF before extracting."
    if not profile_exists:
        return "Create or apply a grid profile before extracting."
    return None


def named_event_message(action_label: str, name: str) -> str:
    return f"{action_label}: {name}"
