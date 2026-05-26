from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.extraction.pattern import RectPx

if TYPE_CHECKING:
    from src.ui.editor.pattern_editor_state import PatternEditorState

_CORNER_DIST = 8   # display pixels to register a corner handle hit
_EDGE_DIST = 5     # display pixels to register an edge handle hit
_DIVIDER_DIST = 5  # display pixels to register a section divider hit
_BODY_PAD = 2      # interior padding before a body hit registers


@dataclass(frozen=True)
class PatternHit:
    # target examples:
    #   "image_corner_tl" | "image_corner_tr" | "image_corner_bl" | "image_corner_br"
    #   "image_edge_t"    | "image_edge_b"    | "image_edge_l"    | "image_edge_r"
    #   "image_body"
    #   "text_corner_*"   | "text_edge_*"     | "text_body"
    #   "section_divider_N"  (N is the 0-based index between sections[N] and sections[N+1])
    #   ""  (no hit)
    target: str
    cursor: str  # "arrow" | "move" | "size_h" | "size_v" | "size_fdiag" | "size_bdiag"


_NO_HIT = PatternHit("", "arrow")


def _d_rect(rect: RectPx, o2d_fn) -> tuple[int, int, int, int]:
    x0d, y0d = o2d_fn(rect.x0, rect.y0)
    x1d, y1d = o2d_fn(rect.x1, rect.y1)
    return x0d, y0d, x1d, y1d


def _check_corners(
    dx: int, dy: int, rd: tuple[int, int, int, int], prefix: str
) -> PatternHit | None:
    x0, y0, x1, y1 = rd
    for name, cx, cy, cursor in (
        ("tl", x0, y0, "size_fdiag"),
        ("tr", x1, y0, "size_bdiag"),
        ("bl", x0, y1, "size_bdiag"),
        ("br", x1, y1, "size_fdiag"),
    ):
        if abs(dx - cx) <= _CORNER_DIST and abs(dy - cy) <= _CORNER_DIST:
            return PatternHit(f"{prefix}_corner_{name}", cursor)
    return None


def _check_edges(
    dx: int, dy: int, rd: tuple[int, int, int, int], prefix: str
) -> PatternHit | None:
    x0, y0, x1, y1 = rd
    mx = (x0 + x1) // 2
    my = (y0 + y1) // 2
    for name, ex, ey, cursor in (
        ("t", mx, y0, "size_v"),
        ("b", mx, y1, "size_v"),
        ("l", x0, my, "size_h"),
        ("r", x1, my, "size_h"),
    ):
        if abs(dx - ex) <= _EDGE_DIST and abs(dy - ey) <= _EDGE_DIST:
            return PatternHit(f"{prefix}_edge_{name}", cursor)
    return None


def _check_body(
    dx: int, dy: int, rd: tuple[int, int, int, int], name: str
) -> PatternHit | None:
    x0, y0, x1, y1 = rd
    p = _BODY_PAD
    if x0 + p < dx < x1 - p and y0 + p < dy < y1 - p:
        return PatternHit(name, "move")
    return None


def resolve_pattern_hit(
    dx: int,
    dy: int,
    state: PatternEditorState,
    o2d_fn,
) -> PatternHit:
    """Return the topmost element hit at display point (dx, dy)."""

    # Image rect handles have highest priority
    if state.image_rect_px is not None:
        ir = _d_rect(state.image_rect_px, o2d_fn)
        hit = _check_corners(dx, dy, ir, "image")
        if hit:
            return hit
        hit = _check_edges(dx, dy, ir, "image")
        if hit:
            return hit

    # Text region handles
    if state.text_region_rect_px is not None:
        tr = _d_rect(state.text_region_rect_px, o2d_fn)
        hit = _check_corners(dx, dy, tr, "text")
        if hit:
            return hit
        hit = _check_edges(dx, dy, tr, "text")
        if hit:
            return hit

    # Section dividers (between consecutive sections)
    if len(state.text_section_rects_px) > 1 and state.text_region_rect_px is not None:
        tr = _d_rect(state.text_region_rect_px, o2d_fn)
        for i, sect in enumerate(state.text_section_rects_px[:-1]):
            if state.segmentation == "rows":
                div_y = o2d_fn(0, sect.y1)[1]
                if abs(dy - div_y) <= _DIVIDER_DIST and tr[0] <= dx <= tr[2]:
                    return PatternHit(f"section_divider_{i}", "size_v")
            else:
                div_x = o2d_fn(sect.x1, 0)[0]
                if abs(dx - div_x) <= _DIVIDER_DIST and tr[1] <= dy <= tr[3]:
                    return PatternHit(f"section_divider_{i}", "size_h")

    # Body hits (lower priority)
    if state.image_rect_px is not None:
        ir = _d_rect(state.image_rect_px, o2d_fn)
        hit = _check_body(dx, dy, ir, "image_body")
        if hit:
            return hit

    if state.text_region_rect_px is not None:
        tr = _d_rect(state.text_region_rect_px, o2d_fn)
        hit = _check_body(dx, dy, tr, "text_body")
        if hit:
            return hit

    return _NO_HIT
