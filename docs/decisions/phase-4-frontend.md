# Phase 4: frontend, design decisions

The reasoning behind the frontend changes in `frontend/src/`.

### 1. One module talks to the backend
`src/api.ts` is the only code that calls the services. It adds the sign-in token to every request, turns network failures and error responses into readable messages ("Could not reach localhost:8002. Is the backend running?" rather than `TypeError: Failed to fetch`), and keeps the service addresses in one place (`src/config/api.ts`, set through `VITE_*` environment variables). The components never build URLs or headers themselves.

### 2. The token, not the body, says who you are
Every request carries `Authorization: Bearer <Firebase ID token>`. The old frontend sent `userId` in the request body, which the backend now ignores (Phase 3, decision 7). `getIdToken()` returns a cached token and refreshes it automatically before it expires, so a long session never starts failing an hour in.

### 3. Uploads go straight to the indexer, in batches of 10
Files are posted to the indexer in batches of 10: each batch is one request and one CLIP batch on the server. Batches are sent one after another rather than all at once, because the indexer processes one batch at a time anyway (Phase 3, decision 8); sending them in parallel would only queue them on the server while holding more of the upload in memory. Each file's outcome is shown individually, and a failed file no longer disappears silently: the old code swallowed indexing errors in an empty `catch`.

### 4. Gallery records use the backend's photo id
The gallery still reads photo records from Firestore, but each record's document id is now the photo id returned by the indexer, which is derived from the photo's content (Phase 3, decision 4). Uploading the same photo twice therefore rewrites one record instead of showing the photo twice in the gallery, matching what the index does.

### 5. Thumbnails in grids, full images in the viewer
Grids load the 384 px thumbnail and the viewer loads the 2048 px display copy. A grid of 30 photos then downloads about 30 × 25 KB instead of 30 full-size photos. The thumbnail is a JPEG, so it also previews HEIC uploads, which most browsers cannot display from the original file.

### 6. The search query lives in the URL
Search navigates to `/result?q=...` instead of passing the query in router state, so results survive a refresh and can be bookmarked or shared (useful for the public demo). Each new query remounts the results component, and the previous request is aborted, so a slow old search can never overwrite a newer one's results.

### 7. The demo is the same app with a flag
`VITE_DEMO_MODE=true` builds the public demo: no sign-in, a landing page with example searches and a browsable grid of the photos (paged from the search service's demo-only `GET /browse`), and no upload or profile controls. The account controls sit in their own component that only the signed-in build renders, so the demo never touches the sign-in code. Free Hugging Face Spaces sleep when idle, so a search that takes more than 3 seconds shows "Waking up the demo server…" instead of looking broken.

### 8. Dataset captions are shown, but kept away from results
Every COCO photo comes with captions written by people when the dataset was made; the benchmark uses them as test queries. Showing them under search results made the demo look like text matching, which is exactly what it is not: search compares the query with the image's vector and never reads a caption. Captions now appear only in the full-size viewer, with a note saying so.

### 9. Profile pictures come from the sign-in provider
Custom profile-picture upload used Firebase Storage, which new projects can only use on the paid plan. The profile now shows the sign-in provider's photo (e.g. the Google account picture) and keeps display-name editing.

### Checks
- `npm run lint` and the TypeScript build pass with no errors (the original code had 21 lint errors; the remaining ones in untouched files, mostly `any` types, were fixed too).
- Both builds were driven in Chromium: the demo against a live demo service (the browse grid and "Show more", example search, typed search, all images loading, the viewer and its caption note, the slow-server notice, a server error, unknown routes), and the signed-in build (every page redirects to login when signed out, including results, which the old app left open).
