# Architecture

## Overview

PDF Finish Extractor is a PyQt6 desktop application that imports material finish catalog data from PDF files into Excel. The user defines a grid layout once per catalog format, defines a field recipe, groups related cells, and exports the extracted rows to an `.xlsx` workbook.

---

## Module Boundaries

```
pdf-finish-extractor/
├── main.py                   Entry point. Creates QApplication and MainWindow.
├── profiles/                 Named grid layouts (JSON). User-managed.
└── src/
    ├── ui/                   PyQt6 UI layer.
    │   ├── main_window.py    Compatibility adapter re-exporting shell MainWindow.
    │   ├── extraction_feedback.py  Compatibility adapter re-exporting feedback helpers.
    │   ├── extraction_session.py  QThread extraction lifecycle seam used by MainWindow.
    │   ├── main_window_intents.py  Compatibility adapter re-exporting shell intent helpers.
    │   ├── profile_menu.py   Compatibility adapter re-exporting profile menu helpers.
    │   ├── grid_editor_lifecycle.py  Grid/profile lifecycle state transforms for GridEditor.
    │   ├── grid_editor_pages.py  Page navigation/omission control state + hint decision helpers.
    │   ├── grid_editor_geometry.py  Cell/region hit-testing and coordinate boundary helpers.
    │   ├── grid_editor_hit_test.py  Line/handle hit precedence and visible-page drag targeting helpers.
    │   ├── grid_editor_interaction_flow.py  Shared interaction-flow helpers for mouse/zoom event wiring.
    │   ├── grid_editor_fields.py  Field recipe dialog and confirmation/prompt helpers.
    │   ├── grid_editor_controls.py  GridEditor toolbar + empty-state composition helpers.
    │   ├── grid_editor_widgets.py  Reusable GridEditor UI primitives (glow button, separators, status chips).
    │   ├── pdf_viewer.py     Renders a PDF page to QPixmap via PyMuPDF.
    │   ├── grid_editor.py    GridEditor state, controls, and interaction handlers.
    │   ├── grid_editor_overlay.py  Overlay rendering + pointer event forwarding seam for GridEditor.
    │   ├── grid_editor_grouping.py  Grouping recipe helpers + click-decision logic.
    │   ├── grid_editor_modes.py  Mode-resolution and cursor/hint behavior helpers.
    │   ├── grid_editor_right_click.py  Right-click decision helper for omit/group/line removal flows.
    │   ├── grid_editor_line_edit.py  Drag/placement line constraints and placement decision helpers.
    │   ├── grid_editor_omit.py  Omit-region move/release decisions and rectangle normalization helpers.
    │   ├── grid_editor_interaction.py  Mouse press/move/release branch-precedence decision helpers.
    │   ├── grid_editor_segments.py  Segment indexing, snapshot updates, and segment-nav state helpers.
    │   ├── preview_panel.py  Shows extracted groups; triggers Excel export.
    │   ├── profile_manager.py  Compatibility adapter re-exporting profile manager.
    │   ├── theme.py  Compatibility adapter re-exporting style tokens and stylesheet.
    │   ├── toast.py  Compatibility adapter re-exporting toast widget helper.
    │   ├── shell/
    │   │   ├── main_window.py  Top-level window, toolbar, wires UI components together.
    │   │   └── main_window_intents.py  Pure guard/preflight/message decisions for MainWindow actions.
    │   ├── feedback/
    │   │   ├── extraction_feedback.py  Pure helpers for extraction progress/status/toast decisions.
    │   │   └── toast.py  Toast presenter widget helper.
    │   ├── profiles/
    │   │   ├── profile_menu.py  Grid layout dropdown row widget + menu population helpers.
    │   │   └── profile_manager.py  UI-facing adapter over profile persistence.
    │   └── style/
    │       ├── theme.py  Design tokens, icon path helper, and global stylesheet.
    │       └── icons/  Bundled SVG assets referenced by the style theme.
    ├── extraction/           Pure extraction logic; no UI, export, or network I/O.
    │   ├── grid.py           Grid data model (lines, field recipe, groups, omit rules).
    │   ├── planner.py        Resolves page-local field rectangles from Grid + segments + omit rules.
    │   ├── field_extractor.py Executes text/image extraction for resolved fields.
    │   ├── group_projection.py Shared field-order projection helpers used by Preview and Export.
    │   ├── extractor.py      Orchestrates planning + field extraction; returns ExtractedGroup list.
    │   └── image_processing.py  Compresses images to WebP for future upload use.
    ├── exporting/            File export logic; no UI, extraction, or network I/O.
    │   └── swatch_workbook.py  Writes extracted groups to Excel.
    ├── common/               Shared cross-layer contracts.
    │   └── errors.py         Typed error classes + UI-safe message mapping.
    ├── profiles/             Profile persistence layer; no UI concerns.
    │   └── repository.py     Filesystem JSON repository for Grid profiles.
    └── upload/               Dormant network I/O kept for later reintegration.
        ├── worker_client.py  POSTs swatch to Cloudflare Worker.
        └── neon_client.py    Read-only Neon queries.
```

**Dependency rule:** `ui` → `extraction`, `exporting`, `profiles`, `upload`, `common`. `profiles` may depend on extraction contracts (`Grid`) but must not import PyQt UI modules. `exporting` accepts extracted groups with typed field values but has no dependency on UI, extraction internals, or network code. `extraction` and `upload` have no dependency on each other or on `ui`. `common` may be imported by any layer for shared contracts only (no PyQt, network, or PDF rendering logic). Upload modules remain in the codebase for later reintegration, but upload actions are not exposed in the current UI.

---

## Data Flow

```
User opens PDF
      │
      ▼
PDFViewer (PyMuPDF → QPixmap)
      │
      ▼
GridEditor — navigate pages, draw lines, define fields, group cells, omit pages/regions
      │  saves/loads
      ▼
ProfileManager (UI adapter)
      │
      ▼
ProfileRepository (profiles/*.json)
      │  Grid (field recipe, groups, omitted_pages, omit_regions)
      ▼
MainWindow spawns _ExtractionWorker on QThread
      │
      ▼
ExtractionSession.start() creates QThread + _ExtractionWorker
      │
      ▼
_ExtractionWorker.run() (off main thread)
  ├─ Extractor.extract_all_pages()
  │  ├─ skip pages in omitted_pages
  │  ├─ for each active page:
  │  │  ├─ ExtractionPlanner.plan_page() resolves typed field areas and applies omit-region filtering
  │  │  ├─ FieldExtractor.extract_groups() reads text/images from resolved areas
  │  │  └─ emit progress signal
  │  └─ return List[ExtractedGroup]
  ├─ emit finished signal with groups
      │
      ▼
PreviewPanel — user reviews, deselects rows, clicks Export Excel
      │
      ▼
exporting.export_swatch_workbook() — writes dynamic field columns
```

---

## Key Design Decisions

### Asynchronous extraction

Extraction is dispatched to a `QThread` worker (`_ExtractionWorker`) via `MainWindow._on_extract()`. This prevents the UI from freezing during large multi-page PDFs. The worker emits signals:

- `progress(page_index, page_count, groups_extracted)` — fires after each page
- `finished(groups, was_cancelled)` — on completion or user cancel
- `failed(error_msg)` — on exception

Cancel requests are checked between pages, allowing graceful interruption without corruption.

### Grid coordinate space

Lines are stored in **rendered pixel space** at 150 DPI. The `Extractor` divides by `150/72 ≈ 2.083` to convert to PDF points before calling PyMuPDF. This means a profile saved on one machine is portable as long as the same DPI constant is used.

`PDFViewer` renders at 150 DPI but scales the displayed image to fit the window. Two helper methods bridge these spaces: `display_to_original_coords()` converts a click position in the scaled label to 150 DPI pixel coordinates, and `original_to_display_coords()` converts back for drawing overlays.

### Field recipe and grouping

Each `FieldDefinition(name, type, click_count)` defines one exported field and the number of cells the user must click for that field. Fields are ordered; that order controls both the grouping click sequence and the Excel column order.

Each `CellGroup` maps field names to selected grid cells. Multi-cell fields must form an adjacent rectangle; the extractor reads the outer rectangle as one area, not as separate cells stitched together. Groups are stored in `Grid.groups` and serialized with the field recipe in profile JSON. Old `pairs` profiles are obsolete and are not migrated.

Changing the field recipe after groups exist clears existing groups after confirmation, because click counts, field types, or order can change how saved cells are interpreted.

### Sparse groups

No field is required for Excel export. A group is emitted as long as at least one field has data. Empty text fields and invalid image fields become blank cells in the exported workbook.

### Dormant two-step material upload

Upload code remains available for future reintegration but is not exposed in the current UI. When re-enabled, uploads should use the two-step workflow per `docs/MATERIAL_SWATCH_UPLOAD_GUIDE.md`:

1. **Material resolution** — `GET /api/v1/projects/{projectId}/materials` to search for the material by composite ID. If found, reuse its UUID; otherwise `POST` to create a minimal record and use its new UUID.
2. **Image upload** — `POST /api/v1/images?entity_type=material&entity_id={uuid}&alt_text=Swatch` with the WebP bytes.

### Multi-page extraction

The grid defined on page 1 is applied unchanged to every subsequent page unless layout segments are created by editing the grid on later pages. If a page has fewer filled cells than the grid implies, sparse groups are still emitted as long as at least one field has data.

### Page omission and region ignore

Mixed-format catalogs are handled via two mechanisms:

**Omitted pages:** `Grid.omitted_pages` lists zero-based page indices to skip entirely.

**Omit regions:** `Grid.omit_regions` lists page-specific rectangular areas in 150-DPI rendered pixel space. During extraction, any group with a field area that intersects an omit region on that page is silently skipped.

Both mechanisms preserve extracted data integrity: skipped groups simply do not appear in the output.

### Excel export

`PreviewPanel` can export selected extracted rows to an `.xlsx` workbook after prompting the user for manufacturer and category. Workbook creation is isolated in `src/exporting/swatch_workbook.py`, which writes:

- row 1: manufacturer label and value
- row 2: category label and value
- row 4: field names from the profile recipe
- row 5 onward: one extracted group per row, with text fields as text cells and image fields as embedded images

Invalid image bytes are skipped gracefully while preserving the rest of the row.

### Typed error modes

Extraction and export failures are wrapped into typed errors (`ExtractionError`, `ExportError`) from `src/common/errors.py`. UI layers map exceptions to user-safe text via `to_user_message(...)` before showing toasts. This keeps raw exception details out of the primary UI path while preserving deterministic error modes for tests.

---

## External Dependencies

| Dependency | Purpose |
|---|---|
| PyQt6 | Desktop UI framework |
| PyMuPDF (`fitz`) | PDF rendering and text/image extraction |
| Pillow | Image compression and image conversion |
| requests | HTTP POST to Cloudflare Worker API |
| psycopg2-binary | Read-only queries to Neon PostgreSQL |
| python-dotenv | Loads `.env` for credentials |
| openpyxl | Writes Excel workbooks |
