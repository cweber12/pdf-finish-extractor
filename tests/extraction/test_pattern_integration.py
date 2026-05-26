from __future__ import annotations

import math
from io import BytesIO

import fitz
from PIL import Image

from src.extraction.pattern import (
    ImageSampleDefinition,
    PatternDetectionOptions,
    RectPx,
    RelativeRect,
    resolve_relative_rect,
)
from src.extraction.pattern_matching import image_matches_sample
from src.extraction.pdf_image_locator import embedded_image_rects_pts, rect_pts_to_px
from src.extraction.rect_extract import extract_text_from_rect

# ---------------------------------------------------------------------------
# Synthetic PDF layout constants
#
# Page: 504 x 720 pt (7" x 10")
# Swatch: 72 x 72 pt = exactly 150 x 150 px at 150 DPI (72pt * 150/72 = 150)
# Hero:   290 x 290 pt => ~604 x 604 px => ~22% of page area (> 10% cap => rejected)
# Tiny:   5 x 5 pt => ~10 x 10 px (< 12 px minimum => rejected)
# ---------------------------------------------------------------------------

_DPI = 150
_PAGE_W_PT, _PAGE_H_PT = 504, 720
_SWATCH_PT = 72
_SWATCH_PX = 150  # exact: 72 * 150/72

_SWATCH_POSITIONS_PT = [
    (50, 50),
    (200, 50),
    (350, 50),
]
_SWATCH_LABELS = ["BEECH", "MAPLE", "WALNUT"]

_HERO_RECT_PT = fitz.Rect(50, 200, 340, 490)   # 290x290 pt
_TINY_RECT_PT = fitz.Rect(450, 50, 455, 55)    # 5x5 pt


def _solid_png(size: int = 10) -> bytes:
    img = Image.new("RGB", (size, size), color=(200, 100, 50))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_and_reload() -> tuple[fitz.Page, list[fitz.Rect]]:
    """Build a synthetic PDF, save+reload, return page and swatch rects in PDF points."""
    doc = fitz.open()
    page = doc.new_page(width=_PAGE_W_PT, height=_PAGE_H_PT)
    png = _solid_png()

    swatch_rects_pt: list[fitz.Rect] = []
    for (x, y), label in zip(_SWATCH_POSITIONS_PT, _SWATCH_LABELS):
        rect = fitz.Rect(x, y, x + _SWATCH_PT, y + _SWATCH_PT)
        swatch_rects_pt.append(rect)
        page.insert_image(rect, stream=png)
        page.insert_text(fitz.Point(x + 4, y + _SWATCH_PT + 12), label, fontsize=10)

    page.insert_image(_HERO_RECT_PT, stream=png)
    page.insert_image(_TINY_RECT_PT, stream=png)

    buf = BytesIO()
    doc.save(buf)
    doc.close()
    buf.seek(0)
    doc2 = fitz.open(stream=buf.read(), filetype="pdf")
    return doc2[0], swatch_rects_pt


def _page_size_px(page: fitz.Page) -> tuple[int, int]:
    return (
        math.ceil(page.rect.width * _DPI / 72),
        math.ceil(page.rect.height * _DPI / 72),
    )


def _make_sample() -> ImageSampleDefinition:
    return ImageSampleDefinition(
        rect_px=RectPx(x0=0, y0=0, x1=_SWATCH_PX, y1=_SWATCH_PX),
        width_px=_SWATCH_PX,
        height_px=_SWATCH_PX,
        aspect_ratio=1.0,
    )


# ---------------------------------------------------------------------------
# Size / aspect filtering
# ---------------------------------------------------------------------------


def test_detects_exactly_three_swatches() -> None:
    """Only the three 72x72pt swatches match; hero and tiny icon are filtered out."""
    page, _ = _build_and_reload()
    sample = _make_sample()
    opts = PatternDetectionOptions(require_text=False)
    page_size = _page_size_px(page)

    rects_pts = embedded_image_rects_pts(page)
    matches = [
        rect_pts_to_px(r)
        for r in rects_pts
        if image_matches_sample(rect_pts_to_px(r), sample, opts, page_size)
    ]
    page.parent.close()

    assert len(matches) == 3


def test_hero_image_rejected_by_area_cap() -> None:
    """290x290 pt hero is ~22% of page area, exceeding the 10% cap."""
    sample = _make_sample()
    opts = PatternDetectionOptions(require_text=False, max_page_area_pct=0.10)

    page_w_px = math.ceil(_PAGE_W_PT * _DPI / 72)
    page_h_px = math.ceil(_PAGE_H_PT * _DPI / 72)
    hero_px = rect_pts_to_px(_HERO_RECT_PT)

    assert not image_matches_sample(hero_px, sample, opts, (page_w_px, page_h_px))


def test_tiny_icon_rejected_by_min_size() -> None:
    """5x5 pt icon converts to ~10-11px, below the 12px minimum."""
    sample = _make_sample()
    opts = PatternDetectionOptions(require_text=False, min_image_width_px=12, min_image_height_px=12)
    page_size = (math.ceil(_PAGE_W_PT * _DPI / 72), math.ceil(_PAGE_H_PT * _DPI / 72))
    tiny_px = rect_pts_to_px(_TINY_RECT_PT)

    assert not image_matches_sample(tiny_px, sample, opts, page_size)


# ---------------------------------------------------------------------------
# Text extraction from detected image rects
# ---------------------------------------------------------------------------


def test_extracts_labels_below_detected_swatches() -> None:
    """Text inserted below each swatch is correctly extracted via a RelativeRect."""
    page, _ = _build_and_reload()
    sample = _make_sample()
    opts = PatternDetectionOptions(require_text=False)
    page_size = _page_size_px(page)

    rects_pts = embedded_image_rects_pts(page)
    matched_pts = sorted(
        [r for r in rects_pts if image_matches_sample(rect_pts_to_px(r), sample, opts, page_size)],
        key=lambda r: r.x0,
    )

    # Text region: same width as image, starting just below, 20pt tall.
    # Represented as RelativeRect: y0=1.0 (image bottom), y1 = 1.0 + 20/72 ≈ 1.28
    text_rel = RelativeRect(x0=0.0, y0=1.0, x1=1.0, y1=1.0 + 20.0 / _SWATCH_PT)

    text_page = page.get_textpage()
    extracted: list[str] = []
    for img_rect_pts in matched_pts:
        img_px = rect_pts_to_px(img_rect_pts)
        text_px = resolve_relative_rect(text_rel, img_px)
        text_pts = fitz.Rect(
            text_px.x0 * 72 / _DPI,
            text_px.y0 * 72 / _DPI,
            text_px.x1 * 72 / _DPI,
            text_px.y1 * 72 / _DPI,
        )
        extracted.append(extract_text_from_rect(page, text_pts, text_page=text_page))

    page.parent.close()

    assert len(extracted) == 3
    labels_found = set(extracted)
    assert "BEECH" in labels_found
    assert "MAPLE" in labels_found
    assert "WALNUT" in labels_found


# ---------------------------------------------------------------------------
# require_text filtering
# ---------------------------------------------------------------------------


def test_require_text_rejects_candidates_with_no_text() -> None:
    """Swatches without text in the extraction rect are excluded when require_text=True."""
    page, _ = _build_and_reload()
    sample = _make_sample()
    page_size = _page_size_px(page)
    opts = PatternDetectionOptions(require_text=False)

    rects_pts = embedded_image_rects_pts(page)
    matched_pts = [
        r for r in rects_pts if image_matches_sample(rect_pts_to_px(r), sample, opts, page_size)
    ]

    # Use a text rect that points ABOVE the image (where there is no text)
    text_rel = RelativeRect(x0=0.0, y0=-0.5, x1=1.0, y1=0.0)
    text_page = page.get_textpage()

    empty_count = sum(
        1
        for img_pts in matched_pts
        for img_px in [rect_pts_to_px(img_pts)]
        for text_px in [resolve_relative_rect(text_rel, img_px)]
        for text_pts in [fitz.Rect(
            text_px.x0 * 72 / _DPI, text_px.y0 * 72 / _DPI,
            text_px.x1 * 72 / _DPI, text_px.y1 * 72 / _DPI,
        )]
        if not extract_text_from_rect(page, text_pts, text_page=text_page)
    )
    page.parent.close()

    # All 3 swatches have no text above them — they would be rejected with require_text=True
    assert empty_count == 3
