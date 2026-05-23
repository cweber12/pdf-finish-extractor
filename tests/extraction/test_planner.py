from __future__ import annotations

from pathlib import Path

import fitz

from src.extraction.grid import CellGroup, FieldDefinition, Grid, GridSegment, OmitRegion
from src.extraction.planner import ExtractionPlanner
from tests.extraction.conftest import H_LINE_PX, V_LINE_PX


def _base_grid() -> Grid:
    return Grid(
        horizontal_lines=[H_LINE_PX],
        vertical_lines=[V_LINE_PX],
        fields=[
            FieldDefinition("swatch", "image", 1),
            FieldDefinition("material_id", "text", 1),
        ],
        groups=[
            CellGroup(field_cells={"swatch": [(0, 0)], "material_id": [(0, 1)]}),
            CellGroup(field_cells={"swatch": [(1, 0)], "material_id": [(1, 1)]}),
        ],
    )


def _planned_group_count(pdf_path: str, planner: ExtractionPlanner, page_index: int = 0) -> int:
    with fitz.open(pdf_path) as doc:
        return len(planner.plan_page(doc[page_index]))


class TestExtractionPlanner:
    def test_plan_page_returns_groups_for_valid_layout(self, single_page_pdf: Path) -> None:
        planner = ExtractionPlanner(_base_grid())

        assert _planned_group_count(str(single_page_pdf), planner) == 2

    def test_plan_page_skips_group_intersecting_omit_region(self, single_page_pdf: Path) -> None:
        grid = _base_grid()
        grid.omit_regions = [OmitRegion(page_index=0, rect=(0, 0, 60, 60))]
        planner = ExtractionPlanner(grid)

        assert _planned_group_count(str(single_page_pdf), planner) == 1

    def test_plan_page_keeps_groups_for_non_intersecting_omit_region(
        self,
        single_page_pdf: Path,
    ) -> None:
        grid = _base_grid()
        grid.omit_regions = [OmitRegion(page_index=0, rect=(1000, 1000, 1100, 1100))]
        planner = ExtractionPlanner(grid)

        assert _planned_group_count(str(single_page_pdf), planner) == 2

    def test_plan_page_uses_segment_for_current_page(self, multi_page_pdf: Path) -> None:
        fields = [FieldDefinition("material_id", "text", 1)]
        segments = [
            GridSegment(
                start_page=0,
                horizontal_lines=[H_LINE_PX],
                vertical_lines=[V_LINE_PX],
                groups=[CellGroup(field_cells={"material_id": [(0, 1)]})],
            ),
            GridSegment(
                start_page=1,
                horizontal_lines=[H_LINE_PX],
                vertical_lines=[V_LINE_PX],
                groups=[],
            ),
        ]
        planner = ExtractionPlanner(Grid(fields=fields), segments=segments)

        with fitz.open(str(multi_page_pdf)) as doc:
            page0_groups = planner.plan_page(doc[0])
            page1_groups = planner.plan_page(doc[1])

        assert len(page0_groups) == 1
        assert len(page1_groups) == 0
