"""Helpers for embedding vectors.

Every vector that goes into or queries an index is L2-normalised (unit length).
For unit vectors, inner product equals cosine similarity:

    a . b = |a| |b| cos(theta) = cos(theta)   when |a| = |b| = 1

so a plain inner-product index gives cosine-similarity search.
"""

from __future__ import annotations

import numpy as np

# How far a norm may drift from 1.0 and still count as normalised. float32
# arithmetic gives errors around 1e-7; 1e-3 leaves room without letting an
# unnormalised vector (norm ~10 for raw CLIP output) slip through.
NORM_TOLERANCE = 1e-3


def l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Return a C-contiguous float32 copy of ``x`` with each row scaled to unit length.

    Accepts a single vector of shape (d,) or a matrix of shape (n, d); always
    returns shape (n, d). Raises ValueError for a zero vector, which has no
    direction and would silently score 0 against everything.
    """
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = x[None, :]
    if x.ndim != 2:
        raise ValueError(f"expected a vector or a matrix, got shape {x.shape}")
    if not np.all(np.isfinite(x)):
        raise ValueError("vectors contain NaN or infinity")
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    if np.any(norms < eps):
        raise ValueError("cannot normalise a zero vector")
    return np.ascontiguousarray(x / norms, dtype=np.float32)


def check_normalized(x: np.ndarray, dim: int) -> np.ndarray:
    """Validate that ``x`` is an (n, dim) float32 matrix of unit vectors and return it.

    Accepts a single (dim,) vector and returns it as (1, dim).
    """
    x = np.asarray(x)
    if x.ndim == 1:
        x = x[None, :]
    if x.ndim != 2 or x.shape[1] != dim:
        raise ValueError(f"expected shape (n, {dim}), got {x.shape}")
    if x.dtype != np.float32:
        raise ValueError(f"expected float32, got {x.dtype}")
    if not np.all(np.isfinite(x)):
        raise ValueError("vectors contain NaN or infinity")
    norms = np.linalg.norm(x, axis=1)
    if x.shape[0] and np.max(np.abs(norms - 1.0)) > NORM_TOLERANCE:
        raise ValueError("vectors are not L2-normalised; call l2_normalize first")
    return np.ascontiguousarray(x)
