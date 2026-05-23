from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import fitz  # PyMuPDF

from src.common.errors import ExtractionError
from src.extraction.field_extractor import ExtractedFieldValue, FieldExtractor
from src.extraction.grid import Grid, GridSegment
from src.extraction.planner import ExtractionPlanner

_DEFAULT_RENDER_DPI = 150
_FULL_PAGE_RENDER_THRESHOLD = 2


@dataclass
class ExtractedGroup:
    values: dict[str, ExtractedFieldValue] = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        return any(value.has_data for value in self.values.values())

    @property
    def field_names(self) -> list[str]:
        return list(self.values)


@dataclass(frozen=True)
class ExtractionProgress:
    """Progress payload emitted after each processed page."""

    page_index: int
    page_count: int
    groups_extracted: int


class Extractor:
    """Apply a saved :class:`Grid` profile to a PDF and return extracted groups."""

    def __init__(
        self,
        pdf_path: str,
        grid: Grid,
        *,
        segments: list[GridSegment] | None = None,
        render_dpi: int = _DEFAULT_RENDER_DPI,
        full_page_render_threshold: int = _FULL_PAGE_RENDER_THRESHOLD,
        png_compress_level: int = 1,
    ) -> None:
        self._pdf_path = pdf_path
        self._grid = grid.normalized()
        self._segments: list[GridSegment] = (
            sorted(segments, key=lambda s: s.start_page) if segments else []
        )
        self._planner = ExtractionPlanner(self._grid, segments=self._segments or None)
        self._field_extractor = FieldExtractor(
            render_dpi=render_dpi,
            full_page_render_threshold=full_page_render_threshold,
            png_compress_level=png_compress_level,
        )

    def extract_all_pages(
        self,
        *,
        progress_callback: Callable[[ExtractionProgress], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[ExtractedGroup]:
        try:
            groups: list[ExtractedGroup] = []
            with fitz.open(self._pdf_path) as doc:
                page_count = len(doc)
                for page_index in range(page_count):
                    if cancel_check and cancel_check():
                        break

                    if page_index not in self._grid.omitted_pages:
                        try:
                            groups.extend(self._extract_page(doc[page_index]))
                        except ExtractionError:
                            raise
                        except Exception as exc:  # noqa: BLE001 - wrapped to typed extraction error
                            raise ExtractionError(
                                f"Could not extract data from page {page_index + 1}.",
                                detail=str(exc),
                            ) from exc

                    if progress_callback:
                        progress_callback(
                            ExtractionProgress(
                                page_index=page_index,
                                page_count=page_count,
                                groups_extracted=len(groups),
                            )
                        )
        except ExtractionError:
            raise
        except Exception as exc:  # noqa: BLE001 - wrapped to typed extraction error
            raise ExtractionError(
                "Could not extract data from this PDF.",
                detail=str(exc),
            ) from exc

        return groups

    def iter_pages(
        self,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Iterable[tuple[ExtractionProgress, list[ExtractedGroup]]]:
        try:
            total_groups = 0
            with fitz.open(self._pdf_path) as doc:
                page_count = len(doc)
                for page_index in range(page_count):
                    if cancel_check and cancel_check():
                        break

                    page_groups = []
                    if page_index not in self._grid.omitted_pages:
                        try:
                            page_groups = self._extract_page(doc[page_index])
                        except ExtractionError:
                            raise
                        except Exception as exc:  # noqa: BLE001 - wrapped to typed extraction error
                            raise ExtractionError(
                                f"Could not extract data from page {page_index + 1}.",
                                detail=str(exc),
                            ) from exc
                        total_groups += len(page_groups)
                    yield (
                        ExtractionProgress(
                            page_index=page_index,
                            page_count=page_count,
                            groups_extracted=total_groups,
                        ),
                        page_groups,
                    )
        except ExtractionError:
            raise
        except Exception as exc:  # noqa: BLE001 - wrapped to typed extraction error
            raise ExtractionError(
                "Could not iterate extraction pages for this PDF.",
                detail=str(exc),
            ) from exc

    def _extract_page(self, page: fitz.Page) -> list[ExtractedGroup]:
        resolved_groups = self._planner.plan_page(page)
        if not resolved_groups:
            return []
        values_list = self._field_extractor.extract_groups(page, resolved_groups)
        return [ExtractedGroup(values=values) for values in values_list]
