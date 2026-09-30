"""demo.deploy_space: the checks and staging that run before anything is uploaded."""

import tarfile

import pytest
from PIL import Image

from common.index_store import IndexStore
from demo import deploy_space
from tests.helpers import unit_vectors


def make_demo(root, n):
    thumbs = root / "demo" / "thumbnails"
    thumbs.mkdir(parents=True)
    for i in range(n):
        Image.new("RGB", (8, 8), "red").save(thumbs / f"{i:012d}.jpg")
    IndexStore(root / "demo" / "index").add("demo", [f"k{i}" for i in range(n)], unit_vectors(n, seed=1))


def test_refuses_to_deploy_without_demo_data(tmp_path):
    with pytest.raises(SystemExit, match="build_index"):
        deploy_space.main(["--data-dir", str(tmp_path), "--dry-run"])


def test_refuses_to_deploy_an_incomplete_demo(tmp_path):
    make_demo(tmp_path, 3)
    with pytest.raises(SystemExit, match="expected 5000"):
        deploy_space.main(["--data-dir", str(tmp_path), "--dry-run"])


def test_stages_a_complete_space(tmp_path):
    make_demo(tmp_path, 4)
    out = tmp_path / "staged"
    deploy_space.main(["--data-dir", str(tmp_path), "--expected-images", "4", "--dry-run", "--stage-dir", str(out)])

    assert (out / "Dockerfile").read_text().count("DEMO_MODE=1") == 1
    front_matter = (out / "README.md").read_text().split("---")[1]
    assert "sdk: docker" in front_matter and "app_port: 7860" in front_matter
    for package in ("common", "services", "bench", "demo"):
        assert (out / package / "__init__.py").exists()
    assert (out / "demo-data" / "index" / "demo" / "index.npz").exists()
    assert not list((out / "demo-data").rglob(".lock"))
    with tarfile.open(out / "demo-data" / "thumbnails.tar") as tar:
        assert sorted(tar.getnames()) == [f"{i:012d}.jpg" for i in range(4)]
    assert not list(out.rglob("__pycache__"))
