from __future__ import annotations

from io import BytesIO

import fitz
import pytest
from PIL import Image

from src.extraction.rect_extract import crop_page_rect_to_png, extract_text_from_rect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _page_with_text(text: str, at: fitz.Point, page_w: int = 400, page_h: int = 400) -> fitz.Page:
    doc = fitz.open()
    page = doc.new_page(width=page_w, height=page_h)
    page.insert_text(at, text, fontsize=12)
    return page


def _solid_color_page(
    color: tuple[float, float, float],
    page_w: int = 200,
    page_h: int = 200,
) -> fitz.Page:
    doc = fitz.open()
    page = doc.new_page(width=page_w, height=page_h)
    page.draw_rect(fitz.Rect(0, 0, page_w, page_h), fill=color, color=color)
    return page


# ---------------------------------------------------------------------------
# extract_text_from_rect
# ---------------------------------------------------------------------------


def test_extract_text_from_rect_returns_text_in_region() -> None:
    page = _page_with_text("HELLO", fitz.Point(20, 50))
    rect = fitz.Rect(0, 30, 200, 70)
    text = extract_text_from_rect(page, rect)
    page.parent.close()
    assert "HELLO" in text


def test_extract_text_from_rect_strips_whitespace() -> None:
    page = _page_with_text("ABC", fitz.Point(20, 50))
    rect = fitz.Rect(0, 30, 200, 70)
    text = extract_text_from_rect(page, rect)
    page.parent.close()
    assert text == text.strip()


def test_extract_text_from_rect_returns_empty_string_for_empty_region() -> None:
    page = _page_with_text("TEXT", fitz.Point(20, 50))
    rect = fitz.Rect(300, 300, 400, 400)  # far from the text
    text = extract_text_from_rect(page, rect)
    page.parent.close()
    assert text == ""


def test_extract_text_from_rect_accepts_pre_built_text_page() -> None:
    page = _page_with_text("REUSE", fitz.Point(20, 50))
    text_pg = page.get_textpage()
    rect = fitz.Rect(0, 30, 200, 70)
    text = extract_text_from_rect(page, rect, text_page=text_pg)
    page.parent.close()
    assert "REUSE" in text


def test_extract_text_multiple_sections() -> None:
    doc = fitz.open()
    page = doc.new_page(width=400, height=200)
    page.insert_text(fitz.Point(20, 50), "SECTION_A", fontsize=12)
    page.insert_text(fitz.Point(20, 150), "SECTION_B", fontsize=12)

    text_a = extract_text_from_rect(page, fitz.Rect(0, 30, 400, 80))
    text_b = extract_text_from_rect(page, fitz.Rect(0, 130, 400, 180))
    doc.close()

    assert "SECTION_A" in text_a
    assert "SECTION_B" in text_b
    assert "SECTION_A" not in text_b
    assert "SECTION_B" not in text_a


# ---------------------------------------------------------------------------
# crop_page_rect_to_png — clip-only path (no page_image)
# ---------------------------------------------------------------------------


def test_crop_returns_png_bytes() -> None:
    page = _solid_color_page((1.0, 0.0, 0.0))
    rect = fitz.Rect(10, 10, 50, 50)
    result = crop_page_rect_to_png(page, rect, render_scale=1.0)
    page.parent.close()
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_crop_produces_non_empty_bytes() -> None:
    page = _solid_color_page((0.0, 1.0, 0.0))
    rect = fitz.Rect(10, 10, 100, 100)
    result = crop_page_rect_to_png(page, rect, render_scale=1.5)
    page.parent.close()
    assert len(result) > 0


def test_crop_out_of_page_bounds_returns_empty_bytes() -> None:
    page = _solid_color_page((0.5, 0.5, 0.5))
    # rect entirely outside the 200×200 page
    rect = fitz.Rect(300, 300, 400, 400)
    result = crop_page_rect_to_png(page, rect, render_scale=1.0)
    page.parent.close()
    # clip = page.rect & rect is empty, so pixmap will be 0×0 — returns empty
    assert result == b""


# ---------------------------------------------------------------------------
# crop_page_rect_to_png — page_image path
# ---------------------------------------------------------------------------


def _render_full_page(page: fitz.Page, scale: float = 1.0) -> Image.Image:
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def test_crop_with_page_image_returns_png_bytes() -> None:
    page = _solid_color_page((0.0, 0.0, 1.0))
    scale = 1.0
    page_image = _render_full_page(page, scale)
    rect = fitz.Rect(10, 10, 80, 80)
    result = crop_page_rect_to_png(page, rect, render_scale=scale, page_image=page_image)
    page_image.close()
    page.parent.close()
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_crop_with_page_image_matches_clip_path() -> None:
    """Both paths must produce the same crop for the same rect."""
    page = _solid_color_page((0.2, 0.4, 0.8))
    scale = 2.0
    rect = fitz.Rect(20, 20, 100, 100)

    result_clip = crop_page_rect_to_png(page, rect, render_scale=scale)

    page_image = _render_full_page(page, scale)
    result_image = crop_page_rect_to_png(page, rect, render_scale=scale, page_image=page_image)
    page_image.close()
    page.parent.close()

    # Both are valid PNGs and decode to images of the same size.
    img_clip = Image.open(BytesIO(result_clip))
    img_image = Image.open(BytesIO(result_image))
    assert img_clip.size == img_image.size
    img_clip.close()
    img_image.close()


def test_crop_with_page_image_outside_bounds_returns_empty() -> None:
    page = _solid_color_page((0.5, 0.5, 0.5))
    scale = 1.0
    page_image = _render_full_page(page, scale)
    rect = fitz.Rect(300, 300, 400, 400)
    result = crop_page_rect_to_png(page, rect, render_scale=scale, page_image=page_image)
    page_image.close()
    page.parent.close()
    assert result == b""
