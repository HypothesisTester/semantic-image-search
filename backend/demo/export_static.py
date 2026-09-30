"""Export the public demo as static files, for a demo that runs entirely in the browser.

    python -m demo.export_static

Needs the output of bench.embed_coco and demo.build_index. Writes to
data/demo/static/ (what gets uploaded):
    manifest.json    counts, vector format, model name
    vectors.f16      5,000 x 512 image vectors, float16, row-major
    photos.json      the photos in vector order: file name and COCO caption
    examples.json    the landing page's example searches with their text
                     vectors, so those work before the browser model loads
    thumbnails/      the 384 px thumbnails

and to data/demo/check/ (kept local, for scripts/verify-browser-model.mjs):
    check.json, check_text_vectors.f32   a sample of captions with the
                     Python model's vectors, to compare the browser's against

Why float16: it halves the download (10 MB -> 5 MB) and, for unit vectors
compared by dot product, changes scores by about 1e-3. The script measures
Recall@K with both precisions to show the ranking is unaffected.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import common  # noqa: F401  -- must load before torch/faiss (macOS OpenMP fix)
import numpy as np

from common.clip import MODEL_NAME, PRETRAINED

from bench.coco import DEFAULT_DATA_DIR, CocoPaths
from bench.metrics import text_to_image_recall

# The landing page's example searches. The frontend lists the same ones
# (src/components/DemoHome.tsx); a test checks the two lists match.
EXAMPLES = [
    "a dog catching a frisbee",
    "a plate of food with broccoli",
    "people surfing on big waves",
    "a cat sleeping on a laptop",
    "a red double-decker bus",
    "a snowy mountain with skiers",
]

# The browser loads this conversion of the same OpenAI weights.
BROWSER_MODEL = "Xenova/clip-vit-base-patch32"
CHECK_SAMPLE = 1000


def normalise_query(text: str) -> str:
    """How queries are matched to precomputed examples (the frontend does the same)."""
    return " ".join(text.lower().split())


def export(data_dir: Path, encoder=None, check_sample: int = CHECK_SAMPLE) -> dict:
    coco = CocoPaths(data_dir)
    demo = data_dir / "demo"
    with open(coco.embeddings / "manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    image_vectors = np.load(coco.embeddings / "image_vectors.npy")
    text_vectors = np.load(coco.embeddings / "text_vectors.npy")
    names = manifest["file_names"]
    thumbs_src = demo / "thumbnails"
    missing = [n for n in names if not (thumbs_src / n).exists()]
    if missing:
        raise SystemExit(f"{len(missing)} thumbnails missing: run `python -m demo.build_index` first")

    out = demo / "static"
    if out.exists():
        shutil.rmtree(out)
    (out / "thumbnails").mkdir(parents=True)

    # Vectors, halved in size, and proof that the ranking survives it.
    half = image_vectors.astype(np.float16)
    half.tofile(out / "vectors.f16")
    recall_fp32 = text_to_image_recall(text_vectors, image_vectors, manifest["caption_image"])
    recall_fp16 = text_to_image_recall(text_vectors, half.astype(np.float32), manifest["caption_image"])

    first_caption: dict[int, str] = {}
    for caption, image in zip(manifest["captions"], manifest["caption_image"]):
        first_caption.setdefault(image, caption)
    photos = [{"file": n, "caption": first_caption.get(i, "")} for i, n in enumerate(names)]
    (out / "photos.json").write_text(json.dumps(photos), encoding="utf-8")

    if encoder is None:
        from common.clip import ClipEncoder

        encoder = ClipEncoder(towers="text")
    example_vectors = encoder.encode_texts(EXAMPLES)
    examples = [
        {"text": text, "key": normalise_query(text), "vector": [round(float(x), 6) for x in vec]}
        for text, vec in zip(EXAMPLES, example_vectors)
    ]
    (out / "examples.json").write_text(json.dumps(examples), encoding="utf-8")

    for name in names:
        shutil.copyfile(thumbs_src / name, out / "thumbnails" / name)

    info = {
        "count": len(names),
        "dim": int(image_vectors.shape[1]),
        "dtype": "float16",
        "model": f"{MODEL_NAME}/{PRETRAINED}",
        "browser_model": BROWSER_MODEL,
        "recall_fp32": {f"R@{k}": v for k, v in recall_fp32.items()},
        "recall_fp16": {f"R@{k}": v for k, v in recall_fp16.items()},
    }
    (out / "manifest.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    # A fixed random sample of captions for comparing the browser model.
    check = demo / "check"
    check.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    picks = np.sort(rng.choice(len(text_vectors), size=min(check_sample, len(text_vectors)), replace=False))
    (check / "check.json").write_text(
        json.dumps(
            {
                "captions": [manifest["captions"][i] for i in picks],
                "caption_image": [manifest["caption_image"][i] for i in picks],
                "dim": int(text_vectors.shape[1]),
            }
        ),
        encoding="utf-8",
    )
    text_vectors[picks].astype(np.float32).tofile(check / "check_text_vectors.f32")
    return info


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    info = export(args.data_dir)
    size_mb = sum(p.stat().st_size for p in (args.data_dir / "demo" / "static").rglob("*") if p.is_file()) / 1e6
    print(f"exported {info['count']} photos ({size_mb:.0f} MB) to {args.data_dir / 'demo' / 'static'}")
    print("text-to-image recall over all captions:")
    for k in ("R@1", "R@5", "R@10"):
        print(f"  {k}: float32 {info['recall_fp32'][k]:.2%}   float16 {info['recall_fp16'][k]:.2%}")
    return info


if __name__ == "__main__":
    main()
