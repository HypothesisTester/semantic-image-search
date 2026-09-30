"""Search service: finds a user's photos from a text description.

    POST /search    {"text": "dog on a beach", "k": 5}, Bearer token
                 -> {"results": [{"rank", "score", "url", "thumbnailUrl", ...}]}
    GET  /photos/<uid>/<id>/<display|thumb>.jpg   (reads the same volume as the indexer)
    GET  /healthz

Demo mode (DEMO_MODE=1) is the same code with three differences: no sign-in,
a single read-only index of COCO images under the user id "demo", and the
COCO thumbnails served at /images/. The public demo therefore exercises the
real search path, not a copy of it.

Only CLIP's text encoder is loaded, since this service never embeds images.
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from common.index_store import IndexStore
from common.photo_store import PhotoStore

from .config import DEMO_UID, Settings
from .web import add_common_routes, add_photo_routes, base_url, current_uid_dependency, make_verifier

log = logging.getLogger("search")


class SearchRequest(BaseModel):
    # Other fields (such as the old frontend's "userId") are ignored: the
    # user always comes from the sign-in token.
    text: str
    k: int = 5


def create_app(settings: Settings | None = None, *, encoder=None, verifier=None) -> FastAPI:
    settings = settings or Settings.from_env()
    index = IndexStore(settings.index_dir)
    model_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if encoder is None:
            from common.clip import ClipEncoder

            app.state.encoder = ClipEncoder(towers="text")
        else:
            app.state.encoder = encoder
        if not settings.demo_mode:
            app.state.verifier = verifier or make_verifier(settings)
        yield

    app = FastAPI(title="Semantic Image Search: search", lifespan=lifespan)
    add_common_routes(app, settings)

    if settings.demo_mode:

        def current_uid() -> str:
            return DEMO_UID

        app.mount("/images", StaticFiles(directory=settings.thumbnails_dir), name="images")

        @app.get("/browse")
        def browse(
            request: Request,
            offset: int = Query(0, ge=0),
            limit: int = Query(24, ge=1, le=60),
        ) -> dict:
            """A page of the demo's photos, for the landing page. Demo mode only:
            signed-in users browse their own library from the frontend's records."""
            total, page = index.list_items(DEMO_UID, offset=offset, limit=limit)
            base = base_url(settings, request)
            return {
                "total": total,
                "items": [
                    {
                        "url": base + meta["url"],
                        "thumbnailUrl": base + meta.get("thumbnail", meta["url"]),
                        **({"caption": meta["caption"]} if meta.get("caption") else {}),
                    }
                    for _, meta in page
                ],
            }
    else:
        current_uid = current_uid_dependency(lambda: app.state.verifier)
        add_photo_routes(app, PhotoStore(settings.photos_dir))

    @app.post("/search")
    def search(body: SearchRequest, request: Request, uid: str = Depends(current_uid)) -> dict:
        text = " ".join(body.text.split())
        if not text:
            raise HTTPException(status_code=422, detail="text must not be empty")
        if len(text) > settings.max_query_chars:
            raise HTTPException(
                status_code=422, detail=f"text must be at most {settings.max_query_chars} characters"
            )
        if body.k < 1:
            raise HTTPException(status_code=422, detail="k must be at least 1")
        k = min(body.k, settings.max_k)

        with model_lock:
            query = app.state.encoder.encode_texts([text])
        hits = index.search(uid, query, k=k)

        base = base_url(settings, request)
        return {
            "results": [
                {
                    "rank": hit.rank,
                    "score": round(hit.score, 4),
                    "url": base + hit.meta["url"],
                    "thumbnailUrl": base + hit.meta.get("thumbnail", hit.meta["url"]),
                    **({"caption": hit.meta["caption"]} if hit.meta.get("caption") else {}),
                }
                for hit in hits
            ]
        }

    return app
