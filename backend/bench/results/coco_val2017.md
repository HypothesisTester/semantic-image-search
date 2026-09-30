# Benchmark: COCO val2017

5,000 images, 25,014 captions. Model: ViT-B-32-quickgelu / openai. Machine: Apple M1 Pro, CLIP on `mps`, FAISS threads: 1.

## Retrieval quality

| Direction | R@1 | R@5 | R@10 |
|---|---|---|---|
| Text to image (photo search) | 30.4% | 54.8% | 66.1% |
| Image to text | 50.0% | 75.0% | 83.3% |

R@K: the share of queries whose correct match is in the top K results.

## Speed

| Measure | p50 | p95 |
|---|---|---|
| Search, top 5 of 5,000 (warm) | 0.29 ms | 0.39 ms |
| Query encoding (CLIP text) | 8.30 ms | 8.71 ms |
| End to end (encode + search) | 8.69 ms | 9.13 ms |
| Cold start (first search after restart) | 7.37 ms | 7.58 ms |
| Add 50 photos to the index | 15 ms | 23 ms |

Adding 50 photos to an index that already holds 4,950 took 19 ms: every add rewrites the whole index file, so the cost grows with the library.

Embedding throughput: **173 images/s** on `mps` (decode + CLIP). Index file: 10.67 MB.

## Exact search as the index grows

| Vectors | Memory | p50 | p95 |
|---|---|---|---|
| 5,000 | 10 MB | 0.23 ms | 0.27 ms |
| 20,000 | 41 MB | 0.92 ms | 0.94 ms |
| 100,000 | 205 MB | 4.35 ms | 4.78 ms |
