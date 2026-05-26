from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

from src.extraction.grid import OmitRegion

PatternSide = Literal["above", "below", "left", "right"]
TextSegmentation = Literal["rows", "columns"]

_PROFILE_TYPE = "image_text_pattern"
_PROFILE_VERSION = 1


@dataclass(frozen=True)
class RectPx:
    """Rectangle in 150-DPI rendered pixel space."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    def to_dict(self) -> dict[str, object]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RectPx:
        return cls(
            x0=int(data["x0"]),
            y0=int(data["y0"]),
            x1=int(data["x1"]),
            y1=int(data["y1"]),
        )


@dataclass(frozen=True)
class RelativeRect:
    """Rect stored as ratios relative to a detected image rect.

    x0 = (rect.x0 - image.x0) / image.width
    y0 = (rect.y0 - image.y0) / image.height
    x1 = (rect.x1 - image.x0) / image.width
    y1 = (rect.y1 - image.y0) / image.height

    Values outside [0, 1] are valid — they extend beyond the image boundary,
    which is expected for adjacent text sections.
    """

    x0: float
    y0: float
    x1: float
    y1: float

    def to_dict(self) -> dict[str, object]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RelativeRect:
        return cls(
            x0=float(data["x0"]),
            y0=float(data["y0"]),
            x1=float(data["x1"]),
            y1=float(data["y1"]),
        )


@dataclass(frozen=True)
class TextSectionDefinition:
    """One named text region, stored relative to the image rect."""

    name: str
    index: int
    relative_rect: RelativeRect

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "index": self.index,
            "relative_rect": self.relative_rect.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextSectionDefinition:
        return cls(
            name=str(data["name"]),
            index=int(data["index"]),
            relative_rect=RelativeRect.from_dict(data["relative_rect"]),
        )


@dataclass(frozen=True)
class ImageSampleDefinition:
    """Reference image used to calibrate size/aspect-ratio matching."""

    rect_px: RectPx
    width_px: int
    height_px: int
    aspect_ratio: float

    def to_dict(self) -> dict[str, object]:
        return {
            "rect_px": self.rect_px.to_dict(),
            "width_px": self.width_px,
            "height_px": self.height_px,
            "aspect_ratio": self.aspect_ratio,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageSampleDefinition:
        return cls(
            rect_px=RectPx.from_dict(data["rect_px"]),
            width_px=int(data["width_px"]),
            height_px=int(data["height_px"]),
            aspect_ratio=float(data["aspect_ratio"]),
        )


@dataclass(frozen=True)
class ImageTextPattern:
    """Authored pattern: one sample image + adjacent text layout."""

    sample: ImageSampleDefinition
    text_side: PatternSide
    segmentation: TextSegmentation
    text_sections: list[TextSectionDefinition]
    image_field_name: str = "swatch"

    def to_dict(self) -> dict[str, object]:
        return {
            "image_field_name": self.image_field_name,
            "sample": self.sample.to_dict(),
            "text_side": self.text_side,
            "segmentation": self.segmentation,
            "text_sections": [s.to_dict() for s in self.text_sections],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageTextPattern:
        text_side = str(data.get("text_side", "below"))
        if text_side not in ("above", "below", "left", "right"):
            text_side = "below"
        seg = str(data.get("segmentation", "rows"))
        if seg not in ("rows", "columns"):
            seg = "rows"
        return cls(
            image_field_name=str(data.get("image_field_name", "swatch")),
            sample=ImageSampleDefinition.from_dict(data["sample"]),
            text_side=text_side,  # type: ignore[arg-type]
            segmentation=seg,  # type: ignore[arg-type]
            text_sections=[
                TextSectionDefinition.from_dict(s) for s in data.get("text_sections", [])
            ],
        )


@dataclass(frozen=True)
class PatternDetectionOptions:
    """Tuning parameters for the size/aspect-ratio image scanner."""

    size_tolerance_pct: float = 0.20
    aspect_ratio_tolerance_pct: float = 0.10
    min_image_width_px: int = 12
    min_image_height_px: int = 12
    max_page_area_pct: float = 0.10
    require_text: bool = True
    sort_order: Literal["reading_order"] = "reading_order"

    def to_dict(self) -> dict[str, object]:
        return {
            "size_tolerance_pct": self.size_tolerance_pct,
            "aspect_ratio_tolerance_pct": self.aspect_ratio_tolerance_pct,
            "min_image_width_px": self.min_image_width_px,
            "min_image_height_px": self.min_image_height_px,
            "max_page_area_pct": self.max_page_area_pct,
            "require_text": self.require_text,
            "sort_order": self.sort_order,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatternDetectionOptions:
        return cls(
            size_tolerance_pct=float(data.get("size_tolerance_pct", 0.20)),
            aspect_ratio_tolerance_pct=float(data.get("aspect_ratio_tolerance_pct", 0.10)),
            min_image_width_px=int(data.get("min_image_width_px", 12)),
            min_image_height_px=int(data.get("min_image_height_px", 12)),
            max_page_area_pct=float(data.get("max_page_area_pct", 0.10)),
            require_text=bool(data.get("require_text", True)),
            sort_order="reading_order",
        )


DetectionStatus = Literal["pending", "accepted", "rejected", "edited", "manual"]


@dataclass
class PatternDetection:
    """One candidate image+text pair detected on a page."""

    page_index: int
    image_rect_px: RectPx
    text_section_rects_px: dict[str, RectPx]
    extracted_text: dict[str, str] = field(default_factory=dict)
    image_bytes: bytes = b""
    status: DetectionStatus = "pending"
    confidence: float = 1.0
    notes: list[str] = field(default_factory=list)


@dataclass
class PatternCorrection:
    """User-authored override for a single detection."""

    page_index: int
    image_rect_px: RectPx
    text_section_rects_px: dict[str, RectPx]
    status: DetectionStatus
    original_image_rect_px: RectPx | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "page_index": self.page_index,
            "image_rect_px": self.image_rect_px.to_dict(),
            "text_section_rects_px": {k: v.to_dict() for k, v in self.text_section_rects_px.items()},
            "status": self.status,
            "original_image_rect_px": (
                self.original_image_rect_px.to_dict()
                if self.original_image_rect_px is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatternCorrection:
        orig = data.get("original_image_rect_px")
        return cls(
            page_index=int(data["page_index"]),
            image_rect_px=RectPx.from_dict(data["image_rect_px"]),
            text_section_rects_px={
                k: RectPx.from_dict(v) for k, v in data.get("text_section_rects_px", {}).items()
            },
            status=data.get("status", "accepted"),  # type: ignore[arg-type]
            original_image_rect_px=RectPx.from_dict(orig) if orig is not None else None,
        )


@dataclass
class ImageTextPatternProfile:
    """Extraction profile for Image + Adjacent Text Pattern mode."""

    pattern: ImageTextPattern
    detection_options: PatternDetectionOptions = field(default_factory=PatternDetectionOptions)
    omitted_pages: list[int] = field(default_factory=list)
    omit_regions: list[OmitRegion] = field(default_factory=list)
    corrections: list[PatternCorrection] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_type": _PROFILE_TYPE,
            "version": _PROFILE_VERSION,
            "image_text_pattern": {
                "pattern": self.pattern.to_dict(),
                "detection_options": self.detection_options.to_dict(),
                "omitted_pages": list(self.omitted_pages),
                "omit_regions": [r.to_dict() for r in self.omit_regions],
                "corrections": [c.to_dict() for c in self.corrections],
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageTextPatternProfile:
        inner = data.get("image_text_pattern", {})
        return cls(
            pattern=ImageTextPattern.from_dict(inner["pattern"]),
            detection_options=PatternDetectionOptions.from_dict(
                inner.get("detection_options", {})
            ),
            omitted_pages=[int(p) for p in inner.get("omitted_pages", [])],
            omit_regions=[OmitRegion.from_dict(r) for r in inner.get("omit_regions", [])],
            corrections=[PatternCorrection.from_dict(c) for c in inner.get("corrections", [])],
        )


# ---------------------------------------------------------------------------
# Review state (issues #20, #21, #22)
# ---------------------------------------------------------------------------

ReviewStatusFilter = Literal["pending", "accepted", "rejected", "all"]


def detection_key(d: PatternDetection) -> str:
    """Stable string key for a detection, based on page and image rect."""
    r = d.image_rect_px
    return f"{d.page_index}:{r.x0}:{r.y0}:{r.x1}:{r.y1}"


def resolve_relative_rect(relative: RelativeRect, image_rect: RectPx) -> RectPx:
    """Compute an absolute pixel rect from a relative rect anchored to image_rect."""
    w = image_rect.width
    h = image_rect.height
    return RectPx(
        x0=round(image_rect.x0 + relative.x0 * w),
        y0=round(image_rect.y0 + relative.y0 * h),
        x1=round(image_rect.x0 + relative.x1 * w),
        y1=round(image_rect.y0 + relative.y1 * h),
    )


@dataclass
class PatternReviewState:
    """Transient review state for a pattern detection session.

    Tracks auto-detected and manual pairs, user corrections, and the current
    filter / cursor position.  Persisted via to_profile_corrections() /
    from_profile_corrections() (issue #22).
    """

    detections: list[PatternDetection] = field(default_factory=list)
    current_detection_index: int = 0
    status_filter: ReviewStatusFilter = "pending"
    corrections: dict[str, PatternCorrection] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Filtering / display
    # ------------------------------------------------------------------

    def visible_detections(self) -> list[PatternDetection]:
        """Return detections matching status_filter with corrections applied."""
        result = []
        for d in self.detections:
            key = detection_key(d)
            effective_status = (
                self.corrections[key].status if key in self.corrections else d.status
            )
            if self.status_filter == "all" or effective_status == self.status_filter:
                result.append(self._with_correction(d))
        return result

    def _with_correction(self, d: PatternDetection) -> PatternDetection:
        key = detection_key(d)
        if key not in self.corrections:
            return d
        c = self.corrections[key]
        return replace(
            d,
            image_rect_px=c.image_rect_px,
            text_section_rects_px=c.text_section_rects_px,
            status=c.status,
        )

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def apply_correction(
        self, detection: PatternDetection, correction: PatternCorrection
    ) -> None:
        """Store a user correction keyed by the detection's original position."""
        self.corrections[detection_key(detection)] = correction

    @property
    def has_corrections(self) -> bool:
        """True when there are unsaved corrections — warn before discarding."""
        return bool(self.corrections)

    def add_manual_pair(
        self,
        page_index: int,
        image_rect_px: RectPx,
        pattern: ImageTextPattern,
    ) -> PatternDetection:
        """Add a user-drawn pair; text sections are generated from the pattern.

        The pair is appended to detections and also stored as a correction so
        it survives save/reopen (issue #21).
        """
        text_section_rects_px = {
            section.name: resolve_relative_rect(section.relative_rect, image_rect_px)
            for section in pattern.text_sections
        }
        detection = PatternDetection(
            page_index=page_index,
            image_rect_px=image_rect_px,
            text_section_rects_px=text_section_rects_px,
            status="manual",
        )
        self.detections.append(detection)
        self.corrections[detection_key(detection)] = PatternCorrection(
            page_index=page_index,
            image_rect_px=image_rect_px,
            text_section_rects_px=text_section_rects_px,
            status="manual",
        )
        return detection

    # ------------------------------------------------------------------
    # Persistence (issue #22)
    # ------------------------------------------------------------------

    def to_profile_corrections(self) -> list[PatternCorrection]:
        """Return all corrections for storage in ImageTextPatternProfile."""
        return list(self.corrections.values())

    @classmethod
    def from_profile_corrections(
        cls, corrections: list[PatternCorrection]
    ) -> PatternReviewState:
        """Reconstruct review state from persisted profile corrections.

        For edited corrections the synthetic detection uses original_image_rect_px
        as its position so that detection_key() stays consistent with the stored
        correction key.
        """
        detections: list[PatternDetection] = []
        corrections_dict: dict[str, PatternCorrection] = {}
        for c in corrections:
            key_rect = (
                c.original_image_rect_px
                if c.original_image_rect_px is not None
                else c.image_rect_px
            )
            d = PatternDetection(
                page_index=c.page_index,
                image_rect_px=key_rect,
                text_section_rects_px=c.text_section_rects_px,
                status=c.status,
            )
            detections.append(d)
            corrections_dict[detection_key(d)] = c
        return cls(detections=detections, corrections=corrections_dict)
