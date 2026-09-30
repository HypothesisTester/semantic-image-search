// Check that the browser's CLIP text encoder agrees with the server's.
//
//   node scripts/verify-browser-model.mjs
//
// Run from frontend/ after `python -m demo.export_static` (in backend/). It
// loads the same quantised model the demo page loads, embeds a sample of
// 1,000 COCO captions, and compares with the Python model's vectors for the
// same captions:
//   - cosine similarity between the two vectors for each caption
//   - text-to-image Recall@1/5/10 over the 5,000 photos, with each model
//
// Uses the Node build of transformers.js, which runs the same ONNX model
// as the browser build. Needs Node 22.18 or newer (to import the shared
// TypeScript maths directly).

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { decodeFloat16, normalize, topK } from '../src/demo/vectorMath.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BROWSER_MODEL = 'Xenova/clip-vit-base-patch32';
const KS = [1, 5, 10];

/** Pure comparison logic, separate from model loading so it can be tested. */
export async function evaluate({ captions, captionImage, pythonVectors, imageVectors, dim, encodeBatch, batchSize = 64 }) {
  const browserVectors = new Float32Array(captions.length * dim);
  for (let start = 0; start < captions.length; start += batchSize) {
    const batch = captions.slice(start, start + batchSize);
    const vectors = await encodeBatch(batch);
    vectors.forEach((v, i) => browserVectors.set(normalize(v), (start + i) * dim));
    process.stdout.write(`\r  embedded ${Math.min(start + batchSize, captions.length)}/${captions.length} captions`);
  }
  process.stdout.write('\n');

  const cosines = captions.map((_, i) => {
    let dot = 0;
    for (let j = 0; j < dim; j++) dot += browserVectors[i * dim + j] * pythonVectors[i * dim + j];
    return dot;
  });
  const sorted = [...cosines].sort((a, b) => a - b);

  const recall = vectors => {
    const hits = Object.fromEntries(KS.map(k => [k, 0]));
    captions.forEach((_, i) => {
      const ranked = topK(imageVectors, dim, vectors.subarray(i * dim, (i + 1) * dim), Math.max(...KS));
      const rank = ranked.findIndex(m => m.index === captionImage[i]);
      KS.forEach(k => { if (rank >= 0 && rank < k) hits[k]++; });
    });
    return Object.fromEntries(KS.map(k => [k, hits[k] / captions.length]));
  };

  return {
    cosine: {
      mean: cosines.reduce((a, b) => a + b, 0) / cosines.length,
      min: sorted[0],
      p1: sorted[Math.floor(sorted.length * 0.01)],
    },
    recallPython: recall(pythonVectors),
    recallBrowser: recall(browserVectors),
  };
}

function readF32(file) {
  const b = readFileSync(file);
  return new Float32Array(b.buffer.slice(b.byteOffset, b.byteOffset + b.length));
}

async function main() {
  const dataDir = path.resolve(process.argv[2] ?? path.join(HERE, '..', '..', 'data'));
  const dtype = process.argv.includes('--fp32') ? 'fp32' : 'q8';
  const check = JSON.parse(readFileSync(path.join(dataDir, 'demo', 'check', 'check.json'), 'utf8'));
  const pythonVectors = readF32(path.join(dataDir, 'demo', 'check', 'check_text_vectors.f32'));
  const f16 = readFileSync(path.join(dataDir, 'demo', 'static', 'vectors.f16'));
  const imageVectors = decodeFloat16(f16.buffer.slice(f16.byteOffset, f16.byteOffset + f16.length));

  console.log(`loading ${BROWSER_MODEL} (${dtype}) ...`);
  const { AutoTokenizer, CLIPTextModelWithProjection } = await import('@huggingface/transformers');
  const tokenizer = await AutoTokenizer.from_pretrained(BROWSER_MODEL);
  const model = await CLIPTextModelWithProjection.from_pretrained(BROWSER_MODEL, { dtype });
  const encodeBatch = async batch => {
    const { text_embeds } = await model(tokenizer(batch, { padding: true, truncation: true }));
    const [n, d] = text_embeds.dims;
    return Array.from({ length: n }, (_, i) => new Float32Array(text_embeds.data.subarray(i * d, (i + 1) * d)));
  };

  const r = await evaluate({
    captions: check.captions,
    captionImage: check.caption_image,
    pythonVectors,
    imageVectors,
    dim: check.dim,
    encodeBatch,
  });

  const pct = x => `${(x * 100).toFixed(1)}%`;
  console.log(`\nBrowser model (${dtype}) vs Python model, ${check.captions.length} COCO captions\n`);
  console.log(`cosine similarity of the two vectors per caption: mean ${r.cosine.mean.toFixed(4)}, worst 1% ${r.cosine.p1.toFixed(4)}, min ${r.cosine.min.toFixed(4)}\n`);
  console.log('| Text-to-image recall | R@1 | R@5 | R@10 |');
  console.log('|---|---|---|---|');
  console.log(`| Python (server) | ${KS.map(k => pct(r.recallPython[k])).join(' | ')} |`);
  console.log(`| Browser (${dtype}) | ${KS.map(k => pct(r.recallBrowser[k])).join(' | ')} |`);
  const gap = Math.abs(r.recallBrowser[5] - r.recallPython[5]);
  console.log(`\n${r.cosine.mean > 0.98 && gap < 0.02 ? 'AGREE' : 'DISAGREE'}: mean cosine ${r.cosine.mean.toFixed(4)}, R@5 difference ${(gap * 100).toFixed(1)} points`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main().catch(err => {
    console.error(err);
    process.exit(1);
  });
}
