from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QDialog, QWidget

from src.extraction.grid import FieldDefinition
from src.ui import grid_editor_fields as fields_module
from src.ui.grid_editor_fields import confirm_field_recipe_change, prompt_field_recipe


def test_confirm_field_recipe_change_without_groups_is_true(qapp) -> None:
    assert confirm_field_recipe_change(QWidget(), has_groups=False) is True


def test_prompt_field_recipe_returns_none_when_dialog_cancelled(monkeypatch, qapp) -> None:
    class FakeDialog:
        def __init__(self, _fields: list[FieldDefinition], _parent: QWidget | None) -> None:
            pass

        def exec(self) -> int:
            return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(fields_module, "FieldRecipeDialog", FakeDialog)
    result = prompt_field_recipe(QWidget(), [FieldDefinition("id", "text", 1)])
    assert result is None
