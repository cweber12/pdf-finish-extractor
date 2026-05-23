# Architecture

## Overview

PDF Finish Extractor is a PyQt6 desktop application that imports material finish catalogs from PDF files into the FFE materials database. The user defines a grid layout once per catalog format (saved as a named profile), and the app applies it to extract swatch images and material IDs from every page, then uploads them through the Cloudflare Worker API.

---

## Module Boundaries

```
pdf-finish-extractor/
├── main.py                   Entry point. Creates QApplication and MainWindow.
├── profiles/                 Named grid layouts (JSON). User-managed.
└── src/
    ├── ui/                   PyQt6 UI layer — no extraction or upload logic.
    │   ├── main_window.py    Top-level window, toolbar, wires UI components together.
    │   ├── pdf_viewer.py     Renders a PDF page to QPixmap via PyMuPDF.
    │   ├── grid_editor.py    Overlay for drawing lines, pairing cells, omitting pages/regions.
    │   ├── preview_panel.py  Shows extracted pairs; triggers upload or export.
    │   └── profile_manager.py  Saves/loads Grid profiles as JSON files.
    ├── extraction/           Pure extraction logic — no UI, no network.
    │   ├── grid.py           Grid data model (lines, pairs, omit rules).
    │   ├── extractor.py      Applies a Grid to a PDF; returns ExtractedPair list.
    │   └── image_processing.py  Compresses images to WebP (matches client rules).
    ├── exporting/            File export logic — no UI, extraction, or network I/O.
    │   └── swatch_workbook.py  Writes extracted IDs and swatch images to Excel.
    └── upload/               Network I/O — no extraction or UI logic.
        ├── worker_client.py  POSTs swatch to Cloudflare Worker (R2 + DB write).
        └── neon_client.py    Read-only Neon queries (duplicate detection only).
```

**Dependency rule:** `ui` → `extraction`, `exporting`, `upload`. `exporting` accepts swatch rows with `material_id` and `image_bytes` fields but has no dependency on UI, extraction internals, or network code. `extraction` and `upload` have no dependency on each other or on `ui`.

---

## Data Flow

```
User opens PDF
      │
      ▼
PDFViewer (PyMuPDF → QPixmap)
      │
      ▼
GridEditor — navigate pages, draw lines, pair cells, omit pages/regions
      │  saves/loads
      ▼
ProfileManager (profiles/*.json)
      │  Grid (includes omitted_pages, omit_regions)
      ▼
MainWindow spawns _ExtractionWorker on QThread
      │
      ▼
_ExtractionWorker.run() (off main thread)
  ├─ Extractor.extract_all_pages()
  │  ├─ skip pages in omitted_pages
  │  ├─ for each active page:
  │  │  ├─ render page to image at 150 DPI
  │  │  ├─ skip pairs intersecting omit_regions
  │  │  ├─ for each pair: clip image cell → PNG bytes, extract text from text cell
  │  │  └─ emit progress signal
  │  └─ return List[ExtractedPair]
  ├─ emit finished signal with pairs
      │
      ▼
NeonClient.material_ids_in_db() — marks duplicates for preview
      │
      ▼
PreviewPanel — user reviews, deselects rows, clicks Upload
      ├─ Export Excel:
      │    ├─ collect manufacturer/category from the user
      │    └─ exporting.export_swatch_workbook() writes header rows plus ID/image rows
      │
      └─ Upload selected:
           │  List[ExtractedPair] (selected)
           ▼
      image_processing.compress_image() — WebP, max 1920 px, 85% quality
           │
           ▼
      WorkerClient.upload() (per row, with inline status updates)
        ├─ resolve material UUID via GET /api/v1/projects/{projectId}/materials
        ├─ if not found: POST to create material record
        └─ POST /api/v1/images?entity_type=material&entity_id={uuid} with WebP bytes
           │
           ▼
      Worker (backend) — upload to R2, upsert image_assets row in Neon
```

---

## Key Design Decisions

### Asynchronous extraction

Extraction is dispatched to a `QThread` worker (`_ExtractionWorker`) via `MainWindow._on_extract()`. This prevents the UI from freezing during large multi-page PDFs. The worker emits signals:
- `progress(page_index, page_count, pairs_extracted)` — fires after each page
- `finished(pairs, was_cancelled)` — on completion or user cancel
- `failed(error_msg)` — on exception

Cancel requests are checked between pages, allowing graceful interruption without corruption.

### Page rendering optimization

Instead of rendering every swatch crop separately, the `Extractor` renders each page once at 150 DPI to a full-page image, then clips every swatch from that cached image. Text extraction data is also cached per page to avoid re-parsing. This dramatically reduces extraction time for multi-swatch catalogs.

### Grid coordinate space

Lines are stored in **rendered pixel space** at 150 DPI. The `Extractor` divides by `150/72 ≈ 2.083` to convert to PDF points before calling PyMuPDF. This means a profile saved on one machine is portable as long as the same DPI constant is used — `RENDER_DPI = 150` is defined in both `pdf_viewer.py` and `extractor.py`.

`PDFViewer` renders at 150 DPI but scales the displayed image to fit the window. Two helper methods bridge these spaces: `display_to_original_coords()` converts a click position in the scaled label to 150 DPI pixel coordinates, and `original_to_display_coords()` converts back for drawing overlays. The `GridEditor` always converts mouse input to 150 DPI before storing, so stored line positions are always in the same space the `Extractor` expects.

### Explicit cell pairing

Each `CellPair(image_cell, text_cell)` names an image cell and its corresponding text cell as `(row, col)` tuples. Pairs are built interactively: the user enters *Pair Cells* mode, clicks an image cell (highlighted orange as pending), then clicks the text cell — a numbered pair is created. Right-clicking a highlighted cell removes its pair. This replaces the old global `pair_direction` approach, which did not support catalogs where text positions vary per row.

Pairs are stored in `Grid.pairs: list[CellPair]` and serialised as `[{"image_cell": [r, c], "text_cell": [r, c]}, ...]` in profile JSON. The `Extractor` iterates `grid.pairs` directly with no direction inference.

### Two-step material upload

Uploads use a two-step workflow per `docs/MATERIAL_SWATCH_UPLOAD_GUIDE.md`:

1. **Material resolution** — `GET /api/v1/projects/{projectId}/materials` to search for the material by composite ID. If found, reuse its UUID; otherwise `POST` to create a minimal record and use its new UUID.
2. **Image upload** — `POST /api/v1/images?entity_type=material&entity_id={uuid}&alt_text=Swatch` with the WebP bytes.

The Cloudflare Worker backend handles the R2 upload and Neon database upsert, so the Python client needs no S3 credentials or direct database write access.

### Multi-page extraction

The grid defined on page 1 is applied unchanged to every subsequent page. No per-page adjustment is made. If a page has fewer filled cells than the grid implies (e.g. the last page of a catalog), cells that yield empty text are silently skipped — no pair is emitted for them.

### Page omission and region ignore

Mixed-format catalogs (where some pages contain diagrams, renderings, or non-extractable content) are handled via two mechanisms:

**Omitted pages:** `Grid.omitted_pages` lists zero-based page indices to skip entirely during extraction. This is useful for cover pages, blank pages, or indexes that don't follow the swatch layout.

**Omit regions:** `Grid.omit_regions` lists page-specific rectangular areas (in 150-DPI rendered pixel space) to exclude. Each `OmitRegion` specifies a `page_index` and `rect: [x0, y0, x1, y1]`. During extraction, any pair whose image or text cell intersects an omit region on that page is silently skipped. This lets a single reusable grid handle pages with embedded diagrams, advertisements, or partial content without requiring per-page layout redefinition.

Both mechanisms preserve the extracted data integrity: skipped pairs simply do not appear in the output. No markers or indicators are left behind.

### Excel swatch export

`PreviewPanel` can export selected extracted rows to an `.xlsx` workbook after prompting the user for manufacturer and category. Workbook creation is isolated in `src/exporting/swatch_workbook.py`, which writes:
- row 1: manufacturer label and value
- row 2: category label and value
- row 4: `ID` and `Image` column headers
- row 5 onward: extracted material IDs with embedded swatch images

Invalid image bytes are skipped gracefully while preserving the material ID row.

### Duplicate detection

Before the preview panel is shown, `NeonClient.material_ids_in_db()` queries the `image_assets` table using `alt_text` as the material ID key. Matching rows are flagged as `is_duplicate = True` and highlighted yellow in the preview. The Worker upserts regardless — the flag is informational only.

### Upload path

Images are uploaded via the Cloudflare Worker API (not direct R2), ensuring security by keeping credentials off the client. The Worker constructs the R2 key as:

```
users/{FIREBASE_UID}/projects/{PROJECT_ID}/materials/{materialId}/{imageId}.webp
```

and inserts or upserts the `image_assets` row. The Python client only needs `API_BASE_URL`, `FIREBASE_API_KEY`, `FIREBASE_REFRESH_TOKEN`, `FIREBASE_UID`, and `PROJECT_ID`.

### Image compression

Compression in `image_processing.py` mirrors the client-side TypeScript (`compress.ts`):
- Max dimension: 1920 px (longest side, aspect ratio preserved)
- Format: WebP at 85% quality
- GIF: returned unchanged (detected by magic bytes `GIF87a` / `GIF89a`)

---

## External Dependencies

| Dependency | Purpose |
|---|---|
| PyQt6 | Desktop UI framework |
| PyMuPDF (`fitz`) | PDF rendering and text/image extraction |
| Pillow | Image compression to WebP |
| requests | HTTP POST to Cloudflare Worker API |
| psycopg2-binary | Read-only queries to Neon PostgreSQL |
| python-dotenv | Loads `.env` for credentials |
| openpyxl | Writes Excel swatch export workbooks |
