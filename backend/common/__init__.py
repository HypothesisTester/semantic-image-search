"""Shared core for the indexing and search services.

- clip:        CLIP encoder (images and text -> L2-normalised 512-d vectors)
- images:      decoding uploaded files into RGB images
- index_store: per-user FAISS indexes on disk, with locking and atomic writes
- auth:        Firebase ID token verification
- vectors:     normalisation and validation helpers
"""
