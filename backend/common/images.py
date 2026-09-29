"""Decode uploaded image files into RGB PIL images ready for CLIP.

The upload form accepts JPEG, PNG, WebP, GIF, BMP, TIFF, HEIC/HEIF and DNG.
Pillow handles most of these; HEIC (the iPhone default) needs pillow-heif, and
DNG (camera RAW) needs rawpy, which is optional.

Two details matter for search quality:
- Phone photos are usually stored sideways with an EXIF "orientation" tag
  telling viewers how to rotate them. CLIP never sees that tag, so we apply
  the rotation here; otherwise a portrait photo is embedded lying on its side.
- Transparent pixels are composited onto white. A plain RGB conversion would
  turn them black, which changes what CLIP sees.
"""

from __future__ import annotations

import io
from pathlib import PurePath

from PIL import Image, ImageOps, UnidentifiedImageError
import pillow_heif

pillow_heif.register_heif_opener()

MAX_BYTES = 50 * 1024 * 1024
# CLIP resizes everything to 224x224, so decoding a 12-megapixel JPEG at full
# size is wasted work. JPEG can decode directly at 1/2, 1/4 or 1/8 scale;
# draft() picks the smallest of those that is still at least this size.
JPEG_DRAFT_SIZE = (448, 448)
RAW_EXTENSIONS = {".dng"}


class ImageDecodeError(ValueError):
    """The file could not be turned into an image. The message is safe to show to users."""


def decode_image(data: bytes, filename: str | None = None) -> Image.Image:
    """Decode file bytes into an upright RGB image.

    ``filename`` is only used to recognise RAW files by extension, because a
    DNG is a TIFF container and Pillow would otherwise open its small
    embedded preview instead of the photo.
    """
    if not data:
        raise ImageDecodeError("the file is empty")
    if len(data) > MAX_BYTES:
        raise ImageDecodeError(f"the file is larger than {MAX_BYTES // (1024 * 1024)} MB")

    if filename and PurePath(filename).suffix.lower() in RAW_EXTENSIONS:
        return _decode_raw(data)

    try:
        img = Image.open(io.BytesIO(data))
        if img.format == "JPEG":
            img.draft("RGB", JPEG_DRAFT_SIZE)
        img.load()  # decodes the first frame only for animated GIF/WebP
    except Image.DecompressionBombError as exc:
        raise ImageDecodeError("the image has too many pixels") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ImageDecodeError("the file is not a supported image") from exc

    img = _apply_exif_orientation(img)
    return _to_rgb(img)


def _apply_exif_orientation(img: Image.Image) -> Image.Image:
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        # Corrupt EXIF data should not make an otherwise valid photo unusable.
        return img


def _to_rgb(img: Image.Image) -> Image.Image:
    try:
        has_alpha = img.mode in ("RGBA", "LA", "PA") or (
            img.mode == "P" and "transparency" in img.info
        )
        if has_alpha:
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return img.convert("RGB")
    except (OSError, ValueError) as exc:
        raise ImageDecodeError(f"unsupported image mode {img.mode!r}") from exc


def _decode_raw(data: bytes) -> Image.Image:
    try:
        import rawpy
    except ImportError as exc:
        raise ImageDecodeError(
            "DNG files need the optional 'rawpy' dependency (pip install '.[raw]')"
        ) from exc
    try:
        with rawpy.imread(io.BytesIO(data)) as raw:
            # half_size is plenty for a 224px model and four times faster.
            # LibRaw applies the camera's orientation itself.
            rgb = raw.postprocess(half_size=True, use_camera_wb=True, output_bps=8)
    except (rawpy.LibRawError, OSError, ValueError) as exc:
        raise ImageDecodeError("the DNG file could not be decoded") from exc
    return Image.fromarray(rgb)
