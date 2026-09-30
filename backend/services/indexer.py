"""Indexing service: accepts photo uploads and adds them to the user's index.

    POST /upload                                 multipart, field "files", Bearer token
    GET  /photos/<uid>/<id>/<display|thumb>.jpg  the stored renditions
    GET  /healthz

For each uploaded file, in order:
    1. decode it (any supported format) into an upright RGB image
    2. store the original plus JPEG display and thumbnail copies
    3. embed all the photos in the request in one batch with CLIP
    4. add the vectors to the user's index, in one locked update

The index is updated last, so every search result points at files that
already exist. A file that fails to decode is reported and skipped; the rest
of the request still succeeds. Re-uploading a photo is harmless: its id
comes from its content, so it replaces its own entry.
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import PurePath

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile

from common.images import MAX_BYTES, ImageDecodeError, decode_image
from common.index_store import IndexStore
from common.photo_store import PhotoStore

from .config import Settings
from .web import add_common_routes, add_photo_routes, base_url, current_uid_dependency, make_verifier

log = logging.getLogger("indexer")


def create_app(settings: Settings | None = None, *, encoder=None, verifier=None) -> FastAPI:
    settings = settings or Settings.from_env()
    index = IndexStore(settings.index_dir)
    photos = PhotoStore(settings.photos_dir)
    # One shared model; requests take turns using it. Handlers run in a
    # thread pool, so waiting on this lock never blocks the event loop.
    model_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if encoder is None:
            from common.clip import ClipEncoder

            app.state.encoder = ClipEncoder()
        else:
            app.state.encoder = encoder
        app.state.verifier = verifier or make_verifier(settings)
        yield

    app = FastAPI(title="Semantic Image Search: indexer", lifespan=lifespan)
    add_common_routes(app, settings)
    add_photo_routes(app, photos)
    current_uid = current_uid_dependency(lambda: app.state.verifier)

    @app.post("/upload")
    def upload(
        request: Request,
        files: list[UploadFile] = File(...),
        uid: str = Depends(current_uid),
    ) -> dict:
        if len(files) > settings.max_files_per_upload:
            raise HTTPException(
                status_code=413,
                detail=f"at most {settings.max_files_per_upload} files per upload",
            )
        start = time.perf_counter()
        results: list[dict] = []
        accepted = []  # (position in results, stored photo, decoded image)

        for upload_file in files:
            name = PurePath(upload_file.filename or "upload").name
            # Read one byte past the limit, so oversized files are caught
            # without reading the whole thing into memory.
            data = upload_file.file.read(MAX_BYTES + 1)
            try:
                image = decode_image(data, filename=name)
            except ImageDecodeError as exc:
                results.append({"filename": name, "ok": False, "error": str(exc)})
                continue
            stored = photos.save(uid, data, name, image)
            accepted.append((len(results), stored, image))
            results.append({})

        added = updated = 0
        if accepted:
            with model_lock:
                vectors = app.state.encoder.encode_images([image for _, _, image in accepted])
            outcome = index.add(
                uid,
                [stored.key for _, stored, _ in accepted],
                vectors,
                metas=[
                    {
                        "url": stored.path("display"),
                        "thumbnail": stored.path("thumb"),
                        "filename": stored.filename,
                    }
                    for _, stored, _ in accepted
                ],
            )
            added, updated = outcome.added, outcome.updated

        base = base_url(settings, request)
        for position, stored, _ in accepted:
            results[position] = {
                "filename": stored.filename,
                "ok": True,
                "id": stored.photo_id,
                "url": base + stored.path("display"),
                "thumbnailUrl": base + stored.path("thumb"),
            }
        failed = len(files) - len(accepted)
        log.info(
            "upload uid=%s files=%d added=%d updated=%d failed=%d in %.0f ms",
            uid, len(files), added, updated, failed, (time.perf_counter() - start) * 1000,
        )
        return {"added": added, "updated": updated, "failed": failed, "results": results}

    return app
