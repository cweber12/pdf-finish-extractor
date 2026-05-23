from __future__ import annotations

import io
from typing import TYPE_CHECKING, cast

from PIL import Image as PILImage
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui import theme

if TYPE_CHECKING:
    from src.extraction.extractor import ExtractedGroup


def _bytes_to_pixmap(image_bytes: bytes) -> QPixmap | None:
    try:
        img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg)
    except Exception:
        return None


class PreviewPanel(QWidget):
    """Shows extracted groups for review and Excel export."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewPanel")
        self._groups: list[ExtractedGroup] = []
        self._field_names: list[str] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QVBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(3)

        title = QLabel("Extraction Preview")
        title.setObjectName("panelTitle")
        header.addWidget(title)

        self._summary = QLabel("Run extraction to review detected groups.")
        self._summary.setObjectName("panelSummary")
        header.addWidget(self._summary)
        layout.addLayout(header)

        self._table = QTableWidget(0, 0)
        horizontal_header = self._table.horizontalHeader()
        if horizontal_header is not None:
            horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            horizontal_header.setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setFrameShape(QFrame.Shape.NoFrame)
        self._table.setCornerButtonEnabled(False)
        vertical_header = self._table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        table_frame = QFrame()
        table_frame.setObjectName("previewTableFrame")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        table_layout.addWidget(self._table)
        layout.addWidget(table_frame, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 2, 0, 0)
        self._export_btn = QPushButton(QIcon(theme.icon_path("save.svg")), "  Export Excel")
        self._export_btn.setToolTip("Export selected rows to an Excel workbook.")
        self._export_btn.clicked.connect(self._on_export_excel)
        btn_row.addWidget(self._export_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def load(self, groups: list[ExtractedGroup]) -> None:
        self._groups = groups
        self._field_names = _field_names(groups)
        self._table.clear()
        self._table.setRowCount(0)
        self._table.setColumnCount(len(self._field_names))
        self._table.setHorizontalHeaderLabels(self._field_names)

        for group in groups:
            row = self._table.rowCount()
            self._table.insertRow(row)

            for column, field_name in enumerate(self._field_names):
                value = group.values.get(field_name)
                if value is None:
                    self._table.setItem(row, column, QTableWidgetItem(""))
                    continue

                if value.field_type == "image":
                    thumb_label = QLabel()
                    thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    thumb_label.setStyleSheet(
                        f"background-color: {theme.BG_PANEL}; border-radius: 7px; padding: 4px;"
                    )
                    pixmap = _bytes_to_pixmap(value.image_bytes)
                    if pixmap:
                        thumb_label.setPixmap(
                            pixmap.scaled(
                                64,
                                64,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        )
                    self._table.setCellWidget(row, column, thumb_label)
                    self._table.setItem(row, column, QTableWidgetItem(""))
                else:
                    self._table.setItem(row, column, QTableWidgetItem(value.text))

            self._table.setRowHeight(row, 74)
            self._table.selectRow(row)

        self._summary.setText(f"{len(groups)} groups found")

    def _on_export_excel(self) -> None:
        selected_rows = self._selected_rows()
        groups = [self._groups[row] for row in selected_rows if row < len(self._groups)]
        if not groups:
            self._show_toast("Select at least one row to export.", success=False)
            return

        manufacturer, ok = QInputDialog.getText(
            self,
            "Export Extracted Data",
            "Manufacturer:",
        )
        if not ok:
            return

        category, ok = QInputDialog.getText(
            self,
            "Export Extracted Data",
            "Category:",
        )
        if not ok:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Extracted Data to Excel",
            "",
            "Excel Workbook (*.xlsx)",
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path = f"{path}.xlsx"

        from src.exporting import export_swatch_workbook
        try:
            export_swatch_workbook(
                path,
                groups,
                manufacturer=manufacturer.strip(),
                category=category.strip(),
            )
        except Exception as exc:  # noqa: BLE001 - user-facing export failure
            detail = str(exc)[:100]
            self._show_toast(f"Excel export failed: {detail}", success=False)
            return

        self._summary.setText(f"Exported {len(groups)} rows to Excel.")
        self._show_toast(f"Exported {len(groups)} rows to Excel.", success=True)

    def _selected_rows(self) -> list[int]:
        return sorted({idx.row() for idx in self._table.selectedIndexes()})

    def _show_toast(self, message: str, *, success: bool) -> None:
        from src.ui.toast import Toast

        Toast.show_in(cast(QWidget, self.window()), message, success=success)


def _field_names(groups: list[ExtractedGroup]) -> list[str]:
    names: list[str] = []
    for group in groups:
        for name in group.values:
            if name not in names:
                names.append(name)
    return names
