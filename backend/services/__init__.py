"""The two HTTP services.

- services.indexer: POST /upload embeds photos into the user's index; GET /photos serves them
- services.search:  POST /search finds a user's photos by text; demo mode serves COCO

Run locally (from backend/):
    uvicorn services.indexer:create_app --factory --port 8001
    uvicorn services.search:create_app --factory --port 8002
"""

import common  # noqa: F401  -- loads before torch/faiss (macOS OpenMP fix)
