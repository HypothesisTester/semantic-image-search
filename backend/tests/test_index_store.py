import multiprocessing as mp
import os
import threading

import numpy as np
import pytest

from common import index_store as index_store_module
from common.index_store import INDEX_FILENAME, IndexCorruptError, IndexStore, item_id
from tests import helpers
from tests.helpers import unit_vectors

UID = "userA"


@pytest.fixture
def store(tmp_path):
    return IndexStore(tmp_path)


def keys(n, prefix="img"):
    return [f"user-images/{UID}/{prefix}{i}.jpg" for i in range(n)]


# ---- basic behaviour --------------------------------------------------------


def test_search_finds_the_exact_vector_first(store):
    vectors = unit_vectors(50, seed=1)
    store.add(UID, keys(50), vectors, metas=[{"url": f"u{i}"} for i in range(50)])

    hits = store.search(UID, vectors[17], k=3)

    assert [h.rank for h in hits] == [1, 2, 3]
    assert hits[0].key == keys(50)[17]
    assert hits[0].meta == {"url": "u17"}
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)
    assert hits[0].score >= hits[1].score >= hits[2].score


def test_k_larger_than_index_returns_everything(store):
    store.add(UID, keys(3), unit_vectors(3, seed=2))
    assert len(store.search(UID, unit_vectors(1, seed=3), k=10)) == 3


def test_unknown_user_gets_no_results(store):
    assert store.search("nobody", unit_vectors(1, seed=0), k=5) == []
    assert store.count("nobody") == 0


def test_rejects_unnormalised_vectors(store):
    with pytest.raises(ValueError, match="normalised"):
        store.add(UID, ["a"], np.ones((1, 512), dtype=np.float32))


def test_rejects_bad_k_and_mismatched_lengths(store):
    with pytest.raises(ValueError):
        store.search(UID, unit_vectors(1, seed=0), k=0)
    with pytest.raises(ValueError, match="keys but"):
        store.add(UID, ["a", "b"], unit_vectors(1, seed=0))


# ---- incremental updates ---------------------------------------------------


def test_incremental_adds_match_a_full_rebuild(tmp_path):
    vectors = unit_vectors(300, seed=4)
    all_keys = keys(300)

    incremental = IndexStore(tmp_path / "incremental")
    for start in range(0, 300, 37):  # uneven batches on purpose
        incremental.add(UID, all_keys[start : start + 37], vectors[start : start + 37])

    rebuilt = IndexStore(tmp_path / "rebuilt")
    rebuilt.add(UID, all_keys, vectors)

    for query in unit_vectors(20, seed=5):
        a = incremental.search(UID, query, k=10)
        b = rebuilt.search(UID, query, k=10)
        assert [h.key for h in a] == [h.key for h in b]
        np.testing.assert_allclose([h.score for h in a], [h.score for h in b], atol=1e-6)


def test_re_adding_a_key_replaces_it_instead_of_duplicating(store):
    first, second = unit_vectors(2, seed=6)
    store.add(UID, ["photo.jpg"], first[None, :], metas=[{"v": 1}])
    result = store.add(UID, ["photo.jpg"], second[None, :], metas=[{"v": 2}])

    assert (result.added, result.updated) == (0, 1)
    assert store.count(UID) == 1
    hit = store.search(UID, second, k=1)[0]
    assert hit.meta == {"v": 2} and hit.score == pytest.approx(1.0, abs=1e-5)


def test_duplicate_keys_in_one_batch_keep_the_last(store):
    vectors = unit_vectors(2, seed=7)
    result = store.add(UID, ["same.jpg", "same.jpg"], vectors, metas=[{"v": 1}, {"v": 2}])
    assert result.added == 1 and store.count(UID) == 1
    assert store.search(UID, vectors[1], k=1)[0].meta == {"v": 2}


def test_remove(store):
    store.add(UID, keys(5), unit_vectors(5, seed=8))
    assert store.remove(UID, [keys(5)[0], keys(5)[1], "not-there.jpg"]) == 2
    assert store.count(UID) == 3
    assert store.remove("nobody", ["x"]) == 0


def test_list_items_pages_in_key_order(store):
    store.add(UID, ["c.jpg", "a.jpg", "b.jpg"], unit_vectors(3, seed=20), metas=[{"n": c} for c in "cab"])
    total, page = store.list_items(UID, offset=0, limit=2)
    assert total == 3 and [k for k, _ in page] == ["a.jpg", "b.jpg"]
    assert store.list_items(UID, offset=2, limit=2)[1] == [("c.jpg", {"n": "c"})]
    assert store.list_items("nobody") == (0, [])
    with pytest.raises(ValueError):
        store.list_items(UID, limit=0)


def test_list_items_sees_new_additions(tmp_path):
    reader, writer = IndexStore(tmp_path), IndexStore(tmp_path)
    writer.add(UID, ["b.jpg"], unit_vectors(1, seed=21))
    assert reader.list_items(UID)[0] == 1
    writer.add(UID, ["a.jpg"], unit_vectors(1, seed=22))
    assert [k for k, _ in reader.list_items(UID)[1]] == ["a.jpg", "b.jpg"]


def test_item_ids_are_stable_and_non_negative():
    assert item_id("a/b.jpg") == item_id("a/b.jpg")
    assert item_id("a/b.jpg") != item_id("a/c.jpg")
    assert all(0 <= item_id(f"k{i}") < 2**63 for i in range(1000))


# ---- isolation and safety --------------------------------------------------


def test_users_are_isolated(tmp_path):
    store = IndexStore(tmp_path)
    a_vectors = unit_vectors(10, seed=9)
    store.add("alice", [f"alice/{i}" for i in range(10)], a_vectors)
    store.add("bob", [f"bob/{i}" for i in range(10)], unit_vectors(10, seed=10))

    hits = store.search("bob", a_vectors[0], k=20)  # Alice's photo as Bob's query
    assert len(hits) == 10
    assert all(h.key.startswith("bob/") for h in hits)


@pytest.mark.parametrize("bad_uid", ["", "../etc", "a/b", "a b", "x" * 129, "..", "é"])
def test_invalid_user_ids_are_rejected(store, bad_uid):
    with pytest.raises(ValueError, match="invalid user id"):
        store.add(bad_uid, ["k"], unit_vectors(1, seed=0))
    with pytest.raises(ValueError, match="invalid user id"):
        store.search(bad_uid, unit_vectors(1, seed=0))


def test_index_survives_a_restart(tmp_path):
    vectors = unit_vectors(20, seed=11)
    IndexStore(tmp_path).add(UID, keys(20), vectors)

    fresh = IndexStore(tmp_path)
    assert fresh.count(UID) == 20
    assert fresh.search(UID, vectors[3], k=1)[0].key == keys(20)[3]


def test_a_failed_write_leaves_the_previous_version_intact(tmp_path, monkeypatch):
    store = IndexStore(tmp_path)
    store.add(UID, keys(5), unit_vectors(5, seed=12))

    def crash(*args, **kwargs):
        raise OSError("simulated crash during write")

    monkeypatch.setattr(index_store_module.os, "replace", crash)
    with pytest.raises(OSError, match="simulated crash"):
        store.add(UID, ["new.jpg"], unit_vectors(1, seed=13))
    monkeypatch.undo()

    assert IndexStore(tmp_path).count(UID) == 5
    leftovers = [p for p in os.listdir(tmp_path / UID) if p.endswith(".tmp")]
    assert leftovers == []


def test_a_corrupt_index_file_raises_a_clear_error(tmp_path):
    (tmp_path / UID).mkdir()
    (tmp_path / UID / INDEX_FILENAME).write_bytes(b"not an index")
    with pytest.raises(IndexCorruptError):
        IndexStore(tmp_path).search(UID, unit_vectors(1, seed=0))


# ---- caching between separate processes/services ---------------------------


def test_reader_sees_new_uploads_without_restarting(tmp_path):
    # Two separate stores stand in for the search service (reader) and the
    # indexer (writer): they share nothing except the directory.
    reader, writer = IndexStore(tmp_path), IndexStore(tmp_path)
    vectors = unit_vectors(2, seed=14)

    writer.add(UID, ["first.jpg"], vectors[:1])
    assert [h.key for h in reader.search(UID, vectors[1], k=5)] == ["first.jpg"]  # now cached

    writer.add(UID, ["second.jpg"], vectors[1:])
    assert reader.search(UID, vectors[1], k=1)[0].key == "second.jpg"


def test_reader_cache_is_reused_when_nothing_changed(tmp_path, monkeypatch):
    store = IndexStore(tmp_path)
    store.add(UID, keys(3), unit_vectors(3, seed=15))
    store.search(UID, unit_vectors(1, seed=16))

    calls = []
    original = IndexStore._parse
    monkeypatch.setattr(IndexStore, "_parse", lambda self, *a: calls.append(1) or original(self, *a))
    for _ in range(5):
        store.search(UID, unit_vectors(1, seed=16))
    assert calls == []


# ---- concurrency -----------------------------------------------------------


def test_concurrent_threads_lose_no_updates(tmp_path):
    store = IndexStore(tmp_path)
    vectors = unit_vectors(80, seed=17)

    def worker(w):
        for i in range(10):
            row = w * 10 + i
            store.add(UID, [f"t{w}/{i}.jpg"], vectors[row : row + 1])

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert IndexStore(tmp_path).count(UID) == 80


def test_concurrent_processes_lose_no_updates(tmp_path):
    ctx = mp.get_context("spawn")  # the default on macOS; also safe with FAISS
    procs = [
        ctx.Process(target=helpers.add_one_at_a_time, args=(str(tmp_path), UID, w, 15))
        for w in range(4)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=120)
        assert p.exitcode == 0

    assert IndexStore(tmp_path).count(UID) == 60


def _race_two_writers(tmp_path, locked):
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(2)
    procs = [
        ctx.Process(
            target=helpers.add_after_barrier,
            args=(locked, str(tmp_path), UID, f"upload{n}.jpg", n, barrier),
        )
        for n in range(2)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=120)
        assert p.exitcode == 0
    return IndexStore(tmp_path).count(UID)


def test_without_the_lock_an_overlapping_upload_is_lost(tmp_path):
    # Demonstrates the bug the lock exists to prevent. Both writers read the
    # same (empty) version, then each writes a version with only its own photo.
    assert _race_two_writers(tmp_path, locked=False) == 1


def test_with_the_lock_both_overlapping_uploads_survive(tmp_path):
    assert _race_two_writers(tmp_path, locked=True) == 2
