# PDF Finish Extractor

A desktop tool for importing material finish catalogs from PDF files into the FFE materials database. It renders the PDF, lets you define a reusable grid layout over the first page, extracts swatch images and material IDs from every page using that grid, and uploads them to Cloudflare R2 + Neon PostgreSQL.

---

## Features

- **PDF viewer** — open and navigate any PDF catalog inside the app
- **Grid editor** — draw horizontal and vertical lines over the page, define typed fields, and group cells for extraction
- **Interactive grouping** — define typed fields, then click cells in field order to build extracted groups with any number of columns
- **Named profiles** — save a grid layout under a name (e.g. "Supplier A – 2 column"); reload it instantly for future PDFs from the same supplier
- **Batch extraction** — the page-1 grid is applied automatically to every subsequent page; extraction runs asynchronously to keep the UI responsive
- **Page omission** — skip full pages or page-specific rectangular regions that contain diagrams, renderings, or other non-extractable content
- **Progress & cancellation** — monitor extraction progress and cancel long-running jobs
- **Preview panel** — review extracted groups and choose which rows to export
- **Excel export** — save extracted swatches to an Excel workbook with manufacturer/category metadata
- **Intelligent upload** — create materials if needed, upload swatch images via the Cloudflare Worker API to R2 + Neon

---

## Tech Stack

| Layer | Library |
|---|---|
| UI | PyQt6 |
| PDF rendering + extraction | PyMuPDF (`fitz`) |
| Image compression | Pillow |
| Network | requests (HTTP) |
| Database | psycopg2 → Neon PostgreSQL (read-only) |
| Excel | openpyxl |
| Config | python-dotenv |

---

## Project Structure

```
pdf-finish-extractor/
├── main.py                     # Entry point — launches the PyQt6 app
├── .env                        # Credentials & config (gitignored)
├── .env.example                # Template — copy to .env and fill in
├── requirements.txt
├── profiles/                   # Named grid profiles saved as JSON
│   └── example-2col.json
├── docs/
│   ├── ARCHITECTURE.md         # System design and data flow
│   ├── MATERIAL_SWATCH_UPLOAD_GUIDE.md  # Upload API details
│   └── adr/                    # Architecture decision records
└── src/
    ├── ui/
    │   ├── main_window.py      # Top-level window, toolbar, extraction worker
    │   ├── pdf_viewer.py       # PDF canvas widget (PyMuPDF → QPixmap)
    │   ├── grid_editor.py      # Line drawing, field grouping, page nav, omit controls
    │   ├── preview_panel.py    # Extraction review (thumbnails + IDs), export, upload
    │   ├── profile_manager.py  # Save / load / select named profiles
    │   ├── theme.py            # Global QSS stylesheet & design tokens
    │   └── toast.py            # Auto-dismiss overlay notifications
    ├── extraction/
    │   ├── grid.py             # Grid, FieldDefinition, CellGroup, OmitRegion models
    │   ├── extractor.py        # PyMuPDF extraction with progress/cancel/omit logic
    │   └── image_processing.py # WebP compression via Pillow
    ├── exporting/
    │   ├── swatch_workbook.py  # Excel workbook generation with metadata
    │   └── __init__.py
    └── upload/
        ├── worker_client.py    # Cloudflare Worker API (materials + images)
        └── neon_client.py      # Neon read-only queries (duplicate detection)
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <repository>
cd pdf-finish-extractor
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

`.env` requires:

```env
# Neon PostgreSQL (read-only for duplicate detection)
DATABASE_URL=postgresql://user:password@your-neon-host/dbname

# Cloudflare Worker API (handles R2 upload + DB writes)
API_BASE_URL=https://your-worker-subdomain.workers.dev

# Firebase authentication (OAuth via worker)
FIREBASE_API_KEY=your_firebase_api_key
FIREBASE_REFRESH_TOKEN=your_firebase_refresh_token
FIREBASE_UID=your_firebase_uid

# FFE context — scopes all uploaded materials to this owner + project
PROJECT_ID=your_project_uuid
```

⚠️ **Note:** Run `python scripts/login.py` to populate Firebase auth tokens interactively.

### 3. Run

```bash
python main.py
```

---

## Usage

### Step 1 — Open a PDF

Use **File → Open** to load a catalog PDF. The first page renders in the viewer.

### Step 2 — Define the grid

1. Use **◀ Previous** / **Next ▶** to navigate pages if needed. Mark pages to skip extraction with **Omit Page** toggle.
2. Click **+ H Line** or **+ V Line** and drag lines across the page to divide it into cells.
3. Open **Fields**, define each field name, type, click count, and order.
4. (Optional) Use **Draw Ignore Area** to mark page-specific regions (diagrams, renderings, blank sections) that should not be extracted.
5. Click **Group Cells** mode, then click cells in field order until each group is complete. Right-click a highlighted cell to remove its group.

### Step 3 — Save a profile (optional but recommended)

Click **Save Profile**, give it a name (e.g. `Supplier A – 2col`). Next time you open a PDF from the same supplier, pick the profile from the dropdown and skip steps 1–3.

### Step 4 — Extract

Click **▶ Extract All Pages**. The app:
1. Applies the grid to every page
2. Runs extraction asynchronously on a background thread (UI remains responsive)
3. Emits progress updates as each page completes
4. Opens the **Preview Panel** showing all extracted groups

In the preview:
- Deselect any row you want to skip.

### Step 5 — Export

Click **Export Excel**. Provide a manufacturer name and category. The app writes an Excel workbook with:
- Manufacturer and category metadata
- Column headers from the field recipe
- One row per extracted group, with text fields as cell text and image fields as embedded images

---

## Grid Profile Format

Profiles are plain JSON stored in `profiles/`. You can edit them directly.

```json
{
  "name": "Supplier A – 2col",
  "horizontal_lines": [120, 240, 360, 480],
  "vertical_lines": [30, 180, 330, 480],
  "fields": [
    {"name": "swatch", "type": "image", "click_count": 1},
    {"name": "material_id", "type": "text", "click_count": 1}
  ],
  "groups": [
    {"field_cells": {"swatch": [[0, 0]], "material_id": [[0, 1]]}},
    {"field_cells": {"swatch": [[0, 2]], "material_id": [[0, 3]]}}
  ],
  "omitted_pages": [2, 5],
  "omit_regions": [
    {"page_index": 1, "rect": [400, 600, 800, 900]}
  ]
}
```

- `horizontal_lines` and `vertical_lines` are y/x coordinates in **150-DPI rendered pixel space** (portable across machines using the same DPI constant)
- `fields` defines the ordered field recipe, including field names, types, and click counts
- `groups` maps each field name to one or more selected cells as `[row, col]` tuples
- `omitted_pages` (optional) lists zero-based page indices to skip entirely (e.g. cover pages, blank pages)
- `omit_regions` (optional) lists page-specific rectangular areas to ignore, as `{page_index, rect: [x0, y0, x1, y1]}` (useful for diagrams or empty sections)

---

## Upload Workflow & Database Integration

See [docs/MATERIAL_SWATCH_UPLOAD_GUIDE.md](docs/MATERIAL_SWATCH_UPLOAD_GUIDE.md) for detailed API documentation.

**High-level:**
1. **Lookup or create material** — `POST /api/v1/projects/{projectId}/materials` with composite ID
2. **Upload swatch image** — `POST /api/v1/images?entity_type=material&entity_id={materialUUID}` with WebP bytes
3. **Worker handles R2 + Neon** — stores at `users/{FIREBASE_UID}/projects/{PROJECT_ID}/materials/{materialId}/{imageId}.webp` and upserts the database record

Upload code remains in the repository for later reintegration, but the current UI focuses on Excel export.

---

## Dependencies

```
PyQt6>=6.6.0          # Desktop UI
PyMuPDF>=1.24.0       # PDF rendering & extraction
Pillow>=10.0.0        # Image compression to WebP
requests>=2.32.0      # HTTP to Cloudflare Worker API
psycopg2-binary>=2.9.0 # Neon PostgreSQL (read-only)
python-dotenv>=1.0.0  # Load .env credentials
```

## Development

**Run linter:**
```bash
.venv\Scripts\ruff check src/ tests/ scripts/
```

**Run tests:**
```bash
.venv\Scripts\pytest tests/ -v
```

**Type checking (strict mode):**
```bash
.venv\Scripts\mypy src/ tests/
```
