from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QAction, QMenu, QToolButton, QWidgetAction

from src.ui.profile_menu import (
    LayoutMenuRow,
    apply_selected_layout_label,
    populate_profile_menu,
)


def test_populate_profile_menu_with_empty_profiles(qapp) -> None:
    menu = QMenu()
    save_calls = 0

    def on_save() -> None:
        nonlocal save_calls
        save_calls += 1

    populate_profile_menu(
        menu,
        profile_names=[],
        selected_profile_name=None,
        on_apply=lambda _name: None,
        on_delete=lambda _name: None,
        on_save=on_save,
        owner=menu,
        save_icon=QIcon(),
    )

    actions = menu.actions()
    assert len(actions) == 3
    assert isinstance(actions[0], QAction)
    assert actions[0].text() == "No saved layouts yet"
    assert not actions[0].isEnabled()
    assert actions[1].isSeparator()

    actions[2].trigger()
    assert save_calls == 1


def test_populate_profile_menu_wires_row_callbacks(qapp) -> None:
    menu = QMenu()
    apply_calls: list[str] = []
    delete_calls: list[str] = []

    populate_profile_menu(
        menu,
        profile_names=["alpha", "beta"],
        selected_profile_name="beta",
        on_apply=apply_calls.append,
        on_delete=delete_calls.append,
        on_save=lambda: None,
        owner=menu,
        save_icon=QIcon(),
    )

    row_actions = [action for action in menu.actions() if isinstance(action, QWidgetAction)]
    assert len(row_actions) == 2

    alpha_row = row_actions[0].defaultWidget()
    beta_row = row_actions[1].defaultWidget()
    assert isinstance(alpha_row, LayoutMenuRow)
    assert isinstance(beta_row, LayoutMenuRow)
    assert alpha_row.property("active") is None
    assert beta_row.property("active") is True

    alpha_row.applyRequested.emit("alpha")
    beta_row.deleteRequested.emit("beta")
    assert apply_calls == ["alpha"]
    assert delete_calls == ["beta"]


def test_apply_selected_layout_label_sets_text_and_property(qapp) -> None:
    button = QToolButton()

    apply_selected_layout_label(button, "Oak")
    assert button.text() == "Oak"
    assert button.property("hasSelection") is True

    apply_selected_layout_label(button, None)
    assert button.text() == "Grid Layouts"
    assert button.property("hasSelection") is False
