"""Shared test helpers. Module-level so that spawned worker processes can import them."""

from __future__ import annotations

import time
from contextlib import nullcontext

import numpy as np

from common.index_store import IndexStore

DIM = 512


def unit_vectors(n: int, seed: int, dim: int = DIM) -> np.ndarray:
    """``n`` random unit vectors, reproducible from ``seed``."""
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((n, dim)).astype(np.float32)
    return x / np.linalg.norm(x, axis=1, keepdims=True)


def add_one_at_a_time(root: str, uid: str, worker: int, count: int) -> None:
    """Worker process: add ``count`` items, one read-modify-write cycle each."""
    store = IndexStore(root)
    vectors = unit_vectors(count, seed=1000 + worker)
    for i in range(count):
        store.add(uid, [f"w{worker}/img{i}.jpg"], vectors[i : i + 1])


class UnlockedSlowStore(IndexStore):
    """An IndexStore with the lock removed and a pause after each read.

    Used to show the lost-update bug that the real lock prevents: two writers
    both read the same version during the pause, then each writes its own
    change on top of it, and the first write is lost.
    """

    def _lock(self, user_dir):
        return nullcontext()

    def _read(self, user_dir):
        snap = super()._read(user_dir)
        time.sleep(0.5)
        return snap


class LockedSlowStore(IndexStore):
    """The same pause as UnlockedSlowStore, with the real lock left in place."""

    def _read(self, user_dir):
        snap = super()._read(user_dir)
        time.sleep(0.5)
        return snap


def add_after_barrier(locked: bool, root: str, uid: str, key: str, seed: int, barrier) -> None:
    """Worker process: wait until every worker is ready, then add one item."""
    store = LockedSlowStore(root) if locked else UnlockedSlowStore(root)
    vector = unit_vectors(1, seed=seed)
    barrier.wait()
    store.add(uid, [key], vector)
