# Phase 5: public demo, design decisions

The reasoning behind the in-browser demo: `backend/demo/export_static.py`, `backend/demo/deploy_static.py`, `frontend/src/demo/`, `frontend/scripts/verify-browser-model.mjs` and `frontend/vercel.json`.

### 1. Why the demo has no server
The first plan ran the search service on a free Hugging Face Space. Hugging Face now requires a paid plan for Docker Spaces, and the other free hosts either need a payment card or have too little memory for CLIP.

But the demo's 5,000 photos never change, so their vectors can be computed once, ahead of time. The only thing that needs a model at search time is the visitor's query, and CLIP's text encoder can run in the browser. The demo therefore becomes static files: free to host, nothing to keep running, and it never sleeps. The signed-in app, with uploads, still runs on the two services.

### 2. Where the pieces live
- **Vercel** serves the frontend, built from the GitHub repo on every push to `main`.
- **A public Hugging Face dataset** holds the data (datasets are still free): the vectors, the photo list, the example searches and the 5,000 thumbnails. The browser downloads them directly from Hugging Face.
- **The Hugging Face Hub** serves the text model itself (`Xenova/clip-vit-base-patch32`, an ONNX conversion of the same OpenAI weights), which the browser caches after the first download.

### 3. The same search, in JavaScript
Search is exact top-k by dot product over all 5,000 unit vectors, the same search FAISS's `IndexFlatIP` does on the server: 5,000 × 512 is 2.6 million multiply-adds, a few milliseconds in JavaScript. At this size a vector library or approximate index would add nothing (Phase 1, decision 2; Phase 2's scaling table).

### 4. float16 vectors, measured
The image vectors are stored as float16, halving the download from 10 MB to 5 MB. For unit vectors compared by dot product this shifts scores by about 0.001. The export measures text-to-image Recall@1/5/10 over all 25,014 captions with both precisions, so the claim that it changes nothing is a measurement, not an assumption. The browser's float16 decoder is checked against numpy bit for bit on 100,000 values, including subnormals and NaN.

### 5. The browser model is checked against the server's, and that changed the choice
A different runtime and a compressed model could quietly change the vectors, so `scripts/verify-browser-model.mjs` runs the browser's model under Node on 1,000 COCO captions and compares it with the Python model: the cosine similarity between the two vectors for each caption, and text-to-image recall with each. (Its comparison logic is itself tested with an encoder that must agree perfectly and a random one that must not.)

The first choice, an 8-bit quantised model picked for its small download, failed that check. Comparing every available precision:

| Browser model | Download | Mean cosine | R@1 | R@5 | R@10 |
|---|---|---|---|---|---|
| Python (reference) | | | 30.1% | 55.0% | 67.8% |
| q8 / int8 / uint8 | 64–65 MB | 0.83 | 21–22% | 44–46% | 56–57% |
| **fp16** | **127 MB** | **1.0000** | **30.1%** | **55.0%** | **67.9%** |
| fp32 | 254 MB | 1.0000 | 30.1% | 55.0% | 67.8% |

8-bit weights cost this model about 10 points of Recall@5, so the demo uses fp16: identical results at half the size of fp32. The model name and precision live in one file (`src/demo/modelConfig.ts`) that both the page and the check import, so they cannot drift apart.

### 6. Nothing heavy loads until it is needed
The landing page and example searches need only the 5 MB of data. The example searches' query vectors are computed by the Python model at export time, so clicking one returns results immediately. The model library (a separate code chunk) and the model are fetched only when a visitor types a search of their own, with a progress message, and the browser caches them for next time.

### 7. Direct links work on Vercel
The frontend is a single-page app, so a link like `/result?q=dog` has no file behind it. `vercel.json` sends every path that is not a real file to `index.html`, so shared and refreshed result links load instead of returning 404.

### 8. One setting keeps the build lean
`@huggingface/transformers` depends on `onnxruntime-node`, whose install step downloads large optional GPU binaries. Neither the browser nor the verification script needs them, so `frontend/.npmrc` skips that step, on developer machines and on Vercel alike.

### Known limits
- The first typed search waits for a 127 MB model download; after that the browser has it cached. Example searches never need it.
- The demo shows 384 px thumbnails only, not full-size images.
