// Copy the demo's data into the site at build time (runs before `npm run build`).
//
// Without this, the page fetches everything from Hugging Face, where each file
// is a redirect to a CDN in another region: slow on a phone before the first
// photo appears. So the build downloads the small data files, the photo
// vectors, the first page of photos and the example searches' results (with
// their thumbnails) into public/demo-data/, to be
// served from the site's own host. The rest of the thumbnails and the model
// still come from Hugging Face. Copying everything at once also keeps the
// photo list and vectors of a deployment in step with each other.
//
// Only for demo builds with a remote VITE_DEMO_DATA_URL. If the download fails,
// the build carries on and the page fetches from Hugging Face as before.

import { mkdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const BUNDLE_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'public', 'demo-data');
export const FIRST_THUMBNAILS = 48;
// Results kept per example search: more than the page shows (12).
export const EXAMPLE_RESULTS = 24;
const EXAMPLE_THUMBNAILS = 12;

/** IEEE 754 half precision to float, as src/demo/vectorMath.ts decodes it. */
export function decodeFloat16(buf) {
  const out = new Float32Array(buf.length / 2);
  for (let i = 0; i < out.length; i++) {
    const h = buf.readUInt16LE(i * 2);
    const sign = h & 0x8000 ? -1 : 1;
    const exp = (h >> 10) & 0x1f;
    const frac = h & 0x3ff;
    out[i] = exp === 0 ? sign * 2 ** -14 * (frac / 1024)
      : exp === 31 ? (frac ? NaN : sign * Infinity)
      : sign * 2 ** (exp - 15) * (1 + frac / 1024);
  }
  return out;
}

/**
 * The top results for each example search, by the same exact dot product
 * the page uses, so clicking an example needs neither the vectors nor a
 * round trip for the photo list.
 */
export function exampleResults(vectors, dim, examples, photos, k = EXAMPLE_RESULTS) {
  const results = {};
  for (const { key, vector } of examples) {
    const scores = [];
    for (let i = 0; i < photos.length; i++) {
      let dot = 0;
      for (let j = 0; j < dim; j++) dot += vectors[i * dim + j] * vector[j];
      scores.push([dot, i]);
    }
    scores.sort((a, b) => b[0] - a[0] || a[1] - b[1]);
    results[key] = scores.slice(0, k).map(([score, i]) => ({ index: i, file: photos[i].file, caption: photos[i].caption, score }));
  }
  return results;
}

async function download(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} for ${url}`);
  return Buffer.from(await res.arrayBuffer());
}

async function inBatches(items, size, fn) {
  for (let i = 0; i < items.length; i += size) await Promise.all(items.slice(i, i + size).map(fn));
}

export async function bundle(baseUrl, outDir = BUNDLE_DIR, firstThumbnails = FIRST_THUMBNAILS) {
  await rm(outDir, { recursive: true, force: true });
  const files = {};
  for (const name of ['manifest.json', 'photos.json', 'examples.json', 'vectors.f16']) {
    files[name] = await download(`${baseUrl}/${name}`);
  }
  const manifest = JSON.parse(files['manifest.json']);
  const photos = JSON.parse(files['photos.json']);
  const expectedBytes = manifest.count * manifest.dim * 2;
  if (photos.length !== manifest.count || files['vectors.f16'].length !== expectedBytes) {
    throw new Error('the demo data is inconsistent (photo count or vector size does not match the manifest)');
  }

  const examples = exampleResults(decodeFloat16(files['vectors.f16']), manifest.dim, JSON.parse(files['examples.json']), photos);
  const thumbnails = photos.slice(0, firstThumbnails).map(p => p.file);
  const exampleThumbnails = Object.values(examples).flatMap(r => r.slice(0, EXAMPLE_THUMBNAILS).map(p => p.file));
  const toCopy = [...new Set([...thumbnails, ...exampleThumbnails])];
  for (const r of Object.values(examples)) r.forEach((p, rank) => (p.bundled = rank < EXAMPLE_THUMBNAILS));

  await mkdir(path.join(outDir, 'thumbnails'), { recursive: true });
  for (const [name, data] of Object.entries(files)) await writeFile(path.join(outDir, name), data);
  await writeFile(path.join(outDir, 'example-results.json'), JSON.stringify(examples));
  await inBatches(toCopy, 8, async file => {
    await writeFile(path.join(outDir, 'thumbnails', file), await download(`${baseUrl}/thumbnails/${file}`));
  });
  // The first page's entries on their own (a few KB), so the first photos can
  // show before the full 0.5 MB list has arrived.
  const firstPage = { total: photos.length, photos: photos.slice(0, firstThumbnails) };
  await writeFile(path.join(outDir, 'first-page.json'), JSON.stringify(firstPage));
  // Read by vite.config.ts: which thumbnails the site serves itself.
  await writeFile(path.join(outDir, 'bundle.json'), JSON.stringify({ thumbnails }));
  return { firstPage: thumbnails.length, copied: toCopy.length };
}

async function main() {
  const baseUrl = process.env.VITE_DEMO_DATA_URL;
  if (process.env.VITE_DEMO_MODE !== 'true' || !baseUrl || !/^https?:\/\//.test(baseUrl)) {
    await rm(BUNDLE_DIR, { recursive: true, force: true });
    console.log('bundle-demo-data: not a static demo build, nothing to copy');
    return;
  }
  try {
    const { firstPage, copied } = await bundle(baseUrl.replace(/\/$/, ''));
    console.log(`bundle-demo-data: copied the demo data and ${copied} thumbnails (the first ${firstPage} and the example searches' results) into public/demo-data`);
  } catch (err) {
    await rm(BUNDLE_DIR, { recursive: true, force: true });
    console.warn(`bundle-demo-data: skipped, the page will fetch from ${baseUrl} instead (${err.message})`);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) await main();
