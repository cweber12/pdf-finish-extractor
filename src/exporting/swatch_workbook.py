from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from openpyxl import Workbook
from openpyxl.drawing.image import Image as WorksheetImage
from openpyxl.styles import Alignment, Font, PatternFill
from PIL import Image as PILImage

_HEADER_FILL = PatternFill("solid", fgColor="E2E8F0")
_COLUMN_FILL = PatternFill("solid", fgColor="CBD5E1")
_BOLD = Font(name="Arial", bold=True)
_BODY = Font(name="Arial")
_MAX_IMAGE_WIDTH = 140
_MAX_IMAGE_HEIGHT = 92


class SwatchWorkbookRow(Protocol):
    material_id: str
    image_bytes: bytes


def export_swatch_workbook(
    path: str | Path,
    pairs: Sequence[SwatchWorkbookRow],
    *,
    manufacturer: str,
    category: str,
) -> None:
    """Write extracted material IDs and swatch images to an Excel workbook."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Swatches"

    sheet["A1"] = "Manufacturer"
    sheet["B1"] = manufacturer
    sheet["A2"] = "Category"
    sheet["B2"] = category
    sheet["A4"] = "ID"
    sheet["B4"] = "Image"

    for cell in ("A1", "A2", "A4", "B4"):
        sheet[cell].font = _BOLD
    for cell in ("A1", "B1", "A2", "B2"):
        sheet[cell].fill = _HEADER_FILL
    for cell in ("A4", "B4"):
        sheet[cell].fill = _COLUMN_FILL
        sheet[cell].alignment = Alignment(horizontal="center")

    sheet.column_dimensions["A"].width = 26
    sheet.column_dimensions["B"].width = 22
    sheet.freeze_panes = "A5"

    for row_index, pair in enumerate(pairs, start=5):
        id_cell = sheet.cell(row=row_index, column=1, value=pair.material_id)
        id_cell.font = _BODY
        id_cell.alignment = Alignment(vertical="center")

        image = _worksheet_image(pair.image_bytes)
        if image is not None:
            sheet.add_image(image, f"B{row_index}")
        sheet.row_dimensions[row_index].height = 74

    workbook.save(path)


def _worksheet_image(image_bytes: bytes) -> WorksheetImage | None:
    try:
        with PILImage.open(io.BytesIO(image_bytes)) as source:
            width, height = _fit_size(source.width, source.height)
            buffer = io.BytesIO()
            source.save(buffer, format="PNG")
    except Exception:
        return None

    buffer.seek(0)
    image = WorksheetImage(buffer)
    image.width = width
    image.height = height
    return image


def _fit_size(width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        return _MAX_IMAGE_WIDTH, _MAX_IMAGE_HEIGHT

    scale = min(_MAX_IMAGE_WIDTH / width, _MAX_IMAGE_HEIGHT / height, 1)
    return max(1, int(width * scale)), max(1, int(height * scale))
