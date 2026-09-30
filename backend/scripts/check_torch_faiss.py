"""Check which setup lets PyTorch and FAISS run together in one process.

On macOS the pip wheels of torch and faiss-cpu each bundle their own OpenMP
runtime, which can crash the process. This script runs the same workload
under several candidate fixes, each in a fresh subprocess, and reports which
ones finish AND return correct results.

    python scripts/check_torch_faiss.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

WORKLOAD = textwrap.dedent(
    """
    import os, sys, threading
    FAISS_FIRST = os.environ["CHECK_FAISS_FIRST"] == "1"
    SINGLE_THREAD = os.environ["CHECK_FAISS_ONE_THREAD"] == "1"

    if FAISS_FIRST:
        import faiss
    import torch
    import numpy as np
    if not FAISS_FIRST:
        import faiss
    if SINGLE_THREAD:
        faiss.omp_set_num_threads(1)

    # Start torch's CPU thread pool the way CLIP does.
    x = torch.randn(512, 512)
    (x @ x).sum().item()
    torch.nn.functional.conv2d(torch.randn(8, 3, 224, 224), torch.randn(16, 3, 3, 3)).sum().item()

    rng = np.random.default_rng(0)
    X = rng.standard_normal((5000, 512)).astype("float32")
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    index = faiss.IndexIDMap2(faiss.IndexFlatIP(512))
    index.add_with_ids(X, np.arange(5000, dtype="int64"))

    # Correctness against plain numpy, single and batched queries.
    for q in range(50):
        D, I = index.search(X[q:q + 1], 5)
        expected = np.argsort(-(X @ X[q]))[:5]
        assert list(I[0]) == list(expected), "wrong results (single query)"
    D, I = index.search(X[:100], 5)
    assert (I[:, 0] == np.arange(100)).all(), "wrong results (batch)"

    # Save/load round trip, as the index store does.
    loaded = faiss.deserialize_index(faiss.serialize_index(index))
    D2, I2 = loaded.search(X[:100], 5)
    assert (I2 == I).all(), "wrong results after reload"

    # Concurrent searches from several threads, as the search service does.
    errors = []
    def worker(seed):
        try:
            for q in range(seed, 5000, 97):
                _, ids = loaded.search(X[q:q + 1], 1)
                assert ids[0][0] == q
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=worker, args=(s,)) for s in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert not errors, errors

    # torch again after FAISS has run.
    (x @ x).sum().item()
    print("OK")
    """
)

VARIANTS = [
    # name, env overrides, faiss imported first, faiss single-threaded
    ("baseline (no fix)", {}, False, False),
    ("KMP_DUPLICATE_LIB_OK", {"KMP_DUPLICATE_LIB_OK": "TRUE"}, False, False),
    ("KMP + import faiss first", {"KMP_DUPLICATE_LIB_OK": "TRUE"}, True, False),
    ("KMP + faiss 1 thread", {"KMP_DUPLICATE_LIB_OK": "TRUE"}, False, True),
    ("KMP + faiss first + 1 thread", {"KMP_DUPLICATE_LIB_OK": "TRUE"}, True, True),
    ("KMP + OMP_NUM_THREADS=1", {"KMP_DUPLICATE_LIB_OK": "TRUE", "OMP_NUM_THREADS": "1"}, False, False),
    ("import faiss first (no KMP)", {}, True, False),
]


def main() -> None:
    print(f"python {sys.version.split()[0]} on {sys.platform}")
    base_env = {k: v for k, v in os.environ.items() if k not in ("KMP_DUPLICATE_LIB_OK", "OMP_NUM_THREADS")}
    for name, extra, faiss_first, one_thread in VARIANTS:
        env = dict(base_env, **extra)
        env["CHECK_FAISS_FIRST"] = "1" if faiss_first else "0"
        env["CHECK_FAISS_ONE_THREAD"] = "1" if one_thread else "0"
        try:
            proc = subprocess.run(
                [sys.executable, "-c", WORKLOAD],
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            print(f"  HANG     {name}")
            continue
        if proc.returncode == 0 and proc.stdout.strip().endswith("OK"):
            print(f"  OK       {name}")
        else:
            detail = (proc.stderr.strip().splitlines() or ["(no output)"])[-1][:100]
            print(f"  FAIL {proc.returncode:>3} {name}: {detail}")


if __name__ == "__main__":
    main()
