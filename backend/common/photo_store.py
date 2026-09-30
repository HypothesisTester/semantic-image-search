"""Stores uploaded photos on local disk and serves them by unguessable URL.

Layout:

    <root>/<uid>/<photo_id>/original.<ext>   the uploaded bytes, untouched
    <root>/<uid>/<photo_id>/display.jpg      upright JPEG, at most 2048 px, for the viewer
    <root>/<uid>/<photo_id>/thumb.jpg        384 px JPEG for the grid

Design notes:

Content-derived ids. ``photo_id`` is the first 128 bits of
SHA-256(uid, file bytes), base64url-encoded. Uploading the same photo twice
therefore gives the same id, so a retried or duplicated upload overwrites
instead of creating a copy, and its index entry is replaced, not duplicated.

Capability URLs. Photos are served to <img> tags, which cannot send an
Authorization header, so the URL itself is the permission: with 128 bits of
id nobody can guess one. This is the same model as Firebase Storage download
URLs or "anyone with the link" sharing. Knowing a photo's bytes lets you
compute its id, but then you already have the photo. The stronger
alternative is short-lived signed URLs, which would also allow revoking
access; they are unnecessary for this app.

Browser-friendly renditions. HEIC (the iPhone default) and DNG do not display
in most browsers, so every upload also gets a JPEG display copy and
thumbnail, already rotated upright.

Atomic writes, as in the index store: each file is written to a temporary
file and moved into place, so a crash never leaves a half-written photo.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePath

from PIL import Image

DISPLAY_MAX = 2048
THUMB_MAX = 384
JPEG_QUALITY = 88
THUMB_QUALITY = 82
VARIANTS = ("display", "thumb")

_UID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22}$")
_EXT_PATTERN = re.compile(r"^\.[a-z0-9]{1,5}$")


def photo_id(uid: str, data: bytes) -> str:
    digest = hashlib.sha256(uid.encode("utf-8") + b"\x00" + data).digest()
    return base64.urlsafe_b64encode(digest[:16]).decode("ascii").rstrip("=")


@dataclass(frozen=True)
class StoredPhoto:
    uid: str
    photo_id: str
    filename: str

    @property
    def key(self) -> str:
        """The index key for this photo."""
        return f"{self.uid}/{self.photo_id}"

    def path(self, variant: str) -> str:
        """URL path of a rendition, relative to the service that serves photos."""
        return f"/photos/{self.uid}/{self.photo_id}/{variant}.jpg"


class PhotoStore:
    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root)

    def save(self, uid: str, data: bytes, filename: str, image: Image.Image) -> StoredPhoto:
        """Store the original bytes plus display and thumbnail JPEGs made from ``image``.

        ``image`` is the decoded, upright RGB image (from common.images.decode_image).
        """
        _check_uid(uid)
        pid = photo_id(uid, data)
        folder = self.root / uid / pid
        folder.mkdir(parents=True, exist_ok=True)

        ext = PurePath(filename).suffix.lower()
        if not _EXT_PATTERN.fullmatch(ext):
            ext = ".bin"
        _write_atomic(folder / f"original{ext}", data)
        _write_atomic(folder / "display.jpg", _jpeg(image, DISPLAY_MAX, JPEG_QUALITY))
        _write_atomic(folder / "thumb.jpg", _jpeg(image, THUMB_MAX, THUMB_QUALITY))
        return StoredPhoto(uid, pid, PurePath(filename).name)

    def file_for(self, uid: str, pid: str, variant: str) -> Path | None:
        """Path of a stored rendition, or None if the request is invalid or missing.

        Every part is validated against a strict pattern before touching the
        filesystem, so a crafted URL cannot escape the photo directory.
        """
        if not (_UID_PATTERN.fullmatch(uid) and _ID_PATTERN.fullmatch(pid) and variant in VARIANTS):
            return None
        path = self.root / uid / pid / f"{variant}.jpg"
        return path if path.is_file() else None


def _check_uid(uid: str) -> None:
    if not isinstance(uid, str) or not _UID_PATTERN.fullmatch(uid):
        raise ValueError("invalid user id")


def _jpeg(image: Image.Image, max_side: int, quality: int) -> bytes:
    copy = image.copy()
    copy.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    copy.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def _write_atomic(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
