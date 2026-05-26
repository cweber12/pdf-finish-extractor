from __future__ import annotations

import math
from io import BytesIO

import fitz
from PIL import Image


def extract_text_from_rect(
    page: fitz.Page,
    rect_pts: fitz.Rect,
    text_page: fitz.TextPage | None = None,
) -> str:
    """Extract and strip text from *rect_pts* on *page*.

    Pass a pre-built *text_page* to avoid redundant extraction when processing
    many rects on the same page.
    """
    return str(page.get_textbox(rect_pts, textpage=text_page)).strip()


def crop_page_rect_to_png(
    page: fitz.Page,
    rect_pts: fitz.Rect,
    render_scale: float,
    page_image: Image.Image | None = None,
    png_compress_level: int = 1,
) -> bytes:
    """Render *rect_pts* from *page* to PNG bytes.

    If *page_image* is provided (the full page already rendered), the crop is
    taken from it without a second render call.  Otherwise the clip region is
    rendered on demand.
    """
    if page_image is None:
        return _crop_clip(page, rect_pts, render_scale, png_compress_level)

    crop_box = _rect_to_pixel_box(rect_pts, render_scale, page_image.width, page_image.height)
    if crop_box is None:
        return b""
    crop = page_image.crop(crop_box)
    try:
        return _encode_png(crop, png_compress_level)
    finally:
        crop.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _crop_clip(
    page: fitz.Page,
    rect_pts: fitz.Rect,
    render_scale: float,
    png_compress_level: int,
) -> bytes:
    mat = fitz.Matrix(render_scale, render_scale)
    clip = page.rect & rect_pts
    if clip.is_empty or clip.is_infinite:
        return b""
    pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    try:
        return _encode_png(image, png_compress_level)
    finally:
        image.close()


def _rect_to_pixel_box(
    rect: fitz.Rect,
    render_scale: float,
    pixmap_width: int,
    pixmap_height: int,
) -> tuple[int, int, int, int] | None:
    left = math.floor(rect.x0 * render_scale)
    top = math.floor(rect.y0 * render_scale)
    right = math.ceil(rect.x1 * render_scale)
    bottom = math.ceil(rect.y1 * render_scale)

    left = max(0, min(left, pixmap_width))
    top = max(0, min(top, pixmap_height))
    right = max(0, min(right, pixmap_width))
    bottom = max(0, min(bottom, pixmap_height))

    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _encode_png(image: Image.Image, compress_level: int) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG", compress_level=compress_level, optimize=False)
    return buf.getvalue()
