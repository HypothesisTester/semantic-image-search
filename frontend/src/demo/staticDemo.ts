// The public demo's search, run entirely in the browser.
//
// The 5,000 photo vectors were computed ahead of time (demo.export_static)
// and are downloaded once, about 5 MB. A query is embedded either from the
// precomputed example searches or by CLIP running in the page, then compared
// with every photo by exact dot product: the same search the server does.

import { decodeFloat16, topK } from './vectorMath';
import { encodeText } from './textEncoder';
import type { ModelProgress } from './textEncoder';

export interface DemoPhoto {
  url: string;
  thumbnailUrl: string;
  caption?: string;
}

export interface DemoResult extends DemoPhoto {
  rank: number;
  score: number;
}

interface Manifest {
  count: number;
  dim: number;
  dtype: string;
}

interface Index {
  dim: number;
  vectors: Float32Array;
  photos: DemoPhoto[];
  examples: Map<string, Float32Array>;
}

/** How queries are matched to precomputed examples (demo.export_static does the same). */
export const normaliseQuery = (text: string) => text.toLowerCase().split(/\s+/).filter(Boolean).join(' ');

// The site's own copy of the data, made at build time (scripts/bundle-demo-data.mjs).
// It serves the data files and the first thumbnails from the site's host,
// without Hugging Face's redirect to a CDN; the rest come from `baseUrl`.
const BUNDLED_THUMBNAILS = __DEMO_BUNDLED_THUMBNAILS__;
const BUNDLE_URL = '/demo-data';
const dataUrl = (baseUrl: string) => (BUNDLED_THUMBNAILS > 0 ? BUNDLE_URL : baseUrl);

let photosPromise: Promise<DemoPhoto[]> | null = null;
let firstPagePromise: Promise<{ total: number; photos: DemoPhoto[] }> | null = null;
let exampleResultsPromise: Promise<Map<string, DemoResult[]>> | null = null;
let indexPromise: Promise<Index> | null = null;

async function fetchOk(url: string): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(url);
  } catch {
    throw new Error('Could not download the demo data. Check your connection and try again.');
  }
  if (!res.ok) throw new Error(`Could not download the demo data (${res.status} for ${url.split('/').pop()}).`);
  return res;
}

/** Retry after a failure instead of caching it. */
function once<T>(get: () => Promise<T> | null, set: (p: Promise<T> | null) => void, load: () => Promise<T>): Promise<T> {
  const existing = get();
  if (existing) return existing;
  const p = load().catch(err => {
    set(null);
    throw err;
  });
  set(p);
  return p;
}

type PhotoEntry = { file: string; caption: string };

function toPhoto(baseUrl: string, p: PhotoEntry, i: number, bundled = i < BUNDLED_THUMBNAILS): DemoPhoto {
  const url = bundled ? `${BUNDLE_URL}/thumbnails/${p.file}` : `${baseUrl}/thumbnails/${p.file}`;
  return { url, thumbnailUrl: url, caption: p.caption || undefined };
}

/** The photo list: all that browsing needs, about 0.5 MB. */
function getPhotos(baseUrl: string): Promise<DemoPhoto[]> {
  return once(() => photosPromise, p => (photosPromise = p), async () => {
    const list = (await fetchOk(`${dataUrl(baseUrl)}/photos.json`).then(r => r.json())) as PhotoEntry[];
    return list.map((p, i) => toPhoto(baseUrl, p, i));
  });
}

/** The site's copy of the first page of the list, a few KB, preloaded by index.html. */
function getFirstPage(baseUrl: string): Promise<{ total: number; photos: DemoPhoto[] }> {
  return once(() => firstPagePromise, p => (firstPagePromise = p), async () => {
    const page = (await fetchOk(`${BUNDLE_URL}/first-page.json`).then(r => r.json())) as { total: number; photos: PhotoEntry[] };
    return { total: page.total, photos: page.photos.map((p, i) => toPhoto(baseUrl, p, i)) };
  });
}

/** Everything searching needs: the photo list plus 5 MB of vectors. */
function getIndex(baseUrl: string): Promise<Index> {
  return once(() => indexPromise, p => (indexPromise = p), async () => {
    const base = dataUrl(baseUrl);
    const [photos, manifest, examples, vectors] = await Promise.all([
      getPhotos(baseUrl),
      fetchOk(`${base}/manifest.json`).then(r => r.json() as Promise<Manifest>),
      fetchOk(`${base}/examples.json`).then(r => r.json() as Promise<{ key: string; vector: number[] }[]>),
      fetchOk(`${base}/vectors.f16`).then(r => r.arrayBuffer()),
    ]);
    if (manifest.dtype !== 'float16') throw new Error(`unsupported vector format ${manifest.dtype}`);
    const decoded = decodeFloat16(vectors);
    if (decoded.length !== manifest.count * manifest.dim || photos.length !== manifest.count) {
      throw new Error('The demo data is incomplete.');
    }
    return {
      dim: manifest.dim,
      vectors: decoded,
      photos,
      examples: new Map(examples.map(e => [e.key, new Float32Array(e.vector)])),
    };
  });
}

type ExampleResult = PhotoEntry & { index: number; score: number; bundled: boolean };

/** The example searches' results, computed at build time (scripts/bundle-demo-data.mjs). */
function getExampleResults(baseUrl: string): Promise<Map<string, DemoResult[]>> {
  return once(() => exampleResultsPromise, p => (exampleResultsPromise = p), async () => {
    const byKey = (await fetchOk(`${BUNDLE_URL}/example-results.json`).then(r => r.json())) as Record<string, ExampleResult[]>;
    return new Map(
      Object.entries(byKey).map(([key, results]) => [
        key,
        results.map((r, i) => ({ ...toPhoto(baseUrl, r, r.index, r.bundled), rank: i + 1, score: r.score })),
      ]),
    );
  });
}

/** Start downloading the search data now, so a search started later doesn't wait. */
export function preloadIndex(baseUrl: string): void {
  getIndex(baseUrl).catch(() => {});
}

export async function browseStatic(baseUrl: string, offset: number, limit: number) {
  if (BUNDLED_THUMBNAILS > 0 && offset + limit <= BUNDLED_THUMBNAILS) {
    const first = await getFirstPage(baseUrl);
    return { total: first.total, items: first.photos.slice(offset, offset + limit) };
  }
  const photos = await getPhotos(baseUrl);
  return { total: photos.length, items: photos.slice(offset, offset + limit) };
}

export async function searchStatic(
  baseUrl: string,
  text: string,
  k: number,
  onModelProgress?: (p: ModelProgress) => void,
): Promise<DemoResult[]> {
  if (BUNDLED_THUMBNAILS > 0) {
    // If the precomputed results can't be loaded, search the normal way below.
    const precomputed = await getExampleResults(baseUrl).then(m => m.get(normaliseQuery(text)), () => undefined);
    if (precomputed && precomputed.length >= k) return precomputed.slice(0, k);
  }
  const index = await getIndex(baseUrl);
  let query = index.examples.get(normaliseQuery(text));
  if (!query) {
    try {
      query = await encodeText(text, onModelProgress);
    } catch {
      throw new Error('Could not download the search model. Check your connection, or try one of the example searches.');
    }
  }
  return topK(index.vectors, index.dim, query, k).map((m, i) => ({
    ...index.photos[m.index],
    rank: i + 1,
    score: m.score,
  }));
}
