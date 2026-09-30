// Where the backend lives, and whether this build is the public demo.
// Set these in frontend/.env.local (see .env.example) or in the host's
// environment settings (e.g. Vercel). Vite bakes them in at build time.

const env = import.meta.env;

/** The public, read-only demo: no sign-in, searches the COCO images. */
export const DEMO_MODE = env.VITE_DEMO_MODE === 'true';

const trimSlash = (url: string) => url.replace(/\/+$/, '');

/** The indexer service (uploads). Unused in demo mode. */
export const INDEX_URL = trimSlash(env.VITE_INDEX_URL ?? 'http://localhost:8001');

/** The search service. Locally the demo runs on 8003 (docker compose --profile demo). */
export const SEARCH_URL = trimSlash(
  env.VITE_SEARCH_URL ?? (DEMO_MODE ? 'http://localhost:8003' : 'http://localhost:8002'),
);

/** Results shown per search. */
export const RESULTS_PER_SEARCH = DEMO_MODE ? 12 : 5;

/** Photos sent to the indexer per request: one CLIP batch each. */
export const UPLOAD_BATCH_SIZE = 10;

export const REPO_URL = 'https://github.com/HypothesisTester/semantic-image-search';
