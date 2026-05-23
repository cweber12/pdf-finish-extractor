"""Unit tests for PDFViewer zoom and coordinate-mapping logic.

These tests operate entirely in memory – no real PDF file is required.  They
reach into private attributes to set up a known state, then verify the public
(or semi-public) helper methods behave correctly.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LABEL_W = 400
LABEL_H = 600
PAGE_W = 500
PAGE_H = 700


@pytest.fixture
def viewer(qapp):
    """PDFViewer with a fixed label geometry and a synthetic pixmap."""
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QPixmap

    from src.ui.pdf_viewer import PDFViewer

    v = PDFViewer()
    v._label.setGeometry(QRect(56, 56, LABEL_W, LABEL_H))
    v._original_pixmap = QPixmap(PAGE_W, PAGE_H)
    v._fit_pixmap()
    return v


# ---------------------------------------------------------------------------
# _fit_scale
# ---------------------------------------------------------------------------

class TestFitScale:
    def test_constrained_by_width(self, viewer):
        # 400/500 = 0.8; 600/700 ≈ 0.857 → width wins
        assert viewer._fit_scale() == pytest.approx(400 / 500)

    def test_returns_one_when_no_pixmap(self, qapp):
        from src.ui.pdf_viewer import PDFViewer

        v = PDFViewer()
        assert v._fit_scale() == 1.0


# ---------------------------------------------------------------------------
# zoom_at
# ---------------------------------------------------------------------------

class TestZoomAt:
    def test_zoom_level_updates(self, viewer):
        viewer.zoom_at(200, 300, 2.0)
        assert viewer.zoom_level == pytest.approx(2.0)

    def test_zoom_clamped_to_max(self, viewer):
        viewer.zoom_at(200, 300, 100.0)
        assert viewer.zoom_level == pytest.approx(viewer._MAX_ZOOM)

    def test_zoom_clamped_to_min(self, viewer):
        # Zooming in first, then trying to zoom below 1.
        viewer.zoom_at(200, 300, 2.0)
        viewer.zoom_at(200, 300, 0.1)
        assert viewer.zoom_level == pytest.approx(1.0)

    def test_focus_point_invariant(self, viewer):
        """The PDF point under the cursor should not move after a zoom."""
        display_x, display_y = 250, 350
        ox_before, oy_before = viewer.display_to_original_coords(display_x, display_y)

        viewer.zoom_at(display_x, display_y, 2.0)

        ox_after, oy_after = viewer.display_to_original_coords(display_x, display_y)

        # Allow a 2-pixel rounding tolerance.
        assert abs(ox_after - ox_before) <= 2
        assert abs(oy_after - oy_before) <= 2

    def test_reset_when_zoom_is_one(self, viewer):
        viewer.zoom_at(200, 300, 2.0)
        viewer.zoom_at(200, 300, 1.0)
        expected_cx = PAGE_W / 2.0
        expected_cy = PAGE_H / 2.0
        assert viewer._viewport_cx == pytest.approx(expected_cx)
        assert viewer._viewport_cy == pytest.approx(expected_cy)


# ---------------------------------------------------------------------------
# pan_by
# ---------------------------------------------------------------------------

class TestPanBy:
    def test_pan_noop_at_zoom_one(self, viewer):
        cx, cy = viewer._viewport_cx, viewer._viewport_cy
        viewer.pan_by(50, 50)
        assert viewer._viewport_cx == cx
        assert viewer._viewport_cy == cy

    def test_pan_moves_viewport(self, viewer):
        viewer.zoom_at(200, 300, 2.0)
        cx_before = viewer._viewport_cx
        cy_before = viewer._viewport_cy
        viewer.pan_by(-20, -30)  # pan right / down in doc coords
        ds = viewer._fit_scale() * viewer.zoom_level
        assert viewer._viewport_cx == pytest.approx(cx_before + 20 / ds)
        assert viewer._viewport_cy == pytest.approx(cy_before + 30 / ds)


# ---------------------------------------------------------------------------
# _viewport_origin – clamping
# ---------------------------------------------------------------------------

class TestViewportOrigin:
    def test_origin_clamped_at_left_edge(self, viewer):
        viewer._zoom = 2.0
        viewer._viewport_cx = 0.0  # force centre too far left
        viewer._viewport_cy = PAGE_H / 2.0
        vx, vy = viewer._viewport_origin()
        assert vx >= 0.0

    def test_origin_clamped_at_top_edge(self, viewer):
        viewer._zoom = 2.0
        viewer._viewport_cx = PAGE_W / 2.0
        viewer._viewport_cy = 0.0  # force centre too far up
        vx, vy = viewer._viewport_origin()
        assert vy >= 0.0

    def test_origin_clamped_at_right_edge(self, viewer):
        viewer._zoom = 2.0
        viewer._viewport_cx = PAGE_W * 10.0  # way off right
        viewer._viewport_cy = PAGE_H / 2.0
        vx, vy = viewer._viewport_origin()
        ds = viewer._fit_scale() * viewer._zoom
        max_vx = PAGE_W - LABEL_W / ds
        assert vx <= max_vx + 1  # +1 for rounding


# ---------------------------------------------------------------------------
# Coordinate round-trip at zoom > 1
# ---------------------------------------------------------------------------

class TestCoordinateRoundTrip:
    def test_round_trip_at_zoom_two(self, viewer):
        viewer.zoom_at(200, 300, 2.0)

        for dx, dy in [(100, 150), (200, 300), (350, 500)]:
            ox, oy = viewer.display_to_original_coords(dx, dy)
            dx2, dy2 = viewer.original_to_display_coords(ox, oy)
            # Allow 2-pixel rounding tolerance.
            assert abs(dx2 - dx) <= 2, f"x round-trip failed: {dx} -> {ox} -> {dx2}"
            assert abs(dy2 - dy) <= 2, f"y round-trip failed: {dy} -> {oy} -> {dy2}"
