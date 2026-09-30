"""Upload the static demo data to a public Hugging Face dataset repository.

    python -m demo.deploy_static

Run from backend/ after `python -m demo.export_static`, and after signing in
once with `hf auth login` (a token with write access). Dataset repositories
are free; the browser then downloads the files straight from Hugging Face.
Re-running it updates the files. --dry-run only checks what would be sent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bench.coco import DEFAULT_DATA_DIR

REQUIRED = ("manifest.json", "vectors.f16", "photos.json", "examples.json")


def check_export(static: Path) -> dict:
    missing = [name for name in REQUIRED if not (static / name).exists()]
    if missing or not (static / "thumbnails").is_dir():
        raise SystemExit(f"no complete export in {static}: run `python -m demo.export_static` first")
    info = json.loads((static / "manifest.json").read_text())
    photos = json.loads((static / "photos.json").read_text())
    expected_bytes = info["count"] * info["dim"] * 2
    thumbnails = len(list((static / "thumbnails").glob("*.jpg")))
    if len(photos) != info["count"] or thumbnails != info["count"]:
        raise SystemExit(f"export is inconsistent: {info['count']} vectors, {len(photos)} photos, {thumbnails} thumbnails")
    if (static / "vectors.f16").stat().st_size != expected_bytes:
        raise SystemExit("vectors.f16 has the wrong size for the manifest")
    return info


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default="semantic-image-search-demo", help="dataset name under your account")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    static = args.data_dir / "demo" / "static"
    info = check_export(static)
    size_mb = sum(p.stat().st_size for p in static.rglob("*") if p.is_file()) / 1e6
    print(f"export: {info['count']} photos, {size_mb:.0f} MB")
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
    repo_id = f"{user}/{args.repo}"
    api.create_repo(repo_id, repo_type="dataset", private=False, exist_ok=True)

    print("uploading (the first time takes a few minutes) ...")
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=static,
        commit_message="Update the demo data",
    )
    base = f"https://huggingface.co/datasets/{repo_id}/resolve/main"
    print()
    print(f"Uploaded: https://huggingface.co/datasets/{repo_id}")
    print()
    print("Settings for the Vercel project:")
    print("  VITE_DEMO_MODE     = true")
    print(f"  VITE_DEMO_DATA_URL = {base}")


if __name__ == "__main__":
    sys.exit(main())
