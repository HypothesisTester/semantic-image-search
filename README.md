# Semantic Image Search

Search your photos with natural language ("dog on a beach", "birthday cake") using CLIP embeddings and a FAISS vector index.

> Work in progress. The backend is being rebuilt; see the roadmap below.

## Structure

```
frontend/   React + TypeScript app (Vite, Firebase Auth, Firestore)
backend/    Indexing and search services (FastAPI, CLIP, FAISS)   [coming]
demo/       Public read-only demo over the COCO val2017 images     [coming]
bench/      Retrieval quality and latency benchmarks               [coming]
```

## Roadmap

- [x] Frontend: upload, gallery, search UI, auth
- [ ] Core: CLIP embeddings, image decoding, per-user FAISS index store
- [ ] COCO index and benchmark (Recall@K, latency)
- [ ] Indexing and search services, Docker Compose
- [ ] Frontend: token auth, local uploads, demo mode
- [ ] Public demo (Hugging Face Spaces + Vercel)

## Running the frontend

```bash
cd frontend
npm ci
npm run dev
```
