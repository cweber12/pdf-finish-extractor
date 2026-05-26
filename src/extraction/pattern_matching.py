from __future__ import annotations

from src.extraction.pattern import ImageSampleDefinition, PatternDetectionOptions, RectPx


def image_matches_sample(
    candidate: RectPx,
    sample: ImageSampleDefinition,
    options: PatternDetectionOptions,
    page_size_px: tuple[int, int],
) -> bool:
    """Return True if *candidate* is a plausible match for the reference *sample*.

    Checks (in order): minimum size, page-area cap, width tolerance, height
    tolerance, and aspect-ratio tolerance.
    """
    w = candidate.width
    h = candidate.height

    if w < options.min_image_width_px or h < options.min_image_height_px:
        return False

    page_area = page_size_px[0] * page_size_px[1]
    if page_area > 0 and (w * h) / page_area > options.max_page_area_pct:
        return False

    tol = options.size_tolerance_pct
    if sample.width_px > 0 and abs(w - sample.width_px) / sample.width_px > tol:
        return False
    if sample.height_px > 0 and abs(h - sample.height_px) / sample.height_px > tol:
        return False

    if h > 0 and sample.aspect_ratio > 0:
        candidate_ar = w / h
        ar_tol = options.aspect_ratio_tolerance_pct
        if abs(candidate_ar - sample.aspect_ratio) / sample.aspect_ratio > ar_tol:
            return False

    return True
