# Semantic Image Search

Search your photos with natural language ("dog on a beach", "birthday cake") using CLIP embeddings and a FAISS vector index.

> Work in progress. The backend is being rebuilt; see the roadmap below.

## Structure

```
frontend/          React + TypeScript app (Vite, Firebase Auth, Firestore)
backend/common/    Shared core: CLIP encoder, image decoding, index store, auth
backend/bench/     COCO val2017 benchmark: Recall@K, latency, scaling
backend/demo/      Builds the public demo's index and thumbnails
backend/services/  Indexer and search HTTP services (FastAPI)
docker-compose.yml Runs both services, plus the demo
docs/decisions/    Design decisions for each phase
```

## Roadmap

- [x] Frontend: upload, gallery, search UI, auth
- [x] Core: CLIP embeddings, image decoding, per-user FAISS index store, token auth
- [x] COCO index and benchmark (Recall@K, latency): see `backend/bench/results/`
- [x] Indexing and search services, Docker Compose
- [ ] Frontend: token auth, local uploads, demo mode
- [ ] Public demo (Hugging Face Spaces + Vercel)

## Running the backend

Requires Docker.

```bash
docker compose up --build
```

The indexer runs at http://localhost:8001 and search at http://localhost:8002. To also run the COCO demo (http://localhost:8003), build its data first with `python -m demo.build_index` in `backend/`, then:

```bash
docker compose --profile demo up --build
```

## Running the frontend

```bash
cd frontend
npm ci
npm run dev
```
