// The in-browser text encoder: CLIP's text half, loaded on first use.
//
// transformers.js runs a quantised (8-bit) ONNX conversion of the same OpenAI
// CLIP ViT-B/32 weights the server uses. The library and model are loaded
// only when a visitor types a search the page has not precomputed, and the
// browser caches the model afterwards.

import { normalize } from './vectorMath';

export const BROWSER_MODEL = 'Xenova/clip-vit-base-patch32';

export interface ModelProgress {
  loadedMB: number;
  totalMB: number;
}

type Encoder = (text: string) => Promise<Float32Array>;

let encoderPromise: Promise<Encoder> | null = null;
const listeners = new Set<(p: ModelProgress) => void>();

async function loadEncoder(): Promise<Encoder> {
  const { AutoTokenizer, CLIPTextModelWithProjection, env } = await import('@huggingface/transformers');
  // Only fetch from the Hugging Face Hub. Looking for a local /models folder
  // first would hit the site's catch-all route and get HTML back.
  env.allowLocalModels = false;

  const onProgress = (info: { status: string; loaded?: number; total?: number }) => {
    if (info.status === 'progress_total' && info.total) {
      const p = { loadedMB: (info.loaded ?? 0) / 1e6, totalMB: info.total / 1e6 };
      listeners.forEach(fn => fn(p));
    }
  };
  const [tokenizer, model] = await Promise.all([
    AutoTokenizer.from_pretrained(BROWSER_MODEL),
    CLIPTextModelWithProjection.from_pretrained(BROWSER_MODEL, {
      dtype: 'q8',
      progress_callback: onProgress,
    }),
  ]);

  return async (text: string) => {
    const inputs = tokenizer([text], { padding: true, truncation: true });
    const { text_embeds } = await model(inputs);
    return normalize(new Float32Array(text_embeds.data as Float32Array));
  };
}

/** Embed a query with CLIP in the browser. The first call downloads the model. */
export async function encodeText(text: string, onProgress?: (p: ModelProgress) => void): Promise<Float32Array> {
  if (onProgress) listeners.add(onProgress);
  try {
    if (!encoderPromise) {
      encoderPromise = loadEncoder().catch(err => {
        encoderPromise = null; // allow a retry after a failed download
        throw err;
      });
    }
    const encode = await encoderPromise;
    return await encode(text);
  } finally {
    if (onProgress) listeners.delete(onProgress);
  }
}
