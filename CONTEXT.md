# PDF Finish Extractor

A desktop tool for importing material finish catalogs from PDFs into the FFE materials database. The user defines a grid layout over a PDF, pairs swatch images with material IDs, and uploads the results.

## Language

### Extraction

**Grid**:
A set of horizontal lines, vertical lines, cell pairs, omitted pages, and omit regions that define how a PDF catalog is divided and which cells are extracted.
_Avoid_: Layout, template, schema

**Profile**:
A saved, named Grid stored as a JSON file in `profiles/`. Reused across extraction runs for catalogs that share the same layout.
_Avoid_: Template, config, preset

**Pair / CellPair**:
An association between one image cell and one text cell in the same Grid. Indicates that the swatch image in the image cell belongs to the material ID in the text cell.
_Avoid_: Link, mapping, connection

**ExtractedPair**:
A resolved Pair with concrete image bytes and material ID text, produced by running the Extractor over a PDF page.
_Avoid_: Result, output, record

**OmitRegion**:
A page-specific rectangle within the Grid that is silently skipped during extraction. Pairs whose cells intersect an OmitRegion on the same page are dropped.
_Avoid_: Ignore area, exclusion zone, skip region

**Material**:
A single finish product in the FFE database, identified by a composite ID (manufacturer + category + code). Each extracted pair maps to one Material.
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
