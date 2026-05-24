from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
    QWidgetAction,
)

from src.ui.style import theme


class LayoutMenuRow(QWidget):
    """A row in the Grid Layouts dropdown: name + inline delete action."""

    applyRequested = pyqtSignal(str)
    deleteRequested = pyqtSignal(str)

    def __init__(self, name: str, is_active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self.setObjectName("layoutMenuRow")
        if is_active:
            self.setProperty("active", True)

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 2, 6, 2)
        row.setSpacing(6)

        apply_btn = QPushButton(name)
        apply_btn.setObjectName("layoutApplyBtn")
        if is_active:
            apply_btn.setProperty("active", True)
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        apply_btn.setToolTip(f"Apply layout '{name}' to the current PDF.")
        apply_btn.clicked.connect(lambda: self.applyRequested.emit(self._name))
        row.addWidget(apply_btn, stretch=1)

        delete_btn = QToolButton()
        delete_btn.setObjectName("layoutDeleteBtn")
        delete_btn.setIcon(QIcon(theme.icon_path("trash.svg")))
        delete_btn.setIconSize(QSize(14, 14))
        delete_btn.setToolTip(f"Delete the saved layout '{name}'.")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setAutoRaise(True)
        delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self._name))
        row.addWidget(delete_btn)


def populate_profile_menu(
    menu: QMenu,
    *,
    profile_names: list[str],
    selected_profile_name: str | None,
    on_apply: Callable[[str], None],
    on_delete: Callable[[str], None],
    on_save: Callable[[], None],
    owner: QWidget,
    save_icon: QIcon,
) -> None:
    """Rebuild the profile menu from persisted profile names."""
    menu.clear()

    if not profile_names:
        empty_action = QAction("No saved layouts yet", owner)
        empty_action.setEnabled(False)
        menu.addAction(empty_action)
    else:
        for name in profile_names:
            row = LayoutMenuRow(
                name,
                is_active=(name == selected_profile_name),
                parent=menu,
            )
            row.applyRequested.connect(on_apply)
            row.deleteRequested.connect(on_delete)
            action = QWidgetAction(menu)
            action.setDefaultWidget(row)
            menu.addAction(action)

    menu.addSeparator()
    save_action = QAction(save_icon, "Save current grid as layout…", owner)
    save_action.triggered.connect(on_save)
    menu.addAction(save_action)


def apply_selected_layout_label(
    button: QToolButton,
    selected_profile_name: str | None,
    *,
    default_text: str = "Grid Layouts",
) -> None:
    """Reflect the active layout on the dropdown button label and style."""
    if selected_profile_name:
        button.setText(selected_profile_name)
        button.setProperty("hasSelection", True)
    else:
        button.setText(default_text)
        button.setProperty("hasSelection", False)

    style = button.style()
    if style is not None:
        style.unpolish(button)
        style.polish(button)

