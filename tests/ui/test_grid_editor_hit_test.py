from src.ui.grid_editor_hit_test import resolve_line_hit


def test_resolve_line_hit_returns_none_when_missing_bounds() -> None:
    assert resolve_line_hit(dx=10, dy=10, h_d=[], v_d=[0, 100], line_hit_dist=5) == (None, None)
    assert resolve_line_hit(dx=10, dy=10, h_d=[0, 100], v_d=[], line_hit_dist=5) == (None, None)


def test_resolve_line_hit_prefers_handle_over_line() -> None:
    hit = resolve_line_hit(
        dx=-14,
        dy=100,
        h_d=[0, 100, 200],
        v_d=[0, 100, 200],
        line_hit_dist=5,
    )

    assert hit == (0, None)


def test_resolve_line_hit_chooses_nearest_overlapping_handle() -> None:
    hit = resolve_line_hit(
        dx=-14,
        dy=103,
        h_d=[0, 100, 104, 200],
        v_d=[0, 200],
        line_hit_dist=5,
    )

    assert hit == (1, None)


def test_resolve_line_hit_respects_page_area_for_line_hits() -> None:
    hit = resolve_line_hit(
        dx=300,
        dy=100,
        h_d=[0, 100, 200],
        v_d=[0, 100, 200],
        line_hit_dist=5,
    )

    assert hit == (None, None)


def test_resolve_line_hit_matches_horizontal_line_inside_page() -> None:
    hit = resolve_line_hit(
        dx=50,
        dy=104,
        h_d=[0, 100, 200],
        v_d=[0, 100, 200],
        line_hit_dist=5,
    )

    assert hit == (0, None)


def test_resolve_line_hit_matches_vertical_line_inside_page() -> None:
    hit = resolve_line_hit(
        dx=96,
        dy=50,
        h_d=[0, 100, 200],
        v_d=[0, 100, 200],
        line_hit_dist=5,
    )

    assert hit == (None, 0)
