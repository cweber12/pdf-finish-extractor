from __future__ import annotations

from dataclasses import dataclass, field

import fitz  # PyMuPDF
from PyQt6.QtGui import QPixmap, QImage

from src.extraction.grid import Grid, CellType, PairDirection

_RENDER_DPI = 150
_SCALE = _RENDER_DPI / 72.0  # pixels per PDF point


@dataclass
class ExtractedPair:
    material_id: str
    image_bytes: bytes
    image_pixmap: QPixmap | None = None
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

        pairs: list[ExtractedPair] = []
        image_cells: list[tuple[int, int]] = []
        text_cells: dict[tuple[int, int], str] = {}

        for ri in range(len(h_pts) - 1):
            for ci in range(len(v_pts) - 1):
                cell_type = g.cell_types.get((ri, ci), CellType.IGNORED)
                rect = fitz.Rect(v_pts[ci], h_pts[ri], v_pts[ci + 1], h_pts[ri + 1])

                if cell_type == CellType.IMAGE:
                    image_cells.append((ri, ci))
                elif cell_type == CellType.TEXT:
                    text = page.get_text("text", clip=rect).strip()
                    text_cells[(ri, ci)] = text

        for (ri, ci) in image_cells:
            paired = self._find_text_cell(ri, ci, text_cells)
            if paired is None:
                continue
            material_id, text_coord = paired
            if not material_id:
                continue

            rect = fitz.Rect(
                v_pts[ci], h_pts[ri], v_pts[ci + 1], h_pts[ri + 1]
            )
            image_bytes = self._crop_image(page, rect)
            pixmap = self._bytes_to_pixmap(image_bytes, rect, page)
            pairs.append(ExtractedPair(
                material_id=material_id,
                image_bytes=image_bytes,
                image_pixmap=pixmap,
            ))

        return pairs

    def _find_text_cell(
        self,
        ri: int,
        ci: int,
        text_cells: dict[tuple[int, int], str],
    ) -> tuple[str, tuple[int, int]] | None:
        direction = self._grid.pair_direction
        offsets = {
            PairDirection.RIGHT: (0, 1),
            PairDirection.LEFT: (0, -1),
            PairDirection.BELOW: (1, 0),
            PairDirection.ABOVE: (-1, 0),
        }
        dr, dc = offsets[direction]
        candidate = (ri + dr, ci + dc)
        text = text_cells.get(candidate)
        if text is not None:
            return text, candidate
        return None

    def _crop_image(self, page: fitz.Page, rect: fitz.Rect) -> bytes:
        mat = fitz.Matrix(_SCALE, _SCALE)
        clip = page.rect & rect
        pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
        return pix.tobytes("png")

    def _bytes_to_pixmap(
        self, image_bytes: bytes, rect: fitz.Rect, page: fitz.Page
    ) -> QPixmap | None:
        try:
            import io
            from PIL import Image as PILImage

            img = PILImage.open(io.BytesIO(image_bytes))
            img = img.convert("RGB")
            data = img.tobytes("raw", "RGB")
            qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
            return QPixmap.fromImage(qimg)
        except Exception:
            return None
