from __future__ import annotations

from src.extraction.extractor import ExtractedFieldValue, ExtractedGroup
from src.extraction.group_projection import (
    detection_to_group,
    detections_to_groups,
    projected_field_names,
)
from src.extraction.pattern import (
    ImageSampleDefinition,
    ImageTextPattern,
    PatternDetection,
    RectPx,
    RelativeRect,
    TextSectionDefinition,
)


def test_projected_field_names_preserves_first_seen_order() -> None:
    groups = [
        ExtractedGroup(
            values={
                "material_id": ExtractedFieldValue("text", text="M1"),
                "swatch": ExtractedFieldValue("image", image_bytes=b"img"),
            }
        ),
        ExtractedGroup(
            values={
                "description": ExtractedFieldValue("text", text="Satin"),
                "material_id": ExtractedFieldValue("text", text="M2"),
            }
        ),
    ]
    assert projected_field_names(groups) == ["material_id", "swatch", "description"]


def test_projected_field_names_handles_empty_input() -> None:
    assert projected_field_names([]) == []


def test_projected_field_names_dedupes_repeated_field_names() -> None:
    groups = [
        ExtractedGroup(values={"a": ExtractedFieldValue("text", text="1")}),
        ExtractedGroup(values={"a": ExtractedFieldValue("text", text="2")}),
        ExtractedGroup(values={"b": ExtractedFieldValue("text", text="3")}),
    ]
    assert projected_field_names(groups) == ["a", "b"]


# ---------------------------------------------------------------------------
# Helpers for pattern detection tests
# ---------------------------------------------------------------------------


def _pattern(
    image_field_name: str = "swatch",
    section_names: list[str] | None = None,
) -> ImageTextPattern:
    names = section_names or ["text_1", "text_2"]
    sample = ImageSampleDefinition(
        rect_px=RectPx(x0=0, y0=0, x1=100, y1=100),
        width_px=100,
        height_px=100,
        aspect_ratio=1.0,
    )
    sections = [
        TextSectionDefinition(
            name=name,
            index=i,
            relative_rect=RelativeRect(
                x0=0.0, y0=1.0 + i * 0.25, x1=1.0, y1=1.0 + (i + 1) * 0.25
            ),
        )
        for i, name in enumerate(names)
    ]
    return ImageTextPattern(
        sample=sample,
        text_side="below",
        segmentation="rows",
        text_sections=sections,
        image_field_name=image_field_name,
    )


def _detection(
    status: str = "accepted",
    extracted_text: dict[str, str] | None = None,
    image_bytes: bytes = b"",
) -> PatternDetection:
    return PatternDetection(
        page_index=0,
        image_rect_px=RectPx(x0=10, y0=10, x1=90, y1=90),
        text_section_rects_px={},
        extracted_text=extracted_text or {},
        image_bytes=image_bytes,
        status=status,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# detection_to_group
# ---------------------------------------------------------------------------


def test_detection_to_group_has_image_field() -> None:
    group = detection_to_group(_detection(image_bytes=b"fake_png"), _pattern())
    assert "swatch" in group.values
    assert group.values["swatch"].field_type == "image"
    assert group.values["swatch"].image_bytes == b"fake_png"


def test_detection_to_group_has_text_fields() -> None:
    group = detection_to_group(
        _detection(extracted_text={"text_1": "Beech", "text_2": "BH-01"}),
        _pattern(),
    )
    assert group.values["text_1"].text == "Beech"
    assert group.values["text_2"].text == "BH-01"


def test_detection_to_group_missing_text_falls_back_to_empty_string() -> None:
    group = detection_to_group(
        _detection(extracted_text={}),
        _pattern(section_names=["text_1"]),
    )
    assert group.values["text_1"].text == ""


def test_detection_to_group_text_fields_have_text_type() -> None:
    group = detection_to_group(
        _detection(extracted_text={"text_1": "x"}),
        _pattern(section_names=["text_1"]),
    )
    assert group.values["text_1"].field_type == "text"


def test_detection_to_group_field_order_image_first_then_sections() -> None:
    group = detection_to_group(
        _detection(),
        _pattern(image_field_name="img", section_names=["a", "b", "c"]),
    )
    assert list(group.values) == ["img", "a", "b", "c"]


def test_detection_to_group_custom_image_field_name() -> None:
    group = detection_to_group(
        _detection(image_bytes=b"x"),
        _pattern(image_field_name="finish_swatch"),
    )
    assert "finish_swatch" in group.values
    assert group.values["finish_swatch"].field_type == "image"


# ---------------------------------------------------------------------------
# detections_to_groups — status filtering
# ---------------------------------------------------------------------------


def test_detections_to_groups_includes_accepted() -> None:
    assert len(detections_to_groups([_detection(status="accepted")], _pattern())) == 1


def test_detections_to_groups_includes_edited() -> None:
    assert len(detections_to_groups([_detection(status="edited")], _pattern())) == 1


def test_detections_to_groups_includes_manual() -> None:
    assert len(detections_to_groups([_detection(status="manual")], _pattern())) == 1


def test_detections_to_groups_excludes_rejected() -> None:
    assert detections_to_groups([_detection(status="rejected")], _pattern()) == []


def test_detections_to_groups_excludes_pending() -> None:
    assert detections_to_groups([_detection(status="pending")], _pattern()) == []


def test_detections_to_groups_mixed_statuses() -> None:
    detections = [
        _detection(status="accepted"),
        _detection(status="rejected"),
        _detection(status="pending"),
        _detection(status="edited"),
        _detection(status="manual"),
    ]
    groups = detections_to_groups(detections, _pattern())
    assert len(groups) == 3  # accepted + edited + manual only


def test_detections_to_groups_empty_input_returns_empty() -> None:
    assert detections_to_groups([], _pattern()) == []


def test_projected_field_names_from_pattern_groups() -> None:
    groups = detections_to_groups(
        [_detection(extracted_text={"finish": "Beech", "code": "BH-01"})],
        _pattern(image_field_name="swatch", section_names=["finish", "code"]),
    )
    assert projected_field_names(groups) == ["swatch", "finish", "code"]
