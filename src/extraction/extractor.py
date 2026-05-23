from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image

from src.extraction.grid import Grid, GridSegment
from src.extraction.planner import ExtractionPlanner

_DEFAULT_RENDER_DPI = 150
_FULL_PAGE_RENDER_THRESHOLD = 2


@dataclass(frozen=True)
class ExtractedFieldValue:
    field_type: str
    text: str = ""
    image_bytes: bytes = b""

    @property
    def has_data(self) -> bool:
        return bool(self.text) if self.field_type == "text" else bool(self.image_bytes)


@dataclass
class ExtractedGroup:
    values: dict[str, ExtractedFieldValue] = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        return any(value.has_data for value in self.values.values())

    @property
    def field_names(self) -> list[str]:
        return list(self.values)


@dataclass(frozen=True)
class ExtractionProgress:
    """Progress payload emitted after each processed page."""

    page_index: int
    page_count: int
    groups_extracted: int


class Extractor:
    """Apply a saved :class:`Grid` profile to a PDF and return extracted groups."""

    def __init__(
        self,
        pdf_path: str,
        grid: Grid,
        *,
        segments: list[GridSegment] | None = None,
        render_dpi: int = _DEFAULT_RENDER_DPI,
        full_page_render_threshold: int = _FULL_PAGE_RENDER_THRESHOLD,
        png_compress_level: int = 1,
    ) -> None:
        self._pdf_path = pdf_path
        self._grid = grid.normalized()
        self._segments: list[GridSegment] = (
            sorted(segments, key=lambda s: s.start_page) if segments else []
        )
        self._planner = ExtractionPlanner(self._grid, segments=self._segments or None)
        self._render_dpi = render_dpi
        self._render_scale = render_dpi / 72.0
        self._full_page_render_threshold = max(1, full_page_render_threshold)
        self._png_compress_level = max(0, min(9, png_compress_level))

    def extract_all_pages(
        self,
        *,
        progress_callback: Callable[[ExtractionProgress], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[ExtractedGroup]:
        groups: list[ExtractedGroup] = []
        with fitz.open(self._pdf_path) as doc:
            page_count = len(doc)
            for page_index in range(page_count):
                if cancel_check and cancel_check():
                    break

                if page_index not in self._grid.omitted_pages:
                    groups.extend(self._extract_page(doc[page_index]))

                if progress_callback:
                    progress_callback(
                        ExtractionProgress(
                            page_index=page_index,
                            page_count=page_count,
                            groups_extracted=len(groups),
                        )
                    )

        return groups

    def iter_pages(
        self,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Iterable[tuple[ExtractionProgress, list[ExtractedGroup]]]:
        total_groups = 0
        with fitz.open(self._pdf_path) as doc:
            page_count = len(doc)
            for page_index in range(page_count):
                if cancel_check and cancel_check():
                    break

                page_groups = []
                if page_index not in self._grid.omitted_pages:
                    page_groups = self._extract_page(doc[page_index])
                    total_groups += len(page_groups)
                yield (
                    ExtractionProgress(
                        page_index=page_index,
                        page_count=page_count,
                        groups_extracted=total_groups,
                    ),
                    page_groups,
                )

    def _extract_page(self, page: fitz.Page) -> list[ExtractedGroup]:
        resolved_groups = self._planner.plan_page(page)
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

        extracted: list[ExtractedGroup] = []
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

                extracted_group = ExtractedGroup(values=values)
                if extracted_group.has_data:
                    extracted.append(extracted_group)
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
