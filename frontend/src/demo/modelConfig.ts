// The text model the demo runs in the browser. Shared by textEncoder.ts and
// scripts/verify-browser-model.mjs, so the page and its check always agree.
// No imports, so Node can load it directly.

/** An ONNX conversion of the same OpenAI CLIP ViT-B/32 weights the server uses. */
export const BROWSER_MODEL = 'Xenova/clip-vit-base-patch32';

/**
 * Half precision. Measured against the Python model on 1,000 COCO captions
 * (scripts/verify-browser-model.mjs): fp16 matches it (mean cosine 1.0000,
 * Recall@5 55.0% vs 55.0%, 127 MB), while every 8-bit version loses about
 * 10 points of Recall@5 (mean cosine 0.83, 64 MB). fp32 also matches, at
 * twice the download.
 */
export const BROWSER_DTYPE = 'fp16';
