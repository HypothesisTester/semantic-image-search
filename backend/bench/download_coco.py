"""Download COCO val2017: 5,000 images (~780 MB) and their captions (~240 MB zip).

    python -m bench.download_coco

Safe to re-run: finished steps are skipped. A download is written to a
.part file and only renamed when complete, so an interrupted run never
leaves a truncated zip behind.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
import zipfile
from pathlib import Path

import requests

from .coco import DEFAULT_DATA_DIR, CocoPaths

IMAGES_URL = "http://images.cocodataset.org/zips/val2017.zip"
ANNOTATIONS_URL = "http://images.cocodataset.org/annotations/annotations_trainval2017.zip"
CAPTIONS_MEMBER = "annotations/captions_val2017.json"
EXPECTED_IMAGES = 5000


def download(url: str, dest: Path, *, chunk: int = 1 << 20) -> Path:
    if dest.exists():
        print(f"already downloaded: {dest.name}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    print(f"downloading {url}")
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        done, start = 0, time.monotonic()
        with open(part, "wb") as f:
            for block in resp.iter_content(chunk):
                f.write(block)
                done += len(block)
                _progress(done, total, start)
    sys.stderr.write("\n")
    if total and done != total:
        part.unlink()
        raise RuntimeError(f"download of {url} was incomplete ({done} of {total} bytes)")
    part.rename(dest)
    return dest


def _progress(done: int, total: int, start: float) -> None:
    elapsed = max(time.monotonic() - start, 1e-6)
    mb, rate = done / 1e6, done / 1e6 / elapsed
    if total:
        sys.stderr.write(f"\r  {mb:7.1f} / {total / 1e6:.1f} MB  ({rate:.1f} MB/s)")
    else:
        sys.stderr.write(f"\r  {mb:7.1f} MB  ({rate:.1f} MB/s)")


def extract_images(zip_path: Path, dest: Path) -> int:
    """Extract the val2017/*.jpg files into ``dest`` and return how many there are."""
    if dest.is_dir() and len(list(dest.glob("*.jpg"))) >= EXPECTED_IMAGES:
        print(f"already extracted: {dest}")
        return len(list(dest.glob("*.jpg")))
    print(f"extracting images to {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            name = Path(member.filename).name
            if member.is_dir() or not name.lower().endswith(".jpg"):
                continue
            with zf.open(member) as src, open(dest / name, "wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count


def extract_captions(zip_path: Path, dest: Path) -> None:
    if dest.exists():
        print(f"already extracted: {dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf, zf.open(CAPTIONS_MEMBER) as src, open(dest, "wb") as dst:
        shutil.copyfileobj(src, dst)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--images-url", default=IMAGES_URL)
    parser.add_argument("--annotations-url", default=ANNOTATIONS_URL)
    parser.add_argument("--expected-images", type=int, default=EXPECTED_IMAGES)
    parser.add_argument("--keep-zips", action="store_true", help="keep the zip files after extracting")
    args = parser.parse_args(argv)

    paths = CocoPaths(args.data_dir)
    downloads = paths.coco / "downloads"

    captions_zip = download(args.annotations_url, downloads / "annotations_trainval2017.zip")
    extract_captions(captions_zip, paths.captions)

    images_zip = download(args.images_url, downloads / "val2017.zip")
    count = extract_images(images_zip, paths.images)
    if count != args.expected_images:
        raise SystemExit(f"expected {args.expected_images} images, found {count}")

    if not args.keep_zips:
        shutil.rmtree(downloads, ignore_errors=True)
    print(f"done: {count} images and captions in {paths.coco}")


if __name__ == "__main__":
    main()
