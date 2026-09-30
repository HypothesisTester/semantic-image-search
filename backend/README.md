# Backend

Shared core (`common/`) for the indexing and search services.

| Module | What it does |
|---|---|
| `common/clip.py` | CLIP ViT-B/32 encoder: images and text to L2-normalised 512-d vectors |
| `common/images.py` | Decodes uploads (JPEG, PNG, WebP, GIF, BMP, TIFF, HEIC, DNG) into upright RGB images |
| `common/index_store.py` | Per-user FAISS indexes on disk, with per-user locking and atomic writes |
| `common/auth.py` | Verifies Firebase ID tokens using only the project id |
| `common/vectors.py` | Normalisation and validation helpers |
| `common/photo_store.py` | Stores uploads, with JPEG display copies and thumbnails |
| `services/indexer.py` | `POST /upload`: embeds photos into the user's index |
| `services/search.py` | `POST /search`: finds a user's photos by text; demo mode |

## Setup

Requires Python 3.11 or newer.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[model,raw,service,dev]"
```

## COCO benchmark

Run from `backend/`. Data goes to `data/` at the repo root, which git ignores.

```bash
python -m bench.download_coco
python -m bench.embed_coco
python -m bench.evaluate
python -m demo.build_index
```

`download_coco` fetches about 1 GB. `evaluate` writes `bench/results/coco_val2017.md` and `.json`.

## Deploying the public demo

After `python -m demo.build_index`, and signing in once with `hf auth login`:

```bash
python -m demo.deploy_space
```

This creates or updates a Hugging Face Space running the search service in demo mode. See `docs/decisions/phase-5-deploy.md`.

## Smoke test against Docker

With `docker compose up` running (and the COCO data downloaded):

```bash
python scripts/smoke_test.py
```

It signs in as a throwaway Firebase user, uploads 20 COCO photos, searches with their captions, and deletes the user afterwards.

## Tests

```bash
pytest
RUN_MODEL_TESTS=1 pytest -m model
```

The first runs everything except the real-weights tests. The second runs those, downloading the CLIP weights (about 350 MB) on first use.

The concurrency tests start separate processes and take a few seconds.
