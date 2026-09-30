"""Stand-ins for CLIP and Firebase, so the services can be tested without either.

FakeEncoder puts an image's average colour and a colour word from the query
into the same space, so "a red photo" really does find the red image:
search behaviour can be checked, not just status codes.
"""

from __future__ import annotations

import numpy as np

from common.auth import AuthError
from common.vectors import l2_normalize

DIM = 512
COLOURS = {
    "red": (255, 0, 0),
    "green": (0, 160, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "white": (255, 255, 255),
    "black": (0, 0, 0),
}


def _colour_vector(rgb) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    v[:3] = np.asarray(rgb, dtype=np.float32) / 255.0 - 0.5  # centred, so black != white
    v[3] = 0.05  # never exactly zero
    return v


class FakeEncoder:
    dim = DIM

    def __init__(self) -> None:
        self.image_calls = 0
        self.text_calls = 0

    def encode_images(self, images):
        self.image_calls += 1
        rows = [_colour_vector(np.asarray(img.convert("RGB")).reshape(-1, 3).mean(axis=0)) for img in images]
        return l2_normalize(np.stack(rows)) if rows else np.empty((0, DIM), np.float32)

    def encode_texts(self, texts):
        self.text_calls += 1
        rows = []
        for text in texts:
            rgb = next((c for name, c in COLOURS.items() if name in text.lower()), (128, 128, 128))
            rows.append(_colour_vector(rgb))
        return l2_normalize(np.stack(rows))


class FakeVerifier:
    """Accepts "Bearer token-<uid>"; anything else is rejected, like a bad Firebase token."""

    def uid_from_header(self, authorization):
        if not authorization or not authorization.startswith("Bearer token-"):
            raise AuthError("invalid token")
        return authorization.removeprefix("Bearer token-")


def auth(uid: str) -> dict:
    return {"Authorization": f"Bearer token-{uid}"}
