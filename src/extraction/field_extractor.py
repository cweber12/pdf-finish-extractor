from __future__ import annotations

from dataclasses import dataclass

import fitz  # PyMuPDF
from PIL import Image

from src.extraction.planner import ResolvedGroup
from src.extraction.rect_extract import crop_page_rect_to_png, extract_text_from_rect


@dataclass(frozen=True)
class ExtractedFieldValue:
    field_type: str
    text: str = ""
    image_bytes: bytes = b""

    @property
    def has_data(self) -> bool:
        return bool(self.text) if self.field_type == "text" else bool(self.image_bytes)


class FieldExtractor:
    """Extract resolved text/image field values from a page."""

    def __init__(
        self,
        *,
        render_dpi: int,
        full_page_render_threshold: int,
        png_compress_level: int,
    ) -> None:
        self._render_scale = render_dpi / 72.0
        self._full_page_render_threshold = max(1, full_page_render_threshold)
        self._png_compress_level = max(0, min(9, png_compress_level))

    def extract_groups(
        self,
        page: fitz.Page,
        resolved_groups: list[ResolvedGroup],
    ) -> list[dict[str, ExtractedFieldValue]]:
        if not resolved_groups:
            return []

        text_page = page.get_textpage()
        image_fields = [
            field
            for group in resolved_groups
            for field in group.fields
            if field.definition.field_type == "image"
        ]
        page_image: Image.Image | None = None
        if len(image_fields) >= self._full_page_render_threshold:
            page_image = self._render_full_page(page)

        extracted: list[dict[str, ExtractedFieldValue]] = []
        try:
            for group in resolved_groups:
                values: dict[str, ExtractedFieldValue] = {}
                for field in group.fields:
                    name = field.definition.name
                    if field.definition.field_type == "image":
                        image_bytes = crop_page_rect_to_png(
                            page,
                            field.rect,
                            self._render_scale,
                            page_image=page_image,
                            png_compress_level=self._png_compress_level,
                        )
                        values[name] = ExtractedFieldValue("image", image_bytes=image_bytes)
                    else:
                        text = extract_text_from_rect(page, field.rect, text_page)
                        values[name] = ExtractedFieldValue("text", text=text)

                if any(value.has_data for value in values.values()):
                    extracted.append(values)
        finally:
            if page_image is not None:
                page_image.close()

        return extracted

    def _render_full_page(self, page: fitz.Page) -> Image.Image:
        mat = fitz.Matrix(self._render_scale, self._render_scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
