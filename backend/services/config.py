"""Configuration from environment variables, shared by both services."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEMO_UID = "demo"


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


@dataclass
class Settings:
    # Where indexes and photos live. In Docker this is a named volume.
    data_dir: Path = Path("/data")
    # Firebase project whose ID tokens are accepted. Required unless demo_mode.
    firebase_project_id: str | None = None
    # Browser origins allowed to call the API (the frontend's address).
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    # Public base URL for photo links, e.g. http://localhost:8001. If unset,
    # links are built from the address the request came in on.
    photos_base_url: str | None = None
    # Demo mode (search service only): no sign-in, one read-only index of COCO
    # images, whose thumbnails this service serves at /images/.
    demo_mode: bool = False
    demo_dir: Path = Path("/demo")
    max_files_per_upload: int = 50
    max_k: int = 50
    max_query_chars: int = 200

    @property
    def index_dir(self) -> Path:
        return self.demo_dir / "index" if self.demo_mode else self.data_dir / "index"

    @property
    def photos_dir(self) -> Path:
        return self.data_dir / "photos"

    @property
    def thumbnails_dir(self) -> Path:
        return self.demo_dir / "thumbnails"

    @classmethod
    def from_env(cls) -> Settings:
        demo = _flag("DEMO_MODE")
        return cls(
            data_dir=Path(os.environ.get("DATA_DIR", "/data")),
            firebase_project_id=os.environ.get("FIREBASE_PROJECT_ID") or None,
            cors_origins=_list("CORS_ORIGINS", "http://localhost:5173"),
            photos_base_url=(os.environ.get("PHOTOS_BASE_URL") or "").rstrip("/") or None,
            demo_mode=demo,
            demo_dir=Path(os.environ.get("DEMO_DIR", "/demo")),
            max_files_per_upload=int(os.environ.get("MAX_FILES_PER_UPLOAD", "50")),
            # The public demo gets a tighter cap on results per query.
            max_k=int(os.environ.get("MAX_K", "20" if demo else "50")),
            max_query_chars=int(os.environ.get("MAX_QUERY_CHARS", "200")),
        )
