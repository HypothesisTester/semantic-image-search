# Phase 3: services and Docker, design decisions

The reasoning behind `backend/services/`, `common/photo_store.py`, the Dockerfile and `docker-compose.yml`.

### 1. Two services, split by workload
- The **indexer** does the heavy, bursty work: decoding photos and running CLIP's image encoder. An upload of 50 photos can take seconds of CPU.
- The **search** service does light, latency-sensitive work: one text embedding and one index lookup, about 9 ms.

Kept apart, a big upload never slows anyone's search, and each can be sized on its own: the search service loads only CLIP's text encoder. They share nothing but the data volume, which the search service mounts **read-only**, so it cannot corrupt an index even if it has a bug.

### 2. Uploads go straight to the indexer
The original design uploaded photos to Firebase Storage, then sent the indexer their URLs to download. New Firebase projects need the paid plan for Storage, and fetching arbitrary URLs from a server is a server-side request forgery risk. The frontend now posts the files directly (multipart), and the indexer stores them itself. Firestore still holds the gallery's metadata.

### 3. Order of work in an upload: files first, index last
Each upload decodes every file, stores it, embeds all accepted photos in **one batch**, then updates the index in **one locked write**. Because the index changes last, every search result points at files that already exist. A file that fails to decode is reported in the response and skipped; the rest of the upload still succeeds.

### 4. Content-derived photo ids make uploads idempotent
A photo's id is the first 128 bits of SHA-256(user id, file bytes). Uploading the same photo again (a retry after a timeout, or a duplicate in the camera roll) lands on the same id, so it replaces its own files and index entry instead of creating a copy. The smoke test checks this against the real stack.

### 5. Photos are served by capability URL
`<img>` tags cannot send an Authorization header, so the unguessable URL is the permission, the same model as Firebase Storage download links. 128 random-looking bits cannot be guessed. Content-derived ids mean a URL always serves the same bytes, so responses are marked `immutable` and browsers cache them indefinitely. The stronger option would be short-lived signed URLs, which can also be revoked; that is not needed here.

### 6. Only clean copies are served
Each upload keeps its original bytes untouched, and makes two JPEGs from the decoded image: a display copy (at most 2048 px) and a thumbnail (384 px). Only the JPEGs are served, because:
- HEIC and DNG do not display in most browsers
- phone photos carry EXIF metadata, often including **GPS coordinates**, and the re-encoded copies contain none (a test checks a photo tagged with a location)

URL parts are validated against strict patterns before touching the filesystem, so a crafted URL cannot read outside the photo folder.

### 7. The user comes from the token, never the request
Both services take the user id from the verified Firebase token. A `userId` in the request body (which the old frontend sent) is ignored; a test sends one claiming to be someone else and gets nothing back.

### 8. One model per process, used in turn
Each service holds one CLIP model, and requests take turns using it via a lock. Several simultaneous inferences on one CPU gain nothing and multiply memory use. FastAPI runs these handlers in a thread pool, so waiting on the lock never blocks the server from accepting other requests.

### 9. Demo mode is configuration, not a separate app
`DEMO_MODE=1` on the search service removes sign-in, points it at the read-only COCO index, and serves the COCO thumbnails. The public demo therefore runs the same search code path as a signed-in user, with a lower cap on results per query (20).

### 10. The Docker image
- **CPU-only PyTorch**, installed in its own cached layer. The default Linux build bundles several GB of CUDA libraries a CPU container never uses.
- **Model weights baked into the image**, and downloads disabled at runtime, so a container starts offline and never fetches 350 MB on boot.
- **Non-root user** and a health check.
- **One image, two services**: `APP` selects which one a container runs.
- **Proxy-aware links**: behind a reverse proxy, photo links are built from the public `https` address. For hosts that don't forward the public hostname, `PHOTOS_BASE_URL` sets it explicitly.
- **A named volume** for the data, not a host folder: it lives in Docker's Linux VM, where the index store's file locks work as on any Linux disk (Phase 1, known limits).

### Known limits
- No deleting photos yet (`IndexStore.remove` exists for it).
- DNG uploads need the optional `rawpy`, which the Docker image leaves out; they are rejected with a clear message.
- No rate limiting on the public demo beyond the per-query caps.
