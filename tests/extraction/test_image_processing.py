import io

from src.extraction.image_processing import compress_image


def _make_png_bytes(width: int = 100, height: int = 100) -> bytes:
    from PIL import Image

    img = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_gif_bytes() -> bytes:
    from PIL import Image

    img = Image.new("P", (10, 10))
    buf = io.BytesIO()
    img.save(buf, format="GIF")
    return buf.getvalue()


class TestCompressImage:
    def test_output_is_webp(self):
        result = compress_image(_make_png_bytes())
        # WebP magic bytes: RIFF????WEBP
        assert result[:4] == b"RIFF"
        assert result[8:12] == b"WEBP"

    def test_small_image_not_upscaled(self):
        from PIL import Image

        result = compress_image(_make_png_bytes(100, 100))
        img = Image.open(io.BytesIO(result))
        assert img.width <= 100
        assert img.height <= 100

    def test_large_image_scaled_down(self):
        from PIL import Image

        result = compress_image(_make_png_bytes(3000, 2000))
        img = Image.open(io.BytesIO(result))
        assert max(img.width, img.height) <= 1920

    def test_aspect_ratio_preserved(self):
        from PIL import Image

        result = compress_image(_make_png_bytes(3000, 1500))
        img = Image.open(io.BytesIO(result))
        # Original ratio 2:1 — should be preserved within 1px rounding
        assert abs(img.width / img.height - 2.0) < 0.02

    def test_gif_returned_unchanged(self):
        gif = _make_gif_bytes()
        result = compress_image(gif)
        assert result == gif
