"""Measure search quality and speed on COCO val2017.

    python -m bench.evaluate

Needs the output of bench.embed_coco. Writes bench/results/coco_val2017.json
and bench/results/coco_val2017.md, and prints the markdown.

Quality: Recall@1/5/10 in both directions over 5,000 images and ~25,000
human-written captions. Text-to-image is the photo-search task.

Speed, on the real code path (common.index_store.IndexStore):
- indexing: adding all 5,000 vectors in upload-sized batches
- search: warm top-5 search latency over the 5,000-image index
- cold start: first search after a restart, including reading the file
- query encoding: CLIP text encoder on one query at a time
- end to end: encode + search, which is what a user waits for
- scaling: exact-search latency as the index grows, the evidence for
  choosing exact search over an approximate index
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import common  # noqa: F401  -- must load before torch (macOS OpenMP fix)
import faiss
import numpy as np

from common.clip import MODEL_NAME, ClipEncoder
from common.index_store import IndexStore
from common.vectors import l2_normalize

from .coco import DEFAULT_DATA_DIR, RESULTS_DIR, CocoPaths
from .metrics import image_to_text_recall, latency_summary, text_to_image_recall

KS = (1, 5, 10)
# Published zero-shot text-to-image Recall@5 for CLIP ViT-B/32 is about 55% on
# the COCO "Karpathy" 5k test split. That split comes from val2014, so it is a
# different 5,000 images from val2017; results here should land nearby, not
# match exactly. Far outside this range points to a preprocessing bug.
EXPECTED_T2I_R5 = (0.45, 0.65)


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--device", default=None)
    parser.add_argument("--queries", type=int, default=1000, help="search latency samples")
    parser.add_argument("--encode-queries", type=int, default=200, help="text encoding latency samples")
    parser.add_argument(
        "--scaling-sizes", default="5000,20000,100000", help="index sizes for the scaling test"
    )
    parser.add_argument("--pretrained", default=None, help=argparse.SUPPRESS)  # "none" in tests
    args = parser.parse_args(argv)

    emb = CocoPaths(args.data_dir).embeddings
    with open(emb / "manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    image_vectors = np.load(emb / "image_vectors.npy")
    text_vectors = np.load(emb / "text_vectors.npy")
    captions, caption_image = manifest["captions"], manifest["caption_image"]
    rng = np.random.default_rng(0)

    print(f"quality over {len(image_vectors)} images and {len(text_vectors)} captions ...")
    t2i = text_to_image_recall(text_vectors, image_vectors, caption_image, KS)
    i2t = image_to_text_recall(text_vectors, image_vectors, caption_image, KS)

    pretrained = manifest["pretrained"] if args.pretrained is None else args.pretrained
    encoder = ClipEncoder(
        pretrained=None if pretrained == "none" else pretrained, device=args.device, towers="text"
    )
    with tempfile.TemporaryDirectory() as tmp:
        print("index store: build, cold start, warm search ...")
        store, store_stats = _store_benchmarks(
            Path(tmp), image_vectors, text_vectors, manifest["file_names"], args.queries, rng
        )
        print("query encoding and end to end ...")
        encode_stats = _encode_benchmarks(encoder, store, captions, args.encode_queries, rng)

    sizes = [int(s) for s in args.scaling_sizes.split(",") if s]
    print(f"exact-search scaling at {sizes} vectors ...")
    scaling = _scaling_benchmarks(sizes, image_vectors.shape[1], rng)

    results = {
        "dataset": {
            "name": "COCO val2017",
            "images": len(image_vectors),
            "captions": len(text_vectors),
        },
        "model": f"{MODEL_NAME} / {manifest['pretrained']}",
        "text_to_image_recall": {f"R@{k}": v for k, v in t2i.items()},
        "image_to_text_recall": {f"R@{k}": v for k, v in i2t.items()},
        "indexing": {
            "embed_images_per_second": manifest["images_per_second"],
            "embed_device": manifest["device"],
            **store_stats["indexing"],
        },
        "search": store_stats["search"],
        "cold_start": store_stats["cold_start"],
        "query_encoding": encode_stats["encode"],
        "end_to_end": encode_stats["end_to_end"],
        "scaling": scaling,
        "machine": _machine(encoder.device),
    }

    low, high = EXPECTED_T2I_R5
    r5 = t2i[5]
    # The reference range only means something for the full val2017 split
    # with the real weights.
    applicable = len(image_vectors) == 5000 and manifest["pretrained"] == "openai"
    results["sanity_check"] = {
        "text_to_image_R@5": r5,
        "expected_range": [low, high],
        "ok": (low <= r5 <= high) if applicable else None,
    }

    args.results_dir.mkdir(parents=True, exist_ok=True)
    with open(args.results_dir / "coco_val2017.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    markdown = render_markdown(results)
    (args.results_dir / "coco_val2017.md").write_text(markdown, encoding="utf-8")
    print()
    print(markdown)
    if results["sanity_check"]["ok"] is False:
        print(
            f"WARNING: text-to-image R@5 = {r5:.1%} is outside the expected "
            f"{low:.0%}-{high:.0%}. Check preprocessing before trusting these numbers."
        )
    return results


def _store_benchmarks(tmp: Path, image_vectors, text_vectors, file_names, n_queries, rng):
    store = IndexStore(tmp)
    keys = [f"coco/val2017/{name}" for name in file_names]
    batch = 50  # a typical multi-photo upload
    add_times = []
    start = time.perf_counter()
    for i in range(0, len(keys), batch):
        t = time.perf_counter()
        store.add("bench", keys[i : i + batch], image_vectors[i : i + batch])
        add_times.append(time.perf_counter() - t)
    build_seconds = time.perf_counter() - start
    index_bytes = os.path.getsize(tmp / "bench" / "index.npz")

    cold = []
    query = text_vectors[:1]
    for _ in range(5):
        fresh = IndexStore(tmp)  # empty cache, like a restarted service
        t = time.perf_counter()
        fresh.search("bench", query, k=5)
        cold.append(time.perf_counter() - t)

    picks = rng.choice(len(text_vectors), size=min(n_queries, len(text_vectors)), replace=False)
    for q in picks[:20]:  # warm up
        store.search("bench", text_vectors[q], k=5)
    search = []
    for q in picks:
        t = time.perf_counter()
        store.search("bench", text_vectors[q], k=5)
        search.append(time.perf_counter() - t)

    return store, {
        "indexing": {
            "store_build_seconds": build_seconds,
            "store_batch_size": batch,
            "store_add_per_batch": latency_summary(add_times),
            # The whole index file is rewritten on every add, so the last
            # batch (into an almost full index) is the slowest.
            "store_add_last_batch_ms": add_times[-1] * 1000.0,
            "store_size_before_last_batch": len(keys) - len(keys[-batch:]),
            "index_file_mb": index_bytes / 1e6,
        },
        "search": {"k": 5, **latency_summary(search)},
        "cold_start": latency_summary(cold),
    }


def _encode_benchmarks(encoder, store: IndexStore, captions, n, rng) -> dict:
    picks = rng.choice(len(captions), size=min(n, len(captions)), replace=False)
    for q in picks[:10]:  # warm up (first calls compile kernels on GPU backends)
        encoder.encode_texts([captions[q]])
    encode, total = [], []
    for q in picks:
        t0 = time.perf_counter()
        vec = encoder.encode_texts([captions[q]])
        t1 = time.perf_counter()
        store.search("bench", vec, k=5)
        t2 = time.perf_counter()
        encode.append(t1 - t0)
        total.append(t2 - t0)
    return {"encode": latency_summary(encode), "end_to_end": latency_summary(total)}


def _scaling_benchmarks(sizes, dim, rng) -> list[dict]:
    rows = []
    for n in sizes:
        corpus = l2_normalize(rng.standard_normal((n, dim)).astype(np.float32))
        queries = l2_normalize(rng.standard_normal((100, dim)).astype(np.float32))
        index = faiss.IndexFlatIP(dim)
        index.add(corpus)
        for q in queries[:5]:
            index.search(q[None, :], 5)
        times = []
        for q in queries:
            t = time.perf_counter()
            index.search(q[None, :], 5)
            times.append(time.perf_counter() - t)
        rows.append({"vectors": n, "memory_mb": n * dim * 4 / 1e6, **latency_summary(times)})
        del corpus, index
    return rows


def _machine(device: str) -> dict:
    info = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "faiss": faiss.__version__,
        "torch_device": device,
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS", "default"),
        "faiss_threads": faiss.omp_get_max_threads(),
    }
    if sys.platform == "darwin":
        try:
            info["cpu"] = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=5
            ).stdout.strip()
        except Exception:
            pass
    else:
        info["cpu"] = platform.processor() or platform.machine()
    try:
        import torch

        info["torch"] = torch.__version__
    except ImportError:
        pass
    return info


def render_markdown(r: dict) -> str:
    pct = lambda x: f"{x * 100:.1f}%"  # noqa: E731
    ms = lambda x: f"{x:.2f} ms" if x < 10 else f"{x:.0f} ms"  # noqa: E731
    t2i, i2t = r["text_to_image_recall"], r["image_to_text_recall"]
    m = r["machine"]
    lines = [
        f"# Benchmark: {r['dataset']['name']}",
        "",
        f"{r['dataset']['images']:,} images, {r['dataset']['captions']:,} captions. "
        f"Model: {r['model']}. Machine: {m.get('cpu', m['machine'])}, "
        f"CLIP on `{m['torch_device']}`, FAISS threads: {m['faiss_threads']}.",
        "",
        "## Retrieval quality",
        "",
        "| Direction | R@1 | R@5 | R@10 |",
        "|---|---|---|---|",
        f"| Text to image (photo search) | {pct(t2i['R@1'])} | {pct(t2i['R@5'])} | {pct(t2i['R@10'])} |",
        f"| Image to text | {pct(i2t['R@1'])} | {pct(i2t['R@5'])} | {pct(i2t['R@10'])} |",
        "",
        "R@K: the share of queries whose correct match is in the top K results.",
        "",
        "## Speed",
        "",
        "| Measure | p50 | p95 |",
        "|---|---|---|",
        f"| Search, top 5 of {r['dataset']['images']:,} (warm) | {ms(r['search']['p50_ms'])} | {ms(r['search']['p95_ms'])} |",
        f"| Query encoding (CLIP text) | {ms(r['query_encoding']['p50_ms'])} | {ms(r['query_encoding']['p95_ms'])} |",
        f"| End to end (encode + search) | {ms(r['end_to_end']['p50_ms'])} | {ms(r['end_to_end']['p95_ms'])} |",
        f"| Cold start (first search after restart) | {ms(r['cold_start']['p50_ms'])} | {ms(r['cold_start']['p95_ms'])} |",
        f"| Add {r['indexing']['store_batch_size']} photos to the index | {ms(r['indexing']['store_add_per_batch']['p50_ms'])} | {ms(r['indexing']['store_add_per_batch']['p95_ms'])} |",
        "",
        f"Adding {r['indexing']['store_batch_size']} photos to an index that already holds "
        f"{r['indexing']['store_size_before_last_batch']:,} took "
        f"{ms(r['indexing']['store_add_last_batch_ms'])}: every add rewrites the whole index file, "
        "so the cost grows with the library.",
        "",
        f"Embedding throughput: **{r['indexing']['embed_images_per_second']:.0f} images/s** "
        f"on `{r['indexing']['embed_device']}` (decode + CLIP). "
        f"Index file: {r['indexing']['index_file_mb']:.2f} MB.",
        "",
        "## Exact search as the index grows",
        "",
        "| Vectors | Memory | p50 | p95 |",
        "|---|---|---|---|",
    ]
    for row in r["scaling"]:
        lines.append(
            f"| {row['vectors']:,} | {row['memory_mb']:.0f} MB | {ms(row['p50_ms'])} | {ms(row['p95_ms'])} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
