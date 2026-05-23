# PDF Finish Extractor

A desktop tool for importing material finish catalog data from PDFs into Excel. The user defines a grid layout over a PDF, groups related catalog cells into extracted rows, and exports the results.

## Language

### Extraction

**Grid**:
A set of horizontal lines, vertical lines, Groups, omitted pages, and omit regions that define how a PDF catalog is divided and which cells are extracted.
_Avoid_: Layout, template, schema

**Profile**:
A saved, named Grid stored as a JSON file in `profiles/`. Reused across extraction runs for catalogs that share the same layout.
_Avoid_: Template, config, preset

**Group**:
One extracted material record in a Grid. A Group contains one or more Fields whose cells are read together into a single spreadsheet row.
_Avoid_: Pair, link, mapping, connection

**Pair**:
An obsolete association between one image cell and one text cell. New Profiles use Groups and Fields instead.
_Avoid_: CellPair, link, mapping, connection

**Field**:
A named part of a Group, associated with one or more grid cells that form one extracted value. Each Field has a type, such as text or image.
_Avoid_: Column, attribute, slot

**Sparse Group**:
An extracted Group where one or more Fields are blank. Sparse Groups are valid as long as at least one Field has data.
_Avoid_: Invalid group, incomplete group

**Field area**:
The rectangular area formed from the outer bounds of one or more adjacent grid cells assigned to a Field. A Field area is extracted as one rectangular area, not as separate cells stitched together.
_Avoid_: Selection, crop zone, multi-cell stitch

**Adjacent cells**:
Grid cells that touch along an edge. Multi-cell Fields use adjacent cells so their Field area matches what the user visually selected.
_Avoid_: Nearby cells, loosely related cells

**Field recipe**:
The ordered set of Fields, their types, and their required click counts for each Group in a Grid.
_Avoid_: Schema, template, form

**Structural recipe edit**:
A change to the Field recipe that can alter how Group clicks are interpreted, such as reordering Fields or changing a Field type or click count.
_Avoid_: Minor edit, cosmetic edit

**ExtractedGroup**:
A resolved Group with concrete field values, produced by running the Extractor over a PDF page.
_Avoid_: Result, output, record

**OmitRegion**:
A page-specific rectangle within the Grid that is silently skipped during extraction. Groups whose cells intersect an OmitRegion on the same page are dropped.
_Avoid_: Ignore area, exclusion zone, skip region

**Material**:
A single finish product in the FFE database, identified by a composite ID (manufacturer + category + code). Upload maps extracted data to Materials, but Excel export does not require a designated Material field.
_Avoid_: Item, product, swatch (as a synonym for the database entity)

**Swatch**:
The cropped image representing a material's visual finish, extracted from a PDF image cell. Distinct from the Material entity it belongs to.
_Avoid_: Image, thumbnail, preview

### Viewer

**Viewport**:
The rectangular region of the rendered PDF page currently visible in the grid editor, expressed as a center point in 150-DPI pixel coordinates plus a zoom level. Changes as the user zooms or pans.
_Avoid_: View, window, visible area

**Zoom level**:
A scalar multiplier over fit-to-view scale. 1.0 shows the full page; values above 1.0 show a sub-region at higher detail. Cannot go below 1.0.
_Avoid_: Scale, magnification, factor

**Fit-to-view**:
The default zoom state (zoom level = 1.0) where the full PDF page is scaled to fill the available display area. Restored automatically on page navigation.
_Avoid_: Default zoom, zoom out, reset zoom

## Example dialogue

> **Dev**: "Should I save the viewport with the profile?"
> **Domain expert**: "No — the viewport is just a display state. Profiles only store the Grid."
>
> **Dev**: "What happens to OmitRegions when I navigate pages?"
> **Domain expert**: "They persist in the Grid. Each OmitRegion belongs to a specific page index, so navigating doesn't remove them — it just shows the regions for the current page."
>
> **Dev**: "Is a swatch the same as a material?"
> **Domain expert**: "No. A swatch is the image crop. The material is the database entity. One material has one swatch, but they're produced at different stages."
>
> **Dev**: "Is a Group the same as the old Pair?"
> **Domain expert**: "No. A Pair only connected one swatch cell to one text cell. A Group is one extracted material record and can contain any number of named Fields."
