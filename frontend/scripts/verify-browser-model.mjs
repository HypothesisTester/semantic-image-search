// Check that the browser's CLIP text encoder agrees with the server's.
//
//   node scripts/verify-browser-model.mjs
//   node scripts/verify-browser-model.mjs --dtypes q8,fp16,fp32   (compare precisions)
//
// Run from frontend/ after `python -m demo.export_static` (in backend/). It
// loads the same model the demo page loads, embeds a sample of
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

function parseArgs(argv) {
  const args = { dataDir: path.join(HERE, '..', '..', 'data'), dtypes: ['q8'] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--dtypes') args.dtypes = argv[++i].split(',');
    else if (argv[i] === '--fp32') args.dtypes = ['fp32'];
    else args.dataDir = argv[i];
  }
  return args;
}

async function main() {
  const { dataDir, dtypes } = parseArgs(process.argv.slice(2));
  const check = JSON.parse(readFileSync(path.join(dataDir, 'demo', 'check', 'check.json'), 'utf8'));
  const pythonVectors = readF32(path.join(dataDir, 'demo', 'check', 'check_text_vectors.f32'));
  const f16 = readFileSync(path.join(dataDir, 'demo', 'static', 'vectors.f16'));
  const imageVectors = decodeFloat16(f16.buffer.slice(f16.byteOffset, f16.byteOffset + f16.length));
  const { AutoTokenizer, CLIPTextModelWithProjection } = await import('@huggingface/transformers');
  const tokenizer = await AutoTokenizer.from_pretrained(BROWSER_MODEL);

  const pct = x => `${(x * 100).toFixed(1)}%`;
  const rows = [];
  let pythonRecall = null;
  for (const dtype of dtypes) {
    console.log(`\nloading ${BROWSER_MODEL} (${dtype}) ...`);
    let sizeMB = null;
    let model;
    try {
      model = await CLIPTextModelWithProjection.from_pretrained(BROWSER_MODEL, {
        dtype,
        progress_callback: info => {
          if (info.status === 'progress_total' && info.total) sizeMB = info.total / 1e6;
        },
      });
    } catch (err) {
      rows.push({ dtype, error: String(err.message ?? err).split('\n')[0] });
      continue;
    }
    const encodeBatch = async batch => {
      const { text_embeds } = await model(tokenizer(batch, { padding: true, truncation: true }));
      const [n, d] = text_embeds.dims;
      return Array.from({ length: n }, (_, i) => new Float32Array(text_embeds.data.subarray(i * d, (i + 1) * d)));
    };
    try {
      const r = await evaluate({
        captions: check.captions,
        captionImage: check.caption_image,
        pythonVectors,
        imageVectors,
        dim: check.dim,
        encodeBatch,
      });
      pythonRecall = r.recallPython;
      rows.push({ dtype, sizeMB, ...r });
    } catch (err) {
      rows.push({ dtype, error: String(err.message ?? err).split('\n')[0] });
    }
  }

  console.log(`\nBrowser model vs Python model, ${check.captions.length} COCO captions\n`);
  console.log('| Model | Download | Mean cosine | Worst 1% | R@1 | R@5 | R@10 | Verdict |');
  console.log('|---|---|---|---|---|---|---|---|');
  if (pythonRecall) {
    console.log(`| Python (server) | - | 1 | 1 | ${KS.map(k => pct(pythonRecall[k])).join(' | ')} | reference |`);
  }
  for (const row of rows) {
    if (row.error) {
      console.log(`| ${row.dtype} | - | - | - | - | - | - | failed: ${row.error.slice(0, 60)} |`);
      continue;
    }
    const gap = Math.abs(row.recallBrowser[5] - row.recallPython[5]);
    const agree = row.cosine.mean > 0.98 && gap < 0.02;
    const size = row.sizeMB ? `${row.sizeMB.toFixed(0)} MB` : 'cached';
    console.log(
      `| ${row.dtype} | ${size} | ${row.cosine.mean.toFixed(4)} | ${row.cosine.p1.toFixed(4)} | ` +
      `${KS.map(k => pct(row.recallBrowser[k])).join(' | ')} | ${agree ? 'AGREE' : 'DISAGREE'} |`,
    );
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main().catch(err => {
    console.error(err);
    process.exit(1);
  });
}
