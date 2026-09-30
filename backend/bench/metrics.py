"""Retrieval metrics and timing summaries."""

from __future__ import annotations

from collections.abc import Sequence

import faiss
import numpy as np


def text_to_image_recall(
    text_vectors: np.ndarray,
    image_vectors: np.ndarray,
    caption_image: Sequence[int],
    ks: Sequence[int] = (1, 5, 10),
) -> dict[int, float]:
    """Fraction of captions whose own image is in the top K images.

    This is the photo-search task: type a description, find the photo.
    """
    gt = np.asarray(caption_image)
    ids = _top_k(image_vectors, text_vectors, max(ks))
    return {k: float(np.mean(np.any(ids[:, :k] == gt[:, None], axis=1))) for k in ks}


def image_to_text_recall(
    text_vectors: np.ndarray,
    image_vectors: np.ndarray,
    caption_image: Sequence[int],
    ks: Sequence[int] = (1, 5, 10),
) -> dict[int, float]:
    """Fraction of images with at least one of their own captions in the top K captions."""
    owner = np.asarray(caption_image)
    ids = _top_k(text_vectors, image_vectors, max(ks))
    hit = owner[ids] == np.arange(len(image_vectors))[:, None]
    return {k: float(np.mean(np.any(hit[:, :k], axis=1))) for k in ks}


def _top_k(corpus: np.ndarray, queries: np.ndarray, k: int) -> np.ndarray:
    index = faiss.IndexFlatIP(corpus.shape[1])
    index.add(np.ascontiguousarray(corpus, dtype=np.float32))
    _, ids = index.search(np.ascontiguousarray(queries, dtype=np.float32), min(k, len(corpus)))
    return ids


def latency_summary(seconds: Sequence[float]) -> dict[str, float]:
    """p50 / p95 / p99 / mean of a list of durations, in milliseconds."""
    ms = np.asarray(seconds, dtype=np.float64) * 1000.0
    return {
        "p50_ms": float(np.percentile(ms, 50)),
        "p95_ms": float(np.percentile(ms, 95)),
        "p99_ms": float(np.percentile(ms, 99)),
        "mean_ms": float(ms.mean()),
        "n": int(ms.size),
    }
