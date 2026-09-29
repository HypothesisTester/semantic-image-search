import io
import sys

import pytest
from PIL import Image

from common import images
from common.images import ImageDecodeError, decode_image


def encode(img: Image.Image, fmt: str, **kwargs) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def test_jpeg_exif_orientation_is_applied():
    # A 40x20 landscape image stored with orientation 6 ("rotate 90 degrees
    # clockwise to display") should come out as 20x40 portrait.
    img = Image.new("RGB", (40, 20), "red")
    exif = img.getexif()
    exif[0x0112] = 6
    out = decode_image(encode(img, "JPEG", exif=exif.tobytes()))
    assert out.size == (20, 40)
    assert out.mode == "RGB"


def test_large_jpegs_are_decoded_at_reduced_size():
    data = encode(Image.new("RGB", (4000, 3000), "blue"), "JPEG")
    out = decode_image(data)
    assert out.width < 4000
    assert min(out.size) >= min(images.JPEG_DRAFT_SIZE)


def test_transparent_png_is_composited_on_white():
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 0))  # fully transparent red
    out = decode_image(encode(img, "PNG"))
    assert out.mode == "RGB"
    assert out.getpixel((5, 5)) == (255, 255, 255)


def test_palette_png_with_transparency():
    img = Image.new("P", (10, 10), 0)
    img.putpalette([0, 0, 0] * 256)
    out = decode_image(encode(img, "PNG", transparency=0))
    assert out.mode == "RGB" and out.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize("mode", ["L", "CMYK", "RGB"])
def test_other_colour_modes_become_rgb(mode):
    fmt = "JPEG" if mode == "CMYK" else "PNG"
    out = decode_image(encode(Image.new(mode, (8, 8)), fmt))
    assert out.mode == "RGB"


def test_animated_gif_uses_the_first_frame():
    frames = [Image.new("RGB", (8, 8), c) for c in ("red", "blue")]
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:])
    r, g, b = decode_image(buf.getvalue()).getpixel((4, 4))
    assert r > 200 and b < 50


@pytest.mark.parametrize("fmt", ["WEBP", "BMP", "TIFF"])
def test_common_formats(fmt):
    out = decode_image(encode(Image.new("RGB", (16, 12), "green"), fmt))
    assert out.size == (16, 12) and out.mode == "RGB"


def test_heic():
    try:
        data = encode(Image.new("RGB", (64, 48), "orange"), "HEIF")
    except (KeyError, OSError, ValueError) as exc:
        pytest.skip(f"HEIF encoder unavailable in this build: {exc}")
    out = decode_image(data, filename="IMG_0001.HEIC")
    assert out.size == (64, 48) and out.mode == "RGB"


def test_empty_garbage_and_oversized_files_are_rejected(monkeypatch):
    with pytest.raises(ImageDecodeError, match="empty"):
        decode_image(b"")
    with pytest.raises(ImageDecodeError, match="not a supported image"):
        decode_image(b"this is not an image at all")
    with pytest.raises(ImageDecodeError, match="not a supported image"):
        decode_image(encode(Image.new("RGB", (50, 50)), "PNG")[:60])  # truncated

    monkeypatch.setattr(images, "MAX_BYTES", 100)
    with pytest.raises(ImageDecodeError, match="larger than"):
        decode_image(b"x" * 101)


def test_decompression_bombs_are_rejected(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(ImageDecodeError, match="too many pixels"):
        decode_image(encode(Image.new("RGB", (100, 100)), "PNG"))


def test_dng_without_rawpy_gives_a_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "rawpy", None)  # makes `import rawpy` fail
    with pytest.raises(ImageDecodeError, match="rawpy"):
        decode_image(b"II*\x00fake", filename="photo.DNG")


def test_corrupt_dng_is_rejected():
    pytest.importorskip("rawpy")
    with pytest.raises(ImageDecodeError, match="DNG"):
        decode_image(b"II*\x00" + b"\x00" * 200, filename="photo.dng")
