"""Build the public demo's index and thumbnails from the COCO embeddings.

    python -m demo.build_index

Needs the output of bench.embed_coco (no re-embedding: it reuses those
vectors). Writes to data/demo/:
    index/demo/index.npz   an IndexStore index for the user id "demo"
    thumbnails/*.jpg       384 px thumbnails that the demo serves

The demo search service will load this index read-only, so it goes through
the same IndexStore code as a real user's library.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import common  # noqa: F401  -- must load before torch/faiss (macOS OpenMP fix)
import numpy as np

from common.images import decode_image
from common.index_store import IndexStore

from bench.coco import DEFAULT_DATA_DIR, CocoPaths

DEMO_UID = "demo"
THUMBNAIL_SIZE = 384
THUMBNAIL_QUALITY = 82


def make_thumbnail(src: Path, dest: Path) -> int:
    img = decode_image(src.read_bytes(), filename=src.name)
    img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
    img.save(dest, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True, progressive=True)
    return dest.stat().st_size


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=None, help="default: <data-dir>/demo")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)

    paths = CocoPaths(args.data_dir)
    out = args.out_dir or args.data_dir / "demo"
    with open(paths.embeddings / "manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    vectors = np.load(paths.embeddings / "image_vectors.npy")
    names = manifest["file_names"]

    first_caption: dict[int, str] = {}
    for caption, image in zip(manifest["captions"], manifest["caption_image"]):
        first_caption.setdefault(image, caption)

    start = time.perf_counter()
    store = IndexStore(out / "index")
    keys = [f"coco/val2017/{name}" for name in names]
    metas = [{"url": f"/images/{name}", "caption": first_caption.get(i, "")} for i, name in enumerate(names)]
    for i in range(0, len(keys), 500):
        store.add(DEMO_UID, keys[i : i + 500], vectors[i : i + 500], metas[i : i + 500])
    print(f"index: {store.count(DEMO_UID)} images in {time.perf_counter() - start:.1f}s")

    thumbs = out / "thumbnails"
    thumbs.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    with ThreadPoolExecutor(args.workers) as pool:
        sizes = list(pool.map(lambda n: make_thumbnail(paths.images / n, thumbs / n), names))
    total_mb = sum(sizes) / 1e6
    print(f"thumbnails: {len(sizes)} ({total_mb:.0f} MB) in {time.perf_counter() - start:.1f}s")
    return {"images": len(names), "thumbnails_mb": total_mb, "out": str(out)}


if __name__ == "__main__":
    main()
