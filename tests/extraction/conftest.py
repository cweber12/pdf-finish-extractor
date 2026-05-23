"""Programmatic PDF fixtures for extractor tests.

All PDFs are built with PyMuPDF at test time — no binary files committed.

Page layout (400 × 400 PDF points, 2 × 2 grid split at the midpoint):

    col 0 (0–200 pt)      col 1 (200–400 pt)
  ┌─────────────────────┬─────────────────────┐
  │  row 0  (0–200 pt)  │                     │
  │                     │                     │
  ├─────────────────────┤                     │
  │  row 1 (200–400 pt) │                     │
  │                     │                     │
  └─────────────────────┴─────────────────────┘

The horizontal / vertical split point in *pixel* space (at 150 DPI):
  round(200 * 150/72) = 417 px
"""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

# Must match src.extraction.extractor._RENDER_DPI
_RENDER_DPI = 150
_SCALE = _RENDER_DPI / 72.0

# Page dimensions in PDF points
PAGE_W = 400
PAGE_H = 400

# Grid line positions in pixel space (passed to Grid.horizontal_lines / vertical_lines)
H_LINE_PX = round(PAGE_H / 2 * _SCALE)  # ≈ 417
V_LINE_PX = round(PAGE_W / 2 * _SCALE)  # ≈ 417

# Materials used in fixtures
MATERIAL_A = ("MAT-001", (0.2, 0.7, 0.3))   # green-ish fill
MATERIAL_B = ("MAT-002", (0.2, 0.3, 0.8))   # blue-ish fill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mid(a: float, b: float) -> float:
    return (a + b) / 2


def add_right_group_rows(
    page: fitz.Page,
    materials: list[tuple[str, tuple[float, float, float]]],
) -> None:
    """Draw one row per material: coloured rect (left col) + text ID (right col)."""
    mid_x = PAGE_W / 2
    row_h = PAGE_H / len(materials)

    for i, (mat_id, color) in enumerate(materials):
        y0 = i * row_h
        y1 = y0 + row_h

        # Coloured rectangle fills the left cell
        page.draw_rect(fitz.Rect(0, y0, mid_x, y1), fill=color, color=color)

        # Text ID in the right cell — baseline well inside the cell
        page.insert_text(
            fitz.Point(mid_x + 20, _mid(y0, y1)),
            mat_id,
            fontsize=14,
        )


def add_below_group_row(
    page: fitz.Page,
    material: tuple[str, tuple[float, float, float]],
) -> None:
    """Image in top-left cell, text in bottom-left cell."""
    mat_id, color = material
    mid_x = PAGE_W / 2
    mid_y = PAGE_H / 2

    # Coloured rect in top-left cell
    page.draw_rect(fitz.Rect(0, 0, mid_x, mid_y), fill=color, color=color)

    # Text ID in bottom-left cell
    page.insert_text(fitz.Point(20, mid_y + mid_y / 2), mat_id, fontsize=14)


# ---------------------------------------------------------------------------
# Session-scoped fixtures  (created once, reused across all tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def single_page_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One page, right-side text groups — MAT-001 (row 0) and MAT-002 (row 1)."""
    path = tmp_path_factory.mktemp("fixtures") / "single_page.pdf"
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    add_right_group_rows(page, [MATERIAL_A, MATERIAL_B])
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def multi_page_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Two identical pages, right-side text groups — 4 groups total."""
    path = tmp_path_factory.mktemp("fixtures") / "multi_page.pdf"
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        add_right_group_rows(page, [MATERIAL_A, MATERIAL_B])
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def empty_text_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One page with coloured rects but NO text in the text cells."""
    path = tmp_path_factory.mktemp("fixtures") / "empty_text.pdf"
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    mid_x = PAGE_W / 2
    # Only draw the coloured rect — no insert_text call
    page.draw_rect(fitz.Rect(0, 0, mid_x, PAGE_H), fill=(0.8, 0.2, 0.2))
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def below_group_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One page, below-text group — image top-left, text bottom-left."""
    path = tmp_path_factory.mktemp("fixtures") / "below_group.pdf"
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    add_below_group_row(page, MATERIAL_A)
    doc.save(str(path))
    doc.close()
    return path
