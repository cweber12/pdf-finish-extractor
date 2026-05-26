from __future__ import annotations

from src.extraction.pattern import (
    ImageSampleDefinition,
    ImageTextPattern,
    ImageTextPatternProfile,
    PatternDetectionOptions,
    PatternCorrection,
    RectPx,
    RelativeRect,
    TextSectionDefinition,
)


# ------------------------------------------------------------------
# RectPx
# ------------------------------------------------------------------


def test_rect_px_round_trip() -> None:
    rect = RectPx(x0=10, y0=20, x1=110, y1=220)
    assert RectPx.from_dict(rect.to_dict()) == rect


def test_rect_px_dimensions() -> None:
    rect = RectPx(x0=10, y0=20, x1=110, y1=220)
    assert rect.width == 100
    assert rect.height == 200


# ------------------------------------------------------------------
# RelativeRect
# ------------------------------------------------------------------


def test_relative_rect_round_trip() -> None:
    rel = RelativeRect(x0=0.0, y0=1.05, x1=1.0, y1=1.30)
    assert RelativeRect.from_dict(rel.to_dict()) == rel


def test_relative_rect_values_outside_unit_range_are_valid() -> None:
    # Negative and >1 offsets are expected for text outside the image boundary.
    rel = RelativeRect(x0=-0.1, y0=1.05, x1=1.1, y1=1.35)
    loaded = RelativeRect.from_dict(rel.to_dict())
    assert loaded.x0 == -0.1
    assert loaded.y1 == 1.35


# ------------------------------------------------------------------
# TextSectionDefinition
# ------------------------------------------------------------------


def test_text_section_definition_round_trip() -> None:
    section = TextSectionDefinition(
        name="finish_name",
        index=0,
        relative_rect=RelativeRect(x0=0.0, y0=1.0, x1=1.0, y1=1.25),
    )
    assert TextSectionDefinition.from_dict(section.to_dict()) == section


# ------------------------------------------------------------------
# ImageSampleDefinition
# ------------------------------------------------------------------


def test_image_sample_definition_round_trip() -> None:
    sample = ImageSampleDefinition(
        rect_px=RectPx(x0=0, y0=0, x1=100, y1=100),
        width_px=100,
        height_px=100,
        aspect_ratio=1.0,
    )
    assert ImageSampleDefinition.from_dict(sample.to_dict()) == sample


# ------------------------------------------------------------------
# ImageTextPattern
# ------------------------------------------------------------------


def _make_pattern(
    text_side: str = "below",
    segmentation: str = "rows",
    section_count: int = 2,
) -> ImageTextPattern:
    sample = ImageSampleDefinition(
        rect_px=RectPx(x0=0, y0=0, x1=80, y1=80),
        width_px=80,
        height_px=80,
        aspect_ratio=1.0,
    )
    sections = [
        TextSectionDefinition(
            name=f"text_{i + 1}",
            index=i,
            relative_rect=RelativeRect(
                x0=0.0,
                y0=1.0 + i * 0.25,
                x1=1.0,
                y1=1.0 + (i + 1) * 0.25,
            ),
        )
        for i in range(section_count)
    ]
    return ImageTextPattern(
        sample=sample,
        text_side=text_side,  # type: ignore[arg-type]
        segmentation=segmentation,  # type: ignore[arg-type]
        text_sections=sections,
    )


def test_image_text_pattern_round_trip() -> None:
    pattern = _make_pattern()
    loaded = ImageTextPattern.from_dict(pattern.to_dict())
    assert loaded.text_side == "below"
    assert loaded.segmentation == "rows"
    assert len(loaded.text_sections) == 2
    assert loaded.text_sections[0].name == "text_1"
    assert loaded.text_sections[1].name == "text_2"


def test_image_text_pattern_invalid_text_side_defaults_to_below() -> None:
    pattern = _make_pattern()
    data = pattern.to_dict()
    data["text_side"] = "diagonal"  # type: ignore[index]
    loaded = ImageTextPattern.from_dict(data)
    assert loaded.text_side == "below"


def test_image_text_pattern_invalid_segmentation_defaults_to_rows() -> None:
    pattern = _make_pattern()
    data = pattern.to_dict()
    data["segmentation"] = "zigzag"  # type: ignore[index]
    loaded = ImageTextPattern.from_dict(data)
    assert loaded.segmentation == "rows"


def test_image_text_pattern_all_text_sides() -> None:
    for side in ("above", "below", "left", "right"):
        pattern = _make_pattern(text_side=side)
        assert ImageTextPattern.from_dict(pattern.to_dict()).text_side == side


def test_image_text_pattern_both_segmentations() -> None:
    for seg in ("rows", "columns"):
        pattern = _make_pattern(segmentation=seg)
        assert ImageTextPattern.from_dict(pattern.to_dict()).segmentation == seg


# ------------------------------------------------------------------
# PatternDetectionOptions
# ------------------------------------------------------------------


def test_pattern_detection_options_defaults_round_trip() -> None:
    opts = PatternDetectionOptions()
    loaded = PatternDetectionOptions.from_dict(opts.to_dict())
    assert loaded.size_tolerance_pct == 0.20
    assert loaded.aspect_ratio_tolerance_pct == 0.10
    assert loaded.require_text is True
    assert loaded.sort_order == "reading_order"


def test_pattern_detection_options_custom_values_round_trip() -> None:
    opts = PatternDetectionOptions(
        size_tolerance_pct=0.05,
        aspect_ratio_tolerance_pct=0.15,
        min_image_width_px=20,
        min_image_height_px=20,
        max_page_area_pct=0.08,
        require_text=False,
    )
    loaded = PatternDetectionOptions.from_dict(opts.to_dict())
    assert loaded.size_tolerance_pct == 0.05
    assert loaded.require_text is False


# ------------------------------------------------------------------
# PatternCorrection
# ------------------------------------------------------------------


def test_pattern_correction_round_trip_with_original() -> None:
    correction = PatternCorrection(
        page_index=2,
        image_rect_px=RectPx(x0=10, y0=10, x1=90, y1=90),
        text_section_rects_px={"finish_name": RectPx(x0=10, y0=90, x1=90, y1=115)},
        status="edited",
        original_image_rect_px=RectPx(x0=12, y0=12, x1=88, y1=88),
    )
    loaded = PatternCorrection.from_dict(correction.to_dict())
    assert loaded.page_index == 2
    assert loaded.status == "edited"
    assert loaded.original_image_rect_px == RectPx(x0=12, y0=12, x1=88, y1=88)
    assert loaded.text_section_rects_px["finish_name"] == RectPx(x0=10, y0=90, x1=90, y1=115)


def test_pattern_correction_round_trip_without_original() -> None:
    correction = PatternCorrection(
        page_index=0,
        image_rect_px=RectPx(x0=0, y0=0, x1=80, y1=80),
        text_section_rects_px={},
        status="manual",
    )
    loaded = PatternCorrection.from_dict(correction.to_dict())
    assert loaded.original_image_rect_px is None
    assert loaded.status == "manual"


# ------------------------------------------------------------------
# ImageTextPatternProfile
# ------------------------------------------------------------------


def test_image_text_pattern_profile_round_trip() -> None:
    profile = ImageTextPatternProfile(
        pattern=_make_pattern(section_count=3),
        detection_options=PatternDetectionOptions(require_text=False),
    )
    loaded = ImageTextPatternProfile.from_dict(profile.to_dict())
    assert loaded.pattern.text_side == "below"
    assert len(loaded.pattern.text_sections) == 3
    assert loaded.detection_options.require_text is False
    assert loaded.omitted_pages == []
    assert loaded.corrections == []


def test_image_text_pattern_profile_to_dict_has_correct_profile_type() -> None:
    profile = ImageTextPatternProfile(pattern=_make_pattern())
    d = profile.to_dict()
    assert d["profile_type"] == "image_text_pattern"
    assert d["version"] == 1


def test_image_text_pattern_profile_preserves_omitted_pages() -> None:
    profile = ImageTextPatternProfile(
        pattern=_make_pattern(),
        omitted_pages=[0, 3, 7],
    )
    loaded = ImageTextPatternProfile.from_dict(profile.to_dict())
    assert loaded.omitted_pages == [0, 3, 7]
