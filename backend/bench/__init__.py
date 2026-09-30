"""Benchmarks on the COCO val2017 images and captions.

Run from the backend/ directory:

    python -m bench.download_coco   # ~1 GB: 5,000 images + captions
    python -m bench.embed_coco      # CLIP vectors for every image and caption
    python -m bench.evaluate        # Recall@K, latency, scaling -> bench/results/
"""

import common  # noqa: F401  -- loads before torch/faiss (macOS OpenMP fix)
