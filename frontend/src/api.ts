// Calls to the indexer and search services.
//
// Every request carries the signed-in user's Firebase ID token. The backend
// takes the user from that token, never from the request body, so there is
// no userId to send. getIdToken() returns a cached token and refreshes it
// automatically shortly before it expires.

import { auth } from './config/firebase';
import { DEMO_DATA_URL, DEMO_MODE, INDEX_URL, SEARCH_URL, STATIC_DEMO } from './config/api';
import type { ModelProgress } from './demo/textEncoder';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export interface UploadResult {
  filename: string;
  ok: boolean;
  id?: string;
  url?: string;
  thumbnailUrl?: string;
  error?: string;
}

export interface SearchResult {
  rank: number;
  score: number;
  url: string;
  thumbnailUrl: string;
  caption?: string;
}

async function authHeaders(): Promise<Record<string, string>> {
  if (DEMO_MODE) return {};
  const user = auth.currentUser;
  if (!user) throw new ApiError('You are signed out. Please sign in again.', 401);
  return { Authorization: `Bearer ${await user.getIdToken()}` };
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') return body.detail;
  } catch {
    // not JSON
  }
  return `The server returned ${res.status} ${res.statusText}`.trim();
}

async function send(url: string, init: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    // fetch only throws for network failures (server down, CORS, offline).
    throw new ApiError(`Could not reach ${new URL(url).host}. Is the backend running?`, 0);
  }
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  return res;
}

/** Upload photos to the indexer. One result per file, in the same order. */
export async function uploadPhotos(files: File[]): Promise<UploadResult[]> {
  const form = new FormData();
  for (const file of files) form.append('files', file, file.name);
  const res = await send(`${INDEX_URL}/upload`, {
    method: 'POST',
    headers: await authHeaders(),
    body: form,
  });
  const body = await res.json();
  return body.results as UploadResult[];
}

export interface BrowsePage {
  total: number;
  items: { url: string; thumbnailUrl: string; caption?: string }[];
}

/** A page of the demo's photos, for its landing page (demo mode only). */
export async function browseDemo(offset: number, limit: number, signal?: AbortSignal): Promise<BrowsePage> {
  if (STATIC_DEMO) {
    const { browseStatic } = await import('./demo/staticDemo');
    return browseStatic(DEMO_DATA_URL, offset, limit);
  }
  const res = await send(`${SEARCH_URL}/browse?offset=${offset}&limit=${limit}`, { signal });
  return (await res.json()) as BrowsePage;
}

/** Search the user's photos (or the demo's) by text. */
export async function searchPhotos(
  text: string,
  k: number,
  signal?: AbortSignal,
  onModelProgress?: (p: ModelProgress) => void,
): Promise<SearchResult[]> {
  if (STATIC_DEMO) {
    const { searchStatic } = await import('./demo/staticDemo');
    return searchStatic(DEMO_DATA_URL, text, k, onModelProgress);
  }
  const res = await send(`${SEARCH_URL}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify({ text, k }),
    signal,
  });
  const body = await res.json();
  return body.results as SearchResult[];
}
