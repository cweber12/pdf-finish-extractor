from __future__ import annotations

import io
from typing import TYPE_CHECKING

from PIL import Image as PILImage
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
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


_DUPLICATE_BG = QColor(120, 78, 8, 90)
_THUMB_BG = QColor(15, 23, 42)


class PreviewPanel(QWidget):
    """Shows extracted (swatch thumbnail, material ID) pairs for review.

    Duplicate rows are tinted amber. Users can deselect rows before upload.
    Each row's Status column updates in place during upload; a toast summarizes
    the final result.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewPanel")
        self._pairs: list[ExtractedPair] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

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

        self._summary = QLabel("Run extraction to review detected swatches and IDs.")
        self._summary.setObjectName("panelSummary")
        header.addWidget(self._summary)
        layout.addLayout(header)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Swatch", "Material ID", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 84)
        self._table.setColumnWidth(2, 112)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 2, 0, 0)
        self._upload_btn = QPushButton(QIcon(theme.icon_path("upload.svg")), "  Upload Selected")
        self._upload_btn.setProperty("primary", True)
        self._upload_btn.setToolTip("Upload selected rows; deselect rows you do not want to send.")
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

            thumb_label = QLabel()
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb_label.setStyleSheet(
                f"background-color: {theme.BG_BASE}; border-radius: 8px; padding: 4px;"
            )
            pixmap = _bytes_to_pixmap(pair.image_bytes)
            if pixmap:
                thumb_label.setPixmap(
                    pixmap.scaled(
                        64,
                        64,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            self._table.setCellWidget(row, 0, thumb_label)

            id_item = QTableWidgetItem(pair.material_id)
            self._table.setItem(row, 1, id_item)

            if pair.is_duplicate:
                status = "Update"
                duplicates += 1
                id_item.setBackground(_DUPLICATE_BG)
            else:
                status = "New"

            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if pair.is_duplicate:
                status_item.setForeground(QColor(theme.WARNING))
                status_item.setBackground(_DUPLICATE_BG)
            else:
                status_item.setForeground(QColor(theme.TEXT_MUTED))
            self._table.setItem(row, 2, status_item)

            self._table.setRowHeight(row, 78)
            self._table.selectRow(row)

        new_count = len(pairs) - duplicates
        self._summary.setText(
            f"{len(pairs)} pairs found • {new_count} new • {duplicates} update existing records"
        )

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def _on_upload(self) -> None:
        selected_rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        to_upload = [(r, self._pairs[r]) for r in selected_rows if r < len(self._pairs)]
        if not to_upload:
            from src.ui.toast import Toast
            Toast.show_in(self.window(), "Select at least one row to upload.", success=False)
            return

        from src.extraction.image_processing import compress_image
        from src.upload.worker_client import WorkerClient

        self._upload_btn.setEnabled(False)
        worker = WorkerClient()
        inserted = updated = failed = 0
        last_error: str = ""

        for row, pair in to_upload:
            self._set_row_status(row, "Uploading…", theme.TEXT_MUTED)
            try:
                compressed = compress_image(pair.image_bytes)
                was_updated = worker.upload(compressed, pair.material_id)
                if was_updated:
                    updated += 1
                    self._set_row_status(row, "✓ Updated", theme.SUCCESS)
                else:
                    inserted += 1
                    self._set_row_status(row, "✓ Inserted", theme.SUCCESS)
            except Exception as exc:
                failed += 1
                last_error = str(exc)
                print(f"Upload error for {pair.material_id!r}: {exc}", flush=True)
                self._set_row_status(row, "✕ Failed", theme.ERROR)

        self._upload_btn.setEnabled(True)

        total = inserted + updated
        msg = f"{total} uploaded ({inserted} new, {updated} updated)"
        if failed:
            msg = (
                f"{failed} failed — {last_error}"
                if total == 0
                else f"{total} uploaded, {failed} failed — {last_error}"
            )
        self._summary.setText(msg)

        from src.ui.toast import Toast
        if failed == 0:
            Toast.show_in(self.window(), msg, success=True)
        else:
            detail = last_error[:80] + "…" if len(last_error) > 80 else last_error
            Toast.show_in(self.window(), f"{failed} failed: {detail}", success=False)

    def _set_row_status(self, row: int, text: str, color: str) -> None:
        item = self._table.item(row, 2)
        if item is None:
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, item)
        item.setText(text)
        item.setForeground(QColor(color))
