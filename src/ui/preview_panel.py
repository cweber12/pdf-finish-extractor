from __future__ import annotations

import io
from typing import TYPE_CHECKING

from PIL import Image as PILImage
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui import theme

if TYPE_CHECKING:
    from src.extraction.extractor import ExtractedPair


def _bytes_to_pixmap(image_bytes: bytes) -> QPixmap | None:
    """Convert raw image bytes (PNG/WebP) to a QPixmap for display."""
    try:
        img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg)
    except Exception:
        return None


# Subtle tint for duplicate rows (dark-theme friendly amber)
_DUPLICATE_BG = QColor(80, 55, 5)


class PreviewPanel(QWidget):
    """Shows extracted (swatch thumbnail, material ID) pairs for review.

    Duplicate rows are tinted amber. The user can deselect rows before uploading.
    Each row's Status column updates in place during upload; a toast summarises
    the final result.
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
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)

        self._summary = QLabel()
        layout.addWidget(self._summary)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["", "Material ID", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 72)
        self._table.setColumnWidth(2, 96)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table, stretch=1)

        btn_row = QHBoxLayout()
        from PyQt6.QtGui import QIcon
        self._upload_btn = QPushButton(QIcon(theme.icon_path("upload.svg")), "  Upload Selected")
        self._upload_btn.setProperty("primary", True)
        self._upload_btn.clicked.connect(self._on_upload)
        btn_row.addStretch()
        btn_row.addWidget(self._upload_btn)
        layout.addLayout(btn_row)

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
            pixmap = _bytes_to_pixmap(pair.image_bytes)
            if pixmap:
                thumb_label.setPixmap(
                    pixmap.scaled(
                        64, 64,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            self._table.setCellWidget(row, 0, thumb_label)

            # Material ID
            id_item = QTableWidgetItem(pair.material_id)
            self._table.setItem(row, 1, id_item)

            # Status badge
            if pair.is_duplicate:
                status = "update"
                duplicates += 1
                for col in (1, 2):
                    item = self._table.item(row, col)
                    if item:
                        item.setBackground(_DUPLICATE_BG)
            else:
                status = "new"

            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if pair.is_duplicate:
                status_item.setForeground(QColor(theme.WARNING))
            else:
                status_item.setForeground(QColor(theme.TEXT_MUTED))
            self._table.setItem(row, 2, status_item)

            self._table.setRowHeight(row, 72)
            self._table.selectRow(row)

        new_count = len(pairs) - duplicates
        self._summary.setText(
            f"{len(pairs)} pairs — {new_count} new, {duplicates} will update"
        )

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def _on_upload(self) -> None:
        selected_rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        to_upload = [(r, self._pairs[r]) for r in selected_rows if r < len(self._pairs)]
        if not to_upload:
            return

        from src.extraction.image_processing import compress_image
        from src.upload.worker_client import WorkerClient

        self._upload_btn.setEnabled(False)
        worker = WorkerClient()
        inserted = updated = failed = 0

        for row, pair in to_upload:
            self._set_row_status(row, "uploading…", theme.TEXT_MUTED)
            try:
                compressed = compress_image(pair.image_bytes)
                was_updated = worker.upload(compressed, pair.material_id)
                if was_updated:
                    updated += 1
                    self._set_row_status(row, "✓ updated", theme.SUCCESS)
                else:
                    inserted += 1
                    self._set_row_status(row, "✓ inserted", theme.SUCCESS)
            except Exception:
                failed += 1
                self._set_row_status(row, "✗ failed", theme.ERROR)

        self._upload_btn.setEnabled(True)

        total = inserted + updated
        msg = f"{total} uploaded ({inserted} new, {updated} updated)"
        if failed:
            msg += f", {failed} failed"
        self._summary.setText(msg)

        from src.ui.toast import Toast
        Toast.show_in(self.window(), msg, success=(failed == 0))

    def _set_row_status(self, row: int, text: str, color: str) -> None:
        item = self._table.item(row, 2)
        if item is None:
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, item)
        item.setText(text)
        item.setForeground(QColor(color))
