from __future__ import annotations

import math
from io import BytesIO

import fitz
import pytest
from PIL import Image

from src.extraction.pattern import RectPx
from src.extraction.pdf_image_locator import (
    drawing_rects_pts,
    embedded_image_rects_pts,
    rect_pts_to_px,
    rect_px_to_pts,
)


# ---------------------------------------------------------------------------
# rect_pts_to_px
# ---------------------------------------------------------------------------


def test_rect_pts_to_px_zero_origin_72pt_square_at_150dpi() -> None:
    px = rect_pts_to_px(fitz.Rect(0, 0, 72, 72), dpi=150)
    assert px == RectPx(0, 0, 150, 150)


def test_rect_pts_to_px_uses_floor_for_origin() -> None:
    # x0 = 1 pt at 150 dpi → 1 * 150/72 = 2.083…, floor = 2
    px = rect_pts_to_px(fitz.Rect(1, 1, 72, 72), dpi=150)
    assert px.x0 == math.floor(1 * 150 / 72)
    assert px.y0 == math.floor(1 * 150 / 72)


def test_rect_pts_to_px_uses_ceil_for_far_corner() -> None:
    # x1 = 10 pt at 150 dpi → 10 * 150/72 = 20.833…, ceil = 21
    px = rect_pts_to_px(fitz.Rect(0, 0, 10, 10), dpi=150)
    assert px.x1 == math.ceil(10 * 150 / 72)
    assert px.y1 == math.ceil(10 * 150 / 72)


def test_rect_pts_to_px_at_72dpi_is_identity_for_integer_coords() -> None:
    px = rect_pts_to_px(fitz.Rect(10, 20, 110, 220), dpi=72)
    assert px == RectPx(10, 20, 110, 220)


# ---------------------------------------------------------------------------
# rect_px_to_pts
# ---------------------------------------------------------------------------


def test_rect_px_to_pts_at_72dpi_is_identity() -> None:
    pts = rect_px_to_pts(RectPx(10, 20, 110, 220), dpi=72)
    assert pts.x0 == pytest.approx(10.0)
    assert pts.y0 == pytest.approx(20.0)
    assert pts.x1 == pytest.approx(110.0)
    assert pts.y1 == pytest.approx(220.0)


def test_rect_px_to_pts_round_trip_at_clean_values() -> None:
    # At 72 DPI, pts == px, so the round-trip is exact.
    original = fitz.Rect(0, 0, 144, 72)
    px = rect_pts_to_px(original, dpi=72)
    back = rect_px_to_pts(px, dpi=72)
    assert back.x0 == pytest.approx(original.x0)
    assert back.y0 == pytest.approx(original.y0)
    assert back.x1 == pytest.approx(original.x1)
    assert back.y1 == pytest.approx(original.y1)


def test_rect_px_to_pts_scale_is_inverse_of_pts_to_px() -> None:
    # 150 px at 150 dpi → 72 pts
    pts = rect_px_to_pts(RectPx(0, 0, 150, 150), dpi=150)
    assert pts.x1 == pytest.approx(72.0)
    assert pts.y1 == pytest.approx(72.0)


# ---------------------------------------------------------------------------
# drawing_rects_pts  (integration — real fitz page)
# ---------------------------------------------------------------------------


def _page_with_drawing(rect: fitz.Rect) -> fitz.Page:
    """Create an in-memory page with a filled rect, save+reload for stream parse."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_rect(rect, color=(0, 0, 0), fill=(1, 0, 0))
    buf = BytesIO()
    doc.save(buf)
    doc.close()
    buf.seek(0)
    doc2 = fitz.open(stream=buf.read(), filetype="pdf")
    return doc2[0]


def test_drawing_rects_pts_returns_drawn_rect() -> None:
    expected = fitz.Rect(10, 20, 100, 150)
    page = _page_with_drawing(expected)
    rects = drawing_rects_pts(page)
    page.parent.close()
    assert len(rects) == 1
    r = rects[0]
    assert r.x0 == pytest.approx(expected.x0, abs=1)
    assert r.y0 == pytest.approx(expected.y0, abs=1)
    assert r.x1 == pytest.approx(expected.x1, abs=1)
    assert r.y1 == pytest.approx(expected.y1, abs=1)


def test_drawing_rects_pts_returns_fitz_rect_objects() -> None:
    page = _page_with_drawing(fitz.Rect(5, 5, 50, 50))
    rects = drawing_rects_pts(page)
    page.parent.close()
    for r in rects:
        assert isinstance(r, fitz.Rect)


def test_drawing_rects_pts_empty_page_returns_empty_list() -> None:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    assert drawing_rects_pts(page) == []
    doc.close()


# ---------------------------------------------------------------------------
# embedded_image_rects_pts  (integration — real fitz page with PNG insert)
# ---------------------------------------------------------------------------


def _minimal_png() -> bytes:
    img = Image.new("RGB", (10, 10), color=(200, 100, 50))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _page_with_embedded_image(img_rect: fitz.Rect) -> fitz.Page:
    """Create an in-memory page with one embedded image, save+reload."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_image(img_rect, stream=_minimal_png())
    buf = BytesIO()
    doc.save(buf)
    doc.close()
    buf.seek(0)
    doc2 = fitz.open(stream=buf.read(), filetype="pdf")
    return doc2[0]


def test_embedded_image_rects_pts_returns_image_rect() -> None:
    expected = fitz.Rect(10, 20, 110, 120)
    page = _page_with_embedded_image(expected)
    rects = embedded_image_rects_pts(page)
    page.parent.close()
    assert len(rects) == 1
    r = rects[0]
    assert r.x0 == pytest.approx(expected.x0, abs=1)
    assert r.y0 == pytest.approx(expected.y0, abs=1)
    assert r.x1 == pytest.approx(expected.x1, abs=1)
    assert r.y1 == pytest.approx(expected.y1, abs=1)


def test_embedded_image_rects_pts_returns_fitz_rect_objects() -> None:
    page = _page_with_embedded_image(fitz.Rect(5, 5, 50, 50))
    rects = embedded_image_rects_pts(page)
    page.parent.close()
    for r in rects:
        assert isinstance(r, fitz.Rect)


def test_embedded_image_rects_pts_empty_page_returns_empty_list() -> None:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    assert embedded_image_rects_pts(page) == []
    doc.close()
