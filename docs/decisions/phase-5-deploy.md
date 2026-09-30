# Phase 5: public demo, design decisions

The reasoning behind `backend/demo/space/`, `backend/demo/deploy_space.py` and `frontend/vercel.json`.

### 1. Two free hosts, split by what each is good at
- **Hugging Face Spaces** runs the search service. Its free CPU tier has 2 cores and 16 GB of memory, enough for CLIP, and it runs any Docker image.
- **Vercel** serves the frontend: a static site, built from the GitHub repo on every push to `main`.

Neither needs a payment card. The full app (sign-in and uploads) stays local, because free hosts give no persistent disk for users' photos.

### 2. The demo runs the real search code
The Space runs `services.search` with `DEMO_MODE=1`, the same code path a signed-in search takes (Phase 3, decision 9), over the index `demo.build_index` built from the benchmark's own vectors. The public demo is therefore exactly the system the benchmark measured, not a separate copy.

### 3. Everything the demo needs is inside the image
The CLIP weights, the index and the thumbnails are all baked into the image at build time, and model downloads are disabled at runtime. A container that wakes from sleep only has to start, with nothing to download, and the Space has no moving parts to break later.

The 5,000 thumbnails travel as one 120 MB tar file, unpacked during the build: one large upload instead of 5,000 small ones.

### 4. Open CORS for the demo only
The demo API allows calls from any website (`CORS_ORIGINS=*`). CORS exists to stop other sites making requests with a visitor's credentials. The demo is public, read-only and uses no cookies or tokens, so there is nothing to protect, and anyone may embed it. The signed-in services keep an explicit list of allowed origins.

### 5. Links use the public address
Behind Hugging Face's proxy, the service cannot rely on seeing its public hostname (Phase 3 found that uvicorn trusts the forwarded scheme but not the forwarded host). The deploy script sets `PHOTOS_BASE_URL` to the Space's public address as a Space variable, so photo links are always correct.

### 6. Deploys are one repeatable command
`python -m demo.deploy_space` checks the demo data is complete (5,000 indexed photos and 5,000 thumbnails), stages the Space, creates it if needed, sets its variables and uploads in one commit. Re-running it updates the Space. `--dry-run` shows exactly what would be sent. A mistake such as deploying a half-built index fails before anything is uploaded.

### 7. Direct links work on Vercel
The frontend is a single-page app: a link like `/result?q=dog` has no file behind it. `vercel.json` rewrites every path that isn't a real file to `index.html`, so shared and refreshed result links load instead of returning 404.

### Known limits
- Free Spaces sleep after two days without visitors. The first request after that waits while the container starts; the frontend says so after 3 seconds (Phase 4, decision 7).
- No rate limiting beyond the per-query caps (at most 20 results, 200 characters).
