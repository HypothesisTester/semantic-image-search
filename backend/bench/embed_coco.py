"""Embed every COCO val2017 image and caption with CLIP.

    python -m bench.embed_coco

Writes to data/coco/embeddings/:
    image_vectors.npy   (5000, 512) float32, unit length, in file_names order
    text_vectors.npy    (~25000, 512) float32, unit length, in captions order
    manifest.json       file names, captions, which image each caption belongs
                        to, the model used, and how long embedding took

Images go through common.images.decode_image, the same path uploads take,
so the benchmark measures what the real indexer does. Decoding runs in a
thread pool one batch ahead of the model, so the CPU prepares the next batch
while the GPU embeds the current one.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import common  # noqa: F401  -- must load before torch (macOS OpenMP fix)
import numpy as np

from common.clip import MODEL_NAME, PRETRAINED, ClipEncoder
from common.images import decode_image

from .coco import DEFAULT_DATA_DIR, CocoPaths, load_split


def _load(path: Path):
    return decode_image(path.read_bytes(), filename=path.name)


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=8, help="image decoding threads")
    parser.add_argument("--device", default=None, help="cuda, mps or cpu (default: best available)")
    parser.add_argument("--limit", type=int, default=None, help="only the first N images (quick trial)")
    parser.add_argument("--pretrained", default=PRETRAINED, help=argparse.SUPPRESS)  # "none" in tests
    args = parser.parse_args(argv)

    paths = CocoPaths(args.data_dir)
    split = load_split(paths)
    if args.limit:
        keep = set(range(args.limit))
        split = type(split)(
            split.file_names[: args.limit],
            [c for c, i in zip(split.captions, split.caption_image) if i in keep],
            [i for i in split.caption_image if i in keep],
        )
    print(f"{len(split.file_names)} images, {len(split.captions)} captions")

    pretrained = None if args.pretrained == "none" else args.pretrained
    encoder = ClipEncoder(pretrained=pretrained, device=args.device, batch_size=args.batch_size)
    print(f"model {MODEL_NAME}/{args.pretrained} on {encoder.device}")

    # Images, with decoding one batch ahead of embedding.
    files = [paths.images / name for name in split.file_names]
    batches = [files[i : i + args.batch_size] for i in range(0, len(files), args.batch_size)]
    image_chunks = []
    start = time.perf_counter()
    with ThreadPoolExecutor(args.workers) as pool:
        pending = [pool.submit(_load, f) for f in batches[0]] if batches else []
        for b in range(len(batches)):
            images = [fut.result() for fut in pending]
            if b + 1 < len(batches):
                pending = [pool.submit(_load, f) for f in batches[b + 1]]
            image_chunks.append(encoder.encode_images(images))
            done = min((b + 1) * args.batch_size, len(files))
            rate = done / (time.perf_counter() - start)
            sys.stderr.write(f"\r  images {done}/{len(files)}  ({rate:.0f} images/s)")
    sys.stderr.write("\n")
    image_seconds = time.perf_counter() - start
    image_vectors = np.concatenate(image_chunks) if image_chunks else np.empty((0, encoder.dim), np.float32)

    # Captions: text is cheap, so use bigger batches.
    encoder.batch_size = max(args.batch_size, 256)
    start = time.perf_counter()
    text_vectors = encoder.encode_texts(split.captions)
    text_seconds = time.perf_counter() - start
    print(f"  captions {len(split.captions)} in {text_seconds:.1f}s")

    out = paths.embeddings
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "image_vectors.npy", image_vectors)
    np.save(out / "text_vectors.npy", text_vectors)
    manifest = {
        "model": MODEL_NAME,
        "pretrained": args.pretrained,
        "device": encoder.device,
        "batch_size": args.batch_size,
        "decode_workers": args.workers,
        "n_images": len(split.file_names),
        "n_captions": len(split.captions),
        "image_seconds": image_seconds,
        "images_per_second": len(split.file_names) / image_seconds if image_seconds else None,
        "text_seconds": text_seconds,
        "captions_per_second": len(split.captions) / text_seconds if text_seconds else None,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "file_names": split.file_names,
        "captions": split.captions,
        "caption_image": split.caption_image,
    }
    with open(out / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    print(
        f"done: {manifest['images_per_second']:.0f} images/s, "
        f"{manifest['captions_per_second']:.0f} captions/s -> {out}"
    )
    return manifest


if __name__ == "__main__":
    main()
