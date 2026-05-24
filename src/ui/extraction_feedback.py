from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionToolbarState:
    open_enabled: bool
    profile_enabled: bool
    extract_enabled: bool
    grid_enabled: bool
    cancel_visible: bool
    cancel_enabled: bool
    progress_visible: bool
    progress_value: int


def toolbar_state_for_running(running: bool) -> ExtractionToolbarState:
    enabled = not running
    return ExtractionToolbarState(
        open_enabled=enabled,
        profile_enabled=enabled,
        extract_enabled=enabled,
        grid_enabled=enabled,
        cancel_visible=running,
        cancel_enabled=running,
        progress_visible=running,
        progress_value=0,
    )


def extraction_progress_value(page_index: int, page_count: int) -> int:
    completed = max(0, page_index + 1)
    if page_count <= 0:
        return 0
    pct = int((completed / page_count) * 100)
    return max(0, min(100, pct))


def extraction_progress_status(
    page_index: int,
    page_count: int,
    groups_extracted: int,
) -> str:
    completed = max(0, page_index + 1)
    return f"Extracting page {completed}/{page_count} • {groups_extracted} groups found"


def coerce_extracted_groups(groups: object) -> list[object]:
    return list(groups) if isinstance(groups, list) else []


def extraction_completion_message(groups_count: int, was_cancelled: bool) -> tuple[str, bool]:
    if was_cancelled:
        return f"Extraction cancelled: {groups_count} groups found.", False
    return f"Extraction complete: {groups_count} groups found.", True


def extraction_failure_toast(error: str, *, max_detail: int = 120) -> str:
    detail = error[:max_detail] + "…" if len(error) > max_detail else error
    return f"Extraction failed: {detail}"
