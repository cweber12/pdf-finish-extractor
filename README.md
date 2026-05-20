# PDF Finish Extractor

A desktop tool for importing material finish catalogs from PDF files into the FFE materials database. It renders the PDF, lets you define a reusable grid layout over the first page, extracts swatch images and material IDs from every page using that grid, and uploads them to Cloudflare R2 + Neon PostgreSQL.

---

## Features

- **PDF viewer** — open and navigate any PDF catalog inside the app
- **Grid editor** — draw horizontal and vertical lines over the first page to divide it into cells; tag each cell as `image`, `text`, or `ignored`
- **Proximity pairing** — set one direction (`right` / `below` / `left` / `above`) to automatically pair every image cell with its adjacent text cell (the material ID)
- **Named profiles** — save a grid layout under a name (e.g. "Supplier A – 2 column"); reload it instantly for future PDFs from the same supplier
- **Batch extraction** — the page-1 grid is applied automatically to every subsequent page
- **Preview panel** — review all extracted (thumbnail, ID) pairs before committing; duplicates are highlighted
- **Upsert upload** — compress swatches to WebP, upload to R2, upsert rows in `image_assets` via a single `INSERT … ON CONFLICT DO UPDATE`

---

## Tech Stack

| Layer | Library |
|---|---|
| UI | PyQt6 |
| PDF rendering + extraction | PyMuPDF (`fitz`) |
| Image compression | Pillow |
| R2 upload | boto3 (S3-compatible) |
| Database | psycopg2 → Neon PostgreSQL |
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
└── src/
    ├── ui/
    │   ├── main_window.py      # Top-level window & layout
    │   ├── pdf_viewer.py       # PDF canvas widget (PyMuPDF → QPixmap)
    │   ├── grid_editor.py      # Line marker drawing & cell tagging
    │   ├── preview_panel.py    # Extraction review (thumbnails + IDs)
    │   └── profile_manager.py  # Save / load / select named profiles
    ├── extraction/
    │   ├── grid.py             # Grid definition data model
    │   ├── extractor.py        # PyMuPDF extraction logic
    │   └── image_processing.py # WebP compression via Pillow
    └── upload/
        ├── r2_client.py        # Cloudflare R2 upload via boto3
        └── neon_client.py      # Neon upsert via psycopg2
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/your-org/pdf-finish-extractor.git
cd pdf-finish-extractor
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

`.env.example`:

```env
# Neon PostgreSQL
DATABASE_URL=postgresql://user:password@your-neon-host/dbname

# Cloudflare R2 (S3-compatible)
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=ffe-images

# FFE context — scopes all uploaded materials to this owner + project
FIREBASE_UID=your_firebase_uid
PROJECT_ID=your_project_uuid
```

### 3. Run

```bash
python main.py
```

---

## Usage

### Step 1 — Open a PDF

Use **File → Open** to load a catalog PDF. The first page renders in the viewer.

### Step 2 — Define the grid

1. Click **Add Horizontal Line** or **Add Vertical Line** and drag lines across the page to divide it into cells.
2. Click each cell to tag it: **Image**, **Text**, or **Ignored**.
3. Set the **pairing direction** (e.g. `text is to the right of image`) in the toolbar. This tells the extractor which text cell holds the ID for each image cell.

### Step 3 — Save a profile (optional but recommended)

Click **Save Profile**, give it a name (e.g. `Supplier A – 2col`). Next time you open a PDF from the same supplier, pick the profile from the dropdown and skip steps 1–3.

### Step 4 — Extract

Click **Extract All Pages**. The app applies the grid to every page and opens the **Preview Panel** showing all extracted (swatch thumbnail, material ID) pairs.

- Rows with a material ID already present in the database are **highlighted in yellow** — they will be upserted (overwritten).
- Deselect any row you want to skip.

### Step 5 — Upload

Click **Upload Selected**. The app:

1. Compresses each swatch to WebP (max 1920 px, 85% quality)
2. Uploads to R2 at `users/{uid}/projects/{projectId}/materials/{materialId}/{imageId}.webp`
3. Upserts a row in `image_assets` in Neon

A progress bar tracks the upload. A summary confirms how many were inserted vs updated.

---

## Grid Profile Format

Profiles are plain JSON stored in `profiles/`. You can edit them directly.

```json
{
  "name": "Supplier A – 2col",
  "horizontal_lines": [120, 240, 360, 480],
  "vertical_lines": [30, 180, 330, 480],
  "cells": [
    { "row": 0, "col": 0, "type": "image" },
    { "row": 0, "col": 1, "type": "text" },
    { "row": 0, "col": 2, "type": "image" },
    { "row": 0, "col": 3, "type": "text" }
  ],
  "pair_direction": "right"
}
```

`horizontal_lines` and `vertical_lines` are y/x coordinates in PDF points (72 pts = 1 inch). The `cells` array describes one representative row — the pattern repeats for all rows on every page.

---

## R2 Path & Database Schema

Images are stored at:

```
users/{FIREBASE_UID}/projects/{PROJECT_ID}/materials/{materialId}/{imageId}.webp
```

Where `materialId` is the text extracted from the PDF and `imageId` is a freshly generated UUID per image.

The `image_assets` row uses `room_id = NULL` and `item_id = NULL` (materials scope). Duplicate detection is keyed on `r2_key` (the full R2 path), which is `UNIQUE` in the schema.

---

## Dependencies

```
PyQt6
PyMuPDF
Pillow
boto3
psycopg2-binary
python-dotenv
```
