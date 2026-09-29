"""CLIP encoder: maps images and text into one shared 512-dimensional space.

Both services use this module, so image vectors (made by the indexer) and text
vectors (made by the search service) always come from the same weights, the
same preprocessing and the same normalisation. If they ever differed, scores
would be meaningless without any error being raised.

torch and open_clip are imported lazily so that the rest of the backend, and
its tests, work without them installed.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from typing import Literal, Protocol

import numpy as np
from PIL import Image

from .vectors import l2_normalize

MODEL_NAME = "ViT-B-32-quickgelu"
# "openai" selects the original OpenAI CLIP weights. OpenAI trained with the
# QuickGELU activation, so the model config must use it too: the plain
# "ViT-B-32" config uses standard GELU, which still runs but produces
# slightly wrong vectors (open_clip warns "QuickGELU mismatch").
PRETRAINED = "openai"
EMBED_DIM = 512

Towers = Literal["both", "text"]


class Encoder(Protocol):
    """Anything that turns images and text into normalised vectors of size ``dim``."""

    dim: int

    def encode_images(self, images: Sequence[Image.Image]) -> np.ndarray: ...

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray: ...


class ClipEncoder:
    """open_clip wrapper returning L2-normalised float32 numpy arrays of shape (n, dim).

    ``towers="text"`` drops the image encoder after loading. The search service
    only ever embeds text, so this saves memory there.
    ``pretrained=None`` builds the model with random weights, which is useful
    for testing the code path without downloading anything.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        pretrained: str | None = PRETRAINED,
        *,
        towers: Towers = "both",
        device: str | None = None,
        batch_size: int = 32,
        cache_dir: str | None = None,
    ) -> None:
        import open_clip
        import torch

        self._torch = torch
        self.device = device or os.environ.get("SIS_DEVICE") or _pick_device(torch)
        self.batch_size = batch_size

        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name,
            pretrained=pretrained,
            device=self.device,
            cache_dir=cache_dir,
        )
        model.eval()
        if towers == "text":
            model.visual = None
        self._model = model
        self._preprocess = preprocess
        self._tokenizer = open_clip.get_tokenizer(model_name)
        self.dim = int(open_clip.get_model_config(model_name)["embed_dim"])

    def encode_images(self, images: Sequence[Image.Image]) -> np.ndarray:
        if self._model.visual is None:
            raise RuntimeError("this encoder was loaded with towers='text'")
        torch = self._torch
        chunks = []
        for batch in _batches(images, self.batch_size):
            pixels = torch.stack([self._preprocess(img) for img in batch]).to(self.device)
            with torch.inference_mode():
                features = self._model.encode_image(pixels)
            chunks.append(features.float().cpu().numpy())
        return self._finish(chunks)

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        torch = self._torch
        chunks = []
        for batch in _batches(texts, self.batch_size):
            tokens = self._tokenizer(list(batch)).to(self.device)
            with torch.inference_mode():
                features = self._model.encode_text(tokens)
            chunks.append(features.float().cpu().numpy())
        return self._finish(chunks)

    def _finish(self, chunks: list[np.ndarray]) -> np.ndarray:
        if not chunks:
            return np.empty((0, self.dim), dtype=np.float32)
        return l2_normalize(np.concatenate(chunks))


def _pick_device(torch) -> str:
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"  # Apple Silicon GPU
    return "cpu"


def _batches(items: Sequence, size: int) -> Iterator[Sequence]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
