from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QPushButton,
    QHeaderView,
    QProgressBar,
)
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from src.extraction.extractor import ExtractedPair


_DUPLICATE_BG = QColor(255, 230, 100)


class PreviewPanel(QWidget):
    """Shows extracted (swatch thumbnail, material ID) pairs for review.

    Duplicate rows (material ID already in the DB) are highlighted yellow.
    The user can deselect rows before uploading.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pairs: list[ExtractedPair] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._summary = QLabel()
        layout.addWidget(self._summary)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["", "Material ID", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 72)
        self._table.setColumnWidth(2, 90)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table, stretch=1)

        btn_row = QHBoxLayout()
        self._upload_btn = QPushButton("Upload Selected")
        self._upload_btn.clicked.connect(self._on_upload)
        btn_row.addStretch()
        btn_row.addWidget(self._upload_btn)
        layout.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, pairs: list[ExtractedPair]) -> None:
        self._pairs = pairs
        self._table.setRowCount(0)

        duplicates = 0
        for pair in pairs:
            row = self._table.rowCount()
            self._table.insertRow(row)

            # Thumbnail
            thumb_label = QLabel()
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if pair.image_pixmap:
                thumb_label.setPixmap(
                    pair.image_pixmap.scaled(
                        64, 64,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            self._table.setCellWidget(row, 0, thumb_label)

            # Material ID
            id_item = QTableWidgetItem(pair.material_id)
            self._table.setItem(row, 1, id_item)

            # Status
            if pair.is_duplicate:
                status = "update"
                duplicates += 1
                for col in range(3):
                    item = self._table.item(row, col)
                    if item:
                        item.setBackground(_DUPLICATE_BG)
            else:
                status = "new"
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, status_item)

            self._table.setRowHeight(row, 72)
            self._table.selectRow(row)

        new_count = len(pairs) - duplicates
        self._summary.setText(
            f"{len(pairs)} pairs extracted — {new_count} new, {duplicates} will update (highlighted)"
        )

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def _on_upload(self) -> None:
        selected_rows = {idx.row() for idx in self._table.selectedIndexes()}
        to_upload = [self._pairs[r] for r in sorted(selected_rows) if r < len(self._pairs)]
        if not to_upload:
            return

        from src.upload.worker_client import WorkerClient
        from src.extraction.image_processing import compress_image

        worker = WorkerClient()

        self._progress.setMaximum(len(to_upload))
        self._progress.setValue(0)
        self._progress.setVisible(True)

        inserted = updated = 0
        for i, pair in enumerate(to_upload, 1):
            compressed = compress_image(pair.image_bytes)
            was_updated = worker.upload(compressed, pair.material_id)
            if was_updated:
                updated += 1
            else:
                inserted += 1
            self._progress.setValue(i)

        self._progress.setVisible(False)
        self._summary.setText(
            f"Done — {inserted} inserted, {updated} updated."
        )
