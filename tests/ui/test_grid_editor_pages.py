from src.ui.editor.grid_editor_pages import (
    omit_all_pages,
    page_controls_state,
    toggle_omitted_page,
    viewing_page_hint,
)


def test_page_controls_state_with_pages() -> None:
    state = page_controls_state(page_count=5, page_index=2, omitted_pages={2, 4})

    assert state.prev_enabled is True
    assert state.next_enabled is True
    assert state.omit_enabled is True
    assert state.page_label == "3/5"
    assert state.omit_checked is True


def test_page_controls_state_without_pages() -> None:
    state = page_controls_state(page_count=0, page_index=0, omitted_pages=set())

    assert state.prev_enabled is False
    assert state.next_enabled is False
    assert state.omit_enabled is False
    assert state.page_label == "—/—"
    assert state.omit_checked is False


def test_toggle_omitted_page_adds_when_missing() -> None:
    result = toggle_omitted_page({1, 3}, 2)

    assert result.omitted_pages == {1, 2, 3}
    assert result.hint == "Current page will be skipped during extraction."


def test_toggle_omitted_page_removes_when_present() -> None:
    result = toggle_omitted_page({1, 2, 3}, 2)

    assert result.omitted_pages == {1, 3}
    assert result.hint == "Current page will be included during extraction."


def test_omit_all_pages_returns_none_when_empty() -> None:
    assert omit_all_pages(0) is None


def test_omit_all_pages_marks_full_range() -> None:
    result = omit_all_pages(4)
    assert result == ({0, 1, 2, 3}, "All 4 pages marked as omitted.")


def test_viewing_page_hint() -> None:
    assert viewing_page_hint(0) == "Viewing page 1. Edits apply to this page and forward."


