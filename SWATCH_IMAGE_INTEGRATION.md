# Swatch Image Integration Context

This document provides the complete context for integrating swatch images with Python uploader, covering compression, R2 storage, and database schema.

## 1. Client-Side Image Compression

**File:** `src/lib/images/compress.ts`

The codebase uses browser APIs for client-side image compression before R2 upload:

```typescript
const MAX_DIMENSION = 1920;
const WEBP_QUALITY = 0.85;

export async function compressImage(file: File): Promise<File> {
  // GIF may be animated — skip conversion to avoid losing frames
  if (file.type === 'image/gif') return file;
  if (typeof createImageBitmap !== 'function' || typeof OffscreenCanvas !== 'function') {
    return file;
  }

  const bitmap = await createImageBitmap(file);
  const { width, height } = bitmap;

  let targetWidth = width;
  let targetHeight = height;

  // Scale to max 1920px on longest dimension (aspect ratio preserved)
  if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
    if (width >= height) {
      targetWidth = MAX_DIMENSION;
      targetHeight = Math.round(height * (MAX_DIMENSION / width));
    } else {
      targetHeight = MAX_DIMENSION;
      targetWidth = Math.round(width * (MAX_DIMENSION / height));
    }
  }

  const canvas = new OffscreenCanvas(targetWidth, targetHeight);
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(bitmap, 0, 0, targetWidth, targetHeight);
  bitmap.close();

  // Convert to WebP at 85% quality
  const blob = await canvas.convertToBlob({ type: 'image/webp', quality: WEBP_QUALITY });

  const baseName = file.name.replace(/\.[^.]+$/, '');
  return new File([blob], `${baseName}.webp`, { type: 'image/webp' });
}
```

### Compression Summary for Python Client
- **Max dimension:** 1920px (longest side)
- **Aspect ratio:** Preserved during scaling
- **Format:** WebP
- **Quality:** 0.85 (85%)
- **GIF handling:** Not converted (preserves animation)
- **File extension:** Converted to `.webp`

---

## 2. R2 Upload Path Structure

**Bucket:** `ffe-images` (private, no public access)

### Swatch Image Path Format
```
users/{uid}/projects/{projectId}/proposal/items/{proposalItemId}/swatches/{imageId}.{ext}
```

### Example
```
users/user123abc/projects/proj-uuid-1234/proposal/items/item-uuid-5678/swatches/image-uuid-9012.webp
```

### Other Entity Path Formats (for reference)
```
users/{uid}/projects/{projectId}/project/{imageId}.{ext}                                    # Project
users/{uid}/projects/{projectId}/rooms/{roomId}/{imageId}.{ext}                            # Room
users/{uid}/projects/{projectId}/rooms/{roomId}/items/{itemId}/{imageId}.{ext}            # Item
users/{uid}/projects/{projectId}/rooms/{roomId}/items/{itemId}/plan/{imageId}.{ext}       # Item Plan
users/{uid}/projects/{projectId}/materials/{materialId}/{imageId}.{ext}                    # Material
users/{uid}/projects/{projectId}/proposal/items/{proposalItemId}/{imageId}.{ext}          # Proposal Item
users/{uid}/projects/{projectId}/proposal/items/{proposalItemId}/plan/{imageId}.{ext}     # Proposal Plan
users/{uid}/projects/{projectId}/proposal/items/{proposalItemId}/swatches/{imageId}.{ext} # SWATCH
users/{uid}/projects/{projectId}/plans/{planId}.{ext}                                      # Measured Plan
```

---

## 3. Database Schema

### Primary Table: `image_assets`

**File:** `db/migrations/0002_image_assets.sql`

```sql
CREATE TABLE IF NOT EXISTS image_assets (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_uid    text        NOT NULL,                    -- Firebase user ID
  project_id   uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  room_id      uuid        REFERENCES rooms(id) ON DELETE CASCADE,
  item_id      uuid        REFERENCES items(id) ON DELETE CASCADE,
  r2_key       text        NOT NULL UNIQUE,             -- Full R2 object path
  filename     text        NOT NULL,                    -- Original filename
  content_type text        NOT NULL,                    -- MIME type (e.g., image/webp)
  byte_size    integer     NOT NULL CHECK (byte_size > 0),  -- Compressed size
  alt_text     text        NOT NULL DEFAULT '',
  is_primary   boolean     NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT image_assets_entity_shape_chk CHECK (
    (room_id IS NULL AND item_id IS NULL)
    OR (room_id IS NOT NULL AND item_id IS NULL)
    OR (room_id IS NOT NULL AND item_id IS NOT NULL)
  )
);
```

### Insert Statement for Swatch Image

**For proposal swatches, use these values:**

```sql
INSERT INTO image_assets (
  id,
  owner_uid,
  project_id,
  room_id,
  item_id,
  r2_key,
  filename,
  content_type,
  byte_size,
  alt_text,
  is_primary,
  created_at,
  updated_at
) VALUES (
  gen_random_uuid(),                                                              -- Auto-generated UUID
  'firebase-user-id',                                                             -- Firebase UID from request
  'project-uuid',                                                                 -- Project ID
  NULL,                                                                           -- Always NULL for swatches
  NULL,                                                                           -- Always NULL for swatches
  'users/firebase-user-id/projects/project-uuid/proposal/items/item-uuid/swatches/image-uuid.webp',  -- R2 path
  'swatch_name.webp',                                                             -- Filename with extension
  'image/webp',                                                                   -- Content-type (or original)
  12345,                                                                          -- Byte size of compressed image
  'Color swatch description',                                                     -- Alt text (optional)
  true,                                                                           -- Mark as primary if first swatch
  now(),
  now()
);
```

### Alternative: Legacy Swatch Colors Table

**File:** `db/migrations/0004_material_swatches.sql`

If storing simple hex color swatches for materials (not image files):

```sql
CREATE TABLE IF NOT EXISTS material_swatches (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  material_id uuid        NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
  swatch_hex  text        NOT NULL,                    -- Hex color (e.g., #FF5733)
  sort_order  integer     NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT material_swatches_hex_chk CHECK (swatch_hex ~ '^#[0-9A-Fa-f]{6}$')
);
```

**Use this only for hex colors, not image files.**

---

## 4. Python Implementation Guide

### Compression (before upload)
```python
from PIL import Image
from io import BytesIO

def compress_swatch_image(image_path, max_dimension=1920, quality=85):
    """Compress swatch image matching client behavior."""
    img = Image.open(image_path)
    
    # Preserve aspect ratio, scale to max dimension
    img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    
    # Convert to WebP
    buffer = BytesIO()
    img.save(buffer, format='WEBP', quality=quality)
    buffer.seek(0)
    
    return buffer.getvalue()  # Returns compressed bytes
```

### R2 Upload
```python
import boto3
import uuid
from io import BytesIO

def upload_swatch_to_r2(
    image_bytes: bytes,
    firebase_uid: str,
    project_id: str,
    proposal_item_id: str,
    s3_client
) -> str:
    """Upload swatch image to R2 and return r2_key."""
    
    image_id = str(uuid.uuid4())
    r2_key = f"users/{firebase_uid}/projects/{project_id}/proposal/items/{proposal_item_id}/swatches/{image_id}.webp"
    
    s3_client.put_object(
        Bucket="ffe-images",
        Key=r2_key,
        Body=image_bytes,
        ContentType="image/webp"
    )
    
    return r2_key
```

### Database Insert
```python
import psycopg2
import uuid
from datetime import datetime

def insert_swatch_image(
    connection,
    firebase_uid: str,
    project_id: str,
    proposal_item_id: str,
    r2_key: str,
    filename: str,
    byte_size: int,
    alt_text: str = ""
) -> str:
    """Insert swatch image metadata into image_assets table."""
    
    image_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + 'Z'
    
    cursor = connection.cursor()
    cursor.execute("""
        INSERT INTO image_assets (
            id, owner_uid, project_id, room_id, item_id,
            r2_key, filename, content_type, byte_size, alt_text,
            is_primary, created_at, updated_at
        ) VALUES (
            %s, %s, %s, NULL, NULL,
            %s, %s, 'image/webp', %s, %s,
            true, %s, %s
        ) RETURNING id;
    """, (
        image_id,
        firebase_uid,
        project_id,
        r2_key,
        filename,
        byte_size,
        alt_text,
        now,
        now
    ))
    
    result = cursor.fetchone()
    connection.commit()
    
    return result[0]
```

---

## 5. Browser Download & Rendering

**Important:** The React app does NOT fetch images directly from public R2 URLs.

- All image access goes through the authenticated API endpoint
- Worker returns blob with `private, max-age=3600` cache headers
- Frontend fetches with authenticated client and renders object URLs

### Fetch Flow
1. `GET /api/v1/images/{imageId}/content`
2. Worker authenticates and streams from R2
3. Browser receives compressed WebP blob
4. Component renders with `URL.createObjectURL()`
5. URL revoked on component unmount

---

## 6. API Endpoints (Reference)

### Upload Swatch
```
POST /api/v1/images?entity_type=proposal_swatch&entity_id={proposalItemId}&alt_text=...
Content-Type: multipart/form-data

file: <compressed image bytes>
```

### List Swatches
```
GET /api/v1/images?entity_type=proposal_swatch&entity_id={proposalItemId}
```

### Fetch Swatch Content
```
GET /api/v1/images/{imageId}/content
```

### Delete Swatch
```
DELETE /api/v1/images/{imageId}
```

---

## 7. Key Constraints & Notes

1. **Max file size:** 5 MB (enforced by API)
2. **Allowed types:** JPEG, PNG, WebP, GIF
3. **Compression:** Convert to WebP at 85% quality before upload
4. **Scaling:** Max 1920px on longest dimension
5. **Database uniqueness:** `r2_key` is UNIQUE
6. **Scoping:** All images scoped to `owner_uid` (Firebase UID) for privacy
7. **GIF handling:** GIF animations are preserved (not converted)
8. **R2 bucket:** Always `private` — no public URLs
9. **Swatch specifics:** Always use `entity_type='proposal_swatch'` and set `room_id` and `item_id` to NULL

---

## 8. Troubleshooting Browser Viewing

- **Image won't load:** Check `owner_uid` matches Firebase token user
- **Wrong compression:** Verify client is using WebP at 0.85 quality
- **Missing in browser:** Ensure `image_assets` row was inserted with correct `r2_key`
- **CORS issues:** Bucket is private — only fetch via authenticated `/api/v1/images/` endpoints
- **Cache problems:** Worker returns 1-hour cache; clear or wait for expiry
