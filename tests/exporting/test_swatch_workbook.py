from __future__ import annotations

import io

from openpyxl import load_workbook
from PIL import Image

from src.exporting import export_swatch_workbook
from src.extraction.extractor import ExtractedPair


def _png_bytes(color: tuple[int, int, int] = (20, 120, 80)) -> bytes:
    image = Image.new("RGB", (32, 24), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_export_swatch_workbook_writes_headers_and_rows(tmp_path) -> None:
    path = tmp_path / "swatches.xlsx"
    pairs = [
        ExtractedPair(material_id="MAT-001", image_bytes=_png_bytes()),
        ExtractedPair(material_id="MAT-002", image_bytes=_png_bytes((40, 80, 180))),
    ]

    export_swatch_workbook(
        path,
        pairs,
        manufacturer="Acme Finishes",
        category="Fabric",
    )

    workbook = load_workbook(path)
    sheet = workbook["Swatches"]

    assert sheet["A1"].value == "Manufacturer"
    assert sheet["B1"].value == "Acme Finishes"
    assert sheet["A2"].value == "Category"
    assert sheet["B2"].value == "Fabric"
    assert sheet["A4"].value == "ID"
    assert sheet["B4"].value == "Image"
    assert sheet["A5"].value == "MAT-001"
    assert sheet["A6"].value == "MAT-002"
    assert len(sheet._images) == 2


def test_export_swatch_workbook_skips_invalid_image_bytes(tmp_path) -> None:
    path = tmp_path / "swatches.xlsx"
    pairs = [ExtractedPair(material_id="MAT-001", image_bytes=b"not an image")]

    export_swatch_workbook(path, pairs, manufacturer="", category="")

    workbook = load_workbook(path)
    sheet = workbook["Swatches"]

    assert sheet["A5"].value == "MAT-001"
    assert sheet._images == []
