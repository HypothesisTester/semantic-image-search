# Phase 2: COCO benchmark, design decisions

The reasoning behind `backend/bench/` and `backend/demo/`.

### 1. The dataset: COCO val2017, labelled as exactly that
COCO val2017 has 5,000 photos, each with about five captions written by people (about 25,000 in total). Captions are the queries and photos are the targets, which is the same task as typing "dog on a beach" into the app.

Published CLIP numbers use a different 5,000 images: the "Karpathy" test split, drawn from val2014. The two sets are similar but not the same, so results here are reported as **COCO val2017**, never as "COCO 5k", and are compared with the published figure only as a sanity range (see 5).

### 2. The metric: Recall@K, in both directions
Recall@K is the share of queries whose correct answer appears in the top K results. For text-to-image, the photo-search direction, a caption counts as a hit if its own photo is in the top K. Image-to-text is reported too, because it is the other standard direction and a large gap between the two would point to a bug. K = 1, 5 and 10 are the conventional cut-offs; K = 5 matches the app, which shows five results.

### 3. The benchmark runs the real code, not a copy
Photos are decoded with `common.images.decode_image` and searched through `common.index_store.IndexStore`, the same functions the services will use. A benchmark on a simplified path would measure something users never experience.

### 4. What "fast" means: percentiles, warm and cold, end to end
- **p50 and p95**, not averages. p95 is what the slowest one in twenty searches feels like; averages hide slow outliers.
- **Warm-up first**, because the first calls on a GPU backend compile kernels and would distort the numbers.
- **Cold start** is measured separately: a new `IndexStore` has an empty cache, so its first search includes reading the file, as after a service restart.
- **End to end** (encode the query with CLIP, then search) is what the user waits for. It shows that search is a small fraction of the total: the text encoder dominates.

### 5. A sanity check against the published figure
Published zero-shot text-to-image Recall@5 for CLIP ViT-B/32 is about 55% on the Karpathy split. `bench.evaluate` warns if val2017 comes out outside 45 to 65%. The check only applies to the full 5,000-image run with the real weights. A result far outside that range means a preprocessing bug; the QuickGELU mismatch found in Phase 1 is exactly the kind of error this would catch.

### 6. The scaling table is the evidence for exact search
Phase 1 argued that exact search is fast enough for a personal library. The scaling table measures it: single-query latency at 5,000, 20,000 and 100,000 vectors. Exact search is linear in the number of vectors, so the table shows where it would stop being acceptable, which is the point at which an approximate index (IVF or HNSW) earns its loss of recall.

### 7. The cost of atomic writes: every add rewrites the file
The index store replaces the whole index file on every update (Phase 1, decision 4). That makes writes safe but means an upload's cost grows with the library: the report shows the last batch, added to an almost full index, next to the median. At 5,000 photos the file is about 10 MB, which is fine. For much larger libraries, the next step would be appending new vectors to small segment files and merging them in the background, the way log-structured storage engines do.

### 8. The demo reuses the benchmark's vectors
`demo.build_index` does not embed anything again: it loads the vectors from `bench.embed_coco` into an `IndexStore` under the user id `demo`, and writes 384 px thumbnails (the app's grid cells are 250 px). The public demo therefore searches exactly the vectors the benchmark scored, through the same code as a real user's library.
