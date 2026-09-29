# Backend

Shared core (`common/`) for the indexing and search services.

| Module | What it does |
|---|---|
| `common/clip.py` | CLIP ViT-B/32 encoder: images and text to L2-normalised 512-d vectors |
| `common/images.py` | Decodes uploads (JPEG, PNG, WebP, GIF, BMP, TIFF, HEIC, DNG) into upright RGB images |
| `common/index_store.py` | Per-user FAISS indexes on disk, with per-user locking and atomic writes |
| `common/auth.py` | Verifies Firebase ID tokens using only the project id |
| `common/vectors.py` | Normalisation and validation helpers |

## Setup

Requires Python 3.11 or newer.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[model,raw,dev]"
```

## Tests

```bash
pytest                           # everything except the real-weights tests
RUN_MODEL_TESTS=1 pytest -m model  # downloads the CLIP weights (~350 MB) on first run
```

The concurrency tests start separate processes and take a few seconds.
