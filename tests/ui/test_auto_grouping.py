from __future__ import annotations

import io

import fitz
from PIL import Image

from src.extraction.grid import CellGroup, FieldDefinition, GridSegment
from src.ui.editor.auto_grouping import (
    AutoGroupProposal,
    _shift_horizontal_lines,
    accept_all_high_confidence,
    build_page_scope,
    commit_accepted_proposals,
    run_auto_group_pass,
    set_proposal_status,
)
from src.ui.editor.grid_editor_segments import layout_state_for_page

GRID_SCALE = 150.0 / 72.0


def _fields() -> list[FieldDefinition]:
    return [
        FieldDefinition("swatch", "image", 1),
        FieldDefinition("material_id", "text", 1),
    ]


def _single_group_segment() -> GridSegment:
    return GridSegment(
        start_page=0,
        horizontal_lines=[80],
        vertical_lines=[100],
        groups=[
            CellGroup(
                field_cells={
                    "swatch": [(0, 0)],
                    "material_id": [(1, 0)],
                }
            )
        ],
    )


def _two_group_segment() -> GridSegment:
    return GridSegment(
        start_page=0,
        horizontal_lines=[120],
        vertical_lines=[100],
        groups=[
            CellGroup(field_cells={"swatch": [(0, 0)]}),
            CellGroup(field_cells={"swatch": [(1, 0)]}),
        ],
    )


def _image_bytes(color: tuple[int, int, int] = (120, 140, 210)) -> bytes:
    image = Image.new("RGB", (20, 20), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _insert_image(page: fitz.Page, rect: fitz.Rect, *, color: tuple[int, int, int] = (120, 140, 210)) -> None:
    page.insert_image(rect, stream=_image_bytes(color), keep_proportion=False)


def test_build_page_scope_current_page_default() -> None:
    pages = build_page_scope(
        page_count=6,
        scope="current",
        current_page_index=3,
        omitted_pages=set(),
    )
    assert pages == [3]


def test_build_page_scope_excludes_omitted_pages() -> None:
    pages = build_page_scope(
        page_count=6,
        scope="all",
        current_page_index=3,
        omitted_pages={1, 4},
    )
    assert pages == [0, 2, 3, 5]


def test_shift_horizontal_lines_applies_vertical_offsets() -> None:
    shifted, notes = _shift_horizontal_lines(
        [200],
        {0: 8.0, 1: 8.0},
        page_height_px=1000,
    )
    assert shifted[0] > 200
    assert notes == []


def test_run_auto_group_pass_matches_embedded_images_with_size_tolerance(tmp_path) -> None:
    pdf_path = tmp_path / "embedded-size-tolerance.pdf"
    segment = _single_group_segment()

    doc = fitz.open()
    template = doc.new_page(width=200, height=200)
    _insert_image(template, fitz.Rect(5, 5, 45, 30))
    template.insert_text(fitz.Point(8, 65), "MAT-001", fontsize=10)

    target = doc.new_page(width=200, height=200)
    _insert_image(target, fitz.Rect(15, 20, 57, 46))
    target.insert_text(fitz.Point(18, 80), "MAT-001", fontsize=10)
    doc.save(str(pdf_path))
    doc.close()

    result = run_auto_group_pass(
        pdf_path=str(pdf_path),
        page_indices=[1],
        template_page_index=0,
        template_segment=segment,
        fields=_fields(),
        existing_proposals={},
    )
    proposal = result.proposals[1]
    assert "image-source: embedded" in proposal.notes
    assert proposal.horizontal_lines[0] > segment.horizontal_lines[0]
    assert proposal.vertical_lines[0] > segment.vertical_lines[0]


def test_run_auto_group_pass_uses_top_left_order_for_multiple_candidates(tmp_path) -> None:
    pdf_path = tmp_path / "embedded-ordering.pdf"
    segment = _two_group_segment()
    fields = [FieldDefinition("swatch", "image", 1)]

    doc = fitz.open()
    template = doc.new_page(width=220, height=260)
    _insert_image(template, fitz.Rect(10, 20, 50, 60))
    _insert_image(template, fitz.Rect(10, 140, 50, 180))

    target = doc.new_page(width=220, height=260)
    _insert_image(target, fitz.Rect(20, 40, 60, 80), color=(40, 150, 120))
    _insert_image(target, fitz.Rect(20, 160, 60, 200), color=(120, 60, 180))
    _insert_image(target, fitz.Rect(20, 210, 60, 250), color=(200, 80, 90))
    doc.save(str(pdf_path))
    doc.close()

    result = run_auto_group_pass(
        pdf_path=str(pdf_path),
        page_indices=[1],
        template_page_index=0,
        template_segment=segment,
        fields=fields,
        existing_proposals={},
    )
    proposal = result.proposals[1]
    expected = round(120 + 20 * GRID_SCALE)
    assert abs(proposal.horizontal_lines[0] - expected) <= 2


def test_run_auto_group_pass_preserves_anchor_relative_text_offset_via_line_shift(tmp_path) -> None:
    pdf_path = tmp_path / "anchor-relative-text.pdf"
    segment = _single_group_segment()

    doc = fitz.open()
    template = doc.new_page(width=200, height=200)
    _insert_image(template, fitz.Rect(8, 8, 48, 38))
    template.insert_text(fitz.Point(10, 66), "MAT-001", fontsize=10)

    target = doc.new_page(width=200, height=200)
    _insert_image(target, fitz.Rect(20, 22, 60, 52))
    target.insert_text(fitz.Point(22, 82), "MAT-001", fontsize=10)
    doc.save(str(pdf_path))
    doc.close()

    result = run_auto_group_pass(
        pdf_path=str(pdf_path),
        page_indices=[1],
        template_page_index=0,
        template_segment=segment,
        fields=_fields(),
        existing_proposals={},
    )
    proposal = result.proposals[1]
    assert proposal.horizontal_lines[0] == round(segment.horizontal_lines[0] + 14 * GRID_SCALE)
    assert proposal.vertical_lines[0] == round(segment.vertical_lines[0] + 12 * GRID_SCALE)


def test_run_auto_group_pass_falls_back_to_drawings_when_embedded_images_missing(tmp_path) -> None:
    pdf_path = tmp_path / "drawing-fallback.pdf"
    segment = _single_group_segment()

    doc = fitz.open()
    template = doc.new_page(width=200, height=200)
    _insert_image(template, fitz.Rect(5, 5, 45, 30))

    target = doc.new_page(width=200, height=200)
    target.draw_rect(fitz.Rect(15, 20, 55, 45), fill=(0.2, 0.6, 0.3), color=(0.2, 0.6, 0.3))
    doc.save(str(pdf_path))
    doc.close()

    result = run_auto_group_pass(
        pdf_path=str(pdf_path),
        page_indices=[1],
        template_page_index=0,
        template_segment=segment,
        fields=_fields(),
        existing_proposals={},
    )
    proposal = result.proposals[1]
    assert "fallback: embedded image anchors missing" in proposal.notes
    assert "image-source: vector drawings" in proposal.notes
    assert proposal.horizontal_lines[0] > segment.horizontal_lines[0]
    assert proposal.vertical_lines[0] > segment.vertical_lines[0]


def test_run_auto_group_pass_falls_back_to_text_anchors_and_penalizes_confidence(tmp_path) -> None:
    pdf_path = tmp_path / "text-fallback.pdf"
    segment = _single_group_segment()

    doc = fitz.open()
    template = doc.new_page(width=200, height=200)
    _insert_image(template, fitz.Rect(5, 5, 45, 30))
    template.insert_text(fitz.Point(12, 68), "MAT-001", fontsize=10)

    target = doc.new_page(width=200, height=200)
    target.insert_text(fitz.Point(12, 84), "MAT-001", fontsize=10)
    doc.save(str(pdf_path))
    doc.close()

    result = run_auto_group_pass(
        pdf_path=str(pdf_path),
        page_indices=[1],
        template_page_index=0,
        template_segment=segment,
        fields=_fields(),
        existing_proposals={},
    )
    proposal = result.proposals[1]
    assert "fallback: text anchors" in proposal.notes
    assert proposal.confidence < 1.0


def test_accept_all_high_confidence_only_updates_pending() -> None:
    template = _single_group_segment()
    proposals = {
        0: AutoGroupProposal(
            page_index=0,
            groups=template.groups,
            confidence=0.8,
            confidence_bucket="high",
            status="pending",
            source_segment_start_page=0,
            notes=[],
            horizontal_lines=[200],
            vertical_lines=[200],
        ),
        1: AutoGroupProposal(
            page_index=1,
            groups=template.groups,
            confidence=0.3,
            confidence_bucket="low",
            status="pending",
            source_segment_start_page=0,
            notes=[],
            horizontal_lines=[200],
            vertical_lines=[200],
        ),
    }
    updated = accept_all_high_confidence(proposals)
    assert updated[0].status == "accepted"
    assert updated[1].status == "pending"


def test_commit_accepted_proposals_updates_segments_without_touching_pending() -> None:
    template = _single_group_segment()
    segments = [template]
    proposals = {
        2: AutoGroupProposal(
            page_index=2,
            groups=template.groups,
            confidence=0.8,
            confidence_bucket="high",
            status="accepted",
            source_segment_start_page=0,
            notes=[],
            horizontal_lines=[230],
            vertical_lines=[200],
        ),
        3: AutoGroupProposal(
            page_index=3,
            groups=template.groups,
            confidence=0.4,
            confidence_bucket="low",
            status="pending",
            source_segment_start_page=0,
            notes=[],
            horizontal_lines=[260],
            vertical_lines=[200],
        ),
    }
    next_segments, next_proposals = commit_accepted_proposals(
        segments=segments,
        proposals=proposals,
    )
    assert 2 not in next_proposals
    assert 3 in next_proposals
    applied = layout_state_for_page(next_segments, 2)
    assert applied is not None
    assert applied.horizontal_lines == [230]


def test_set_proposal_status_updates_page() -> None:
    template = _single_group_segment()
    proposals = {
        5: AutoGroupProposal(
            page_index=5,
            groups=template.groups,
            confidence=0.7,
            confidence_bucket="medium",
            status="pending",
            source_segment_start_page=0,
            notes=[],
            horizontal_lines=[220],
            vertical_lines=[200],
        )
    }
    updated = set_proposal_status(proposals, page_index=5, status="rejected")
    assert updated[5].status == "rejected"


def median_shift_px(*deltas_pts: float) -> float:
    values = [delta * GRID_SCALE for delta in deltas_pts]
    values.sort()
    mid = len(values) // 2
    if len(values) % 2 == 0:
        return (values[mid - 1] + values[mid]) / 2.0
    return values[mid]
