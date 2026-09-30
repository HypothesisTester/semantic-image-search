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

async function load(baseUrl: string): Promise<Index> {
  const [manifest, photos, examples, vectors] = await Promise.all([
    fetchOk(`${baseUrl}/manifest.json`).then(r => r.json() as Promise<Manifest>),
    fetchOk(`${baseUrl}/photos.json`).then(r => r.json() as Promise<{ file: string; caption: string }[]>),
    fetchOk(`${baseUrl}/examples.json`).then(r => r.json() as Promise<{ key: string; vector: number[] }[]>),
    fetchOk(`${baseUrl}/vectors.f16`).then(r => r.arrayBuffer()),
  ]);
  if (manifest.dtype !== 'float16') throw new Error(`unsupported vector format ${manifest.dtype}`);
  const decoded = decodeFloat16(vectors);
  if (decoded.length !== manifest.count * manifest.dim || photos.length !== manifest.count) {
    throw new Error('The demo data is incomplete.');
  }
  return {
    dim: manifest.dim,
    vectors: decoded,
    photos: photos.map(p => {
      const url = `${baseUrl}/thumbnails/${p.file}`;
      return { url, thumbnailUrl: url, caption: p.caption || undefined };
    }),
    examples: new Map(examples.map(e => [e.key, new Float32Array(e.vector)])),
  };
}

function getIndex(baseUrl: string): Promise<Index> {
  if (!indexPromise) {
    indexPromise = load(baseUrl).catch(err => {
      indexPromise = null;
      throw err;
    });
  }
  return indexPromise;
}

export async function browseStatic(baseUrl: string, offset: number, limit: number) {
  const index = await getIndex(baseUrl);
  return { total: index.photos.length, items: index.photos.slice(offset, offset + limit) };
}

export async function searchStatic(
  baseUrl: string,
  text: string,
  k: number,
  onModelProgress?: (p: ModelProgress) => void,
): Promise<DemoResult[]> {
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
