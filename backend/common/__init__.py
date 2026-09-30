"""Shared core for the indexing and search services.

- clip:        CLIP encoder (images and text -> L2-normalised 512-d vectors)
- images:      decoding uploaded files into RGB images
- index_store: per-user FAISS indexes on disk, with locking and atomic writes
- auth:        Firebase ID token verification
- vectors:     normalisation and validation helpers
"""

import os
import sys
import warnings

if sys.platform == "darwin":
    # On macOS, the PyTorch and faiss-cpu wheels each bundle their own copy of
    # the OpenMP runtime (libomp). Loaded into one process, they crash it:
    # with no fix the second copy aborts ("OMP: Error #15"); allowing the
    # duplicate still segfaults once both run worker threads. The only
    # combination that runs correctly (see scripts/check_torch_faiss.py) is
    # allowing the duplicate AND limiting OpenMP to one thread, so the two
    # runtimes never run threads at the same time.
    #
    # Cost: CPU-side torch and FAISS work runs on one core on a Mac. CLIP runs
    # on the Apple GPU (MPS) there, and exact search over a personal library
    # takes about a millisecond on one core, so this barely matters. Linux
    # builds (the Docker images, the public demo) share one OpenMP runtime
    # and are not affected.
    #
    # Both must be set before either library starts OpenMP, which is why this
    # lives in the package __init__: every entry point imports `common` first.
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    if "torch" in sys.modules or "faiss" in sys.modules:
        warnings.warn(
            "import `common` before torch/faiss on macOS, or they may crash the process",
            RuntimeWarning,
            stacklevel=2,
        )
