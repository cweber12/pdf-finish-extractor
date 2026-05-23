from __future__ import annotations

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image

from src.extraction.grid import CellPair, Grid, GridSegment

# Grid coordinates are stored in 150-DPI rendered-pixel space.
_GRID_DPI = 150
_GRID_SCALE = _GRID_DPI / 72.0  # grid pixels per PDF point

# Rendering at 150 DPI keeps the existing output size/quality behavior.
_DEFAULT_RENDER_DPI = 150

# Full-page rendering is much faster when a page has several swatch crops.
# For a single crop, clipped rendering can use less memory.
_FULL_PAGE_RENDER_THRESHOLD = 2


@dataclass
class ExtractedPair:
    material_id: str
    image_bytes: bytes
    is_duplicate: bool = False


@dataclass(frozen=True)
class ExtractionProgress:
    """Progress payload emitted after each processed page."""

    page_index: int
    page_count: int
    pairs_extracted: int


@dataclass(frozen=True)
class _ResolvedPair:
    """Pair whose grid cells have been converted to PDF-point rectangles."""

    source: CellPair
    image_rect: fitz.Rect
    text_rect: fitz.Rect


class Extractor:
    """Apply a saved :class:`Grid` profile to a PDF and return image/ID pairs.

    Performance notes
    -----------------
    The original implementation called ``page.get_pixmap(...)`` for every image
    cell. On multi-page PDFs this becomes expensive because the same page is
    rasterized repeatedly.

    This implementation renders each page at most once when there are multiple
    crops on that page, then crops the image cells from that in-memory page
    image. Text extraction also reuses a single ``TextPage`` per page.
    """

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
        # Per-page layout segments override the global grid's lines/pairs for
        # specific page ranges. The segment with the highest start_page that is
        # still <= the page being extracted wins.
        self._segments: list[GridSegment] = (
            sorted(segments, key=lambda s: s.start_page) if segments else []
        )
        self._render_dpi = render_dpi
        self._render_scale = render_dpi / 72.0
        self._full_page_render_threshold = max(1, full_page_render_threshold)
        # Low compression keeps extraction responsive. Images can still be
        # recompressed later by ``image_processing.compress_image`` before upload.
        self._png_compress_level = max(0, min(9, png_compress_level))

    def extract_all_pages(
        self,
        *,
        progress_callback: Callable[[ExtractionProgress], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[ExtractedPair]:
        """Extract all configured pairs from every page.

        Parameters
        ----------
        progress_callback:
            Optional callback called once per page. Useful when extraction is
            run in a background worker and the UI wants a progress indicator.
        cancel_check:
            Optional callback. If it returns True between pages, extraction
            stops cleanly and returns pairs extracted so far.
        """
        pairs: list[ExtractedPair] = []
        with fitz.open(self._pdf_path) as doc:
            page_count = len(doc)
            for page_index in range(page_count):
                if cancel_check and cancel_check():
                    break

                if page_index not in self._grid.omitted_pages:
                    page = doc[page_index]
                    pairs.extend(self._extract_page(page))

                if progress_callback:
                    progress_callback(
                        ExtractionProgress(
                            page_index=page_index,
                            page_count=page_count,
                            pairs_extracted=len(pairs),
                        )
                    )

        return pairs

    def iter_pages(
        self,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Iterable[tuple[ExtractionProgress, list[ExtractedPair]]]:
        """Yield extracted pairs page-by-page.

        This is useful for future UI updates where the preview can be populated
        incrementally instead of waiting for the entire PDF to finish.
        """
        total_pairs = 0
        with fitz.open(self._pdf_path) as doc:
            page_count = len(doc)
            for page_index in range(page_count):
                if cancel_check and cancel_check():
                    break

                page_pairs = []
                if page_index not in self._grid.omitted_pages:
                    page_pairs = self._extract_page(doc[page_index])
                    total_pairs += len(page_pairs)
                yield (
                    ExtractionProgress(
                        page_index=page_index,
                        page_count=page_count,
                        pairs_extracted=total_pairs,
                    ),
                    page_pairs,
                )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extract_page(self, page: fitz.Page) -> list[ExtractedPair]:
        resolved_pairs = self._resolve_pairs_for_page(page)
        if not resolved_pairs:
            return []

        # Build text extraction data once per page instead of once per pair.
        text_page = page.get_textpage()

        pending: list[tuple[str, fitz.Rect]] = []
        for pair in resolved_pairs:
            material_id = self._extract_cell_text(page, pair.text_rect, text_page)
            if material_id:
                pending.append((material_id, pair.image_rect))

        if not pending:
            return []

        if len(pending) >= self._full_page_render_threshold:
            return self._crop_from_full_page_render(page, pending)

        return [
            ExtractedPair(material_id=material_id, image_bytes=self._crop_clip(page, image_rect))
            for material_id, image_rect in pending
        ]

    def _layout_for_page(
        self, page_index: int
    ) -> tuple[list[int], list[int], list[CellPair]]:
        """Return the (h_lines, v_lines, pairs) that apply to ``page_index``.

        When per-page segments are present the segment with the highest
        ``start_page`` that is still <= ``page_index`` wins. Falls back to the
        global grid when no segments are configured.
        """
        if not self._segments:
            return (
                self._grid.horizontal_lines,
                self._grid.vertical_lines,
                self._grid.pairs,
            )
        applicable = [s for s in self._segments if s.start_page <= page_index]
        seg = applicable[-1] if applicable else self._segments[0]
        return seg.horizontal_lines, seg.vertical_lines, seg.pairs

    def _resolve_pairs_for_page(self, page: fitz.Page) -> list[_ResolvedPair]:
        h_pts, v_pts = self._page_boundaries(page)
        omit_regions = self._omit_regions_for_page(page)
        _, _, pairs = self._layout_for_page(int(page.number))

        resolved: list[_ResolvedPair] = []
        for pair in pairs:
            image_rect = self._cell_rect(pair.image_cell, h_pts, v_pts)
            text_rect = self._cell_rect(pair.text_cell, h_pts, v_pts)
            if image_rect is None or text_rect is None:
                continue

            image_rect = page.rect & image_rect
            text_rect = page.rect & text_rect
            if image_rect.is_empty or text_rect.is_empty:
                continue
            if any(
                _rects_intersect(image_rect, omitted) or _rects_intersect(text_rect, omitted)
                for omitted in omit_regions
            ):
                continue

            resolved.append(
                _ResolvedPair(
                    source=pair,
                    image_rect=image_rect,
                    text_rect=text_rect,
                )
            )

        return resolved

    def _omit_regions_for_page(self, page: fitz.Page) -> list[fitz.Rect]:
        """Return page-specific omit regions converted to PDF points."""
        page_index = int(getattr(page, "number", 0))
        regions: list[fitz.Rect] = []
        for region in self._grid.omit_regions:
            if region.page_index != page_index:
                continue

            x0, y0, x1, y1 = region.rect
            rect = fitz.Rect(
                x0 / _GRID_SCALE,
                y0 / _GRID_SCALE,
                x1 / _GRID_SCALE,
                y1 / _GRID_SCALE,
            )
            rect = page.rect & rect
            if not rect.is_empty:
                regions.append(rect)
        return regions

    def _page_boundaries(self, page: fitz.Page) -> tuple[list[float], list[float]]:
        """Return sorted horizontal/vertical boundaries in PDF points."""
        h_lines, v_lines, _ = self._layout_for_page(int(page.number))

        h_pts = [0.0]
        h_pts.extend(y / _GRID_SCALE for y in h_lines)
        h_pts.append(float(page.rect.height))

        v_pts = [0.0]
        v_pts.extend(x / _GRID_SCALE for x in v_lines)
        v_pts.append(float(page.rect.width))

        # Clamp profile lines to the current page and remove duplicates. This
        # prevents invalid or zero-width cells on PDFs with slightly different
        # page sizes.
        h_pts = _dedupe_sorted(_clamp(v, 0.0, float(page.rect.height)) for v in h_pts)
        v_pts = _dedupe_sorted(_clamp(v, 0.0, float(page.rect.width)) for v in v_pts)
        return h_pts, v_pts

    @staticmethod
    def _cell_rect(
        cell: tuple[int, int],
        h_pts: list[float],
        v_pts: list[float],
    ) -> fitz.Rect | None:
        row, col = cell
        if row < 0 or col < 0 or row >= len(h_pts) - 1 or col >= len(v_pts) - 1:
            return None
        return fitz.Rect(v_pts[col], h_pts[row], v_pts[col + 1], h_pts[row + 1])

    @staticmethod
    def _extract_cell_text(page: fitz.Page, rect: fitz.Rect, text_page: fitz.TextPage) -> str:
        # get_textbox() is faster here because it directly extracts text within
        # the rectangle from the already-built TextPage.
        return page.get_textbox(rect, textpage=text_page).strip()

    def _crop_from_full_page_render(
        self,
        page: fitz.Page,
        pending: list[tuple[str, fitz.Rect]],
    ) -> list[ExtractedPair]:
        mat = fitz.Matrix(self._render_scale, self._render_scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # Convert the rendered page once, then crop all swatches from it.
        page_image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        results: list[ExtractedPair] = []
        for material_id, rect in pending:
            crop_box = self._rect_to_pixel_box(rect, pix.width, pix.height)
            if crop_box is None:
                continue

            crop = page_image.crop(crop_box)
            results.append(
                ExtractedPair(
                    material_id=material_id,
                    image_bytes=self._encode_png(crop),
                )
            )

        # Drop references promptly on large PDFs.
        page_image.close()
        return results

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


def _rects_intersect(a: fitz.Rect, b: fitz.Rect) -> bool:
    return not (a.x1 <= b.x0 or a.x0 >= b.x1 or a.y1 <= b.y0 or a.y0 >= b.y1)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _dedupe_sorted(values: Iterable[float], *, tolerance: float = 0.01) -> list[float]:
    result: list[float] = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
    return result
