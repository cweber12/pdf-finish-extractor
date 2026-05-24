from __future__ import annotations

from src.extraction.grid import CellGroup, GridSegment
from src.ui.editor.auto_grouping import (
    AutoGroupProposal,
    _shift_horizontal_lines,
    accept_all_high_confidence,
    build_page_scope,
    commit_accepted_proposals,
    set_proposal_status,
)
from src.ui.editor.grid_editor_segments import layout_state_for_page


def _template_segment() -> GridSegment:
    return GridSegment(
        start_page=0,
        horizontal_lines=[200],
        vertical_lines=[200],
        groups=[
            CellGroup(field_cells={"material_id": [(0, 0)]}),
            CellGroup(field_cells={"material_id": [(1, 0)]}),
        ],
    )


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


def test_accept_all_high_confidence_only_updates_pending() -> None:
    template = _template_segment()
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
    template = _template_segment()
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
    template = _template_segment()
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
