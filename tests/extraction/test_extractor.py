"""Tests for Extractor group and field extraction."""

from __future__ import annotations

from pathlib import Path

from src.extraction.extractor import Extractor
from src.extraction.grid import CellGroup, FieldDefinition, Grid, OmitRegion
from tests.extraction.conftest import H_LINE_PX, MATERIAL_A, MATERIAL_B, V_LINE_PX


def right_grid() -> Grid:
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


def below_grid() -> Grid:
    return Grid(
        horizontal_lines=[H_LINE_PX],
        vertical_lines=[V_LINE_PX],
        fields=[
            FieldDefinition("swatch", "image", 1),
            FieldDefinition("material_id", "text", 1),
        ],
        groups=[CellGroup(field_cells={"swatch": [(0, 0)], "material_id": [(1, 0)]})],
    )


class TestExtractorGroups:
    def test_extracts_expected_material_ids(self, single_page_pdf: Path) -> None:
        groups = Extractor(str(single_page_pdf), right_grid()).extract_all_pages()
        ids = [group.values["material_id"].text for group in groups]
        assert MATERIAL_A[0] in ids
        assert MATERIAL_B[0] in ids

    def test_extracts_two_groups_from_single_page(self, single_page_pdf: Path) -> None:
        groups = Extractor(str(single_page_pdf), right_grid()).extract_all_pages()
        assert len(groups) == 2

    def test_image_field_bytes_are_png(self, single_page_pdf: Path) -> None:
        groups = Extractor(str(single_page_pdf), right_grid()).extract_all_pages()
        for group in groups:
            assert group.values["swatch"].image_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_multi_page_yields_groups_from_every_page(self, multi_page_pdf: Path) -> None:
        groups = Extractor(str(multi_page_pdf), right_grid()).extract_all_pages()
        assert len(groups) == 4

    def test_empty_text_field_still_yields_sparse_group(self, empty_text_pdf: Path) -> None:
        grid = Grid(
            vertical_lines=[V_LINE_PX],
            fields=[
                FieldDefinition("swatch", "image", 1),
                FieldDefinition("material_id", "text", 1),
            ],
            groups=[CellGroup(field_cells={"swatch": [(0, 0)], "material_id": [(0, 1)]})],
        )

        groups = Extractor(str(empty_text_pdf), grid).extract_all_pages()

        assert len(groups) == 1
        assert groups[0].values["material_id"].text == ""
        assert groups[0].values["swatch"].image_bytes

    def test_no_groups_defined_yields_nothing(self, single_page_pdf: Path) -> None:
        grid = Grid(
            horizontal_lines=[H_LINE_PX],
            vertical_lines=[V_LINE_PX],
            fields=[FieldDefinition("material_id", "text", 1)],
            groups=[],
        )

        assert Extractor(str(single_page_pdf), grid).extract_all_pages() == []

    def test_out_of_range_cell_is_skipped(self, single_page_pdf: Path) -> None:
        grid = Grid(
            horizontal_lines=[H_LINE_PX],
            vertical_lines=[V_LINE_PX],
            fields=[FieldDefinition("material_id", "text", 1)],
            groups=[CellGroup(field_cells={"material_id": [(99, 99)]})],
        )

        assert Extractor(str(single_page_pdf), grid).extract_all_pages() == []

    def test_below_group_extracts_correct_id(self, below_group_pdf: Path) -> None:
        groups = Extractor(str(below_group_pdf), below_grid()).extract_all_pages()
        assert len(groups) == 1
        assert groups[0].values["material_id"].text == MATERIAL_A[0]

    def test_multi_cell_field_extracts_as_one_area(self, single_page_pdf: Path) -> None:
        grid = Grid(
            horizontal_lines=[H_LINE_PX],
            vertical_lines=[V_LINE_PX],
            fields=[FieldDefinition("row_text", "text", 2)],
            groups=[CellGroup(field_cells={"row_text": [(0, 0), (0, 1)]})],
        )

        groups = Extractor(str(single_page_pdf), grid).extract_all_pages()

        assert len(groups) == 1
        assert MATERIAL_A[0] in groups[0].values["row_text"].text

    def test_omit_region_intersecting_any_field_skips_group(self, single_page_pdf: Path) -> None:
        grid = right_grid()
        grid.omit_regions = [OmitRegion(page_index=0, rect=(0, 0, 50, 50))]

        groups = Extractor(str(single_page_pdf), grid).extract_all_pages()

        assert len(groups) == 1
        assert groups[0].values["material_id"].text == MATERIAL_B[0]
