"""Per-user FAISS indexes stored on local disk.

Layout on disk:

    <root>/<uid>/index.npz   the FAISS index and its id -> item map, in ONE file
    <root>/<uid>/.lock       held while a writer updates that user's index

Design notes (see also the Phase 1 pull request):

Exact search. Each user gets ``IndexIDMap2(IndexFlatIP(512))``: brute-force
inner product over every vector, wrapped so that vectors carry our own ids.
A personal library is thousands of photos, not millions. 10,000 x 512 float32
is about 20 MB and a full scan takes about a millisecond, so approximate
indexes (HNSW, IVF) would lose recall and gain nothing at this size.

One file, swapped atomically. The index and its id map must always agree.
Both go into one .npz file, written to a temporary file in the same directory,
fsynced, and moved into place with os.replace, which is atomic on POSIX. A
reader therefore sees the whole old version or the whole new version, never a
mix, and a crash mid-write leaves the previous version intact.

A lock per user. An upload is read -> modify -> write. Without a lock, two
overlapping uploads for one user both read version N, and the second write
silently discards the first upload's vectors (a "lost update"). Writers hold an
exclusive file lock on that user's directory, which works across threads and
across processes (e.g. several indexer workers sharing one volume). Readers
never need the lock, because of the atomic swap above.

Stable ids. An item's id is derived from its key (the file's storage path) by
hashing, so indexing the same file twice replaces its vector instead of adding
a duplicate. With 63-bit ids the chance of any collision among n photos is
about n^2 / 2^64 (the birthday bound): for 10,000 photos, about 1 in 2 x 10^11.

Read cache. The search service keeps recently used indexes in memory and
reloads one only when its file changes, detected by (inode, mtime, size).
os.replace always creates a new inode, so a new version is never missed.
Writers always work on a fresh copy read from disk and never mutate a cached
index, and FAISS allows concurrent searches on one index from many threads.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import faiss
import numpy as np
from filelock import FileLock

from .vectors import check_normalized

INDEX_FILENAME = "index.npz"
LOCK_FILENAME = ".lock"
FORMAT_VERSION = 1

# Firebase uids are up to 128 characters from this alphabet. Validating them
# also prevents path traversal, since uids become directory names.
_UID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_ID_MASK = (1 << 63) - 1


class IndexCorruptError(RuntimeError):
    """An index file exists but cannot be read."""


def item_id(key: str) -> int:
    """Stable non-negative 63-bit id for an item key, e.g. its storage path."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & _ID_MASK


@dataclass(frozen=True)
class Hit:
    rank: int  # 1 = best match
    score: float  # cosine similarity, in [-1, 1]
    key: str
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AddResult:
    added: int  # keys that were new
    updated: int  # keys that already existed and had their vector replaced


class _Snapshot:
    """One user's index and its id -> (key, meta) map, as loaded from one file."""

    def __init__(self, index: faiss.Index, items: dict[int, dict]) -> None:
        self.index = index
        self.items = items

    @classmethod
    def empty(cls, dim: int) -> _Snapshot:
        return cls(faiss.IndexIDMap2(faiss.IndexFlatIP(dim)), {})

    def search(self, query: np.ndarray, k: int) -> list[Hit]:
        k = min(k, self.index.ntotal)
        if k == 0:
            return []
        scores, ids = self.index.search(query, k)
        hits = []
        for score, id_ in zip(scores[0], ids[0]):
            if id_ < 0:  # FAISS pads with -1 when there are fewer than k results
                continue
            item = self.items[int(id_)]
            hits.append(
                Hit(rank=len(hits) + 1, score=float(score), key=item["key"], meta=item["meta"])
            )
        return hits


@dataclass
class _CacheEntry:
    signature: tuple[int, int, int]
    snapshot: _Snapshot


class IndexStore:
    """Per-user FAISS indexes under ``root``. Safe to share across threads and processes."""

    def __init__(
        self,
        root: str | os.PathLike,
        dim: int = 512,
        *,
        cache_size: int = 64,
        lock_timeout: float = 30.0,
    ) -> None:
        self.root = Path(root)
        self.dim = dim
        self.cache_size = cache_size
        self.lock_timeout = lock_timeout
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._cache_lock = threading.Lock()

    # ---- writes -----------------------------------------------------------

    def add(
        self,
        uid: str,
        keys: Sequence[str],
        vectors: np.ndarray,
        metas: Sequence[dict] | None = None,
    ) -> AddResult:
        """Insert or replace vectors for ``keys`` in ``uid``'s index.

        ``vectors`` must be an (n, dim) float32 matrix of unit vectors.
        ``metas`` are small JSON-serialisable dicts returned with search hits
        (e.g. the image URL). If a key appears twice in one call, the last wins.
        """
        vectors = check_normalized(vectors, self.dim)
        if len(keys) != len(vectors):
            raise ValueError(f"{len(keys)} keys but {len(vectors)} vectors")
        metas = list(metas) if metas is not None else [{} for _ in keys]
        if len(metas) != len(keys):
            raise ValueError(f"{len(keys)} keys but {len(metas)} metas")
        if not keys:
            return AddResult(added=0, updated=0)

        # De-duplicate within the batch: FAISS would store both copies.
        latest: dict[int, int] = {}
        for row, key in enumerate(keys):
            latest[item_id(key)] = row
        ids = np.fromiter(latest.keys(), dtype=np.int64, count=len(latest))
        rows = list(latest.values())

        user_dir = self._user_dir(uid)
        user_dir.mkdir(parents=True, exist_ok=True)
        with self._lock(user_dir):
            snap = self._read(user_dir) or _Snapshot.empty(self.dim)
            existing = np.array([i for i in ids if int(i) in snap.items], dtype=np.int64)
            if existing.size:
                snap.index.remove_ids(existing)
            snap.index.add_with_ids(vectors[rows], ids)
            for id_, row in latest.items():
                snap.items[id_] = {"key": keys[row], "meta": metas[row]}
            self._write(user_dir, snap)
        return AddResult(added=len(ids) - existing.size, updated=int(existing.size))

    def remove(self, uid: str, keys: Sequence[str]) -> int:
        """Remove ``keys`` from ``uid``'s index. Returns how many were present."""
        user_dir = self._user_dir(uid)
        if not (user_dir / INDEX_FILENAME).exists():
            return 0
        with self._lock(user_dir):
            snap = self._read(user_dir)
            if snap is None:
                return 0
            ids = [item_id(k) for k in keys]
            present = np.array([i for i in set(ids) if i in snap.items], dtype=np.int64)
            if present.size == 0:
                return 0
            snap.index.remove_ids(present)
            for id_ in present:
                del snap.items[int(id_)]
            self._write(user_dir, snap)
        return int(present.size)

    # ---- reads ------------------------------------------------------------

    def search(self, uid: str, query: np.ndarray, k: int = 5) -> list[Hit]:
        """Top-``k`` items in ``uid``'s index by cosine similarity to ``query``.

        Returns an empty list for a user with no index yet.
        """
        if k <= 0:
            raise ValueError("k must be positive")
        query = check_normalized(query, self.dim)
        if query.shape[0] != 1:
            raise ValueError("search takes exactly one query vector")
        snap = self._load_cached(self._user_dir(uid), uid)
        return snap.search(query, k) if snap else []

    def count(self, uid: str) -> int:
        snap = self._load_cached(self._user_dir(uid), uid)
        return snap.index.ntotal if snap else 0

    # ---- internals --------------------------------------------------------

    def _user_dir(self, uid: str) -> Path:
        if not isinstance(uid, str) or not _UID_PATTERN.fullmatch(uid):
            raise ValueError("invalid user id")
        return self.root / uid

    def _lock(self, user_dir: Path) -> FileLock:
        # A new FileLock (and so a new file descriptor) per call: flock() locks
        # conflict between descriptors, so this excludes other threads in this
        # process as well as other processes.
        return FileLock(str(user_dir / LOCK_FILENAME), timeout=self.lock_timeout)

    def _read(self, user_dir: Path) -> _Snapshot | None:
        path = user_dir / INDEX_FILENAME
        try:
            with open(path, "rb") as f:
                return self._parse(f, path)
        except FileNotFoundError:
            return None

    def _parse(self, f, path: Path) -> _Snapshot:
        try:
            with np.load(f, allow_pickle=False) as data:
                version = int(data["version"])
                index_bytes = data["index"]
                items_json = data["items"].tobytes()
            if version != FORMAT_VERSION:
                raise IndexCorruptError(f"{path}: unsupported format version {version}")
            index = faiss.deserialize_index(index_bytes)
            items = {int(k): v for k, v in json.loads(items_json).items()}
        except IndexCorruptError:
            raise
        except Exception as exc:
            raise IndexCorruptError(f"{path}: cannot read index") from exc
        if index.ntotal != len(items) or index.d != self.dim:
            raise IndexCorruptError(f"{path}: index and id map disagree")
        return _Snapshot(index, items)

    def _write(self, user_dir: Path, snap: _Snapshot) -> None:
        items_json = json.dumps({str(k): v for k, v in snap.items.items()}).encode("utf-8")
        fd, tmp_path = tempfile.mkstemp(dir=user_dir, prefix=".index-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                np.savez(
                    f,
                    version=np.array(FORMAT_VERSION),
                    index=faiss.serialize_index(snap.index),
                    items=np.frombuffer(items_json, dtype=np.uint8),
                )
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, user_dir / INDEX_FILENAME)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise
        _fsync_dir(user_dir)

    def _load_cached(self, user_dir: Path, uid: str) -> _Snapshot | None:
        path = user_dir / INDEX_FILENAME
        try:
            f = open(path, "rb")
        except FileNotFoundError:
            with self._cache_lock:
                self._cache.pop(uid, None)
            return None
        with f:
            # Take the signature from the open descriptor, so it describes
            # exactly the version we are about to read even if the file is
            # replaced in the meantime.
            st = os.fstat(f.fileno())
            signature = (st.st_ino, st.st_mtime_ns, st.st_size)
            with self._cache_lock:
                entry = self._cache.get(uid)
                if entry is not None and entry.signature == signature:
                    self._cache.move_to_end(uid)
                    return entry.snapshot
            snap = self._parse(f, path)
        with self._cache_lock:
            self._cache[uid] = _CacheEntry(signature, snap)
            self._cache.move_to_end(uid)
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return snap


def _fsync_dir(path: Path) -> None:
    """Persist the rename itself, so it survives a power loss."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass  # not supported on every filesystem
    finally:
        os.close(fd)
