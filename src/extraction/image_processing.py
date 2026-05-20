from __future__ import annotations

import io

from PIL import Image


_MAX_DIMENSION = 1920
_WEBP_QUALITY = 85


def compress_image(image_bytes: bytes) -> bytes:
    """Compress raw image bytes to WebP, matching the client-side compression rules.

    - Max dimension: 1920 px (longest side, aspect ratio preserved)
    - Format: WebP at 85% quality
    - GIF: returned unchanged to preserve animation
    """
    # Detect GIF by magic bytes and skip conversion
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=_WEBP_QUALITY)
    return buf.getvalue()
