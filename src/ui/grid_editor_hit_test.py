from __future__ import annotations


def resolve_line_hit(
    *,
    dx: int,
    dy: int,
    h_d: list[int],
    v_d: list[int],
    line_hit_dist: int,
    handle_hit_padding: int = 5,
    page_hit_padding: int = 2,
    handle_outset: float = 14.0,
    handle_length: float = 22.0,
    handle_thickness: float = 9.0,
) -> tuple[int | None, int | None]:
    """Return line hit as (h_index, None) or (None, v_index)."""
    if len(h_d) < 2 or len(v_d) < 2:
        return None, None

    page_left = v_d[0]
    page_right = v_d[-1]
    page_top = h_d[0]
    page_bottom = h_d[-1]

    handle_candidates: list[tuple[float, str, int]] = []

    h_tab_x = page_left - handle_outset
    for idx, cy in enumerate(h_d[1:-1]):
        left = h_tab_x - (handle_length / 2.0)
        top = cy - (handle_thickness / 2.0)
        if _contains_point(
            dx,
            dy,
            left=left - handle_hit_padding,
            top=top - handle_hit_padding,
            width=handle_length + (2 * handle_hit_padding),
            height=handle_thickness + (2 * handle_hit_padding),
        ):
            center_y = top + (handle_thickness / 2.0)
            handle_candidates.append((abs(dy - center_y), "h", idx))

    v_tab_y = page_top - handle_outset
    for idx, cx in enumerate(v_d[1:-1]):
        left = cx - (handle_thickness / 2.0)
        top = v_tab_y - (handle_length / 2.0)
        if _contains_point(
            dx,
            dy,
            left=left - handle_hit_padding,
            top=top - handle_hit_padding,
            width=handle_thickness + (2 * handle_hit_padding),
            height=handle_length + (2 * handle_hit_padding),
        ):
            center_x = left + (handle_thickness / 2.0)
            handle_candidates.append((abs(dx - center_x), "v", idx))

    if handle_candidates:
        _distance, kind, idx = min(handle_candidates, key=lambda item: item[0])
        return (idx, None) if kind == "h" else (None, idx)

    if not _contains_point(
        dx,
        dy,
        left=page_left - page_hit_padding,
        top=page_top - page_hit_padding,
        width=(page_right - page_left) + (2 * page_hit_padding),
        height=(page_bottom - page_top) + (2 * page_hit_padding),
    ):
        return None, None

    for i, y_d in enumerate(h_d[1:-1]):
        if abs(dy - y_d) <= line_hit_dist:
            return i, None
    for i, x_d in enumerate(v_d[1:-1]):
        if abs(dx - x_d) <= line_hit_dist:
            return None, i
    return None, None


def _contains_point(
    x: float,
    y: float,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
) -> bool:
    right = left + width
    bottom = top + height
    return left <= x <= right and top <= y <= bottom
