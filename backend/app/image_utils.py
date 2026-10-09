"""Validate and sanitise uploaded product photos. Everything happens in memory; nothing touches disk.

The output is always a freshly encoded RGB JPEG: EXIF orientation is applied to the
pixels, and no metadata (EXIF/GPS, ICC, XMP, comments) is carried over.
"""

from __future__ import annotations

import base64
import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.errors import AppError

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream", ""}
MAX_SIDE_PX = 1568  # Claude's recommended long-edge size; larger images are downscaled server-side anyway
MAX_PIXELS = 40_000_000  # refuse decompression bombs well before Pillow's own limit
JPEG_QUALITY = 85


@dataclass(frozen=True)
class PreparedImage:
    base64_data: str
    media_type: str
    width: int
    height: int


def prepare_image(data: bytes, content_type: str | None, max_bytes: int) -> PreparedImage:
    if not data:
        raise AppError(400, "empty_image", "The uploaded image is empty.")
    if len(data) > max_bytes:
        raise AppError(413, "image_too_large", f"Images must be at most {max_bytes // (1024 * 1024)} MB.")
    if (content_type or "").lower() not in ALLOWED_CONTENT_TYPES:
        raise AppError(415, "unsupported_image_type", "Only JPEG, PNG and WebP images are accepted.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            # Pass 1: identify and verify integrity (verify() leaves the image unusable).
            with Image.open(io.BytesIO(data)) as probe:
                fmt = probe.format
                if fmt not in ALLOWED_FORMATS:
                    raise AppError(415, "unsupported_image_type", "Only JPEG, PNG and WebP images are accepted.")
                if probe.width * probe.height > MAX_PIXELS:
                    raise AppError(413, "image_too_large", "Image dimensions are too large.")
                probe.verify()
            # Pass 2: decode for real.
            with Image.open(io.BytesIO(data)) as img:
                img.load()
                img = ImageOps.exif_transpose(img)
                img = _to_rgb(img)
                img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX), Image.Resampling.LANCZOS)
                out = io.BytesIO()
                # No exif=/icc_profile= arguments: the re-encoded file carries no metadata.
                img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                width, height = img.size
    except AppError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise AppError(400, "invalid_image", "The file is not a valid JPEG, PNG or WebP image.")
    except (OSError, SyntaxError, ValueError):
        # Truncated or corrupt files surface as OSError/SyntaxError from Pillow's decoders.
        raise AppError(400, "invalid_image", "The image file is corrupt or truncated.")

    return PreparedImage(
        base64_data=base64.standard_b64encode(out.getvalue()).decode("ascii"),
        media_type="image/jpeg",
        width=width,
        height=height,
    )


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")
