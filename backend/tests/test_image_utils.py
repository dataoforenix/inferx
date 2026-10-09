from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from app.errors import AppError
from app.image_utils import MAX_SIDE_PX, prepare_image

MB = 1024 * 1024


def encode(img: Image.Image, fmt: str, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kw)
    return buf.getvalue()


def decode(prepared) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(prepared.base64_data)))


@pytest.mark.parametrize(("fmt", "ctype"), [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")])
def test_accepts_allowed_formats_and_outputs_jpeg(fmt, ctype):
    data = encode(Image.new("RGB", (64, 48), (200, 10, 10)), fmt)
    out = prepare_image(data, ctype, 8 * MB)
    img = decode(out)
    assert out.media_type == "image/jpeg" and img.format == "JPEG" and img.mode == "RGB"
    assert (out.width, out.height) == (64, 48)


def test_transparent_png_converted_to_rgb_on_white():
    data = encode(Image.new("RGBA", (10, 10), (0, 0, 0, 0)), "PNG")
    img = decode(prepare_image(data, "image/png", 8 * MB))
    assert img.mode == "RGB"
    assert img.getpixel((5, 5))[0] > 240  # fully transparent -> white


def test_exif_orientation_applied_and_metadata_stripped():
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° when displayed
    exif[0x010F] = "SecretCam"  # camera make
    data = encode(Image.new("RGB", (200, 100)), "JPEG", exif=exif)
    out = prepare_image(data, "image/jpeg", 8 * MB)
    img = decode(out)
    assert (img.width, img.height) == (100, 200)
    assert len(img.getexif()) == 0
    assert b"SecretCam" not in base64.b64decode(out.base64_data)


def test_large_images_are_downscaled():
    data = encode(Image.new("RGB", (4000, 3000)), "JPEG")
    out = prepare_image(data, "image/jpeg", 8 * MB)
    assert max(out.width, out.height) == MAX_SIDE_PX
    assert out.width / out.height == pytest.approx(4 / 3, rel=0.01)


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_rejects_other_formats(fmt):
    data = encode(Image.new("RGB", (10, 10)), fmt)
    with pytest.raises(AppError) as exc:
        prepare_image(data, "application/octet-stream", 8 * MB)
    assert exc.value.status_code == 415


def test_rejects_disallowed_content_type():
    data = encode(Image.new("RGB", (10, 10)), "PNG")
    with pytest.raises(AppError) as exc:
        prepare_image(data, "text/html", 8 * MB)
    assert exc.value.status_code == 415


def test_png_disguised_as_jpeg_is_sniffed_not_trusted():
    data = encode(Image.new("RGB", (10, 10)), "PNG")
    assert prepare_image(data, "image/jpeg", 8 * MB).media_type == "image/jpeg"


@pytest.mark.parametrize("data", [b"not an image at all", b"\x89PNG\r\n\x1a\n" + b"\x00" * 50])
def test_rejects_garbage(data):
    with pytest.raises(AppError) as exc:
        prepare_image(data, "image/png", 8 * MB)
    assert exc.value.status_code == 400


def test_rejects_truncated_image():
    data = encode(Image.effect_noise((400, 400), 50).convert("RGB"), "JPEG")
    with pytest.raises(AppError) as exc:
        prepare_image(data[: len(data) // 2], "image/jpeg", 8 * MB)
    assert exc.value.status_code == 400


def test_rejects_empty_and_oversized():
    with pytest.raises(AppError) as exc:
        prepare_image(b"", "image/png", 8 * MB)
    assert exc.value.status_code == 400
    data = encode(Image.new("RGB", (10, 10)), "PNG")
    with pytest.raises(AppError) as exc:
        prepare_image(data, "image/png", len(data) - 1)
    assert exc.value.status_code == 413


def test_rejects_decompression_bomb_dimensions():
    data = encode(Image.new("1", (8000, 8000)), "PNG")  # tiny file, 64M pixels
    assert len(data) < 8 * MB
    with pytest.raises(AppError) as exc:
        prepare_image(data, "image/png", 8 * MB)
    assert exc.value.status_code == 413
