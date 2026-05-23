from __future__ import annotations

import math
from dataclasses import dataclass
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image

from src.extraction.planner import ResolvedGroup


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
                        image_bytes = self._extract_image_field(page, field.rect, page_image)
                        values[name] = ExtractedFieldValue("image", image_bytes=image_bytes)
                    else:
                        text = self._extract_cell_text(page, field.rect, text_page)
                        values[name] = ExtractedFieldValue("text", text=text)

                if any(value.has_data for value in values.values()):
                    extracted.append(values)
        finally:
            if page_image is not None:
                page_image.close()

        return extracted

    @staticmethod
    def _extract_cell_text(page: fitz.Page, rect: fitz.Rect, text_page: fitz.TextPage) -> str:
        return str(page.get_textbox(rect, textpage=text_page)).strip()

    def _render_full_page(self, page: fitz.Page) -> Image.Image:
        mat = fitz.Matrix(self._render_scale, self._render_scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def _extract_image_field(
        self,
        page: fitz.Page,
        rect: fitz.Rect,
        page_image: Image.Image | None,
    ) -> bytes:
        if page_image is None:
            return self._crop_clip(page, rect)

        crop_box = self._rect_to_pixel_box(rect, page_image.width, page_image.height)
        if crop_box is None:
            return b""
        crop = page_image.crop(crop_box)
        try:
            return self._encode_png(crop)
        finally:
            crop.close()

    def _crop_clip(self, page: fitz.Page, rect: fitz.Rect) -> bytes:
        mat = fitz.Matrix(self._render_scale, self._render_scale)
        clip = page.rect & rect
        pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        try:
            return self._encode_png(image)
        finally:
            image.close()

    def _rect_to_pixel_box(
        self,
        rect: fitz.Rect,
        pixmap_width: int,
        pixmap_height: int,
    ) -> tuple[int, int, int, int] | None:
        left = math.floor(rect.x0 * self._render_scale)
        top = math.floor(rect.y0 * self._render_scale)
        right = math.ceil(rect.x1 * self._render_scale)
        bottom = math.ceil(rect.y1 * self._render_scale)

        left = max(0, min(left, pixmap_width))
        top = max(0, min(top, pixmap_height))
        right = max(0, min(right, pixmap_width))
        bottom = max(0, min(bottom, pixmap_height))

        if right <= left or bottom <= top:
            return None
        return left, top, right, bottom

    def _encode_png(self, image: Image.Image) -> bytes:
        buf = BytesIO()
        image.save(
            buf,
            format="PNG",
            compress_level=self._png_compress_level,
            optimize=False,
        )
        return buf.getvalue()
