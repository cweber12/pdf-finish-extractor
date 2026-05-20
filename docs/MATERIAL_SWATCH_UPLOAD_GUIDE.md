# Material Swatch Upload Guide

## Problem: 404 Error

Your Python program is hitting:
```
POST /api/v1/materials/{id}/swatch
```

**This endpoint does not exist.** The 404 is expected because there's no `/materials/{id}/swatch` route in the API.

---

## Correct Upload Workflow

### Step 1: Create or Lookup Material

First, create a material entry in the database (or lookup existing). This gives you a **UUID** that the image API requires.

**Endpoint:**
```
POST /api/v1/projects/{projectId}/materials
```

**Request Body:**
```json
{
  "name": "Material Name",
  "material_id": "80017/90009",           // Your composite ID
  "description": "Optional description",
  "swatch_hex": "#D9D4C8",                // Optional, default shown
  "manufacturer": "Manufacturer Name",     // Optional
  "source_url": "https://example.com"     // Optional
}
```

**Response:**
```json
{
  "material": {
    "id": "550e8400-e29b-41d4-a716-446655440000",  // ← SAVE THIS UUID
    "projectId": "project-uuid",
    "name": "Material Name",
    "materialId": "80017/90009",
    "description": "Optional description",
    "swatchHex": "#D9D4C8",
    "manufacturer": "Manufacturer Name",
    "sourceUrl": "https://example.com",
    "createdAt": "2026-05-19T12:00:00Z",
    "updatedAt": "2026-05-19T12:00:00Z"
  }
}
```

### Step 2: Upload Swatch Image

Now use the **images API** (not materials API) with the UUID from Step 1.

**Endpoint:**
```
POST /api/v1/images?entity_type=material&entity_id={materialUUID}&alt_text=...
```

**Where:**
- `{materialUUID}` = the `id` from Step 1 (e.g., `550e8400-e29b-41d4-a716-446655440000`)
- `entity_type` = always `"material"`
- `alt_text` = optional description (URL-encoded)

**Request Body (multipart/form-data):**
```
file: <compressed image bytes>
```

**Response:**
```json
{
  "image": {
    "id": "image-uuid",
    "entityType": "material",
    "ownerUid": "firebase-uid",
    "projectId": "project-uuid",
    "materialId": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "swatch.webp",
    "contentType": "image/webp",
    "byteSize": 12345,
    "altText": "Color swatch description",
    "isPrimary": true,
    "createdAt": "2026-05-19T12:00:00Z",
    "updatedAt": "2026-05-19T12:00:00Z"
  }
}
```

---

## Answer: Do You Need Separate ID Fields?

### Current Schema
```sql
CREATE TABLE materials (
  id           uuid        PRIMARY KEY,    -- System UUID (for API)
  project_id   uuid        NOT NULL,
  name         text        NOT NULL,
  material_id  text        NOT NULL,       -- Your custom ID (80017/90009)
  description  text        NOT NULL DEFAULT '',
  swatch_hex   text        NOT NULL DEFAULT '#D9D4C8',
  manufacturer text        NOT NULL DEFAULT '',
  source_url   text        NOT NULL DEFAULT '',
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT materials_swatch_hex_chk CHECK (swatch_hex ~ '^#[0-9A-Fa-f]{6}$')
);
```

### Do You Need Another ID Field?

**NO.** The current schema is correct:
- **`id`** (UUID) = system identifier used by all APIs and foreign keys
- **`material_id`** (text) = your composite ID (`80017/90009`) for business logic / lookups

### How to Lookup by Your Composite ID

If you want to find a material by your composite ID without knowing the UUID:

```sql
SELECT id FROM materials 
WHERE project_id = {projectId} 
  AND material_id = '80017/90009'
LIMIT 1;
```

Then use that `id` in your image upload.

---

## Step-by-Step Python Implementation

### 1. Create Material (if not exists)

```python
import requests
import json

def create_material(project_id, material_id_text, name, firebase_token):
    """Create material and return UUID."""
    url = f"https://ffe-api.ffe-builder.workers.dev/api/v1/projects/{project_id}/materials"
    headers = {
        "Authorization": f"Bearer {firebase_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": name or f"Material {material_id_text}",
        "material_id": material_id_text,  # "80017/90009"
        "description": "",
        "swatch_hex": "#D9D4C8",
        "manufacturer": "",
        "source_url": ""
    }
    
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    
    material_uuid = response.json()["material"]["id"]
    return material_uuid  # ← Use this for image upload
```

### 2. Upload Swatch Image

```python
def upload_swatch_image(project_id, material_uuid, image_path, firebase_token):
    """Upload swatch image for material."""
    from io import BytesIO
    from PIL import Image
    
    # Compress image (matching client behavior)
    img = Image.open(image_path)
    img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
    
    buffer = BytesIO()
    img.save(buffer, format='WEBP', quality=85)
    buffer.seek(0)
    
    # Upload via images API
    url = f"https://ffe-api.ffe-builder.workers.dev/api/v1/images?entity_type=material&entity_id={material_uuid}&alt_text=Swatch"
    headers = {
        "Authorization": f"Bearer {firebase_token}"
    }
    files = {
        "file": ("swatch.webp", buffer, "image/webp")
    }
    
    response = requests.post(url, files=files, headers=headers)
    response.raise_for_status()
    
    image_id = response.json()["image"]["id"]
    return image_id
```

### 3. Full Workflow

```python
def upload_material_swatch(project_id, material_id_text, image_path, firebase_token, name=None):
    """Complete workflow: create material and upload swatch."""
    try:
        # Step 1: Create material
        print(f"Creating material for {material_id_text}...")
        material_uuid = create_material(project_id, material_id_text, name, firebase_token)
        print(f"✓ Material created: {material_uuid}")
        
        # Step 2: Upload image
        print(f"Uploading swatch image...")
        image_id = upload_swatch_image(project_id, material_uuid, image_path, firebase_token)
        print(f"✓ Swatch uploaded: {image_id}")
        
        return {
            "material_uuid": material_uuid,
            "image_id": image_id,
            "status": "success"
        }
    except requests.exceptions.HTTPError as e:
        print(f"✗ Upload error: {e.response.status_code} {e.response.text}")
        return {"status": "error", "message": str(e)}
```

---

## Materials Table: Required Fields

**At minimum, only these are required:**
- `project_id` (UUID) — must reference an existing project
- `name` (text) — any non-empty string
- `material_id` (text) — your composite ID or empty string (default)

**All others have defaults:**
- `swatch_hex` → defaults to `#D9D4C8` (beige)
- `description` → defaults to empty string
- `manufacturer` → defaults to empty string
- `source_url` → defaults to empty string

**Example INSERT:**
```sql
INSERT INTO materials (project_id, name, material_id)
VALUES ('project-uuid-here', 'Material 80017/90009', '80017/90009')
RETURNING id;
```

---

## What Your Python Program Was Missing

1. ✗ **Wrong endpoint:** Used `/api/v1/materials/{id}/swatch` (doesn't exist)
2. ✓ **Should use:** `/api/v1/images?entity_type=material&entity_id={materialUUID}`
3. ✗ **Wrong ID type:** Used composite ID `80017/90009` directly in URL
4. ✓ **Should use:** UUID from material lookup/creation
5. ✗ **No material creation:** Images API requires existing material record
6. ✓ **Should do:** Create material first, then upload image

---

## Lookup Existing Material by Composite ID

If you want to check if a material already exists before creating:

```python
def get_material_by_composite_id(project_id, material_id_text, firebase_token):
    """Get material UUID by your composite ID."""
    url = f"https://ffe-api.ffe-builder.workers.dev/api/v1/projects/{project_id}/materials"
    headers = {
        "Authorization": f"Bearer {firebase_token}"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    materials = response.json()["materials"]
    for mat in materials:
        if mat["materialId"] == material_id_text:  # camelCase in response
            return mat["id"]
    
    return None  # Not found

# Usage
material_uuid = get_material_by_composite_id(project_id, "80017/90009", token)
if not material_uuid:
    print("Material not found, creating...")
    material_uuid = create_material(project_id, "80017/90009", None, token)
```

---

## Constraints & Limits

1. **Material name uniqueness:** Project-scoped unique on lowercase name
   ```sql
   UNIQUE (project_id, lower(name))
   ```
   - Same name different case → conflict
   - Same name in different project → OK

2. **Swatch color format:** Must be valid hex `#RRGGBB`
   ```sql
   CHECK (swatch_hex ~ '^#[0-9A-Fa-f]{6}$')
   ```

3. **Image file size:** Max 5 MB (enforced by API)

4. **Swatch image uniqueness:** One primary image per material
   ```sql
   UNIQUE (material_id) WHERE is_primary AND material_id IS NOT NULL
   ```

---

## Testing the Flow

```bash
# 1. Get your Firebase token
export FIREBASE_TOKEN="your-token-here"
export PROJECT_ID="your-project-uuid"

# 2. Create material
curl -X POST https://ffe-api.ffe-builder.workers.dev/api/v1/projects/$PROJECT_ID/materials \
  -H "Authorization: Bearer $FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Material",
    "material_id": "80017/90009"
  }'

# 3. Upload swatch (replace MATERIAL_UUID with response from step 2)
curl -X POST "https://ffe-api.ffe-builder.workers.dev/api/v1/images?entity_type=material&entity_id=MATERIAL_UUID&alt_text=Test" \
  -H "Authorization: Bearer $FIREBASE_TOKEN" \
  -F "file=@swatch.webp"
```
