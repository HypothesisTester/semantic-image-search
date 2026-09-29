# Phase 1: backend core, design decisions

The reasoning behind the shared core in `backend/common/`.

### 1. Every vector is L2-normalised, so inner product = cosine similarity
For unit vectors, `a · b = |a||b|cos θ = cos θ`. Raw CLIP outputs have a norm of about 10. After normalising, every score is a cosine similarity between -1 and 1, and a plain inner-product index does cosine search. `test_inner_product_index_equals_cosine_similarity` checks this on 200 random vectors. Non-normalised vectors are rejected on the way in instead of silently producing wrong scores.

### 2. Exact search (`IndexFlatIP`), not approximate (HNSW/IVF)
A personal library is thousands of photos. 10,000 photos × 512 floats × 4 bytes ≈ **20 MB**, and one query is about 5 million multiply-adds, roughly a millisecond. Approximate indexes trade recall for speed, which is only worth it at millions of vectors or with a tight latency budget. *When would you switch?* When one index reaches millions of vectors: then IVF or HNSW, measured against this exact index as the ground truth.

### 3. Stable hashed ids (`IndexIDMap2`)
Each photo's id is the first 63 bits of SHA-256 of its storage path. Uploading the same file twice replaces its vector instead of adding a duplicate, and removing a photo needs only its path. The chance of any collision among *n* photos is about n²/2⁶⁴ (the birthday bound): about **1 in 2 × 10¹¹** for 10,000 photos.

### 4. One file per user, swapped atomically
The index and its id → photo map live in **one** `.npz` file. A write goes to a temporary file in the same directory, is fsynced, then moved into place with `os.replace`, which is atomic on POSIX. So:
- a reader sees the whole old version or the whole new version, never an index from one version with a map from another
- a crash mid-write leaves the previous version intact (`test_a_failed_write_leaves_the_previous_version_intact` simulates exactly this)

### 5. A per-user lock around every update
An upload is **read → modify → write**. Without a lock, two overlapping uploads for one user both read version N, and the second write discards the first upload's photos: a *lost update*. `test_without_the_lock_an_overlapping_upload_is_lost` reproduces the bug (2 uploads, only 1 survives). `test_with_the_lock_both_overlapping_uploads_survive` shows the fix (both survive).
- **Per user, not global:** uploads from different users never wait for each other.
- **A file lock (`flock`), not `threading.Lock`:** it also works across processes, so several indexer workers can share one volume. Tested with 8 threads and with 4 separate processes.
- **Readers take no lock:** the atomic swap in (4) already guarantees they see a consistent version.

### 6. The search service caches indexes, and notices new uploads
Loading an index on every query would waste time, so recently used indexes stay in memory (LRU, 64 users). Before each search the file is `stat`ed: if its (inode, mtime, size) changed, it is reloaded. `os.replace` always produces a new inode, so a new version is never missed. Writers never modify a cached index; they always work on a fresh copy from disk. FAISS allows concurrent searches on one index from many threads.

### 7. The user id comes from the verified token, never the request body
The old backend trusted `userId` in the request body, so anyone could search anyone's photos. Now the service verifies the Firebase ID token and uses its `sub` claim. Verification follows Firebase's documented checks: RS256 signature by a known Google key, `exp`/`iat`, `aud` = project id, `iss` = `https://securetoken.google.com/<project>`, non-empty `sub`, and `auth_time` in the past. It needs **no service-account key**, only Google's public certificates, which are cached per their `Cache-Control` header. If a refresh fails, the previous certificates keep being used. The tests use their own RSA key and cover each failure case, including a forged payload and an unsigned (`alg: none`) token.

### 8. Image decoding details that affect search quality
- **EXIF orientation:** phones store portrait photos sideways plus a "rotate me" tag. CLIP never sees the tag, so we rotate first; otherwise portraits are embedded lying on their side.
- **Transparency on white:** a plain RGB conversion turns transparent pixels black.
- **JPEG draft decoding:** CLIP only needs 224×224. A 4000×3000 JPEG is decoded directly at 1000×750, **16× fewer pixels**, which speeds up indexing.
- **Limits:** a 50 MB file cap and Pillow's decompression-bomb check, so a tiny file claiming to be a gigapixel image is rejected.
- **HEIC** (the iPhone default) via `pillow-heif`; **DNG** via optional `rawpy`, with a clear error if it's missing.

### 9. torch is optional for everything except the encoder
torch and open_clip are imported only when an encoder is created, so the index, auth and image code (and their tests) run without a 2 GB dependency. The search service can load CLIP with `towers="text"` and drop the image half, since it only ever embeds text.

---

## Known limits (deliberate for now)
- **Single machine.** The lock and atomic rename need all writers on one filesystem. In Phase 3 that's a Docker *named* volume. Across machines you'd use object storage with conditional writes (e.g. GCS generation preconditions) instead.
- No delete-photo endpoint yet (`IndexStore.remove` exists for when there is one).
