from src.extraction.grid import OmitRegion
from src.ui.grid_editor_geometry import (
    cell_at_orig_point,
    clamped_orig_point,
    grid_orig_boundaries,
    omit_region_index_at_orig_point,
)


def test_grid_orig_boundaries_adds_edges_and_sorts() -> None:
    h, v = grid_orig_boundaries([200, 100], [300, 50], page_height=500, page_width=400)

    assert h == [0, 100, 200, 500]
    assert v == [0, 50, 300, 400]


def test_cell_at_orig_point_returns_row_col_when_inside() -> None:
    cell = cell_at_orig_point(
        120,
        140,
        page_height=400,
        page_width=300,
        horizontal_lines=[100, 250],
        vertical_lines=[90, 200],
    )

    assert cell == (1, 1)


def test_cell_at_orig_point_returns_none_when_outside() -> None:
    assert (
        cell_at_orig_point(
            -1,
            50,
            page_height=400,
            page_width=300,
            horizontal_lines=[100],
            vertical_lines=[90],
        )
        is None
    )
    assert (
        cell_at_orig_point(
            301,
            50,
            page_height=400,
            page_width=300,
            horizontal_lines=[100],
            vertical_lines=[90],
        )
        is None
    )


def test_omit_region_index_at_orig_point_prefers_latest_matching_region() -> None:
    regions = [
        OmitRegion(page_index=0, rect=(0, 0, 50, 50)),
        OmitRegion(page_index=0, rect=(10, 10, 60, 60)),
        OmitRegion(page_index=1, rect=(0, 0, 100, 100)),
    ]

    idx = omit_region_index_at_orig_point(20, 20, regions=regions, page_index=0)

    assert idx == 1


def test_omit_region_index_at_orig_point_ignores_other_pages() -> None:
    regions = [OmitRegion(page_index=1, rect=(0, 0, 50, 50))]
    assert omit_region_index_at_orig_point(20, 20, regions=regions, page_index=0) is None


def test_clamped_orig_point_with_page_size() -> None:
    assert clamped_orig_point(-10, 800, page_height=500, page_width=300) == (0, 500)
    assert clamped_orig_point(100, 200, page_height=500, page_width=300) == (100, 200)


def test_clamped_orig_point_without_page_size() -> None:
    assert clamped_orig_point(-5, 10, page_height=None, page_width=None) == (0, 10)
