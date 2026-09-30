"""demo.export_static and demo.deploy_static: the static, in-browser demo's data."""

import json
import re
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from demo import deploy_static, export_static
from tests.fakes import FakeEncoder
from tests.helpers import unit_vectors

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


@pytest.fixture
def data(tmp_path):
    """The outputs of bench.embed_coco and demo.build_index, for 40 photos."""
    n, per_image = 40, 2
    emb = tmp_path / "coco" / "embeddings"
    emb.mkdir(parents=True)
    images = unit_vectors(n, seed=1)
    owner = list(np.repeat(np.arange(n), per_image))
    noise = unit_vectors(n * per_image, seed=2) * 0.3
    texts = images[owner] + noise
    texts /= np.linalg.norm(texts, axis=1, keepdims=True)
    np.save(emb / "image_vectors.npy", images)
    np.save(emb / "text_vectors.npy", texts.astype(np.float32))
    names = [f"{i:012d}.jpg" for i in range(n)]
    (emb / "manifest.json").write_text(json.dumps({
        "file_names": names,
        "captions": [f"caption {i // per_image}-{i % per_image}" for i in range(n * per_image)],
        "caption_image": [int(i) for i in owner],
    }))
    thumbs = tmp_path / "demo" / "thumbnails"
    thumbs.mkdir(parents=True)
    for name in names:
        Image.new("RGB", (8, 8), "red").save(thumbs / name)
    return tmp_path


def test_export_writes_everything_the_browser_needs(data):
    info = export_static.export(data, encoder=FakeEncoder(), check_sample=30)
    static = data / "demo" / "static"

    assert info["count"] == 40 and info["dim"] == 512 and info["dtype"] == "float16"
    vectors = np.fromfile(static / "vectors.f16", dtype=np.float16).reshape(40, 512)
    np.testing.assert_allclose(vectors.astype(np.float32), np.load(data / "coco/embeddings/image_vectors.npy"), atol=1e-3)

    photos = json.loads((static / "photos.json").read_text())
    assert photos[3] == {"file": "000000000003.jpg", "caption": "caption 3-0"}
    assert len(list((static / "thumbnails").glob("*.jpg"))) == 40

    examples = json.loads((static / "examples.json").read_text())
    assert [e["text"] for e in examples] == export_static.EXAMPLES
    assert all(len(e["vector"]) == 512 and abs(np.linalg.norm(e["vector"]) - 1) < 1e-4 for e in examples)
    assert examples[0]["key"] == "a dog catching a frisbee"

    check = json.loads((data / "demo/check/check.json").read_text())
    check_vectors = np.fromfile(data / "demo/check/check_text_vectors.f32", dtype=np.float32).reshape(-1, 512)
    assert len(check["captions"]) == len(check["caption_image"]) == len(check_vectors) == 30


def test_float16_does_not_change_the_ranking(data):
    info = export_static.export(data, encoder=FakeEncoder(), check_sample=10)
    for k in ("R@1", "R@5", "R@10"):
        assert info["recall_fp16"][k] == pytest.approx(info["recall_fp32"][k], abs=0.02)


def test_export_refuses_missing_thumbnails(data):
    next((data / "demo" / "thumbnails").glob("*.jpg")).unlink()
    with pytest.raises(SystemExit, match="thumbnails missing"):
        export_static.export(data, encoder=FakeEncoder())


def test_query_normalisation_matches_the_frontend():
    assert export_static.normalise_query("  A Dog\n catching  a FRISBEE ") == "a dog catching a frisbee"
    source = (FRONTEND / "src/demo/staticDemo.ts").read_text()
    assert ".toLowerCase().split(/\\s+/).filter(Boolean).join(' ')" in source


def test_examples_match_the_frontend_list():
    source = (FRONTEND / "src/components/DemoHome.tsx").read_text()
    block = source[source.index("const EXAMPLES = [") : source.index("];", source.index("const EXAMPLES = ["))]
    assert re.findall(r"'([^']+)'", block) == export_static.EXAMPLES


def test_deploy_checks_the_export_before_uploading(data):
    with pytest.raises(SystemExit, match="export_static"):
        deploy_static.main(["--data-dir", str(data), "--dry-run"])
    export_static.export(data, encoder=FakeEncoder(), check_sample=5)
    deploy_static.main(["--data-dir", str(data), "--dry-run"])  # complete export: passes

    (data / "demo/static/vectors.f16").write_bytes(b"\x00" * 10)
    with pytest.raises(SystemExit, match="wrong size"):
        deploy_static.main(["--data-dir", str(data), "--dry-run"])
