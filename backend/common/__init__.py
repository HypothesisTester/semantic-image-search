"""Shared core for the indexing and search services.

- clip:        CLIP encoder (images and text -> L2-normalised 512-d vectors)
- images:      decoding uploaded files into RGB images
- index_store: per-user FAISS indexes on disk, with locking and atomic writes
- auth:        Firebase ID token verification
- vectors:     normalisation and validation helpers
"""

import os
import sys

if sys.platform == "darwin":
    # On macOS, the PyTorch and faiss-cpu wheels each bundle their own copy of
    # the OpenMP runtime (libomp). When both are loaded into one process, the
    # second copy to start aborts the program ("OMP: Error #15"). This setting
    # lets the second copy start. It must be set before either library starts
    # OpenMP, which is why it lives here: every entry point imports `common`
    # first. Linux builds (the Docker images) share one runtime and never
    # need it.
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
