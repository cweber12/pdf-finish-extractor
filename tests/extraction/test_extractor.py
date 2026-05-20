"""Tests for Extractor — applies a Grid to a PDF and returns ExtractedPairs."""

from __future__ import annotations

from pathlib import Path

from src.extraction.extractor import Extractor
from src.extraction.grid import CellPair, Grid
from tests.extraction.conftest import H_LINE_PX, MATERIAL_A, MATERIAL_B, V_LINE_PX

# ---------------------------------------------------------------------------
# Grid factories
# ---------------------------------------------------------------------------


def right_grid() -> Grid:
    """Explicit pairs: col-0 image → col-1 text, two rows.

    Matches the fixture layout: one horizontal split at H_LINE_PX,
    one vertical split at V_LINE_PX → 2 rows × 2 cols.
    """
    return Grid(
        horizontal_lines=[H_LINE_PX],
        vertical_lines=[V_LINE_PX],
        pairs=[
            CellPair(image_cell=(0, 0), text_cell=(0, 1)),
            CellPair(image_cell=(1, 0), text_cell=(1, 1)),
        ],
    )


def below_grid() -> Grid:
    """Image cell top-left, text cell bottom-left."""
    return Grid(
        horizontal_lines=[H_LINE_PX],
        vertical_lines=[V_LINE_PX],
        pairs=[CellPair(image_cell=(0, 0), text_cell=(1, 0))],
    )


# ---------------------------------------------------------------------------
# Extraction correctness
# ---------------------------------------------------------------------------


class TestExtractorRightPairing:
    def test_extracts_expected_material_ids(self, single_page_pdf: Path) -> None:
        pairs = Extractor(str(single_page_pdf), right_grid()).extract_all_pages()
        ids = [p.material_id for p in pairs]
        assert MATERIAL_A[0] in ids
        assert MATERIAL_B[0] in ids

    def test_extracts_two_pairs_from_single_page(self, single_page_pdf: Path) -> None:
        pairs = Extractor(str(single_page_pdf), right_grid()).extract_all_pages()
        assert len(pairs) == 2

    def test_image_bytes_are_png(self, single_page_pdf: Path) -> None:
        pairs = Extractor(str(single_page_pdf), right_grid()).extract_all_pages()
        for pair in pairs:
            assert pair.image_bytes[:8] == b"\x89PNG\r\n\x1a\n", (
                f"Expected PNG magic bytes for material {pair.material_id}"
            )

    def test_image_bytes_are_non_empty(self, single_page_pdf: Path) -> None:
        pairs = Extractor(str(single_page_pdf), right_grid()).extract_all_pages()
        for pair in pairs:
            assert len(pair.image_bytes) > 0


class TestExtractorMultiPage:
    def test_multi_page_yields_pairs_from_every_page(self, multi_page_pdf: Path) -> None:
        pairs = Extractor(str(multi_page_pdf), right_grid()).extract_all_pages()
        assert len(pairs) == 4  # 2 materials × 2 pages

    def test_multi_page_same_ids_repeated(self, multi_page_pdf: Path) -> None:
        pairs = Extractor(str(multi_page_pdf), right_grid()).extract_all_pages()
        ids = [p.material_id for p in pairs]
        assert ids.count(MATERIAL_A[0]) == 2
        assert ids.count(MATERIAL_B[0]) == 2


class TestExtractorEdgeCases:
    def test_empty_text_cell_yields_no_pairs(self, empty_text_pdf: Path) -> None:
        """If the text cell has no text, the pair is silently skipped."""
        grid = Grid(
            horizontal_lines=[],
            vertical_lines=[V_LINE_PX],
            pairs=[CellPair(image_cell=(0, 0), text_cell=(0, 1))],
        )
        pairs = Extractor(str(empty_text_pdf), grid).extract_all_pages()
        assert pairs == []

    def test_no_pairs_defined_yields_nothing(self, single_page_pdf: Path) -> None:
        """A Grid with lines but no pairs should return nothing."""
        grid = Grid(
            horizontal_lines=[H_LINE_PX],
            vertical_lines=[V_LINE_PX],
            pairs=[],
        )
        pairs = Extractor(str(single_page_pdf), grid).extract_all_pages()
        assert pairs == []

    def test_out_of_range_cell_is_skipped(self, single_page_pdf: Path) -> None:
        """A CellPair referencing a non-existent cell index is silently skipped."""
        grid = Grid(
            horizontal_lines=[H_LINE_PX],
            vertical_lines=[V_LINE_PX],
            pairs=[CellPair(image_cell=(99, 99), text_cell=(0, 1))],
        )
        pairs = Extractor(str(single_page_pdf), grid).extract_all_pages()
        assert pairs == []


class TestExtractorBelowPairing:
    def test_below_pair_extracts_correct_id(self, below_pair_pdf: Path) -> None:
        pairs = Extractor(str(below_pair_pdf), below_grid()).extract_all_pages()
        assert len(pairs) == 1
        assert pairs[0].material_id == MATERIAL_A[0]

    def test_below_pair_image_bytes_are_png(self, below_pair_pdf: Path) -> None:
        pairs = Extractor(str(below_pair_pdf), below_grid()).extract_all_pages()
        assert pairs[0].image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
