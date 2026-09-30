"""Pieces both services share: sign-in checks, CORS, health check, URL building."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from common.auth import AuthError, FirebaseTokenVerifier
from common.photo_store import PhotoStore

from .config import Settings

# Anything with uid_from_header(header) -> uid; tests pass a fake.
Verifier = FirebaseTokenVerifier


def make_verifier(settings: Settings) -> Verifier:
    if not settings.firebase_project_id:
        raise RuntimeError("FIREBASE_PROJECT_ID must be set (or DEMO_MODE=1 for the search service)")
    return FirebaseTokenVerifier(settings.firebase_project_id)


def current_uid_dependency(get_verifier: Callable[[], Verifier]):
    """A FastAPI dependency returning the signed-in user's id from the Bearer token.

    The user id always comes from the verified token. A ``userId`` sent in the
    request body is ignored, so nobody can act as another user.
    """

    def current_uid(authorization: str | None = Header(default=None)) -> str:
        try:
            return get_verifier().uid_from_header(authorization)
        except AuthError as exc:
            raise HTTPException(
                status_code=401,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    return current_uid


def add_common_routes(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}


def base_url(settings: Settings, request: Request) -> str:
    """Base for absolute photo links: the configured public URL, else this request's origin."""
    return settings.photos_base_url or str(request.base_url).rstrip("/")


def add_photo_routes(app: FastAPI, photos: PhotoStore) -> None:
    """GET /photos/<uid>/<photo_id>/<display|thumb>.jpg

    No sign-in check: <img> tags cannot send one, so the unguessable URL is
    the permission (see common.photo_store). Photo ids are derived from the
    content, so a URL always serves the same bytes and browsers may cache it
    forever.
    """

    @app.get("/photos/{uid}/{pid}/{variant}.jpg")
    def photo(uid: str, pid: str, variant: str) -> FileResponse:
        path = photos.file_for(uid, pid, variant)
        if path is None:
            raise HTTPException(status_code=404, detail="photo not found")
        return FileResponse(
            path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )
