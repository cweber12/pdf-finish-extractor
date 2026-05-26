from __future__ import annotations

import pytest

from src.extraction.pattern import ImageSampleDefinition, PatternDetectionOptions, RectPx
from src.extraction.pattern_matching import image_matches_sample


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample(width: int = 100, height: int = 100) -> ImageSampleDefinition:
    return ImageSampleDefinition(
        rect_px=RectPx(x0=0, y0=0, x1=width, y1=height),
        width_px=width,
        height_px=height,
        aspect_ratio=width / height,
    )


def _opts(**kwargs: object) -> PatternDetectionOptions:
    return PatternDetectionOptions(**kwargs)  # type: ignore[arg-type]


_PAGE = (1000, 1000)


# ---------------------------------------------------------------------------
# Exact match
# ---------------------------------------------------------------------------


def test_exact_match_passes() -> None:
    sample = _sample(100, 100)
    candidate = RectPx(x0=10, y0=10, x1=110, y1=110)
    assert image_matches_sample(candidate, sample, PatternDetectionOptions(), _PAGE) is True


# ---------------------------------------------------------------------------
# Within tolerance
# ---------------------------------------------------------------------------


def test_candidate_within_width_tolerance_passes() -> None:
    sample = _sample(100, 100)
    # 8% wider — well within 20% default tolerance; AR also needs to be inside 10% AR tol
    candidate = RectPx(0, 0, 108, 100)
    opts = _opts(size_tolerance_pct=0.20, aspect_ratio_tolerance_pct=0.10)
    assert image_matches_sample(candidate, sample, opts, _PAGE) is True


def test_candidate_within_height_tolerance_passes() -> None:
    sample = _sample(100, 100)
    candidate = RectPx(0, 0, 100, 110)
    opts = _opts(size_tolerance_pct=0.10, aspect_ratio_tolerance_pct=0.15)
    assert image_matches_sample(candidate, sample, opts, _PAGE) is True


def test_candidate_within_aspect_ratio_tolerance_passes() -> None:
    # sample is 100×100 (AR=1.0), candidate is 105×100 (AR=1.05), AR tol 10%
    sample = _sample(100, 100)
    candidate = RectPx(0, 0, 105, 100)
    opts = _opts(size_tolerance_pct=0.20, aspect_ratio_tolerance_pct=0.10)
    assert image_matches_sample(candidate, sample, opts, _PAGE) is True


# ---------------------------------------------------------------------------
# Outside tolerance
# ---------------------------------------------------------------------------


def test_candidate_outside_width_tolerance_fails() -> None:
    sample = _sample(100, 100)
    # 25% wider, tolerance is 20%
    candidate = RectPx(0, 0, 125, 100)
    opts = _opts(size_tolerance_pct=0.20)
    assert image_matches_sample(candidate, sample, opts, _PAGE) is False


def test_candidate_outside_height_tolerance_fails() -> None:
    sample = _sample(100, 100)
    candidate = RectPx(0, 0, 100, 125)
    opts = _opts(size_tolerance_pct=0.20)
    assert image_matches_sample(candidate, sample, opts, _PAGE) is False


def test_candidate_outside_aspect_ratio_tolerance_fails() -> None:
    # sample 100×100 (AR=1.0), candidate 150×100 (AR=1.5), tol=10%
    sample = _sample(100, 100)
    candidate = RectPx(0, 0, 150, 100)
    opts = _opts(size_tolerance_pct=0.60, aspect_ratio_tolerance_pct=0.10)
    assert image_matches_sample(candidate, sample, opts, _PAGE) is False


# ---------------------------------------------------------------------------
# Page area cap
# ---------------------------------------------------------------------------


def test_candidate_exceeding_page_area_threshold_fails() -> None:
    sample = _sample(100, 100)
    # Page is 100×100 = 10000 px²; candidate is 50×50 = 2500 px² = 25% > 10%
    candidate = RectPx(0, 0, 50, 50)
    opts = _opts(size_tolerance_pct=0.60, aspect_ratio_tolerance_pct=0.60, max_page_area_pct=0.10)
    assert image_matches_sample(candidate, sample, opts, (100, 100)) is False


def test_candidate_below_page_area_threshold_passes() -> None:
    sample = _sample(30, 30)
    # Page 1000×1000 = 1_000_000; candidate 30×30 = 900 = 0.09% << 10%
    candidate = RectPx(0, 0, 30, 30)
    opts = _opts(size_tolerance_pct=0.20, max_page_area_pct=0.10)
    assert image_matches_sample(candidate, sample, opts, _PAGE) is True


# ---------------------------------------------------------------------------
# Tiny icon rejection
# ---------------------------------------------------------------------------


def test_tiny_icon_width_fails() -> None:
    sample = _sample(100, 100)
    candidate = RectPx(0, 0, 5, 100)  # width=5 < default min_image_width_px=12
    assert image_matches_sample(candidate, sample, PatternDetectionOptions(), _PAGE) is False


def test_tiny_icon_height_fails() -> None:
    sample = _sample(100, 100)
    candidate = RectPx(0, 0, 100, 5)  # height=5 < default min_image_height_px=12
    assert image_matches_sample(candidate, sample, PatternDetectionOptions(), _PAGE) is False


def test_min_size_exactly_at_threshold_passes() -> None:
    sample = _sample(12, 12)
    candidate = RectPx(0, 0, 12, 12)
    opts = _opts(min_image_width_px=12, min_image_height_px=12)
    assert image_matches_sample(candidate, sample, opts, _PAGE) is True


def test_min_size_one_below_threshold_fails() -> None:
    sample = _sample(100, 100)
    candidate = RectPx(0, 0, 11, 100)
    opts = _opts(min_image_width_px=12, min_image_height_px=12, size_tolerance_pct=1.0)
    assert image_matches_sample(candidate, sample, opts, _PAGE) is False
