from __future__ import annotations

import io

from PIL import Image, ImageOps

_MAX_DIMENSION = 1920
_WEBP_QUALITY = 85


def compress_image(image_bytes: bytes) -> bytes:
    """Compress image bytes to WebP before upload.

    - Max dimension: 1920 px on the longest side
    - Format: WebP at 85% quality
    - GIF: returned unchanged to preserve animation
    - Existing WebP under the max size is returned unchanged to avoid needless
      recompression work
    """
    if not image_bytes:
        return image_bytes

    # Preserve animated GIFs.
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return image_bytes

    with Image.open(io.BytesIO(image_bytes)) as source:
        source_format = (source.format or "").upper()
        image = ImageOps.exif_transpose(source)

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        elif image.mode == "RGBA":
            # WebP supports alpha, but swatch crops are expected to be opaque.
            # Compositing avoids unexpected black backgrounds from viewers that
            # do not handle alpha consistently.
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.getchannel("A"))
            image = background
        else:
            image = image.copy()

    needs_resize = max(image.size) > _MAX_DIMENSION
    already_webp = image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP"

    if already_webp and not needs_resize:
        image.close()
        return image_bytes

    if needs_resize:
        image.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    image.save(
        buf,
        format="WEBP",
        quality=_WEBP_QUALITY,
        method=4,
        optimize=False,
    )
    image.close()
    return buf.getvalue()
