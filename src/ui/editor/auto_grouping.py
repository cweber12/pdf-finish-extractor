from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import TYPE_CHECKING

from src.extraction.grid import CellAddress, CellGroup, GridSegment
from src.ui.editor.grid_editor_segments import record_segment_change

GRID_SCALE = 150.0 / 72.0
MIN_LINE_GAP = 3
HIGH_CONFIDENCE_MIN = 0.75
MEDIUM_CONFIDENCE_MIN = 0.45

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
    existing_proposals: dict[int, AutoGroupProposal],
) -> AutoGroupResult:
    import fitz

    if not page_indices:
        return AutoGroupResult(proposals={}, processed_pages=[], skipped_pages=[])

    with fitz.open(pdf_path) as doc:
        if template_page_index < 0 or template_page_index >= len(doc):
            return AutoGroupResult(proposals={}, processed_pages=[], skipped_pages=page_indices)

        template_page = doc[template_page_index]
        row_indices = _used_rows(template_segment.groups)
        template_anchors, template_notes = _row_anchors_for_page(
            template_page,
            template_segment.horizontal_lines,
            template_segment.vertical_lines,
            row_indices,
            template_segment.groups,
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
            notes = [*template_notes, *target_notes, *offset_notes, *line_notes]
            confidence = _confidence_from_notes(notes)
            proposals[page_index] = AutoGroupProposal(
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
            penalty += 0.22
        if "clamped" in note:
            penalty += 0.10
        if "missing" in note:
            penalty += 0.12
    return max(0.0, 1.0 - min(0.95, penalty))


def _used_rows(groups: list[CellGroup]) -> list[int]:
    rows = {row for group in groups for row, _ in group.cells()}
    return sorted(rows)


def _row_anchors_for_page(
    page: "fitz.Page",
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

    cleaned: list[int] = []
    for value in shifted:
        clamped = max(MIN_LINE_GAP, min(page_height_px - MIN_LINE_GAP, value))
        if clamped != value:
            notes.append("line clamped to page bounds")
        if cleaned and clamped - cleaned[-1] < MIN_LINE_GAP:
            clamped = cleaned[-1] + MIN_LINE_GAP
            notes.append("line clamped for minimum gap")
        cleaned.append(clamped)
    return cleaned, notes


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
