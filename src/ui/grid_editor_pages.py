from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageControlsState:
    prev_enabled: bool
    next_enabled: bool
    omit_enabled: bool
    page_label: str
    omit_checked: bool


@dataclass(frozen=True)
class ToggleOmittedPageResult:
    omitted_pages: set[int]
    hint: str


def page_controls_state(
    *,
    page_count: int,
    page_index: int,
    omitted_pages: set[int],
) -> PageControlsState:
    has_pages = page_count > 0
    return PageControlsState(
        prev_enabled=has_pages and page_index > 0,
        next_enabled=has_pages and page_index < page_count - 1,
        omit_enabled=has_pages,
        page_label=f"{page_index + 1}/{page_count}" if has_pages else "—/—",
        omit_checked=page_index in omitted_pages,
    )


def toggle_omitted_page(omitted_pages: set[int], page_index: int) -> ToggleOmittedPageResult:
    updated = set(omitted_pages)
    if page_index in updated:
        updated.remove(page_index)
        return ToggleOmittedPageResult(
            omitted_pages=updated,
            hint="Current page will be included during extraction.",
        )
    updated.add(page_index)
    return ToggleOmittedPageResult(
        omitted_pages=updated,
        hint="Current page will be skipped during extraction.",
    )


def omit_all_pages(page_count: int) -> tuple[set[int], str] | None:
    if page_count <= 0:
        return None
    return set(range(page_count)), f"All {page_count} pages marked as omitted."


def viewing_page_hint(page_index: int) -> str:
    return f"Viewing page {page_index + 1}. Edits apply to this page and forward."
