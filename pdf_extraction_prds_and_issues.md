# PDF Catalog Extraction PRDs + Implementation Issues

**Audience:** coding agent / implementation agent  
**Project area:** PyQt6 PDF grid editor + PyMuPDF extraction pipeline  
**Primary goal:** preserve manual grid extraction while adding a separate image + adjacent text pattern extraction mode for catalog swatch PDFs.

---

## 1. Executive Summary

The current project has a working **manual grid extraction** model:

- The user defines row/column boundaries over a rendered PDF page.
- The user defines fields and groups cells into export rows.
- Grid edits are stored as page-forward layout segments.
- The extractor applies the saved grid/segments to each page and crops image/text fields.

That grid mode should remain intentionally manual. Do **not** turn grid mode into an auto-detection workflow. It is still valuable for catalogs where every page uses a uniform swatch layout.

The new feature should be a separate **Image + Adjacent Text Pattern Mode**:

- The user crops/selects a sample image region.
- The user chooses whether the related text is above, below, left, or right of the image.
- The app creates an adjustable text box aligned to that side.
- The user chooses how many text sections exist and whether they are segmented by row or column.
- The adjustable text box displays the requested number of adjustable cells.
- The saved pattern is applied to all pages by scanning embedded PDF images and matching only by similar size/aspect ratio, not by color/visual similarity.
- Users can review, reject, add, and manually correct detected image/text pairs before export.

This document is organized as PRDs and implementation issues that can be published directly into GitHub, Linear, Jira, or another issue tracker.

---

## 2. Current Implementation Review

### 2.1 Files reviewed

Current extraction/backend-ish files:

- `src/extraction/grid.py`
- `src/extraction/planner.py`
- `src/extraction/field_extractor.py`
- `src/extraction/extractor.py`
- `src/extraction/group_projection.py`
- `src/common/image_processing.py`

Current editor/UI files:

- `src/ui/editor/grid_editor.py`
- `src/ui/editor/grid_editor_controls.py`
- `src/ui/editor/grid_editor_fields.py`
- `src/ui/editor/grid_editor_geometry.py`
- `src/ui/editor/grid_editor_grouping.py`
- `src/ui/editor/grid_editor_hit_test.py`
- `src/ui/editor/grid_editor_interaction.py`
- `src/ui/editor/grid_editor_interaction_flow.py`
- `src/ui/editor/grid_editor_lifecycle.py`
- `src/ui/editor/grid_editor_line_edit.py`
- `src/ui/editor/grid_editor_modes.py`
- `src/ui/editor/grid_editor_omit.py`
- `src/ui/editor/grid_editor_overlay.py`
- `src/ui/editor/grid_editor_pages.py`
- `src/ui/editor/grid_editor_right_click.py`
- `src/ui/editor/grid_editor_segments.py`
- `src/ui/editor/grid_editor_widgets.py`
- `src/ui/editor/pdf_viewer.py`
- `src/ui/editor/auto_grouping.py`

### 2.2 Current strengths to preserve

#### Manual grid model

The project already has a clear grid data model:

- `FieldDefinition`
- `CellGroup`
- `OmitRegion`
- `GridSegment`
- `Grid`

The important feature is `GridSegment`: each segment has `start_page`, `horizontal_lines`, `vertical_lines`, and `groups`. This is the right concept for “current page and subsequent pages until the next manual adjustment.”

Preserve this behavior.

#### Segment application behavior

`grid_editor_segments.py` already contains the correct conceptual behavior:

- `segment_index_for_page()` finds the most recent segment whose `start_page <= page_index`.
- `record_segment_change()` inserts or replaces the segment starting at the current page.
- `layout_state_for_page()` loads the segment applicable to the current page.
- `adjacent_segment_start_page()` supports navigation between segment start pages.

This should become the official behavior of manual grid mode.

#### Grid editor interaction primitives

The editor has useful modular pieces:

- line placement
- line dragging
- group selection
- right-click removal
- omit-region drawing
- PDF coordinate conversion
- overlay painting
- PDF zoom/pan/rendering

Reuse these where possible, but avoid making `GridEditor` responsible for every future extraction mode. The new feature should not make `grid_editor.py` much larger.

#### Field extraction utility

`FieldExtractor` already knows how to crop images from rectangles and extract text from rectangles. That logic should be reused or generalized for pattern extraction.

### 2.3 Current issues / risks

#### Grid mode currently includes auto-grouping controls

`auto_grouping.py` and related buttons in `grid_editor_controls.py` attempt to generate proposals by matching image anchors and snapping grid lines. That conflicts with the desired product direction:

> Grid mode should intentionally remain manual/user-defined only, with no auto-detection.

Recommendation:

- Remove auto-grouping controls from normal grid mode.
- Either delete auto-grouping if unused, or move it behind an experimental/dev flag.
- Do not reuse auto-grouping as the new pattern scanner. It produces adjusted grid proposals; the new scanner should produce image/text pair detections.

#### Current extraction is grid-first

`Extractor` currently applies a saved `Grid` and optional `GridSegment` list. It calls `ExtractionPlanner.plan_page(page)`, then `FieldExtractor.extract_groups(...)`.

This is good for manual grid mode but should not be stretched to solve pattern detection. Add a separate extraction path for image/text patterns.

#### Current profile persistence may not fully represent segments

`Grid.to_dict()` serializes the base grid, fields, groups, omitted pages, and omit regions. `GridSegment.to_dict()` exists separately, but the project should verify that saved profiles persist and reload segments. If profiles only save `Grid` and not `segments`, users may lose page-forward layout adjustments.

#### Current coordinate systems need explicit documentation

The UI uses 150-DPI rendered pixel coordinates. PyMuPDF uses PDF points. The code converts between these systems in several places. The new pattern mode must clearly specify whether each stored rectangle is:

- 150-DPI UI pixels,
- PDF points, or
- relative percentages/offsets from an image rectangle.

Recommendation:

- Store user-authored overlay rectangles in 150-DPI UI pixel space for UI editing.
- Convert to PDF points for extraction.
- Store pattern text sections as relative offsets from the image rectangle so they can be applied to detected images across pages.

---

# PRD 1 — Preserve Manual Grid Extraction Mode

## Product Requirement

Manual Grid Mode remains a first-class extraction mode for catalogs with uniform swatch layouts. It must stay user-defined only. No automatic grid generation or auto-detection should be required or implied.

## User Story

As a user working with a catalog that has the same swatch table layout on every page, I want to manually define a grid once, adjust it when the layout changes, and have each grid definition apply to the current and following pages until I define another grid.

## Scope

### In scope

- Preserve row and column boundary tools.
- Preserve grouping by field recipe.
- Preserve page omission and page-specific omit regions.
- Preserve layout segments:
  - a segment begins on the current page when the user changes the grid/groups;
  - a segment applies from its `start_page` through the page before the next segment;
  - later manual edits create or update the segment for that page.
- Persist and reload grid segments with profiles.
- Rename or clarify UI labels to communicate “Manual Grid Mode.”

### Out of scope

- Auto-detecting grids.
- Auto-snapping grid lines from image anchors.
- Matching page layouts automatically.
- Pattern-based swatch scanning. That belongs to Pattern Mode.

## Functional Requirements

1. Users can open a PDF and enter Manual Grid Mode.
2. Users can add horizontal and vertical boundaries.
3. Users can drag existing boundaries.
4. Users can right-click a boundary to remove it.
5. When a grid boundary changes, existing groups for that segment are cleared if necessary.
6. Users can define extraction fields with names, types, and click counts.
7. Users can click cells in field order to create extraction groups.
8. Users can omit a whole page from extraction.
9. Users can draw page-specific omit regions.
10. When users adjust the grid on page `N`, that layout applies to page `N` and subsequent pages until another segment starts.
11. Users can navigate between layout segment start pages.
12. Exports use the segment active for each page.

## Acceptance Criteria

- Given a PDF with 10 pages and a grid created on page 1, all pages use that grid until another segment exists.
- Given a user changes grid lines on page 5, pages 1–4 continue using the original segment and pages 5–10 use the new segment.
- Given a user changes grid lines again on page 8, pages 5–7 use the page-5 segment and pages 8–10 use the page-8 segment.
- Given the user saves and reloads the profile, all segments are preserved.
- Given the user exports, extraction respects omitted pages and page-specific omit regions.
- No auto-grouping controls are visible in the standard manual grid toolbar.

---

# Issue 1.1 — Clarify Manual Grid Mode and Remove Auto-Grouping From Main Grid UI

## Problem

The current toolbar includes auto-group proposal controls. This makes grid mode look partially automatic, but the desired behavior is intentionally manual.

## Proposed Solution

- Rename the grid workflow in UI copy to **Manual Grid**.
- Remove these standard toolbar controls from grid mode:
  - run auto group
  - accept high-confidence auto proposals
  - commit auto proposals
  - accept current proposal
  - reject current proposal
  - auto status chips
- Optionally keep the underlying auto-grouping code temporarily behind a dev-only flag if needed for comparison.

## Files likely involved

- `src/ui/editor/grid_editor_controls.py`
- `src/ui/editor/grid_editor.py`
- `src/ui/editor/auto_grouping.py`
- tests for grid editor controls, if present

## Implementation Notes

- Delete or hide `_auto_group_btn`, `_auto_accept_btn`, `_auto_commit_btn`, `_auto_accept_page_btn`, `_auto_reject_page_btn`, `_auto_page_label`, and `_auto_summary_label` from normal UI.
- Remove `_update_auto_group_widgets()` calls if no longer needed.
- Remove imports from `auto_grouping.py` in `grid_editor.py` if auto grouping is fully removed.
- If keeping as experimental, isolate behind a config constant like `ENABLE_EXPERIMENTAL_AUTO_GROUPING = False`.

## Acceptance Criteria

- Manual grid toolbar contains only manual grid actions, navigation, fields, page omission, segment navigation, zoom, and clear.
- Opening a PDF does not show “Auto: none” or proposal counters.
- No user-facing tooltip suggests automatic grid snapping.
- Manual grid tests still pass.

---

# Issue 1.2 — Persist and Reload Grid Segments

## Problem

`GridSegment` has `to_dict()` / `from_dict()`, and `GridEditor.current_segments()` returns current segments, but the base `Grid` serialization does not include segments. Confirm whether profile persistence stores segments. If not, page-forward manual grid behavior may be session-only.

## Proposed Solution

Introduce a profile wrapper that stores both the base `Grid` and the list of `GridSegment` objects.

## Proposed Data Model

```python
@dataclass
class GridExtractionProfile:
    profile_type: Literal["manual_grid"] = "manual_grid"
    version: int = 2
    grid: Grid
    segments: list[GridSegment]
```

Serialized shape:

```json
{
  "profile_type": "manual_grid",
  "version": 2,
  "grid": {
    "horizontal_lines": [],
    "vertical_lines": [],
    "fields": [],
    "groups": [],
    "omitted_pages": [],
    "omit_regions": []
  },
  "segments": [
    {
      "start_page": 0,
      "horizontal_lines": [120, 240],
      "vertical_lines": [80, 180],
      "groups": []
    }
  ]
}
```

## Migration Requirements

- Existing profiles with only `Grid` data should load as:
  - `grid = existing_grid`
  - `segments = [GridSegment(start_page=0, horizontal_lines=grid.horizontal_lines, vertical_lines=grid.vertical_lines, groups=grid.groups)]`
- New saved profiles should include both `grid` and `segments`.

## Acceptance Criteria

- Segment list survives save/reload.
- Existing profiles still load.
- Extractor receives the saved segments when exporting.

---

# Issue 1.3 — Add Unit Tests for Segment Behavior

## Problem

Page-forward grid behavior is central to manual grid mode and should be locked by tests.

## Proposed Tests

Add tests around `grid_editor_segments.py`:

1. `segment_index_for_page()` returns the highest segment start page not greater than the page index.
2. `record_segment_change()` inserts a new segment if the current page is not already a segment start.
3. `record_segment_change()` replaces a segment if the current page is already a segment start.
4. `layout_state_for_page()` returns the correct layout for pages before, at, and after a segment boundary.
5. `adjacent_segment_start_page()` returns correct previous/next segment starts.

## Acceptance Criteria

- Tests pass without loading a PDF.
- Tests directly verify the page-forward contract.

---

# Issue 1.4 — Keep Grid Extraction Pipeline Stable

## Problem

The new pattern extraction feature should not destabilize the working manual grid extraction path.

## Proposed Solution

Keep the existing pipeline for manual grid mode:

```text
GridExtractionProfile
    ↓
ExtractionPlanner.plan_page()
    ↓
FieldExtractor.extract_groups()
    ↓
ExtractedGroup[]
```

## Files likely involved

- `src/extraction/extractor.py`
- `src/extraction/planner.py`
- `src/extraction/field_extractor.py`
- `src/extraction/grid.py`

## Acceptance Criteria

- Existing manual grid extraction behavior is unchanged.
- Pattern mode does not require modifications to `ExtractionPlanner` except possibly shared utility extraction helpers.
- Existing manual grid tests pass.

---

# PRD 2 — Extraction Mode Architecture

## Product Requirement

The app should support multiple extraction modes without making grid mode responsible for pattern scanning.

## User Story

As a user, I want to choose the extraction workflow that matches my catalog:

- Manual Grid Mode for uniform pages.
- Image + Adjacent Text Pattern Mode for swatches with labels in variable page layouts.

## Proposed Architecture

Introduce a top-level profile model that can represent different extraction strategies.

```python
ExtractionProfile = ManualGridProfile | ImageTextPatternProfile
```

## Proposed Data Models

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class ManualGridProfile:
    profile_type: Literal["manual_grid"]
    version: int
    grid: Grid
    segments: list[GridSegment]

@dataclass
class ImageTextPatternProfile:
    profile_type: Literal["image_text_pattern"]
    version: int
    pattern: "ImageTextPattern"
    omitted_pages: list[int]
    omit_regions: list[OmitRegion]
    detection_options: "PatternDetectionOptions"
```

Shared result model:

```python
@dataclass
class ExtractedRecord:
    page_index: int
    source_rect: tuple[float, float, float, float]
    values: dict[str, ExtractedFieldValue]
    status: Literal["auto", "accepted", "edited", "manual"]
```

## Functional Requirements

1. Profile loading detects `profile_type`.
2. UI routes the profile to the correct editor mode.
3. Export routes the profile to the correct extractor.
4. Both modes produce a common tabular/exportable row structure.
5. Both modes support omitted pages and omit regions.

## Acceptance Criteria

- Manual grid profiles load into Manual Grid Mode.
- Pattern profiles load into Pattern Mode.
- Export works from both modes.
- New mode architecture does not require a large conditional blob inside `GridEditor`.

---

# Issue 2.1 — Add Profile Type Routing

## Problem

The current profile appears grid-centric. Adding pattern mode without a wrapper will cause accidental coupling.

## Proposed Solution

Add profile routing at save/load and export time.

## Proposed Serialized Shape

```json
{
  "profile_type": "manual_grid",
  "version": 2,
  "manual_grid": {
    "grid": {},
    "segments": []
  }
}
```

```json
{
  "profile_type": "image_text_pattern",
  "version": 1,
  "image_text_pattern": {
    "pattern": {},
    "detection_options": {},
    "omitted_pages": [],
    "omit_regions": []
  }
}
```

## Implementation Notes

- Keep backward compatibility with existing grid-only profiles.
- Add `profile_type` only for new saves.
- Avoid storing pattern fields inside `Grid`.

## Acceptance Criteria

- Legacy grid profiles still open.
- New grid profiles save with explicit `profile_type`.
- Pattern profiles save/load independently.

---

# Issue 2.2 — Introduce a Mode Selector in the UI

## Problem

Users need to choose the right extraction workflow before editing.

## Proposed Solution

Add a workflow selector after opening a PDF or in the editor toolbar:

- **Manual Grid**
  - Best for uniform pages.
  - User defines rows/columns and groups cells.
- **Image + Text Pattern**
  - Best for swatches with labels in variable page layouts.
  - User selects one image and defines adjacent text regions.

## UI Notes

- This can be a segmented control, dropdown, or two-card selection screen.
- Do not auto-switch modes without user confirmation if unsaved work exists.
- Show a warning when switching modes:
  - “Switching modes will keep the PDF open but uses a different extraction profile.”

## Acceptance Criteria

- Users can clearly distinguish manual grid extraction from pattern extraction.
- Switching modes does not silently discard unsaved profiles.
- Each mode has its own toolbar actions.

---

# PRD 3 — Image + Adjacent Text Pattern Authoring

## Product Requirement

Users can define a reusable local image/text pattern by cropping a sample image and configuring the adjacent text layout.

## User Story

As a user extracting material swatches from a catalog, I want to select one swatch image, tell the app where the label text is, resize the text region, split it into sections, and then scan the whole PDF for all matching swatch-size images with labels.

## Core Workflow

1. User opens PDF.
2. User selects **Image + Text Pattern** mode.
3. User drags a crop rectangle around one swatch image.
4. User chooses text side:
   - above
   - below
   - left
   - right
5. App creates an adjacent text box aligned to the chosen side.
6. User chooses:
   - text section count
   - segmentation direction: row or column
   - optional field names
7. Text box displays that number of adjustable sections.
8. User drags the overall text box and/or internal section dividers.
9. User saves the pattern.
10. User runs detection across pages.
11. User reviews detections and corrections.
12. User exports.

## UI Requirements

### Pattern toolbar controls

Add a dedicated Pattern Mode toolbar. Suggested controls:

- Select Image Crop
- Text Side: Above / Below / Left / Right
- Text Sections: numeric spinner
- Segment Direction: Rows / Columns
- Field Names
- Match Tolerance
- Run Scan
- Review Detections
- Clear Pattern
- Export

### Text side behavior

If text side is `below`, create the text box under the image crop.

If text side is `above`, create the text box above the image crop.

If text side is `right`, create the text box to the right of the image crop.

If text side is `left`, create the text box to the left of the image crop.

The initial text box should align to the image crop edge:

- below/above: same left/right as image crop, adjustable height
- left/right: same top/bottom as image crop, adjustable width

### Text section segmentation behavior

If user defines 3 sections in a column under the image:

```text
[ image ]
[ text 1 ]
[ text 2 ]
[ text 3 ]
```

If user defines 2 sections in a row under the image:

```text
[ image ]
[ text 1 ][ text 2 ]
```

If text is on the right with 3 sections in a column:

```text
[ image ][ text 1 ]
        [ text 2 ]
        [ text 3 ]
```

### Handles

Pattern overlay should support:

- Drag image crop rectangle.
- Resize image crop rectangle.
- Drag text region.
- Resize text region.
- Drag section dividers.
- Reset text region from side/default.
- Delete pattern.

## Proposed Data Models

Create a new file:

`src/extraction/pattern.py`

```python
from dataclasses import dataclass, field
from typing import Literal

PatternSide = Literal["above", "below", "left", "right"]
TextSegmentation = Literal["rows", "columns"]

@dataclass(frozen=True)
class RectPx:
    """150-DPI rendered pixel-space rectangle."""
    x0: int
    y0: int
    x1: int
    y1: int

@dataclass(frozen=True)
class RelativeRect:
    """Rect stored relative to the detected image rect.

    Values are ratios of the sample image width/height:
    x0 = (rect.x0 - image.x0) / image.width
    y0 = (rect.y0 - image.y0) / image.height
    x1 = (rect.x1 - image.x0) / image.width
    y1 = (rect.y1 - image.y0) / image.height
    """
    x0: float
    y0: float
    x1: float
    y1: float

@dataclass(frozen=True)
class TextSectionDefinition:
    name: str
    index: int
    relative_rect: RelativeRect

@dataclass(frozen=True)
class ImageSampleDefinition:
    rect_px: RectPx
    width_px: int
    height_px: int
    aspect_ratio: float

@dataclass(frozen=True)
class ImageTextPattern:
    image_field_name: str = "swatch"
    sample: ImageSampleDefinition
    text_side: PatternSide
    segmentation: TextSegmentation
    text_sections: list[TextSectionDefinition]
```

Detection options:

```python
@dataclass(frozen=True)
class PatternDetectionOptions:
    size_tolerance_pct: float = 0.20
    aspect_ratio_tolerance_pct: float = 0.10
    min_image_width_px: int = 12
    min_image_height_px: int = 12
    max_page_area_pct: float = 0.10
    require_text: bool = True
    sort_order: Literal["reading_order"] = "reading_order"
```

Detection result:

```python
@dataclass
class PatternDetection:
    page_index: int
    image_rect_px: RectPx
    text_section_rects_px: dict[str, RectPx]
    extracted_text: dict[str, str] = field(default_factory=dict)
    image_bytes: bytes = b""
    status: Literal["pending", "accepted", "rejected", "edited", "manual"] = "pending"
    confidence: float = 1.0
    notes: list[str] = field(default_factory=list)
```

Manual corrections:

```python
@dataclass
class PatternCorrection:
    page_index: int
    original_image_rect_px: RectPx | None
    image_rect_px: RectPx
    text_section_rects_px: dict[str, RectPx]
    status: Literal["accepted", "rejected", "edited", "manual"]
```

## Acceptance Criteria

- User can draw a sample image crop.
- User can select text side.
- App creates a text box aligned to the chosen side.
- User can resize/move the text box.
- User can choose section count and segmentation.
- Text region shows the correct number of sections.
- User can resize individual sections.
- Pattern profile can be saved/reloaded.
- Pattern is stored as relative text offsets from the image crop.

---

# Issue 3.1 — Build Pattern Mode Editor State

## Problem

The current `GridEditor` state is grid-specific. Pattern mode needs different state without overloading grid concepts.

## Proposed Solution

Create a new editor state model.

Possible file:

`src/ui/editor/pattern_editor_state.py`

```python
@dataclass
class PatternEditorState:
    image_rect_px: RectPx | None = None
    text_side: PatternSide = "below"
    segmentation: TextSegmentation = "rows"
    section_count: int = 1
    text_region_rect_px: RectPx | None = None
    text_section_rects_px: list[RectPx] = field(default_factory=list)
    selected_handle: str | None = None
    selected_section_index: int | None = None
```

## Acceptance Criteria

- Pattern editor state can represent incomplete and complete patterns.
- Changing section count regenerates or preserves section rects in a predictable way.
- Changing text side prompts the user before repositioning an already customized text box.
- Unit tests cover section generation for above/below/left/right and rows/columns.

---

# Issue 3.2 — Add Pattern Overlay Drawing

## Problem

The current overlay draws grid lines, cell groups, omitted pages, and omit previews. Pattern mode needs image crop and adjacent text section overlays.

## Proposed Solution

Create a separate pattern overlay renderer rather than bloating `grid_editor_overlay.py`.

Possible files:

- `src/ui/editor/pattern_overlay.py`
- `src/ui/editor/pattern_editor.py`

Draw:

- image crop rectangle
- text region rectangle
- internal section dividers
- resize handles
- side indicator arrow or label
- pending/accepted/rejected detection overlays during review mode

## Overlay Color Proposal

- Image crop: accent border
- Text region: secondary border
- Text sections: light alternating fills
- Accepted detections: green-ish border
- Rejected detections: muted red/dashed border
- Edited/manual detections: amber border

## Acceptance Criteria

- Pattern overlay works at fit-to-view and zoomed states.
- Overlay uses the same display/original coordinate conversion as the existing viewer.
- Users can visually understand which rectangle is image and which is text.
- Section labels such as `text_1`, `text_2`, `text_3` are visible.

---

# Issue 3.3 — Add Pattern Interaction Handling

## Problem

Pattern mode needs drawing, dragging, resizing, and section divider interactions.

## Proposed Solution

Create interaction helpers similar to the current grid helper modules.

Possible files:

- `src/ui/editor/pattern_hit_test.py`
- `src/ui/editor/pattern_interaction.py`
- `src/ui/editor/pattern_geometry.py`

Required actions:

```python
PatternPressAction = Literal[
    "begin_image_crop",
    "begin_drag_image",
    "begin_resize_image",
    "begin_drag_text_region",
    "begin_resize_text_region",
    "begin_drag_section_divider",
    "begin_pan",
    "right_click",
    "none",
]
```

## Acceptance Criteria

- Dragging in “Select Image Crop” mode creates an image rectangle.
- Resizing the image rectangle updates sample size.
- Text region remains relative to image unless user manually drags it.
- Section dividers can be dragged without crossing each other.
- Minimum rectangle sizes prevent invalid patterns.

---

# Issue 3.4 — Add Text Section Configuration Dialog/Panel

## Problem

Users need a simple way to define how many adjacent text fields exist and how they are segmented.

## Proposed Solution

Add a small panel/dialog:

Fields:

- Text side: above/below/left/right
- Section count: integer 1–6 initially
- Segmentation: rows/columns
- Field names:
  - default: `text_1`, `text_2`, ...
  - user-editable
- Reset text box from image side

## Acceptance Criteria

- If section count changes from 1 to 3 and segmentation is rows, the text box is split into 3 horizontal stacked cells.
- If section count changes from 1 to 2 and segmentation is columns, the text box is split into 2 side-by-side cells.
- Field names persist into export columns.
- Invalid duplicate field names are rejected or automatically deduped.

---

# PRD 4 — Pattern Detection + Extraction Engine

## Product Requirement

Pattern Mode scans each PDF page for embedded image rectangles that match the sample image size/aspect ratio and extracts adjacent text using the saved relative text layout.

## User Story

As a user, I want the app to find all swatches that are shaped like my selected example, even if the page layout changes, and export the swatch image with its adjacent labels.

## Detection Strategy

Primary detection should use PyMuPDF, not OpenCV.

### Why

The user’s PDFs contain embedded images and selectable text. The most reliable primary approach is:

1. Use PyMuPDF to find embedded image rectangles.
2. Filter by size/aspect ratio.
3. Generate text rectangles from the saved relative pattern.
4. Extract text from those rectangles.
5. Extract/crop image bytes from image rectangles.

### Do not match by color or visual similarity

The sample image might be Beech, but matches may be Maple, Walnut, Metal, or other finishes. Match the component structure, not image content.

## Algorithm

```text
For each page:
    skip omitted pages
    collect embedded image rectangles using page.get_image_info(xrefs=True)
    convert image rects from PDF points to 150-DPI pixel space
    filter candidates by sample width/height/aspect ratio
    reject huge hero images and tiny icons
    for each candidate:
        create text section rects from RelativeRect values
        skip if any section intersects an omit region
        extract text from each section
        if require_text and all text sections are empty:
            reject or mark low-confidence
        crop/extract image bytes
        emit PatternDetection
sort detections by page, y, x
```

## Proposed Module

Create:

`src/extraction/pattern_extractor.py`

Primary class:

```python
class PatternExtractor:
    def __init__(
        self,
        pdf_path: str,
        profile: ImageTextPatternProfile,
        *,
        render_dpi: int = 150,
        png_compress_level: int = 1,
    ) -> None:
        ...

    def detect_all_pages(
        self,
        progress_callback: Callable[[ExtractionProgress], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[PatternDetection]:
        ...

    def extract_accepted(
        self,
        detections: list[PatternDetection],
    ) -> list[ExtractedRecord]:
        ...
```

## Matching Rules

Given sample dimensions:

```python
sample_w = profile.pattern.sample.width_px
sample_h = profile.pattern.sample.height_px
sample_ratio = sample_w / sample_h
```

A candidate matches when:

```python
abs(candidate_w - sample_w) <= sample_w * size_tolerance_pct
abs(candidate_h - sample_h) <= sample_h * size_tolerance_pct
abs(candidate_ratio - sample_ratio) <= sample_ratio * aspect_ratio_tolerance_pct
```

Also enforce:

- candidate width >= `min_image_width_px`
- candidate height >= `min_image_height_px`
- candidate area <= page area * `max_page_area_pct`

## Text Rect Generation

Each text section stores a `RelativeRect` based on the sample image rectangle.

Example conversion:

```python
def apply_relative_rect(image_rect: RectPx, rel: RelativeRect) -> RectPx:
    w = image_rect.x1 - image_rect.x0
    h = image_rect.y1 - image_rect.y0
    return RectPx(
        x0=round(image_rect.x0 + rel.x0 * w),
        y0=round(image_rect.y0 + rel.y0 * h),
        x1=round(image_rect.x0 + rel.x1 * w),
        y1=round(image_rect.y0 + rel.y1 * h),
    )
```

This allows “text below image” to be represented by relative `y` values greater than `1.0`.

Example:

```python
# Text below image, same width, starting 5% image-height below image bottom.
RelativeRect(x0=0.0, y0=1.05, x1=1.0, y1=1.30)
```

## Acceptance Criteria

- Pattern extractor finds matching embedded image rectangles across pages with different overall layouts.
- Pattern extractor does not require a grid.
- Pattern extractor ignores hero images by max area.
- Text sections are generated from relative offsets.
- Export rows include image + each text section.
- Extraction supports cancellation and progress callbacks similar to current `Extractor`.

---

# Issue 4.1 — Extract Embedded Image Rect Utilities

## Problem

`auto_grouping.py` already has image-rect detection helpers, but they are tied to auto-grid proposals. Pattern mode should not depend on auto-grouping.

## Proposed Solution

Create a shared utility module:

`src/extraction/pdf_image_locator.py`

Functions:

```python
def embedded_image_rects_pts(page: fitz.Page) -> list[fitz.Rect]:
    ...

def drawing_rects_pts(page: fitz.Page) -> list[fitz.Rect]:
    ...

def rect_pts_to_px(rect: fitz.Rect, dpi: int = 150) -> RectPx:
    ...

def rect_px_to_pts(rect: RectPx, dpi: int = 150) -> fitz.Rect:
    ...
```

## Acceptance Criteria

- Pattern extractor uses this module.
- Auto-grouping is not imported by pattern extraction.
- Unit tests can fake rectangles without opening a PDF where practical.

---

# Issue 4.2 — Build Size/Aspect Candidate Filter

## Problem

The detector must match swatch-like images by dimensions only, not visual content.

## Proposed Solution

Create:

`src/extraction/pattern_matching.py`

Functions:

```python
def image_matches_sample(
    candidate: RectPx,
    sample: ImageSampleDefinition,
    options: PatternDetectionOptions,
    page_size_px: tuple[int, int],
) -> bool:
    ...
```

## Acceptance Criteria

- Candidate exactly matching sample passes.
- Candidate within tolerance passes.
- Candidate outside width tolerance fails.
- Candidate outside height tolerance fails.
- Candidate outside aspect tolerance fails.
- Candidate exceeding page area threshold fails.
- Tiny icons fail.

---

# Issue 4.3 — Build Pattern Text Extraction

## Problem

Text sections need to be extracted from generated rectangles.

## Proposed Solution

Reuse the idea from `FieldExtractor._extract_cell_text`, but expose a small rectangle-based extraction utility.

Possible module:

`src/extraction/rect_extract.py`

```python
def extract_text_from_rect(
    page: fitz.Page,
    rect_pts: fitz.Rect,
    text_page: fitz.TextPage | None = None,
) -> str:
    return str(page.get_textbox(rect_pts, textpage=text_page)).strip()
```

Add a future-safe option to extract words and join by reading order if `get_textbox()` proves inconsistent.

## Acceptance Criteria

- Text extraction works for one section.
- Text extraction works for multiple row/column sections.
- Empty text is preserved as empty string.
- If `require_text=True`, candidates with no text are rejected or marked low confidence.

---

# Issue 4.4 — Build Pattern Image Cropping

## Problem

Pattern extractor needs to export image bytes for each detected image rectangle.

## Proposed Solution

Reuse the cropping behavior from `FieldExtractor`, but make it callable without `ResolvedGroup`.

Options:

1. Add public method to `FieldExtractor`:
   - `extract_image_rect(page, rect_pts) -> bytes`
2. Move rectangle crop code to shared utility:
   - `src/extraction/rect_extract.py`

Preferred:

```python
def crop_page_rect_to_png(
    page: fitz.Page,
    rect_pts: fitz.Rect,
    render_scale: float,
    page_image: Image.Image | None = None,
    png_compress_level: int = 1,
) -> bytes:
    ...
```

## Acceptance Criteria

- Pattern extraction can produce PNG bytes for each detected image.
- Manual grid extraction still works.
- No duplicated crop math across extractors.

---

# PRD 5 — Detection Review + Manual Corrections

## Product Requirement

Users can review detected image/text pairs, reject false positives, correct text boxes, and add missed pairs manually.

## User Story

As a user, I want to verify detections before export so the final table does not include hero images, icons, wrong text, or missed swatches.

## Review UI

### Required capabilities

- Show current page with detection overlays.
- Detection overlays show:
  - image rectangle
  - text section rectangles
  - status
  - row/index badge
- User can:
  - accept detection
  - reject detection
  - edit image/text rectangles
  - add a missed detection manually
  - reset edited detection from pattern
  - move to next/previous detection
  - filter by status

### Suggested statuses

```python
DetectionStatus = Literal[
    "pending",
    "accepted",
    "rejected",
    "edited",
    "manual"
]
```

### Suggested controls

- Accept
- Reject
- Accept All Visible
- Reject All Visible
- Add Pair
- Edit Boxes
- Reset Boxes
- Previous / Next Detection
- Show: Pending / Accepted / Rejected / All

## Acceptance Criteria

- User can reject a false positive and it will not export.
- User can edit a text section rectangle and the edited text is used for export.
- User can add a missed image/text pair manually.
- Corrections persist with the profile or extraction session.
- Review UI remains separate from manual grid grouping.

---

# Issue 5.1 — Add Pattern Detection Review State

## Problem

Detection results and user corrections need a state model independent from raw pattern profile.

## Proposed Data Model

```python
@dataclass
class PatternReviewState:
    detections: list[PatternDetection]
    current_detection_index: int = 0
    status_filter: Literal["pending", "accepted", "rejected", "all"] = "pending"
    corrections: dict[str, PatternCorrection] = field(default_factory=dict)
```

Detection key:

```python
def detection_key(d: PatternDetection) -> str:
    return f"{d.page_index}:{d.image_rect_px.x0}:{d.image_rect_px.y0}:{d.image_rect_px.x1}:{d.image_rect_px.y1}"
```

## Acceptance Criteria

- The review state can return visible detections by status.
- Corrections override original detection rectangles.
- Re-running scan warns before discarding corrections.

---

# Issue 5.2 — Add Manual Add Pair Tool

## Problem

Size/aspect matching may miss valid swatches. Users need a manual fallback.

## Proposed Solution

In Pattern Review mode:

1. Click **Add Pair**.
2. Draw image rectangle.
3. App generates text section rectangles using saved relative pattern.
4. User can adjust sections.
5. Detection is saved with status `manual`.

## Acceptance Criteria

- Manual pair exports like detected pairs.
- Manual pair includes image bytes and all text sections.
- Manual pair persists in review state/profile as a correction.

---

# Issue 5.3 — Persist Corrections

## Problem

Users should not lose review work when saving/reopening a project.

## Proposed Solution

Store corrections with the pattern profile or a project-specific extraction session.

Possible profile shape:

```json
{
  "profile_type": "image_text_pattern",
  "version": 1,
  "image_text_pattern": {
    "pattern": {},
    "detection_options": {},
    "omitted_pages": [],
    "omit_regions": [],
    "corrections": []
  }
}
```

## Acceptance Criteria

- Accepted/rejected/edited/manual statuses persist.
- Reopening the PDF/profile restores review state.
- Export respects persisted corrections.

---

# PRD 6 — Export Integration

## Product Requirement

Both manual grid extraction and pattern extraction produce a consistent exportable table.

## User Story

As a user, I want to export extracted swatch image/text pairs into a table where each detected image is one row and each configured text section is its own column.

## Export Output

For Pattern Mode with 3 text sections:

```text
page | image | text_1 | text_2 | text_3
```

For a material swatch catalog, field names might be:

```text
page | swatch | finish_name | finish_code | collection
```

## Functional Requirements

1. Export only accepted, edited, and manual detections.
2. Exclude rejected detections.
3. Export image bytes into the image column.
4. Export each text section as its own column.
5. Preserve page index and reading order.
6. Support the same downstream projection/export path as grid results where possible.

## Proposed Shared Result

```python
@dataclass
class ExtractedRecord:
    page_index: int
    values: dict[str, ExtractedFieldValue]
    source: Literal["manual_grid", "image_text_pattern"]
    source_rect_px: RectPx | None = None
    status: str = "accepted"
```

## Acceptance Criteria

- Pattern export rows are sorted by page, top-to-bottom, left-to-right.
- Multi-section text appears in separate columns.
- Empty text sections export as empty cells.
- Rejected detections do not export.
- Manual grid export continues working.

---

# Issue 6.1 — Unify Extracted Row Projection

## Problem

The existing projection helpers operate around `ExtractedGroup`. Pattern mode may produce records that are not grid cell groups.

## Proposed Solution

Either:

1. Convert pattern detections to `ExtractedGroup`, or
2. Introduce `ExtractedRecord` and adapt export code to accept both.

Preferred transitional approach:

- Pattern extractor emits `ExtractedGroup`-compatible objects for minimal export disruption.
- Add `source` metadata later if needed.

## Acceptance Criteria

- Existing export code works with manual grid output.
- Pattern output can be exported without major duplicated exporter logic.
- Column order follows pattern field definitions.

---

# Issue 6.2 — Add Export Preview for Pattern Mode

## Problem

Users need to verify text segmentation before generating files.

## Proposed Solution

Add a simple preview table:

- image thumbnail
- page number
- text fields
- status

## Acceptance Criteria

- Preview shows the same rows that will export.
- Rejecting/editing a detection updates preview.
- Preview supports the configured text section names.

---

# PRD 7 — UI Architecture Updates

## Product Requirement

The UI should remain maintainable as a second extraction workflow is added.

## Current Concern

`GridEditor` currently owns many responsibilities:

- PDF viewer
- grid state
- mode handling
- segment management
- omit regions
- auto-group proposal state
- toolbar
- overlay
- interactions

Adding Pattern Mode directly into `GridEditor` would make the file harder to maintain.

## Proposed UI Architecture

```text
PDFExtractionWorkspace
    ├── PDFViewer
    ├── ModeSelector
    ├── ManualGridEditor
    │   ├── ManualGridToolbar
    │   ├── ManualGridOverlay
    │   └── ManualGridState
    └── PatternEditor
        ├── PatternToolbar
        ├── PatternOverlay
        └── PatternReviewPanel
```

This can be implemented incrementally without a full rewrite:

1. Keep current `GridEditor` as Manual Grid editor.
2. Add separate `PatternEditor` using the same `PDFViewer` patterns.
3. Later extract shared PDF viewer container if needed.

## Acceptance Criteria

- Pattern Mode does not add large amounts of pattern-specific code to `GridEditor`.
- Manual grid files remain focused on grid behavior.
- Pattern files are separately testable.

---

# Issue 7.1 — Create PatternEditor Using PDFViewer

## Problem

Pattern mode needs access to the same page rendering, zoom, pan, and coordinate mapping as grid mode.

## Proposed Solution

Create `PatternEditor` that owns a `PDFViewer` or receives a shared viewer from a parent workspace.

Initial simpler approach:

- `PatternEditor` owns its own `PDFViewer`, similar to `GridEditor`.
- Later refactor shared workspace if duplication becomes painful.

## Required Public API

```python
class PatternEditor(QWidget):
    open_requested = pyqtSignal()

    def load_pdf(self, path: str) -> None: ...
    def current_profile(self) -> ImageTextPatternProfile | None: ...
    def apply_profile(self, profile: ImageTextPatternProfile) -> None: ...
    def current_page_index(self) -> int: ...
```

## Acceptance Criteria

- PatternEditor can open and display a PDF.
- PatternEditor can draw overlays using 150-DPI coordinates.
- PatternEditor can save/load a pattern profile.

---

# Issue 7.2 — Add Pattern Toolbar

## Problem

Pattern authoring has different tools than grid authoring.

## Proposed Solution

Create:

`src/ui/editor/pattern_editor_controls.py`

Controls:

- Crop Image
- Text Side dropdown
- Sections spinner
- Rows/Columns toggle
- Field Names
- Match Tolerance
- Run Scan
- Review
- Clear
- Export

## Acceptance Criteria

- Pattern controls are visible only in Pattern Mode.
- Manual grid controls are visible only in Manual Grid Mode.
- Tooltips explain what each control does in plain language.

---

# Issue 7.3 — Shared Omit Page / Omit Region Behavior

## Problem

Both modes need page omission and omit regions, but omit-region behavior is currently grid-editor-owned.

## Proposed Solution

Move omit state helpers to shared modules:

- keep `OmitRegion` in extraction data model
- keep geometry in reusable functions
- optionally create `omit_overlay.py` rendering helpers

Pattern Mode should support:

- omit current page
- omit all pages
- draw omit region
- omit regions respected by detection/extraction

## Acceptance Criteria

- Pattern detection skips omitted pages.
- Pattern detection skips candidates whose image or text sections intersect omit regions.
- Omit regions render correctly in Pattern Mode.

---

# PRD 8 — Testing and Quality Plan

## Product Requirement

The implementation should have enough tests to protect both workflows.

## Test Areas

### Manual grid tests

- grid normalization
- segment behavior
- planner applies correct segment by page
- omitted pages/regions
- field extraction still works

### Pattern geometry tests

- relative rect conversion
- section generation for all text sides
- rows vs columns segmentation
- divider movement bounds
- rectangle normalization

### Pattern detection tests

- matching by width/height/aspect ratio
- rejecting hero images
- rejecting tiny icons
- applying text rect offsets
- sorting detections by reading order
- require text behavior

### Pattern extraction tests

- extract text from generated rectangles
- crop image rectangles
- export accepted detections only
- corrections override generated rectangles

### UI logic tests

- toolbar mode separation
- no auto-group controls in manual grid mode
- pattern editor state transitions
- field name validation

## Acceptance Criteria

- New business logic is unit tested without requiring GUI where possible.
- GUI-specific behavior is isolated behind small adapter methods.
- Existing tests pass.

---

# Issue 8.1 — Add Pattern Geometry Unit Tests

## Proposed Test Cases

1. `RelativeRect` below image converts correctly.
2. `RelativeRect` above image converts correctly.
3. `RelativeRect` left/right image converts correctly.
4. 3 row sections produce 3 stacked rectangles.
5. 2 column sections produce 2 side-by-side rectangles.
6. Section rects do not overlap incorrectly.
7. Invalid section count is clamped/rejected.

## Acceptance Criteria

- Tests pass independently of PyQt.
- Tests use simple rectangles and deterministic expected output.

---

# Issue 8.2 — Add Pattern Matching Unit Tests

## Proposed Test Cases

1. exact size match passes.
2. within tolerance passes.
3. outside width tolerance fails.
4. outside height tolerance fails.
5. outside aspect tolerance fails.
6. huge page hero image fails.
7. tiny icon fails.

## Acceptance Criteria

- Matching code has no PyQt dependency.
- Tests clearly document expected tolerance behavior.

---

# Issue 8.3 — Add Integration Test With Synthetic PDF

## Problem

Pattern extraction should be validated against a simple generated PDF.

## Proposed Solution

Create a small test PDF with:

- multiple embedded square images
- text underneath each image
- one large hero image
- one icon
- one omitted region

Use PyMuPDF to generate or load test assets.

## Acceptance Criteria

- Extractor returns only the intended swatch image/text pairs.
- Hero image is ignored.
- Icon is ignored.
- Omitted candidate is skipped.
- Text fields match expected values.

---

# Recommended Implementation Order

## Phase 1 — Stabilize Manual Grid Mode

1. Remove/hide auto-grouping from main manual grid UI.
2. Confirm and fix segment persistence.
3. Add segment tests.
4. Verify existing grid export.

## Phase 2 — Add Profile Architecture

1. Add `profile_type` wrapper.
2. Add backward-compatible legacy grid loading.
3. Add mode selector.
4. Route export by mode.

## Phase 3 — Add Pattern Data + Geometry

1. Add pattern data models.
2. Add relative rect conversion.
3. Add text section generation.
4. Add unit tests.

## Phase 4 — Add Pattern Authoring UI

1. Add PatternEditor shell.
2. Add PatternToolbar.
3. Add PatternOverlay.
4. Add interactions for image crop, text region, and section dividers.
5. Add save/load for pattern profile.

## Phase 5 — Add Pattern Detection

1. Add embedded image locator utilities.
2. Add size/aspect matching.
3. Add pattern detector.
4. Add text/image extraction.
5. Add progress/cancel support.

## Phase 6 — Add Review + Corrections

1. Add detection review state.
2. Add detection overlay statuses.
3. Add accept/reject/edit/manual add.
4. Persist corrections.

## Phase 7 — Export + QA

1. Convert detections to export rows.
2. Add export preview.
3. Add integration tests.
4. Run lint/typecheck/tests/build.

---

# Agent Guidance

## Do

- Keep Manual Grid Mode manual only.
- Preserve `GridSegment` page-forward behavior.
- Add Pattern Mode as a separate workflow.
- Use PyMuPDF embedded image rectangles as the primary detector.
- Match candidate images by size/aspect ratio only.
- Store text regions as relative offsets from the image rectangle.
- Reuse existing crop/text extraction logic where clean.
- Keep UI logic modular.
- Write tests for business logic.

## Do Not

- Do not make grid mode auto-detect swatches.
- Do not use visual/color similarity for pattern matching.
- Do not make OpenCV a primary requirement for embedded-image PDFs.
- Do not put pattern detection state into `Grid` or `CellGroup`.
- Do not make `GridEditor` absorb all Pattern Mode behavior.
- Do not remove manual grid mode.
- Do not break legacy grid profile loading.

---

# Suggested Issue Titles

1. `PRD: Preserve manual grid extraction mode`
2. `Issue: Remove auto-grouping controls from manual grid toolbar`
3. `Issue: Persist and reload grid layout segments`
4. `Issue: Add tests for page-forward grid segment behavior`
5. `PRD: Add extraction mode architecture`
6. `Issue: Add profile_type wrapper for manual grid and pattern profiles`
7. `Issue: Add extraction mode selector UI`
8. `PRD: Add image + adjacent text pattern authoring`
9. `Issue: Add ImageTextPattern data models`
10. `Issue: Add PatternEditor state and toolbar`
11. `Issue: Add PatternOverlay drawing for image/text boxes`
12. `Issue: Add pattern crop and text-section interactions`
13. `PRD: Add pattern detection and extraction engine`
14. `Issue: Add PyMuPDF embedded image locator utilities`
15. `Issue: Add size/aspect-ratio image candidate matcher`
16. `Issue: Add text-section extraction from relative rectangles`
17. `Issue: Add image crop extraction utility for arbitrary rectangles`
18. `PRD: Add detection review and manual corrections`
19. `Issue: Add pattern detection review state`
20. `Issue: Add manual add-pair workflow`
21. `Issue: Persist pattern corrections`
22. `PRD: Add export integration for pattern detections`
23. `Issue: Convert pattern detections to export rows`
24. `Issue: Add pattern export preview`
25. `PRD: Add testing and QA coverage for both extraction modes`

---

# Definition of Done

This project update is complete when:

- Manual Grid Mode still works as a user-defined grid extractor.
- Grid edits on a page apply to that page and following pages until the next manual grid segment.
- Auto-grouping is not presented as part of standard Manual Grid Mode.
- Users can create an Image + Adjacent Text Pattern from one cropped image sample.
- Users can configure text side, section count, segmentation direction, and field names.
- Pattern Mode finds embedded images across pages using size/aspect ratio matching.
- Pattern Mode extracts image + adjacent text sections into exportable rows.
- Users can review, reject, edit, and manually add image/text pairs.
- Both modes export clean tables.
- Profile save/load supports both modes.
- Existing manual grid tests pass.
- New pattern geometry, matching, extraction, and correction tests are added.
