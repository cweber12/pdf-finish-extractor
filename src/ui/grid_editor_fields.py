from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.extraction.grid import FieldDefinition


class FieldRecipeDialog(QDialog):
    """Dialog for editing the ordered extraction field recipe."""

    def __init__(self, fields: list[FieldDefinition], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fields")
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Type", "Clicks"])
        header = self._table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        for field_def in fields:
            self._append_row(field_def)

        add_text = QPushButton("Add Text")
        add_text.clicked.connect(lambda: self._append_row(FieldDefinition("field", "text", 1)))
        add_image = QPushButton("Add Image")
        add_image.clicked.connect(lambda: self._append_row(FieldDefinition("image", "image", 1)))
        remove = QPushButton("Remove")
        remove.clicked.connect(self._remove_selected)
        up = QPushButton("Up")
        up.clicked.connect(lambda: self._move_selected(-1))
        down = QPushButton("Down")
        down.clicked.connect(lambda: self._move_selected(1))

        tools = QHBoxLayout()
        tools.addWidget(add_text)
        tools.addWidget(add_image)
        tools.addWidget(remove)
        tools.addStretch()
        tools.addWidget(up)
        tools.addWidget(down)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(tools)
        layout.addWidget(buttons)
        self.resize(520, 320)

    def fields(self) -> list[FieldDefinition]:
        result: list[FieldDefinition] = []
        seen: set[str] = set()
        for row in range(self._table.rowCount()):
            name_item = self._table.item(row, 0)
            name = name_item.text().strip() if name_item else ""
            if not name or name in seen:
                continue
            type_widget = self._table.cellWidget(row, 1)
            click_widget = self._table.cellWidget(row, 2)
            field_type = "text"
            if isinstance(type_widget, QComboBox):
                field_type = type_widget.currentText().lower()
            click_count = 1
            if isinstance(click_widget, QSpinBox):
                click_count = click_widget.value()
            seen.add(name)
            result.append(
                FieldDefinition(
                    name=name,
                    field_type=field_type,  # type: ignore[arg-type]
                    click_count=click_count,
                )
            )
        return result

    def _append_row(self, field_def: FieldDefinition) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(field_def.name))

        type_box = QComboBox()
        type_box.addItems(["text", "image"])
        type_box.setCurrentText(field_def.field_type)
        self._table.setCellWidget(row, 1, type_box)

        clicks = QSpinBox()
        clicks.setRange(1, 20)
        clicks.setValue(max(1, field_def.click_count))
        self._table.setCellWidget(row, 2, clicks)
        self._table.selectRow(row)

    def _remove_selected(self) -> None:
        row = self._selected_row()
        if row is not None:
            self._table.removeRow(row)

    def _move_selected(self, delta: int) -> None:
        row = self._selected_row()
        if row is None:
            return
        target = row + delta
        if target < 0 or target >= self._table.rowCount():
            return
        current = self.fields()
        current[row], current[target] = current[target], current[row]
        self._table.setRowCount(0)
        for field_def in current:
            self._append_row(field_def)
        self._table.selectRow(target)

    def _selected_row(self) -> int | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return indexes[0].row()


def confirm_field_recipe_change(parent: QWidget, *, has_groups: bool) -> bool:
    if not has_groups:
        return True
    confirm = QMessageBox(parent)
    confirm.setWindowTitle("Change fields")
    confirm.setIcon(QMessageBox.Icon.Warning)
    confirm.setText("Changing fields will clear existing groups.")
    confirm.setInformativeText("Continue?")
    confirm.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
    )
    confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
    return confirm.exec() == QMessageBox.StandardButton.Yes


def prompt_field_recipe(parent: QWidget, fields: list[FieldDefinition]) -> list[FieldDefinition] | None:
    dialog = FieldRecipeDialog(fields, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.fields()
