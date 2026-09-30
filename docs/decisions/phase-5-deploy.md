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

### 6. The model loads early where that is cheap, and never blocks the page
The landing page and example searches need only the 5 MB of data. The example searches' query vectors are computed by the Python model at export time, so clicking one returns results immediately. The model library (a separate code chunk) and the 127 MB model are fetched in the background so that a typed search is instant too, but only when that is cheap (`src/demo/preload.ts`):
- shortly after the first photos load, on a computer or a connection the browser reports as Wi-Fi or wired, unless it asks to save data or reports a slow connection;
- otherwise, as soon as the visitor taps or types in the search box, on any device. Phones on mobile data therefore never download it just for visiting.

A search that starts while the download is running waits for the same download, with a progress bar. The browser caches the model, so later visits skip the download.

### 7. Direct links work on Vercel
The frontend is a single-page app, so a link like `/result?q=dog` has no file behind it. `vercel.json` sends every path that is not a real file to `index.html`, so shared and refreshed result links load instead of returning 404.

### 8. One setting keeps the build lean
`@huggingface/transformers` depends on `onnxruntime-node`, whose install step downloads large optional GPU binaries. Neither the browser nor the verification script needs them, so `frontend/.npmrc` skips that step, on developer machines and on Vercel alike.

### 9. The first photos don't wait for anything they don't need
On a phone the landing page used to take about 15 seconds to show a photo. Three things added up: the page downloaded all the search data, including the 5 MB of vectors, before showing the photo list; every file on Hugging Face is a redirect to a CDN, possibly in another region, costing extra round trips per file and per thumbnail; and the demo shipped the Firebase sign-in code it never uses.

- **Browsing needs only the photo list**, so it no longer waits for the vectors. They download in the background a second after the first photos appear, or as soon as the visitor touches the search box or an example.
- **The build copies the data into the site** (`frontend/scripts/bundle-demo-data.mjs`, run before `npm run build`): the data files, the vectors, the first 48 thumbnails, and a few-KB list of the first page. These are served by Vercel's own CDN with no redirect, and `index.html` preloads the first page's list and first 12 photos alongside the app's code. Copying the list and vectors together also keeps a deployment's data consistent. If the copy fails, the build carries on and the page fetches from Hugging Face as before.
- **Example searches are answered at build time.** The same script ranks all 5,000 photos for each example, by the same dot product the page uses (checked by a test), and includes their photos, so tapping an example needs neither the vectors nor Hugging Face.
- **The sign-in app is a separate code chunk**, which the demo never loads: the demo's main script went from 138 KB to 78 KB compressed.

With the throttling used for these measurements (a phone on 4G: 150 ms latency, 4 Mbps), the first photos went from 14.4 s to about 2 s.

### Known limits
- A search typed before the background download finishes still waits for the rest of it (127 MB on the first visit only). Example searches never need the model.
- The demo shows 384 px thumbnails only, not full-size images.
