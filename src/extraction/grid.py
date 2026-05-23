from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CellPair:
    """An explicit pairing of one image cell with one text cell.

    Cell addresses are ``(row_index, col_index)`` within the grid formed by
    ``horizontal_lines`` and ``vertical_lines``.
    """

    image_cell: tuple[int, int]
    text_cell: tuple[int, int]

    def to_dict(self) -> dict:
        return {
            "image_cell": list(self.image_cell),
            "text_cell": list(self.text_cell),
        }

    @classmethod
    def from_dict(cls, data: dict) -> CellPair:
        return cls(
            image_cell=_coerce_cell(data["image_cell"]),
            text_cell=_coerce_cell(data["text_cell"]),
        )


@dataclass(frozen=True)
class OmitRegion:
    """A page-specific rectangular area to skip during extraction.

    Coordinates are stored in the same 150-DPI rendered-pixel space as grid
    lines. ``page_index`` is zero-based. Regions are page-specific on purpose:
    they are intended for catalog pages that contain diagrams, renderings, ads,
    or other non-swatch areas inside an otherwise reusable layout.
    """

    page_index: int
    rect: tuple[int, int, int, int]  # x0, y0, x1, y1

    def to_dict(self) -> dict:
        return {
            "page_index": self.page_index,
            "rect": list(self.rect),
        }

    @classmethod
    def from_dict(cls, data: dict) -> OmitRegion:
        page_index = int(data.get("page_index", 0))
        rect = _coerce_rect(data.get("rect", [0, 0, 0, 0]))
        return cls(page_index=page_index, rect=rect)


@dataclass
class GridSegment:
    """Grid lines and pairings that apply from ``start_page`` onward.

    Stored in 150-DPI pixel space, the same coordinate system as :class:`Grid`.
    A segment covers all pages from ``start_page`` up to (but not including)
    the ``start_page`` of the next segment in a sorted sequence.
    """

    start_page: int
    horizontal_lines: list[int] = field(default_factory=list)
    vertical_lines: list[int] = field(default_factory=list)
    pairs: list[CellPair] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "start_page": self.start_page,
            "horizontal_lines": sorted(self.horizontal_lines),
            "vertical_lines": sorted(self.vertical_lines),
            "pairs": [p.to_dict() for p in self.pairs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GridSegment":
        return cls(
            start_page=int(data.get("start_page", 0)),
            horizontal_lines=[int(v) for v in data.get("horizontal_lines", [])],
            vertical_lines=[int(v) for v in data.get("vertical_lines", [])],
            pairs=[CellPair.from_dict(p) for p in data.get("pairs", [])],
        )


@dataclass
class Grid:
    """Defines a grid layout, pairings, and per-PDF omit rules.

    ``horizontal_lines`` and ``vertical_lines`` are pixel coordinates in the
    150-DPI rendered image space used by the editor and extractor.

    ``pairs`` explicitly lists which cells go together. Each :class:`CellPair`
    names the image cell and the text cell that contains the material ID.

    ``omitted_pages`` skips entire zero-based PDF pages during extraction.
    ``omit_regions`` skips page-specific rectangles that intersect a pair's
    image or text cell. This lets mixed catalog pages silently ignore diagrams,
    renderings, or empty sections without changing the reusable grid.
    """

    horizontal_lines: list[int] = field(default_factory=list)
    vertical_lines: list[int] = field(default_factory=list)
    pairs: list[CellPair] = field(default_factory=list)
    omitted_pages: list[int] = field(default_factory=list)
    omit_regions: list[OmitRegion] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return (
            not self.horizontal_lines
            and not self.vertical_lines
            and not self.pairs
            and not self.omitted_pages
            and not self.omit_regions
        )

    @property
    def has_pairs(self) -> bool:
        return bool(self.pairs)

    def normalized(self) -> Grid:
        """Return a cleaned copy of the grid/settings.

        This keeps saved profiles tolerant of accidental duplicate lines,
        negative coordinates, malformed omit rectangles, or invalid pair data
        without mutating the object owned by the UI.
        """
        horizontal = _dedupe_ints(v for v in self.horizontal_lines if v >= 0)
        vertical = _dedupe_ints(v for v in self.vertical_lines if v >= 0)
        omitted_pages = _dedupe_ints(v for v in self.omitted_pages if v >= 0)

        max_row = len(horizontal)
        max_col = len(vertical)

        pairs: list[CellPair] = []
        seen_pairs: set[tuple[tuple[int, int], tuple[int, int]]] = set()

        for pair in self.pairs:
            if not _cell_is_valid(pair.image_cell, max_row, max_col):
                continue
            if not _cell_is_valid(pair.text_cell, max_row, max_col):
                continue

            key = (pair.image_cell, pair.text_cell)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            pairs.append(pair)

        regions: list[OmitRegion] = []
        seen_regions: set[tuple[int, tuple[int, int, int, int]]] = set()
        for region in self.omit_regions:
            if region.page_index < 0:
                continue
            rect = _normalize_rect(region.rect)
            if rect is None:
                continue
            key = (region.page_index, rect)
            if key in seen_regions:
                continue
            seen_regions.add(key)
            regions.append(OmitRegion(page_index=region.page_index, rect=rect))

        return Grid(
            horizontal_lines=horizontal,
            vertical_lines=vertical,
            pairs=pairs,
            omitted_pages=omitted_pages,
            omit_regions=regions,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        normalized = self.normalized()
        return {
            "horizontal_lines": normalized.horizontal_lines,
            "vertical_lines": normalized.vertical_lines,
            "pairs": [p.to_dict() for p in normalized.pairs],
            "omitted_pages": normalized.omitted_pages,
            "omit_regions": [r.to_dict() for r in normalized.omit_regions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Grid:
        grid = cls(
            horizontal_lines=[int(v) for v in data.get("horizontal_lines", [])],
            vertical_lines=[int(v) for v in data.get("vertical_lines", [])],
            pairs=[CellPair.from_dict(p) for p in data.get("pairs", [])],
            omitted_pages=[int(v) for v in data.get("omitted_pages", [])],
            omit_regions=[OmitRegion.from_dict(r) for r in data.get("omit_regions", [])],
        )
        return grid.normalized()


def _coerce_cell(value: object) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Invalid cell address: {value!r}")
    return int(value[0]), int(value[1])


def _coerce_rect(value: object) -> tuple[int, int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"Invalid omit region rect: {value!r}")
    return int(value[0]), int(value[1]), int(value[2]), int(value[3])


def _normalize_rect(rect: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    x0, y0, x1, y1 = rect
    left, right = sorted((int(x0), int(x1)))
    top, bottom = sorted((int(y0), int(y1)))
    if right - left < 2 or bottom - top < 2:
        return None
    return left, top, right, bottom


def _dedupe_ints(values) -> list[int]:  # noqa: ANN001
    return sorted(set(int(v) for v in values))


def _cell_is_valid(cell: tuple[int, int], max_row: int, max_col: int) -> bool:
    row, col = cell
    # With N horizontal lines there are N + 1 rows; same for vertical lines.
    return 0 <= row <= max_row and 0 <= col <= max_col
