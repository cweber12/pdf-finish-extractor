from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.extraction.extractor import ExtractedGroup


def projected_field_names(groups: Sequence[ExtractedGroup]) -> list[str]:
    """Return first-seen field order across extracted groups."""
    names: list[str] = []
    for group in groups:
        for name in group.values:
            if name not in names:
                names.append(name)
    return names
