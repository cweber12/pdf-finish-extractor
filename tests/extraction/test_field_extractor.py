from __future__ import annotations

from pathlib import Path

import fitz

from src.extraction.field_extractor import FieldExtractor
from src.extraction.grid import CellGroup, FieldDefinition, Grid
from src.extraction.planner import ExtractionPlanner
from tests.extraction.conftest import H_LINE_PX, V_LINE_PX


def _grid() -> Grid:
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


class TestFieldExtractor:
    def test_extract_groups_with_clip_render_path(self, single_page_pdf: Path) -> None:
        planner = ExtractionPlanner(_grid())
        extractor = FieldExtractor(
            render_dpi=150,
            full_page_render_threshold=99,
            png_compress_level=1,
        )

        with fitz.open(str(single_page_pdf)) as doc:
            resolved = planner.plan_page(doc[0])
            groups = extractor.extract_groups(doc[0], resolved)

        assert len(groups) == 2
        material_ids = {group["material_id"].text for group in groups}
        assert material_ids == {"MAT-001", "MAT-002"}
        assert all(group["swatch"].image_bytes[:8] == b"\x89PNG\r\n\x1a\n" for group in groups)

    def test_extract_groups_with_full_page_render_path(self, single_page_pdf: Path) -> None:
        planner = ExtractionPlanner(_grid())
        extractor = FieldExtractor(
            render_dpi=150,
            full_page_render_threshold=1,
            png_compress_level=1,
        )

        with fitz.open(str(single_page_pdf)) as doc:
            resolved = planner.plan_page(doc[0])
            groups = extractor.extract_groups(doc[0], resolved)

        assert len(groups) == 2
        assert all(group["swatch"].image_bytes for group in groups)

    def test_drops_group_when_all_extracted_values_are_blank(self, empty_text_pdf: Path) -> None:
        grid = Grid(
            vertical_lines=[V_LINE_PX],
            fields=[FieldDefinition("material_id", "text", 1)],
            groups=[CellGroup(field_cells={"material_id": [(0, 1)]})],
        )
        planner = ExtractionPlanner(grid)
        extractor = FieldExtractor(
            render_dpi=150,
            full_page_render_threshold=1,
            png_compress_level=1,
        )

        with fitz.open(str(empty_text_pdf)) as doc:
            resolved = planner.plan_page(doc[0])
            groups = extractor.extract_groups(doc[0], resolved)

        assert groups == []
