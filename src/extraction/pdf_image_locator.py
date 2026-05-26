from __future__ import annotations

import math

import fitz

from src.extraction.pattern import RectPx

_DEFAULT_DPI = 150


def embedded_image_rects_pts(page: fitz.Page) -> list[fitz.Rect]:
    """Return bounding rectangles (in PDF points) for all embedded images on the page."""
    rects: list[fitz.Rect] = []
    for info in page.get_image_info(xrefs=True):
        raw_bbox = info.get("bbox")
        if raw_bbox is None:
            continue
        rect = fitz.Rect(
            float(raw_bbox[0]),
            float(raw_bbox[1]),
            float(raw_bbox[2]),
            float(raw_bbox[3]),
        )
        if rect.is_empty or rect.is_infinite:
            continue
        rects.append(rect)
    return rects


def drawing_rects_pts(page: fitz.Page) -> list[fitz.Rect]:
    """Return bounding rectangles (in PDF points) for all vector drawing paths on the page."""
    rects: list[fitz.Rect] = []
    for path in page.get_drawings():
        raw_rect = path.get("rect")
        if raw_rect is None:
            continue
        rect = fitz.Rect(
            float(raw_rect.x0),
            float(raw_rect.y0),
            float(raw_rect.x1),
            float(raw_rect.y1),
        )
        if rect.is_empty or rect.is_infinite:
            continue
        rects.append(rect)
    return rects


def rect_pts_to_px(rect: fitz.Rect, dpi: int = _DEFAULT_DPI) -> RectPx:
    """Convert a PDF-points rect to pixel-space using floor/ceil to avoid clipping."""
    scale = dpi / 72.0
    return RectPx(
        x0=math.floor(rect.x0 * scale),
        y0=math.floor(rect.y0 * scale),
        x1=math.ceil(rect.x1 * scale),
        y1=math.ceil(rect.y1 * scale),
    )


def rect_px_to_pts(rect: RectPx, dpi: int = _DEFAULT_DPI) -> fitz.Rect:
    """Convert a pixel-space RectPx back to PDF points."""
    scale = 72.0 / dpi
    return fitz.Rect(
        rect.x0 * scale,
        rect.y0 * scale,
        rect.x1 * scale,
        rect.y1 * scale,
    )
