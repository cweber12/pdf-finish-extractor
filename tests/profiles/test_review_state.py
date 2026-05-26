from __future__ import annotations

import pytest

from src.extraction.pattern import (
    ImageSampleDefinition,
    ImageTextPattern,
    PatternCorrection,
    PatternDetection,
    PatternReviewState,
    RectPx,
    RelativeRect,
    TextSectionDefinition,
    detection_key,
    resolve_relative_rect,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rect(x0: int = 10, y0: int = 10, x1: int = 90, y1: int = 90) -> RectPx:
    return RectPx(x0=x0, y0=y0, x1=x1, y1=y1)


def _detection(
    page_index: int = 0,
    rect: RectPx | None = None,
    status: str = "pending",
) -> PatternDetection:
    return PatternDetection(
        page_index=page_index,
        image_rect_px=rect or _rect(),
        text_section_rects_px={},
        status=status,  # type: ignore[arg-type]
    )


def _simple_pattern() -> ImageTextPattern:
    sample = ImageSampleDefinition(
        rect_px=RectPx(x0=0, y0=0, x1=80, y1=80),
        width_px=80,
        height_px=80,
        aspect_ratio=1.0,
    )
    section = TextSectionDefinition(
        name="finish_name",
        index=0,
        relative_rect=RelativeRect(x0=0.0, y0=1.0, x1=1.0, y1=1.25),
    )
    return ImageTextPattern(
        sample=sample,
        text_side="below",
        segmentation="rows",
        text_sections=[section],
    )


# ---------------------------------------------------------------------------
# detection_key (#20)
# ---------------------------------------------------------------------------


def test_detection_key_encodes_page_and_rect() -> None:
    d = _detection(page_index=3, rect=RectPx(10, 20, 90, 180))
    assert detection_key(d) == "3:10:20:90:180"


def test_detection_key_unique_per_position() -> None:
    d1 = _detection(page_index=0, rect=RectPx(10, 10, 90, 90))
    d2 = _detection(page_index=0, rect=RectPx(100, 10, 180, 90))
    assert detection_key(d1) != detection_key(d2)


def test_detection_key_unique_per_page() -> None:
    d1 = _detection(page_index=0)
    d2 = _detection(page_index=1)
    assert detection_key(d1) != detection_key(d2)


# ---------------------------------------------------------------------------
# resolve_relative_rect (#21)
# ---------------------------------------------------------------------------


def test_resolve_relative_rect_below_image() -> None:
    image_rect = RectPx(x0=10, y0=10, x1=90, y1=90)  # 80×80
    rel = RelativeRect(x0=0.0, y0=1.0, x1=1.0, y1=1.25)
    result = resolve_relative_rect(rel, image_rect)
    assert result.x0 == 10
    assert result.y0 == 90   # 10 + 1.0 * 80
    assert result.x1 == 90
    assert result.y1 == 110  # 10 + 1.25 * 80


def test_resolve_relative_rect_identity() -> None:
    image_rect = RectPx(x0=0, y0=0, x1=100, y1=100)
    rel = RelativeRect(x0=0.0, y0=0.0, x1=1.0, y1=1.0)
    assert resolve_relative_rect(rel, image_rect) == image_rect


def test_resolve_relative_rect_fractional_values() -> None:
    image_rect = RectPx(x0=0, y0=0, x1=100, y1=200)
    rel = RelativeRect(x0=0.25, y0=0.5, x1=0.75, y1=1.0)
    result = resolve_relative_rect(rel, image_rect)
    assert result == RectPx(x0=25, y0=100, x1=75, y1=200)


# ---------------------------------------------------------------------------
# visible_detections (#20)
# ---------------------------------------------------------------------------


def test_visible_detections_default_filter_returns_pending() -> None:
    state = PatternReviewState(
        detections=[
            _detection(status="pending"),
            _detection(page_index=1, status="accepted"),
        ],
    )
    visible = state.visible_detections()
    assert len(visible) == 1
    assert visible[0].status == "pending"


def test_visible_detections_all_filter_returns_all() -> None:
    state = PatternReviewState(
        detections=[
            _detection(status="pending"),
            _detection(page_index=1, status="accepted"),
        ],
        status_filter="all",
    )
    assert len(state.visible_detections()) == 2


def test_visible_detections_rejected_filter() -> None:
    state = PatternReviewState(
        detections=[
            _detection(status="rejected"),
            _detection(page_index=1, status="pending"),
        ],
        status_filter="rejected",
    )
    visible = state.visible_detections()
    assert len(visible) == 1
    assert visible[0].status == "rejected"


def test_visible_detections_correction_overrides_status() -> None:
    d = _detection(status="pending")
    state = PatternReviewState(detections=[d], status_filter="accepted")
    state.apply_correction(
        d,
        PatternCorrection(
            page_index=d.page_index,
            image_rect_px=d.image_rect_px,
            text_section_rects_px={},
            status="accepted",
        ),
    )
    visible = state.visible_detections()
    assert len(visible) == 1
    assert visible[0].status == "accepted"


def test_visible_detections_correction_overrides_rect() -> None:
    d = _detection(rect=RectPx(10, 10, 90, 90))
    state = PatternReviewState(detections=[d], status_filter="all")
    new_rect = RectPx(15, 15, 85, 85)
    state.apply_correction(
        d,
        PatternCorrection(
            page_index=0,
            image_rect_px=new_rect,
            text_section_rects_px={},
            status="edited",
            original_image_rect_px=d.image_rect_px,
        ),
    )
    visible = state.visible_detections()
    assert visible[0].image_rect_px == new_rect


def test_visible_detections_does_not_mutate_original_detection() -> None:
    d = _detection(rect=RectPx(10, 10, 90, 90))
    state = PatternReviewState(detections=[d], status_filter="all")
    state.apply_correction(
        d,
        PatternCorrection(
            page_index=0,
            image_rect_px=RectPx(20, 20, 80, 80),
            text_section_rects_px={},
            status="edited",
        ),
    )
    state.visible_detections()
    assert d.image_rect_px == RectPx(10, 10, 90, 90)


# ---------------------------------------------------------------------------
# has_corrections (#20)
# ---------------------------------------------------------------------------


def test_has_corrections_false_when_empty() -> None:
    assert PatternReviewState().has_corrections is False


def test_has_corrections_true_after_correction() -> None:
    d = _detection()
    state = PatternReviewState(detections=[d])
    state.apply_correction(
        d,
        PatternCorrection(
            page_index=0,
            image_rect_px=d.image_rect_px,
            text_section_rects_px={},
            status="accepted",
        ),
    )
    assert state.has_corrections is True


# ---------------------------------------------------------------------------
# add_manual_pair (#21)
# ---------------------------------------------------------------------------


def test_add_manual_pair_adds_to_detections() -> None:
    state = PatternReviewState()
    detection = state.add_manual_pair(
        page_index=2,
        image_rect_px=RectPx(10, 10, 90, 90),
        pattern=_simple_pattern(),
    )
    assert detection in state.detections
    assert detection.status == "manual"
    assert detection.page_index == 2


def test_add_manual_pair_generates_text_section_rects() -> None:
    state = PatternReviewState()
    image_rect = RectPx(x0=10, y0=10, x1=90, y1=90)  # 80×80
    detection = state.add_manual_pair(
        page_index=0, image_rect_px=image_rect, pattern=_simple_pattern()
    )
    # RelativeRect(0.0, 1.0, 1.0, 1.25) on 80×80 at (10,10) → y0=90, y1=110
    assert "finish_name" in detection.text_section_rects_px
    s = detection.text_section_rects_px["finish_name"]
    assert s.x0 == 10
    assert s.y0 == 90
    assert s.x1 == 90
    assert s.y1 == 110


def test_add_manual_pair_adds_correction() -> None:
    state = PatternReviewState()
    detection = state.add_manual_pair(
        page_index=0,
        image_rect_px=RectPx(10, 10, 90, 90),
        pattern=_simple_pattern(),
    )
    key = detection_key(detection)
    assert key in state.corrections
    assert state.corrections[key].status == "manual"


def test_add_manual_pair_exports_with_all_filter() -> None:
    state = PatternReviewState(status_filter="all")
    state.add_manual_pair(
        page_index=0, image_rect_px=RectPx(10, 10, 90, 90), pattern=_simple_pattern()
    )
    assert len(state.visible_detections()) == 1


def test_add_manual_pair_correction_matches_detection_text_sections() -> None:
    state = PatternReviewState()
    detection = state.add_manual_pair(
        page_index=0,
        image_rect_px=RectPx(10, 10, 90, 90),
        pattern=_simple_pattern(),
    )
    key = detection_key(detection)
    correction = state.corrections[key]
    assert correction.text_section_rects_px == detection.text_section_rects_px


# ---------------------------------------------------------------------------
# to_profile_corrections / from_profile_corrections (#22)
# ---------------------------------------------------------------------------


def test_to_profile_corrections_returns_all_corrections() -> None:
    d1 = _detection(page_index=0, rect=RectPx(10, 10, 90, 90))
    d2 = _detection(page_index=1, rect=RectPx(10, 10, 90, 90))
    state = PatternReviewState(detections=[d1, d2])
    state.apply_correction(
        d1,
        PatternCorrection(
            page_index=0, image_rect_px=d1.image_rect_px,
            text_section_rects_px={}, status="accepted",
        ),
    )
    state.apply_correction(
        d2,
        PatternCorrection(
            page_index=1, image_rect_px=d2.image_rect_px,
            text_section_rects_px={}, status="rejected",
        ),
    )
    corrections = state.to_profile_corrections()
    assert len(corrections) == 2
    assert {c.status for c in corrections} == {"accepted", "rejected"}


def test_from_profile_corrections_accepted_round_trip() -> None:
    saved = [
        PatternCorrection(
            page_index=0,
            image_rect_px=RectPx(10, 10, 90, 90),
            text_section_rects_px={"finish_name": RectPx(10, 90, 90, 115)},
            status="accepted",
        )
    ]
    state = PatternReviewState.from_profile_corrections(saved)
    assert len(state.detections) == 1
    assert state.detections[0].page_index == 0
    assert state.detections[0].status == "accepted"
    assert state.has_corrections is True


def test_from_profile_corrections_edited_uses_original_rect_as_key() -> None:
    original_rect = RectPx(10, 10, 90, 90)
    corrected_rect = RectPx(15, 15, 85, 85)
    saved = [
        PatternCorrection(
            page_index=0,
            image_rect_px=corrected_rect,
            text_section_rects_px={},
            status="edited",
            original_image_rect_px=original_rect,
        )
    ]
    state = PatternReviewState.from_profile_corrections(saved)
    state.status_filter = "all"
    visible = state.visible_detections()
    assert len(visible) == 1
    assert visible[0].image_rect_px == corrected_rect
    assert visible[0].status == "edited"


def test_from_profile_corrections_empty() -> None:
    state = PatternReviewState.from_profile_corrections([])
    assert state.detections == []
    assert state.corrections == {}


def test_profile_corrections_full_round_trip() -> None:
    state = PatternReviewState(
        detections=[
            _detection(page_index=0, rect=RectPx(10, 10, 90, 90)),
            _detection(page_index=1, rect=RectPx(100, 10, 180, 90)),
        ],
        status_filter="all",
    )
    state.apply_correction(
        state.detections[0],
        PatternCorrection(
            page_index=0, image_rect_px=RectPx(10, 10, 90, 90),
            text_section_rects_px={}, status="accepted",
        ),
    )
    state.apply_correction(
        state.detections[1],
        PatternCorrection(
            page_index=1, image_rect_px=RectPx(100, 10, 180, 90),
            text_section_rects_px={}, status="rejected",
        ),
    )

    restored = PatternReviewState.from_profile_corrections(state.to_profile_corrections())
    restored.status_filter = "all"
    visible = restored.visible_detections()
    assert {v.status for v in visible} == {"accepted", "rejected"}


def test_manual_pair_survives_profile_round_trip() -> None:
    state = PatternReviewState()
    state.add_manual_pair(
        page_index=0,
        image_rect_px=RectPx(10, 10, 90, 90),
        pattern=_simple_pattern(),
    )

    restored = PatternReviewState.from_profile_corrections(state.to_profile_corrections())
    restored.status_filter = "all"
    visible = restored.visible_detections()
    assert len(visible) == 1
    assert visible[0].status == "manual"
    assert "finish_name" in visible[0].text_section_rects_px
