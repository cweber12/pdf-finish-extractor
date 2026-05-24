from __future__ import annotations

from src.extraction.extractor import ExtractedFieldValue, ExtractedGroup
from src.extraction.group_projection import projected_field_names


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
