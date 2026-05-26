from __future__ import annotations

from collections.abc import Sequence

from src.extraction.extractor import ExtractedGroup
from src.extraction.field_extractor import ExtractedFieldValue
from src.extraction.pattern import ImageTextPattern, PatternDetection

_EXPORTABLE_STATUSES = {"accepted", "edited", "manual"}


def projected_field_names(groups: Sequence[ExtractedGroup]) -> list[str]:
    """Return first-seen field order across extracted groups."""
    names: list[str] = []
    for group in groups:
        for name in group.values:
            if name not in names:
                names.append(name)
    return names


def detection_to_group(
    detection: PatternDetection,
    pattern: ImageTextPattern,
) -> ExtractedGroup:
    """Convert one PatternDetection to an ExtractedGroup for export or preview."""
    values: dict[str, ExtractedFieldValue] = {
        pattern.image_field_name: ExtractedFieldValue(
            field_type="image", image_bytes=detection.image_bytes
        )
    }
    for section in pattern.text_sections:
        values[section.name] = ExtractedFieldValue(
            field_type="text",
            text=detection.extracted_text.get(section.name, ""),
        )
    return ExtractedGroup(values=values)


def detections_to_groups(
    detections: list[PatternDetection],
    pattern: ImageTextPattern,
) -> list[ExtractedGroup]:
    """Convert accepted/edited/manual detections to ExtractedGroups for export.

    Pending and rejected detections are excluded.
    """
    return [
        detection_to_group(d, pattern)
        for d in detections
        if d.status in _EXPORTABLE_STATUSES
    ]
