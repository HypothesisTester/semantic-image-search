"""Phase 2 pipeline tests: metrics, and download -> embed -> evaluate -> demo index
end to end on a tiny fake COCO served from a local web server."""

import http.server
import io
import json
import threading
import zipfile
from functools import partial

import numpy as np
import pytest
from PIL import Image

from bench import download_coco
from bench.coco import CocoPaths, load_split
from bench.metrics import image_to_text_recall, latency_summary, text_to_image_recall

# ---- metrics -----------------------------------------------------------------


def test_recall_on_a_hand_built_example():
    # Three images along the axes. Caption 0 points exactly at its image;
    # caption 1 points at image 1 but belongs to image 2; caption 2 points
    # mostly at image 1 but a little at its own image 2.
    images = np.eye(3, dtype=np.float32)
    texts = np.array([[1, 0, 0], [0, 1, 0], [0, 0.8, 0.6]], dtype=np.float32)
    owner = [0, 2, 2]

    t2i = text_to_image_recall(texts, images, owner, ks=(1, 2, 3))
    # R@1: only caption 0. R@2: caption 2 finds image 2 second; caption 1's
    # second hit is a tie between images 0 and 2 (both score 0), so it can go
    # either way. R@3: everything.
    assert t2i[1] == pytest.approx(1 / 3)
    assert t2i[2] in (pytest.approx(2 / 3), pytest.approx(1.0))
    assert t2i[3] == pytest.approx(1.0)

    i2t = image_to_text_recall(texts, images, owner, ks=(1, 3))
    # Image 0's best caption is its own; image 1 has no captions so it never
    # hits; image 2's best caption is caption 2 (score 0.6), which is its own.
    assert i2t[1] == pytest.approx(2 / 3)
    assert i2t[3] == pytest.approx(2 / 3)


def test_perfect_embeddings_give_perfect_recall():
    rng = np.random.default_rng(0)
    images = rng.standard_normal((50, 16)).astype(np.float32)
    images /= np.linalg.norm(images, axis=1, keepdims=True)
    owner = np.repeat(np.arange(50), 2)
    texts = images[owner]  # every caption equals its image's vector
    assert text_to_image_recall(texts, images, owner)[1] == 1.0
    assert image_to_text_recall(texts, images, owner)[1] == 1.0


def test_latency_summary_converts_to_milliseconds():
    s = latency_summary([0.001] * 99 + [0.1])
    assert s["p50_ms"] == pytest.approx(1.0)
    assert s["p99_ms"] > 1.0 and s["n"] == 100


# ---- end to end ----------------------------------------------------------------

COLOURS = ["red", "green", "blue", "yellow", "purple", "orange", "black", "white", "pink", "grey", "brown", "cyan"]


def make_fake_coco(root):
    """Two zips shaped like the real COCO downloads, with 12 images and 2 captions each."""
    images_zip, annotations = io.BytesIO(), {"images": [], "annotations": []}
    with zipfile.ZipFile(images_zip, "w") as zf:
        for i, colour in enumerate(COLOURS):
            name = f"{i + 1:012d}.jpg"
            buf = io.BytesIO()
            Image.new("RGB", (64, 48), colour).save(buf, format="JPEG")
            zf.writestr(f"val2017/{name}", buf.getvalue())
            annotations["images"].append({"id": i + 1, "file_name": name})
            for j, text in enumerate([f"a {colour} square", f"something\n{colour}"]):
                annotations["annotations"].append({"id": 100 * (i + 1) + j, "image_id": i + 1, "caption": text})
    ann_zip = io.BytesIO()
    with zipfile.ZipFile(ann_zip, "w") as zf:
        zf.writestr("annotations/captions_val2017.json", json.dumps(annotations))
        zf.writestr("annotations/instances_val2017.json", "{}")  # present in the real zip, ignored
    (root / "val2017.zip").write_bytes(images_zip.getvalue())
    (root / "annotations.zip").write_bytes(ann_zip.getvalue())


@pytest.fixture
def local_server(tmp_path, monkeypatch):
    served = tmp_path / "served"
    served.mkdir()
    make_fake_coco(served)
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(served))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_download_extracts_images_and_captions_and_is_rerunnable(tmp_path, local_server):
    data = tmp_path / "data"
    args = [
        "--data-dir", str(data),
        "--images-url", f"{local_server}/val2017.zip",
        "--annotations-url", f"{local_server}/annotations.zip",
        "--expected-images", "12",
    ]
    download_coco.main(args)
    paths = CocoPaths(data)
    assert len(list(paths.images.glob("*.jpg"))) == 12
    assert paths.captions.exists()
    assert not (paths.coco / "downloads").exists()  # zips removed after extracting
    download_coco.main(args)  # second run: everything skipped, still fine

    split = load_split(paths)
    assert len(split.file_names) == 12 and len(split.captions) == 24
    assert split.captions[1] == "something red"  # newline normalised
    assert split.caption_image[:4] == [0, 0, 1, 1]


def test_download_rejects_the_wrong_image_count(tmp_path, local_server):
    with pytest.raises(SystemExit, match="expected 5000"):
        download_coco.main([
            "--data-dir", str(tmp_path / "data"),
            "--images-url", f"{local_server}/val2017.zip",
            "--annotations-url", f"{local_server}/annotations.zip",
        ])


def test_full_pipeline_on_fake_coco(tmp_path, local_server):
    pytest.importorskip("torch")
    pytest.importorskip("open_clip")
    from bench import embed_coco, evaluate
    from demo import build_index
    from common.index_store import IndexStore

    data = tmp_path / "data"
    download_coco.main([
        "--data-dir", str(data),
        "--images-url", f"{local_server}/val2017.zip",
        "--annotations-url", f"{local_server}/annotations.zip",
        "--expected-images", "12",
    ])

    # Random weights: checks the plumbing, not the quality.
    manifest = embed_coco.main([
        "--data-dir", str(data), "--pretrained", "none", "--device", "cpu",
        "--batch-size", "5", "--workers", "2",
    ])
    emb = CocoPaths(data).embeddings
    image_vectors = np.load(emb / "image_vectors.npy")
    text_vectors = np.load(emb / "text_vectors.npy")
    assert image_vectors.shape == (12, 512) and text_vectors.shape == (24, 512)
    np.testing.assert_allclose(np.linalg.norm(image_vectors, axis=1), 1.0, atol=1e-5)
    assert manifest["n_images"] == 12 and manifest["images_per_second"] > 0

    results_dir = tmp_path / "results"
    results = evaluate.main([
        "--data-dir", str(data), "--results-dir", str(results_dir), "--device", "cpu",
        "--queries", "10", "--encode-queries", "5", "--scaling-sizes", "100,300",
    ])
    for direction in ("text_to_image_recall", "image_to_text_recall"):
        assert set(results[direction]) == {"R@1", "R@5", "R@10"}
        assert all(0.0 <= v <= 1.0 for v in results[direction].values())
    assert results["text_to_image_recall"]["R@10"] >= results["text_to_image_recall"]["R@1"]
    assert [row["vectors"] for row in results["scaling"]] == [100, 300]
    assert results["search"]["p50_ms"] > 0 and results["end_to_end"]["n"] == 5
    assert results["sanity_check"]["ok"] is None  # only meaningful for the real 5,000-image run
    md = (results_dir / "coco_val2017.md").read_text()
    assert "| Text to image (photo search) |" in md
    assert json.loads((results_dir / "coco_val2017.json").read_text())["dataset"]["images"] == 12

    summary = build_index.main(["--data-dir", str(data), "--workers", "2"])
    demo = data / "demo"
    store = IndexStore(demo / "index")
    assert store.count("demo") == 12
    hit = store.search("demo", image_vectors[3], k=1)[0]
    assert hit.meta == {"url": "/images/000000000004.jpg", "caption": "a yellow square"}
    thumbs = sorted((demo / "thumbnails").glob("*.jpg"))
    assert len(thumbs) == 12 and summary["images"] == 12
    with Image.open(thumbs[0]) as t:
        assert max(t.size) <= 384
