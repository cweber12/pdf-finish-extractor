from __future__ import annotations

from src.extraction.pattern import PatternSide, RectPx

_DEFAULT_TEXT_RATIO = 0.35
_MIN_SIZE = 8


def default_text_region(image_rect: RectPx, side: PatternSide) -> RectPx:
    """Return a text region rectangle adjacent to image_rect on the given side."""
    w = image_rect.x1 - image_rect.x0
    h = image_rect.y1 - image_rect.y0
    if side == "below":
        gap = max(round(h * _DEFAULT_TEXT_RATIO), _MIN_SIZE)
        return RectPx(image_rect.x0, image_rect.y1, image_rect.x1, image_rect.y1 + gap)
    if side == "above":
        gap = max(round(h * _DEFAULT_TEXT_RATIO), _MIN_SIZE)
        return RectPx(image_rect.x0, image_rect.y0 - gap, image_rect.x1, image_rect.y0)
    if side == "right":
        gap = max(round(w * _DEFAULT_TEXT_RATIO), _MIN_SIZE)
        return RectPx(image_rect.x1, image_rect.y0, image_rect.x1 + gap, image_rect.y1)
    # left
    gap = max(round(w * _DEFAULT_TEXT_RATIO), _MIN_SIZE)
    return RectPx(image_rect.x0 - gap, image_rect.y0, image_rect.x0, image_rect.y1)


def normalize_rect(x0: int, y0: int, x1: int, y1: int) -> RectPx:
    """Return a RectPx with guaranteed x0 < x1 and y0 < y1."""
    return RectPx(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def clamp_rect_to_page(rect: RectPx, page_w: int, page_h: int) -> RectPx:
    return RectPx(
        x0=max(0, min(rect.x0, page_w)),
        y0=max(0, min(rect.y0, page_h)),
        x1=max(0, min(rect.x1, page_w)),
        y1=max(0, min(rect.y1, page_h)),
    )


def apply_rect_resize(rect: RectPx, handle_suffix: str, ox: int, oy: int) -> RectPx:
    """Return a resized rect by moving the given handle to (ox, oy) in original coords."""
    x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
    if handle_suffix == "tl":
        x0, y0 = ox, oy
    elif handle_suffix == "tr":
        x1, y0 = ox, oy
    elif handle_suffix == "bl":
        x0, y1 = ox, oy
    elif handle_suffix == "br":
        x1, y1 = ox, oy
    elif handle_suffix == "t":
        y0 = oy
    elif handle_suffix == "b":
        y1 = oy
    elif handle_suffix == "l":
        x0 = ox
    elif handle_suffix == "r":
        x1 = ox
    return RectPx(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def translate_rect(rect: RectPx, dx: int, dy: int) -> RectPx:
    return RectPx(rect.x0 + dx, rect.y0 + dy, rect.x1 + dx, rect.y1 + dy)


def clamp_section_divider(
    sections: list[RectPx], index: int, value: int, segmentation: str
) -> list[RectPx]:
    """Move the divider between sections[index] and sections[index+1], clamped to neighbours."""
    if index < 0 or index >= len(sections) - 1:
        return sections
    result = list(sections)
    if segmentation == "rows":
        lo = sections[index].y0 + _MIN_SIZE
        hi = sections[index + 1].y1 - _MIN_SIZE
        value = max(lo, min(hi, value))
        s0 = sections[index]
        s1 = sections[index + 1]
        result[index] = RectPx(s0.x0, s0.y0, s0.x1, value)
        result[index + 1] = RectPx(s1.x0, value, s1.x1, s1.y1)
    else:
        lo = sections[index].x0 + _MIN_SIZE
        hi = sections[index + 1].x1 - _MIN_SIZE
        value = max(lo, min(hi, value))
        s0 = sections[index]
        s1 = sections[index + 1]
        result[index] = RectPx(s0.x0, s0.y0, value, s0.y1)
        result[index + 1] = RectPx(value, s1.y0, s1.x1, s1.y1)
    return result
