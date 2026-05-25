from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import median
from typing import TYPE_CHECKING

from src.extraction.grid import CellAddress, CellGroup, FieldDefinition, GridSegment
from src.ui.editor.grid_editor_segments import record_segment_change

GRID_SCALE = 150.0 / 72.0
MIN_LINE_GAP = 3
HIGH_CONFIDENCE_MIN = 0.75
MEDIUM_CONFIDENCE_MIN = 0.45
SIZE_TOLERANCE_PCT = 0.05

if TYPE_CHECKING:
    import fitz


@dataclass(frozen=True)
class AutoGroupProposal:
    page_index: int
    groups: list[CellGroup]
    confidence: float
    confidence_bucket: str
    status: str
    source_segment_start_page: int
    notes: list[str]
    horizontal_lines: list[int]
    vertical_lines: list[int]


@dataclass(frozen=True)
class AutoGroupResult:
    proposals: dict[int, AutoGroupProposal]
    processed_pages: list[int]
    skipped_pages: list[int]


@dataclass(frozen=True)
class _TemplateAnchor:
    group_index: int
    rect: tuple[float, float, float, float]


def build_page_scope(
    *,
    page_count: int,
    scope: str,
    current_page_index: int,
    omitted_pages: set[int],
    range_start: int | None = None,
    range_end: int | None = None,
) -> list[int]:
    if page_count <= 0:
        return []

    if scope == "current":
        pages = [current_page_index]
    elif scope == "range":
        start = 0 if range_start is None else max(0, min(page_count - 1, range_start))
        end = page_count - 1 if range_end is None else max(0, min(page_count - 1, range_end))
        lo, hi = sorted((start, end))
        pages = list(range(lo, hi + 1))
    else:
        pages = list(range(page_count))

    return [page for page in pages if page not in omitted_pages]


def run_auto_group_pass(
    *,
    pdf_path: str,
    page_indices: list[int],
    template_page_index: int,
    template_segment: GridSegment,
    fields: list[FieldDefinition],
    existing_proposals: dict[int, AutoGroupProposal],
    size_tolerance_pct: float = SIZE_TOLERANCE_PCT,
) -> AutoGroupResult:
    import fitz

    if not page_indices:
        return AutoGroupResult(proposals={}, processed_pages=[], skipped_pages=[])

    with fitz.open(pdf_path) as doc:
        if template_page_index < 0 or template_page_index >= len(doc):
            return AutoGroupResult(proposals={}, processed_pages=[], skipped_pages=page_indices)

        template_page = doc[template_page_index]
        anchor_field_name = _anchor_field_name(fields, template_segment.groups)
        if anchor_field_name is None:
            return _run_text_anchor_fallback(
                doc=doc,
                page_indices=page_indices,
                template_page=template_page,
                template_segment=template_segment,
                existing_proposals=existing_proposals,
            )

        template_anchors, anchor_notes = _template_anchor_rects(
            template_page,
            template_segment,
            anchor_field_name,
        )
        if not template_anchors:
            return _run_text_anchor_fallback(
                doc=doc,
                page_indices=page_indices,
                template_page=template_page,
                template_segment=template_segment,
                existing_proposals=existing_proposals,
                base_notes=[*anchor_notes, "fallback: template image anchors unavailable"],
            )

        expected_width = median([anchor.rect[2] - anchor.rect[0] for anchor in template_anchors])
        expected_height = median([anchor.rect[3] - anchor.rect[1] for anchor in template_anchors])
        template_by_reading_order = sorted(
            template_anchors,
            key=lambda anchor: (anchor.rect[1], anchor.rect[0]),
        )

        proposals: dict[int, AutoGroupProposal] = {}
        processed: list[int] = []
        skipped: list[int] = []
        for page_index in page_indices:
            existing = existing_proposals.get(page_index)
            if existing is not None and existing.status in {"accepted", "rejected"}:
                skipped.append(page_index)
                continue

            if page_index < 0 or page_index >= len(doc):
                skipped.append(page_index)
                continue

            page = doc[page_index]
            page_notes: list[str] = []
            candidate_rects = _embedded_image_candidates(
                page,
                expected_width=expected_width,
                expected_height=expected_height,
                size_tolerance_pct=size_tolerance_pct,
            )
            if candidate_rects:
                page_notes.append("image-source: embedded")
            else:
                page_notes.append("fallback: embedded image anchors missing")
                candidate_rects = _drawing_rect_candidates(
                    page,
                    expected_width=expected_width,
                    expected_height=expected_height,
                    size_tolerance_pct=size_tolerance_pct,
                )
                if candidate_rects:
                    page_notes.append("image-source: vector drawings")

            if candidate_rects:
                sorted_candidates = sorted(candidate_rects, key=lambda rect: (rect[1], rect[0]))
                if len(sorted_candidates) < len(template_by_reading_order):
                    page_notes.append("fallback: insufficient image candidates on page")
                else:
                    selected = sorted_candidates[: len(template_by_reading_order)]
                    proposed_h, proposed_v, snap_notes = _snap_lines_from_anchor_matches(
                        template_segment=template_segment,
                        template_anchors=template_by_reading_order,
                        target_anchors=selected,
                        page=page,
                    )
                    notes = [*anchor_notes, *page_notes, *snap_notes]
                    confidence = _confidence_from_notes(notes)
                    proposals[page_index] = AutoGroupProposal(
                        page_index=page_index,
                        groups=list(template_segment.groups),
                        confidence=confidence,
                        confidence_bucket=_confidence_bucket(confidence),
                        status="pending",
                        source_segment_start_page=template_segment.start_page,
                        notes=notes,
                        horizontal_lines=proposed_h,
                        vertical_lines=proposed_v,
                    )
                    processed.append(page_index)
                    continue

            fallback = _text_anchor_proposal_for_page(
                page=page,
                page_index=page_index,
                template_page=template_page,
                template_segment=template_segment,
                base_notes=[*anchor_notes, *page_notes, "fallback: text anchors"],
            )
            proposals[page_index] = fallback
            processed.append(page_index)

        return AutoGroupResult(proposals=proposals, processed_pages=processed, skipped_pages=skipped)


def accept_all_high_confidence(
    proposals: dict[int, AutoGroupProposal],
) -> dict[int, AutoGroupProposal]:
    updated = dict(proposals)
    for page_index, proposal in proposals.items():
        if proposal.status != "pending":
            continue
        if proposal.confidence_bucket != "high":
            continue
        updated[page_index] = _replace_status(proposal, "accepted")
    return updated


def set_proposal_status(
    proposals: dict[int, AutoGroupProposal],
    *,
    page_index: int,
    status: str,
) -> dict[int, AutoGroupProposal]:
    proposal = proposals.get(page_index)
    if proposal is None:
        return dict(proposals)
    updated = dict(proposals)
    updated[page_index] = _replace_status(proposal, status)
    return updated


def _replace_status(proposal: AutoGroupProposal, status: str) -> AutoGroupProposal:
    return AutoGroupProposal(
        page_index=proposal.page_index,
        groups=list(proposal.groups),
        confidence=proposal.confidence,
        confidence_bucket=proposal.confidence_bucket,
        status=status,
        source_segment_start_page=proposal.source_segment_start_page,
        notes=list(proposal.notes),
        horizontal_lines=list(proposal.horizontal_lines),
        vertical_lines=list(proposal.vertical_lines),
    )


def _confidence_bucket(score: float) -> str:
    if score >= HIGH_CONFIDENCE_MIN:
        return "high"
    if score >= MEDIUM_CONFIDENCE_MIN:
        return "medium"
    return "low"


def _confidence_from_notes(notes: list[str]) -> float:
    penalty = 0.0
    for note in notes:
        if "fallback" in note:
            penalty += 0.20
        if "clamped" in note:
            penalty += 0.10
        if "missing" in note:
            penalty += 0.12
    return max(0.0, 1.0 - min(0.95, penalty))


def _anchor_field_name(
    fields: list[FieldDefinition],
    groups: list[CellGroup],
) -> str | None:
    for field in fields:
        if field.field_type != "image":
            continue
        if any(field.name in group.field_cells for group in groups):
            return field.name
    return None


def _template_anchor_rects(
    page: fitz.Page,
    segment: GridSegment,
    anchor_field_name: str,
) -> tuple[list[_TemplateAnchor], list[str]]:
    notes: list[str] = []
    h_bounds, v_bounds = _grid_bounds_px(
        page,
        segment.horizontal_lines,
        segment.vertical_lines,
    )
    anchors: list[_TemplateAnchor] = []
    embedded_rects = _embedded_image_rects(page)
    drawing_rects = _drawing_rects(page)
    for group_index, group in enumerate(segment.groups):
        cells = group.field_cells.get(anchor_field_name)
        if not cells:
            continue
        field_rect_px = _field_rect_px(cells, h_bounds, v_bounds)
        if field_rect_px is None:
            notes.append(f"missing template anchor bounds for group {group_index}")
            continue
        field_rect = _rect_px_to_pts(field_rect_px)
        embedded = _best_intersecting_rect(field_rect, embedded_rects)
        if embedded is not None:
            anchors.append(_TemplateAnchor(group_index=group_index, rect=embedded))
            continue
        drawing = _best_intersecting_rect(field_rect, drawing_rects)
        if drawing is not None:
            notes.append(f"fallback template anchor via drawing for group {group_index}")
            anchors.append(_TemplateAnchor(group_index=group_index, rect=drawing))
            continue
        notes.append(f"fallback template anchor via field area for group {group_index}")
        anchors.append(_TemplateAnchor(group_index=group_index, rect=field_rect))
    return anchors, notes


def _embedded_image_candidates(
    page: fitz.Page,
    *,
    expected_width: float,
    expected_height: float,
    size_tolerance_pct: float,
) -> list[tuple[float, float, float, float]]:
    candidates: list[tuple[float, float, float, float]] = []
    for rect in _embedded_image_rects(page):
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        if width <= 0 or height <= 0:
            continue
        if not _size_matches(
            width=width,
            height=height,
            expected_width=expected_width,
            expected_height=expected_height,
            size_tolerance_pct=size_tolerance_pct,
        ):
            continue
        candidates.append(rect)
    return candidates


def _drawing_rect_candidates(
    page: fitz.Page,
    *,
    expected_width: float,
    expected_height: float,
    size_tolerance_pct: float,
) -> list[tuple[float, float, float, float]]:
    candidates: list[tuple[float, float, float, float]] = []
    for rect in _drawing_rects(page):
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        if width <= 0 or height <= 0:
            continue
        if not _size_matches(
            width=width,
            height=height,
            expected_width=expected_width,
            expected_height=expected_height,
            size_tolerance_pct=size_tolerance_pct,
        ):
            continue
        candidates.append(rect)
    return candidates


def _embedded_image_rects(page: fitz.Page) -> list[tuple[float, float, float, float]]:
    rects: list[tuple[float, float, float, float]] = []
    for info in page.get_image_info(xrefs=True):
        raw_bbox = info.get("bbox")
        if raw_bbox is None:
            continue
        rects.append(
            (
                float(raw_bbox[0]),
                float(raw_bbox[1]),
                float(raw_bbox[2]),
                float(raw_bbox[3]),
            )
        )
    return rects


def _drawing_rects(page: fitz.Page) -> list[tuple[float, float, float, float]]:
    rects: list[tuple[float, float, float, float]] = []
    for path in page.get_drawings():
        raw_rect = path.get("rect")
        if raw_rect is None:
            continue
        rects.append((float(raw_rect.x0), float(raw_rect.y0), float(raw_rect.x1), float(raw_rect.y1)))
    return rects


def _best_intersecting_rect(
    reference: tuple[float, float, float, float],
    candidates: list[tuple[float, float, float, float]],
) -> tuple[float, float, float, float] | None:
    best: tuple[float, float, float, float] | None = None
    best_area = 0.0
    for candidate in candidates:
        area = _intersection_area(reference, candidate)
        if area <= 0.0:
            continue
        if area > best_area:
            best = candidate
            best_area = area
    return best


def _intersection_area(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[2], b[2])
    bottom = min(a[3], b[3])
    if right <= left or bottom <= top:
        return 0.0
    return (right - left) * (bottom - top)


def _size_matches(
    *,
    width: float,
    height: float,
    expected_width: float,
    expected_height: float,
    size_tolerance_pct: float,
) -> bool:
    w_tol = max(1.0, abs(expected_width) * size_tolerance_pct)
    h_tol = max(1.0, abs(expected_height) * size_tolerance_pct)
    expected_ratio = expected_width / expected_height if expected_height else 0.0
    ratio = width / height if height else 0.0
    ratio_tol = 0.05
    return (
        abs(width - expected_width) <= w_tol
        and abs(height - expected_height) <= h_tol
        and abs(ratio - expected_ratio) <= ratio_tol
    )


def _snap_lines_from_anchor_matches(
    *,
    template_segment: GridSegment,
    template_anchors: list[_TemplateAnchor],
    target_anchors: list[tuple[float, float, float, float]],
    page: fitz.Page,
) -> tuple[list[int], list[int], list[str]]:
    notes: list[str] = []
    h_suggestions: dict[int, list[float]] = defaultdict(list)
    v_suggestions: dict[int, list[float]] = defaultdict(list)

    h_count = len(template_segment.horizontal_lines) + 1
    v_count = len(template_segment.vertical_lines) + 1

    for template_anchor, target_anchor in zip(template_anchors, target_anchors, strict=True):
        group = template_segment.groups[template_anchor.group_index]
        dx_px = (target_anchor[0] - template_anchor.rect[0]) * GRID_SCALE
        dy_px = (target_anchor[1] - template_anchor.rect[1]) * GRID_SCALE
        row_boundaries, col_boundaries = _group_boundary_indexes(group)
        for boundary_index in row_boundaries:
            if 1 <= boundary_index < h_count:
                base = template_segment.horizontal_lines[boundary_index - 1]
                h_suggestions[boundary_index].append(base + dy_px)
        for boundary_index in col_boundaries:
            if 1 <= boundary_index < v_count:
                base = template_segment.vertical_lines[boundary_index - 1]
                v_suggestions[boundary_index].append(base + dx_px)

    page_height_px = round(page.rect.height * GRID_SCALE)
    page_width_px = round(page.rect.width * GRID_SCALE)
    proposed_h = _resolve_internal_lines(
        original_lines=template_segment.horizontal_lines,
        suggestions=h_suggestions,
        max_value=page_height_px,
        notes=notes,
    )
    proposed_v = _resolve_internal_lines(
        original_lines=template_segment.vertical_lines,
        suggestions=v_suggestions,
        max_value=page_width_px,
        notes=notes,
    )
    return proposed_h, proposed_v, notes


def _group_boundary_indexes(group: CellGroup) -> tuple[set[int], set[int]]:
    row_boundaries: set[int] = set()
    col_boundaries: set[int] = set()
    for cells in group.field_cells.values():
        for row, col in cells:
            row_boundaries.add(row)
            row_boundaries.add(row + 1)
            col_boundaries.add(col)
            col_boundaries.add(col + 1)
    return row_boundaries, col_boundaries


def _resolve_internal_lines(
    *,
    original_lines: list[int],
    suggestions: dict[int, list[float]],
    max_value: int,
    notes: list[str],
) -> list[int]:
    if not original_lines:
        return []

    proposed: list[int] = []
    for boundary_index, base in enumerate(sorted(original_lines), start=1):
        values = suggestions.get(boundary_index)
        if values:
            proposed.append(round(median(values)))
        else:
            proposed.append(base)
            notes.append(f"missing anchor suggestions for boundary {boundary_index}")
    return _clamp_internal_lines(proposed, max_value=max_value, notes=notes)


def _clamp_internal_lines(values: list[int], *, max_value: int, notes: list[str]) -> list[int]:
    cleaned: list[int] = []
    for value in values:
        clamped = max(MIN_LINE_GAP, min(max_value - MIN_LINE_GAP, value))
        if clamped != value:
            notes.append("line clamped to page bounds")
        if cleaned and clamped - cleaned[-1] < MIN_LINE_GAP:
            clamped = cleaned[-1] + MIN_LINE_GAP
            notes.append("line clamped for minimum gap")
        cleaned.append(clamped)
    return cleaned


def _grid_bounds_px(
    page: fitz.Page,
    horizontal_lines: list[int],
    vertical_lines: list[int],
) -> tuple[list[int], list[int]]:
    return (
        [0, *sorted(horizontal_lines), round(page.rect.height * GRID_SCALE)],
        [0, *sorted(vertical_lines), round(page.rect.width * GRID_SCALE)],
    )


def _field_rect_px(
    cells: list[CellAddress],
    h_bounds: list[int],
    v_bounds: list[int],
) -> tuple[int, int, int, int] | None:
    rects = [_cell_rect_px(cell, h_bounds, v_bounds) for cell in cells]
    if any(rect is None for rect in rects):
        return None
    valid = [rect for rect in rects if rect is not None]
    left = min(rect[0] for rect in valid)
    top = min(rect[1] for rect in valid)
    right = max(rect[2] for rect in valid)
    bottom = max(rect[3] for rect in valid)
    return left, top, right, bottom


def _cell_rect_px(
    cell: CellAddress,
    h_bounds: list[int],
    v_bounds: list[int],
) -> tuple[int, int, int, int] | None:
    row, col = cell
    if row < 0 or col < 0 or row + 1 >= len(h_bounds) or col + 1 >= len(v_bounds):
        return None
    return (v_bounds[col], h_bounds[row], v_bounds[col + 1], h_bounds[row + 1])


def _rect_px_to_pts(rect: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    return (
        rect[0] / GRID_SCALE,
        rect[1] / GRID_SCALE,
        rect[2] / GRID_SCALE,
        rect[3] / GRID_SCALE,
    )


def _run_text_anchor_fallback(
    *,
    doc: fitz.Document,
    page_indices: list[int],
    template_page: fitz.Page,
    template_segment: GridSegment,
    existing_proposals: dict[int, AutoGroupProposal],
    base_notes: list[str] | None = None,
) -> AutoGroupResult:
    proposals: dict[int, AutoGroupProposal] = {}
    processed: list[int] = []
    skipped: list[int] = []
    for page_index in page_indices:
        existing = existing_proposals.get(page_index)
        if existing is not None and existing.status in {"accepted", "rejected"}:
            skipped.append(page_index)
            continue
        if page_index < 0 or page_index >= len(doc):
            skipped.append(page_index)
            continue
        page = doc[page_index]
        proposal = _text_anchor_proposal_for_page(
            page=page,
            page_index=page_index,
            template_page=template_page,
            template_segment=template_segment,
            base_notes=base_notes,
        )
        proposals[page_index] = proposal
        processed.append(page_index)
    return AutoGroupResult(proposals=proposals, processed_pages=processed, skipped_pages=skipped)


def _text_anchor_proposal_for_page(
    *,
    page: fitz.Page,
    page_index: int,
    template_page: fitz.Page,
    template_segment: GridSegment,
    base_notes: list[str] | None = None,
) -> AutoGroupProposal:
    row_indices = _used_rows(template_segment.groups)
    template_anchors, template_notes = _row_anchors_for_page(
        template_page,
        template_segment.horizontal_lines,
        template_segment.vertical_lines,
        row_indices,
        template_segment.groups,
    )
    target_anchors, target_notes = _row_anchors_for_page(
        page,
        template_segment.horizontal_lines,
        template_segment.vertical_lines,
        row_indices,
        template_segment.groups,
    )
    offsets, offset_notes = _row_offsets(
        row_indices=row_indices,
        template_anchors=template_anchors,
        target_anchors=target_anchors,
    )
    proposed_lines, line_notes = _shift_horizontal_lines(
        template_segment.horizontal_lines,
        offsets,
        page_height_px=round(page.rect.height * GRID_SCALE),
    )
    notes = [*(base_notes or []), *template_notes, *target_notes, *offset_notes, *line_notes]
    confidence = _confidence_from_notes(notes)
    return AutoGroupProposal(
        page_index=page_index,
        groups=list(template_segment.groups),
        confidence=confidence,
        confidence_bucket=_confidence_bucket(confidence),
        status="pending",
        source_segment_start_page=template_segment.start_page,
        notes=notes,
        horizontal_lines=proposed_lines,
        vertical_lines=list(template_segment.vertical_lines),
    )


def _used_rows(groups: list[CellGroup]) -> list[int]:
    rows = {row for group in groups for row, _ in group.cells()}
    return sorted(rows)


def _row_anchors_for_page(
    page: fitz.Page,
    horizontal_lines: list[int],
    vertical_lines: list[int],
    row_indices: list[int],
    groups: list[CellGroup],
) -> tuple[dict[int, float], list[str]]:
    notes: list[str] = []
    h_bounds = [0, *sorted(horizontal_lines), round(page.rect.height * GRID_SCALE)]
    v_bounds = [0, *sorted(vertical_lines), round(page.rect.width * GRID_SCALE)]
    blocks = page.get_text("blocks")
    anchors: dict[int, float] = {}

    row_x_ranges = _row_horizontal_spans(groups, v_bounds)
    for row in row_indices:
        if row + 1 >= len(h_bounds):
            notes.append(f"missing row bounds for row {row}")
            continue
        y0_pts = h_bounds[row] / GRID_SCALE
        y1_pts = h_bounds[row + 1] / GRID_SCALE
        x_span = row_x_ranges.get(row)
        candidate_ys: list[float] = []
        for block in blocks:
            if len(block) < 5:
                continue
            bx0, by0, bx1, by1 = float(block[0]), float(block[1]), float(block[2]), float(block[3])
            if by1 <= y0_pts or by0 >= y1_pts:
                continue
            if x_span is not None:
                sx0, sx1 = x_span
                if bx1 <= sx0 or bx0 >= sx1:
                    continue
            candidate_ys.append((by0 + by1) / 2.0)
        if candidate_ys:
            anchors[row] = median(candidate_ys)
            continue
        anchors[row] = (y0_pts + y1_pts) / 2.0
        notes.append(f"fallback row anchor for row {row}")
    return anchors, notes


def _row_horizontal_spans(groups: list[CellGroup], v_bounds: list[int]) -> dict[int, tuple[float, float]]:
    spans: dict[int, tuple[float, float]] = {}
    for group in groups:
        for row, col in group.cells():
            if col + 1 >= len(v_bounds):
                continue
            x0 = v_bounds[col] / GRID_SCALE
            x1 = v_bounds[col + 1] / GRID_SCALE
            existing = spans.get(row)
            if existing is None:
                spans[row] = (x0, x1)
            else:
                spans[row] = (min(existing[0], x0), max(existing[1], x1))
    return spans


def _row_offsets(
    *,
    row_indices: list[int],
    template_anchors: dict[int, float],
    target_anchors: dict[int, float],
) -> tuple[dict[int, float], list[str]]:
    notes: list[str] = []
    offsets: dict[int, float] = {}
    for row in row_indices:
        if row not in template_anchors or row not in target_anchors:
            offsets[row] = 0.0
            notes.append(f"missing anchor for row {row}")
            continue
        offsets[row] = target_anchors[row] - template_anchors[row]
    return offsets, notes


def _shift_horizontal_lines(
    horizontal_lines: list[int],
    row_offsets_pts: dict[int, float],
    *,
    page_height_px: int,
) -> tuple[list[int], list[str]]:
    if not horizontal_lines:
        return [], []

    notes: list[str] = []
    offsets_px = {row: delta * GRID_SCALE for row, delta in row_offsets_pts.items()}
    shifted: list[int] = []
    for boundary_index, value in enumerate(sorted(horizontal_lines)):
        top_delta = offsets_px.get(boundary_index, 0.0)
        bottom_delta = offsets_px.get(boundary_index + 1, top_delta)
        delta = (top_delta + bottom_delta) / 2.0
        shifted.append(round(value + delta))
    return _clamp_internal_lines(shifted, max_value=page_height_px, notes=notes), notes


def proposal_cells(proposal: AutoGroupProposal) -> list[CellAddress]:
    return [cell for group in proposal.groups for cell in group.cells()]


def commit_accepted_proposals(
    *,
    segments: list[GridSegment],
    proposals: dict[int, AutoGroupProposal],
) -> tuple[list[GridSegment], dict[int, AutoGroupProposal]]:
    next_segments = list(segments)
    next_proposals = dict(proposals)
    accepted = sorted(
        (proposal for proposal in proposals.values() if proposal.status == "accepted"),
        key=lambda proposal: proposal.page_index,
    )
    for proposal in accepted:
        next_segments = record_segment_change(
            segments=next_segments,
            page_index=proposal.page_index,
            horizontal_lines=proposal.horizontal_lines,
            vertical_lines=proposal.vertical_lines,
            groups=proposal.groups,
        )
        del next_proposals[proposal.page_index]
    return next_segments, next_proposals
