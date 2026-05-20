from __future__ import annotations

from dataclasses import dataclass

import fitz  # PyMuPDF

from src.extraction.grid import Grid

_RENDER_DPI = 150
_SCALE = _RENDER_DPI / 72.0  # pixels per PDF point


@dataclass
class ExtractedPair:
    material_id: str
    image_bytes: bytes
    is_duplicate: bool = False


class Extractor:
    """Applies a :class:`Grid` to every page of a PDF and returns image/ID pairs.

    Coordinate mapping
    ------------------
    The grid stores line positions in *rendered pixel* space (at 150 DPI).
    PyMuPDF works in *PDF points* (72 pts = 1 inch).
    We divide pixel coords by ``_SCALE`` to convert before passing to PyMuPDF.
    """

    def __init__(self, pdf_path: str, grid: Grid) -> None:
        self._pdf_path = pdf_path
        self._grid = grid

    def extract_all_pages(self) -> list[ExtractedPair]:
        pairs: list[ExtractedPair] = []
        doc = fitz.open(self._pdf_path)
        try:
            for page in doc:
                pairs.extend(self._extract_page(page))
        finally:
            doc.close()
        return pairs

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extract_page(self, page: fitz.Page) -> list[ExtractedPair]:
        g = self._grid
        h_pts = [y / _SCALE for y in [0] + sorted(g.horizontal_lines)]
        h_pts.append(page.rect.height)
        v_pts = [x / _SCALE for x in [0] + sorted(g.vertical_lines)]
        v_pts.append(page.rect.width)

        def cell_rect(ri: int, ci: int) -> fitz.Rect | None:
            if ri >= len(h_pts) - 1 or ci >= len(v_pts) - 1:
                return None
            return fitz.Rect(v_pts[ci], h_pts[ri], v_pts[ci + 1], h_pts[ri + 1])

        results: list[ExtractedPair] = []
        for pair in g.pairs:
            img_rect = cell_rect(*pair.image_cell)
            txt_rect = cell_rect(*pair.text_cell)
            if img_rect is None or txt_rect is None:
                continue
            material_id = page.get_text("text", clip=txt_rect).strip()
            if not material_id:
                continue
            image_bytes = self._crop_image(page, img_rect)
            results.append(ExtractedPair(material_id=material_id, image_bytes=image_bytes))
        return results

    def _crop_image(self, page: fitz.Page, rect: fitz.Rect) -> bytes:
        mat = fitz.Matrix(_SCALE, _SCALE)
        clip = page.rect & rect
        pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
        return pix.tobytes("png")
