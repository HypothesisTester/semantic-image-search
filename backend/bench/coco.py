"""Where the benchmark data lives, and how to read the COCO captions file."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# <repo>/data, which .gitignore excludes. backend/bench/coco.py -> parents[2] is the repo root.
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


@dataclass(frozen=True)
class CocoPaths:
    root: Path

    @property
    def coco(self) -> Path:
        return self.root / "coco"

    @property
    def images(self) -> Path:
        return self.coco / "val2017"

    @property
    def captions(self) -> Path:
        return self.coco / "annotations" / "captions_val2017.json"

    @property
    def embeddings(self) -> Path:
        return self.coco / "embeddings"


@dataclass(frozen=True)
class CocoSplit:
    """Images in a fixed order, and every caption pointing at its image's position."""

    file_names: list[str]
    captions: list[str]
    caption_image: list[int]  # caption i describes file_names[caption_image[i]]


def load_split(paths: CocoPaths) -> CocoSplit:
    with open(paths.captions, encoding="utf-8") as f:
        data = json.load(f)
    images = sorted(data["images"], key=lambda im: im["id"])
    position = {im["id"]: i for i, im in enumerate(images)}
    annotations = sorted(data["annotations"], key=lambda a: (a["image_id"], a["id"]))
    captions, caption_image = [], []
    for ann in annotations:
        text = " ".join(ann["caption"].split())  # some captions have stray newlines
        if ann["image_id"] in position and text:
            captions.append(text)
            caption_image.append(position[ann["image_id"]])
    return CocoSplit([im["file_name"] for im in images], captions, caption_image)
