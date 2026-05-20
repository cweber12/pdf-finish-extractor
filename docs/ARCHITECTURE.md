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
    │   ├── grid_editor.py    Overlay for drawing lines and tagging cells.
    │   ├── preview_panel.py  Shows extracted pairs; triggers upload.
    │   └── profile_manager.py  Saves/loads Grid profiles as JSON files.
    ├── extraction/           Pure extraction logic — no UI, no network.
    │   ├── grid.py           Grid data model (lines, explicit CellPair list).
    │   ├── extractor.py      Applies a Grid to a PDF; returns ExtractedPair list.
    │   └── image_processing.py  Compresses images to WebP (matches client rules).
    └── upload/               Network I/O — no extraction or UI logic.
        ├── worker_client.py  POSTs swatch to Cloudflare Worker (R2 + DB write).
        └── neon_client.py    Read-only Neon queries (duplicate detection only).
```

**Dependency rule:** `ui` → `extraction`, `upload`. `extraction` and `upload` have no dependency on each other or on `ui`.

---

## Data Flow

```
User opens PDF
      │
      ▼
PDFViewer (PyMuPDF → QPixmap)
      │
      ▼
GridEditor — user draws lines on overlay, clicks two cells to form explicit pairs
      │  saves/loads
      ▼
ProfileManager (profiles/*.json)
      │  Grid
      ▼
Extractor.extract_all_pages()
  ├── converts pixel coords → PDF points (÷ RENDER_DPI/72)
  ├── clips each image cell → PNG bytes via PyMuPDF
  ├── reads text from paired text cell via page.get_text("text", clip=rect)
  └── returns List[ExtractedPair]
      │
      ▼
NeonClient.material_ids_in_db()   ← marks duplicates before preview
      │
      ▼
PreviewPanel — user reviews, deselects rows, clicks Upload
      │  List[ExtractedPair] (selected)
      ▼
image_processing.compress_image() — WebP, max 1920 px, 85% quality
      │
      ▼
WorkerClient.upload()
  POST /api/v1/materials/{materialId}/swatch
  → Worker uploads to R2 + upserts image_assets row in Neon
```

---

## Key Design Decisions

### Grid coordinate space

Lines are stored in **rendered pixel space** at 150 DPI. The `Extractor` divides by `150/72 ≈ 2.083` to convert to PDF points before calling PyMuPDF. This means a profile saved on one machine is portable as long as the same DPI constant is used — `RENDER_DPI = 150` is defined in both `pdf_viewer.py` and `extractor.py`.

`PDFViewer` renders at 150 DPI but scales the displayed image to fit the window. Two helper methods bridge these spaces: `display_to_original_coords()` converts a click position in the scaled label to 150 DPI pixel coordinates, and `original_to_display_coords()` converts back for drawing overlays. The `GridEditor` always converts mouse input to 150 DPI before storing, so stored line positions are always in the same space the `Extractor` expects.

### Explicit cell pairing

Each `CellPair(image_cell, text_cell)` names an image cell and its corresponding text cell as `(row, col)` tuples. Pairs are built interactively: the user enters *Pair Cells* mode, clicks an image cell (highlighted orange as pending), then clicks the text cell — a numbered pair is created. Right-clicking a highlighted cell removes its pair. This replaces the old global `pair_direction` approach, which did not support catalogs where text positions vary per row.

Pairs are stored in `Grid.pairs: list[CellPair]` and serialised as `[{"image_cell": [r, c], "text_cell": [r, c]}, ...]` in profile JSON. The `Extractor` iterates `grid.pairs` directly with no direction inference.

### Multi-page extraction

The grid defined on page 1 is applied unchanged to every subsequent page. No per-page adjustment is made. If a page has fewer filled cells than the grid implies (e.g. the last page of a catalog), cells that yield empty text are silently skipped — no pair is emitted for them.

### Duplicate detection

Before the preview panel is shown, `NeonClient.material_ids_in_db()` queries the `image_assets` table using `alt_text` as the material ID key. Matching rows are flagged as `is_duplicate = True` and highlighted yellow in the preview. The Worker upserts regardless — the flag is informational only.

### Upload path

Images are uploaded via the existing Worker API rather than directly to R2, so no R2 API credentials are stored locally. The Worker constructs the R2 key as:

```
users/{uid}/projects/{projectId}/materials/{materialId}/{imageId}.webp
```

and inserts/upserts the `image_assets` row. The Python client only needs `API_BASE_URL`, `API_SECRET`, `FIREBASE_UID`, and `PROJECT_ID`.

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
