"""Deploy the public demo's search service to a Hugging Face Space.

    python -m demo.deploy_space

Run from backend/ after `python -m demo.build_index`, and after signing in
once with `hf auth login` (a token with write access). It:
  1. checks the demo index and thumbnails are complete
  2. stages the backend code, the Space's Dockerfile and README, the index,
     and the thumbnails packed into one tar file
  3. creates the Space if needed (Docker SDK, free CPU hardware)
  4. sets PHOTOS_BASE_URL to the Space's public address
  5. uploads everything in one commit; Hugging Face then builds the image

Re-running it updates the Space. --dry-run stages the files without
uploading, to inspect what would be sent.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

import common  # noqa: F401  -- loads before torch/faiss (macOS OpenMP fix)
from common.index_store import IndexStore

from bench.coco import DEFAULT_DATA_DIR

BACKEND = Path(__file__).resolve().parents[1]
SPACE_TEMPLATE = Path(__file__).resolve().parent / "space"
CODE = ["common", "services", "bench", "demo"]
DEMO_UID = "demo"


def check_demo_data(demo_dir: Path, expected: int) -> int:
    index_file = demo_dir / "index" / DEMO_UID / "index.npz"
    thumbs = demo_dir / "thumbnails"
    if not index_file.exists() or not thumbs.is_dir():
        raise SystemExit(f"no demo data in {demo_dir}: run `python -m demo.build_index` first")
    count = IndexStore(demo_dir / "index").count(DEMO_UID)
    images = len(list(thumbs.glob("*.jpg")))
    if count != expected or images != expected:
        raise SystemExit(f"expected {expected} indexed photos and thumbnails, found {count} and {images}")
    return count


def stage(demo_dir: Path, out: Path) -> None:
    """Lay out the Space repository in ``out``."""
    shutil.copy(SPACE_TEMPLATE / "Dockerfile", out / "Dockerfile")
    shutil.copy(SPACE_TEMPLATE / "README.md", out / "README.md")
    shutil.copy(BACKEND / "pyproject.toml", out / "pyproject.toml")
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "results")
    for name in CODE:
        shutil.copytree(BACKEND / name, out / name, ignore=ignore)
    data = out / "demo-data"
    shutil.copytree(demo_dir / "index", data / "index", ignore=shutil.ignore_patterns(".lock", "*.tmp"))
    # Uncompressed: the thumbnails are JPEGs already, so gzip would gain nothing.
    with tarfile.open(data / "thumbnails.tar", "w") as tar:
        for path in sorted((demo_dir / "thumbnails").glob("*.jpg")):
            tar.add(path, arcname=path.name)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--space", default="semantic-image-search", help="Space name under your account")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--expected-images", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true", help="stage the files, but do not upload")
    parser.add_argument("--stage-dir", type=Path, default=None, help="where to stage (default: a temp folder)")
    args = parser.parse_args(argv)

    demo_dir = args.data_dir / "demo"
    count = check_demo_data(demo_dir, args.expected_images)
    print(f"demo data: {count} photos")

    staging = args.stage_dir or Path(tempfile.mkdtemp(prefix="space-"))
    staging.mkdir(parents=True, exist_ok=True)
    stage(demo_dir, staging)
    size_mb = sum(p.stat().st_size for p in staging.rglob("*") if p.is_file()) / 1e6
    print(f"staged {size_mb:.0f} MB in {staging}")
    if args.dry_run:
        print("dry run: nothing uploaded")
        return

    from huggingface_hub import HfApi
    from huggingface_hub.errors import HfHubHTTPError, LocalTokenNotFoundError

    api = HfApi()
    try:
        user = api.whoami()["name"]
    except (LocalTokenNotFoundError, HfHubHTTPError):
        raise SystemExit("not signed in to Hugging Face: run `hf auth login` with a write token first")
    repo_id = f"{user}/{args.space}"

    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
    host = api.space_info(repo_id).host or f"https://{repo_id.replace('/', '-').replace('_', '-').lower()}.hf.space"
    api.add_space_variable(repo_id, "PHOTOS_BASE_URL", host)
    print(f"space: https://huggingface.co/spaces/{repo_id}")

    print("uploading (the first time takes a few minutes) ...")
    api.upload_folder(
        repo_id=repo_id,
        repo_type="space",
        folder_path=staging,
        commit_message="Deploy the demo search service",
    )
    if args.stage_dir is None:
        shutil.rmtree(staging, ignore_errors=True)

    print()
    print("Uploaded. Hugging Face is now building the image; watch it at")
    print(f"  https://huggingface.co/spaces/{repo_id}")
    print("When it says Running, the demo API is live at")
    print(f"  {host}")
    print()
    print("Settings for the Vercel project:")
    print("  VITE_DEMO_MODE  = true")
    print(f"  VITE_SEARCH_URL = {host}")


if __name__ == "__main__":
    sys.exit(main())
