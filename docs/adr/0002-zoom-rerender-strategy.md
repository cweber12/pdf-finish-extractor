# ADR 0002 — Zoom re-renders the PDF page at higher DPI

When the user zooms in on the grid editor, the PDF page is re-rendered at `base_dpi × fit_scale × zoom_level` DPI using a debounced background `QThread` worker, rather than scaling up the existing 150-DPI pixmap with Qt's built-in transform. The scaled-up existing pixmap is shown immediately as a placeholder while the re-render is in flight.

## Considered options

**Scale the existing 150-DPI pixmap (rejected).** Fast — no re-render needed. But at 4–8× zoom the pixel grid of the original render becomes visible, making fine swatch boundary decisions imprecise. Grid line placement is the primary reason for zooming, so visual fidelity at that step matters.

**Re-render synchronously on every wheel tick (rejected).** Produces a sharp frame but blocks the main thread for each fitz render, causing visible stutter on large pages.

## Consequences

- `PDFViewer` gains a `QTimer` + `QThread` worker that renders on debounce (~150 ms of wheel-idle).
- The placeholder path (scaled existing pixmap) must remain correct so the overlay stays usable during the render delay.
- Zoom state (`zoom_level`, viewport center) lives in `PDFViewer` so that `display_to_original_coords` and `original_to_display_coords` are always consistent with the displayed frame.
