# ADR 0001 — UI Design System

**Status:** Accepted  
**Date:** 2026-05-19

## Context

The application shipped with a completely unstyled PyQt6 UI — system-default widgets, no colour scheme, no spacing discipline, no visual hierarchy. As an internal tool used for repeated data-entry work, the raw appearance created friction and made the app feel unfinished.

## Decision

Apply a cohesive dark-theme design system across all UI components, delivered as a global QSS stylesheet loaded at `QApplication` startup.

Key choices:

| Concern | Decision | Alternatives considered |
|---|---|---|
| Theme | Dark (`#0f1117` base) | Light, system-adaptive |
| Accent | Teal `#06b6d4` | Indigo `#6366f1`, Amber `#f59e0b` |
| Action bar | Styled `QWidget`, top of window | `QToolBar`, left sidebar |
| Mode toggles | Segmented control (connected pill bar) | Separate checkable buttons, radio buttons |
| Icons | Bundled SVGs in `src/ui/icons/` | Unicode symbols, no icons |
| Typography | System font (Segoe UI) + size scale | Bundled Inter |
| Empty state | Centered prompt + teal "Open PDF" CTA | Blank area, dashed drop zone |
| Upload feedback | Inline row status + auto-dismiss toast | Modal dialog, progress bar only |

## Consequences

- All styling lives in `src/ui/theme.py` as a single QSS string + colour/font constants. Components import `theme` for colours; they do not hardcode hex values.
- `main.py` calls `app.setStyleSheet(theme.STYLESHEET)` once at startup.
- The `QProgressBar` in `PreviewPanel` is removed; per-row status cells replace it.
- `GridEditor` gains an `open_requested` signal so the empty state "Open PDF" button can trigger the file dialog without coupling `GridEditor` to `MainWindow`.
- SVG icons require PyQt6's built-in SVG renderer (included in the standard `PyQt6` wheel).
