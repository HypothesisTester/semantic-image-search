// Vector maths for the in-browser demo. No dependencies, so the same code
// runs in the browser and in scripts/verify-browser-model.mjs under Node.

/** Decode IEEE 754 half-precision floats (little-endian) into a Float32Array. */
export function decodeFloat16(buffer: ArrayBuffer): Float32Array {
  const halves = new Uint16Array(buffer);
  const out = new Float32Array(halves.length);
  for (let i = 0; i < halves.length; i++) {
    const h = halves[i];
    const sign = h & 0x8000 ? -1 : 1;
    const exponent = (h >> 10) & 0x1f;
    const fraction = h & 0x3ff;
    if (exponent === 0) {
      out[i] = sign * 2 ** -14 * (fraction / 1024); // zero or subnormal
    } else if (exponent === 0x1f) {
      out[i] = fraction ? NaN : sign * Infinity;
    } else {
      out[i] = sign * 2 ** (exponent - 15) * (1 + fraction / 1024);
    }
  }
  return out;
}

/** Scale a vector to unit length, so a dot product is a cosine similarity. */
export function normalize(v: Float32Array): Float32Array {
  let sum = 0;
  for (let i = 0; i < v.length; i++) sum += v[i] * v[i];
  const norm = Math.sqrt(sum);
  if (norm === 0) throw new Error('cannot normalise a zero vector');
  const out = new Float32Array(v.length);
  for (let i = 0; i < v.length; i++) out[i] = v[i] / norm;
  return out;
}

export interface Match {
  index: number;
  score: number;
}

/**
 * Exact top-k by dot product over `vectors`, a row-major (n x dim) matrix.
 * The same search FAISS's IndexFlatIP does on the server: 5,000 x 512 is
 * 2.6 million multiply-adds, a few milliseconds in JavaScript.
 */
export function topK(vectors: Float32Array, dim: number, query: Float32Array, k: number): Match[] {
  if (query.length !== dim) throw new Error(`query has ${query.length} dimensions, expected ${dim}`);
  const n = vectors.length / dim;
  const best: Match[] = []; // kept sorted, best first; k is small
  for (let row = 0; row < n; row++) {
    let score = 0;
    const offset = row * dim;
    for (let j = 0; j < dim; j++) score += vectors[offset + j] * query[j];
    if (best.length < k || score > best[best.length - 1].score) {
      let pos = best.length;
      while (pos > 0 && best[pos - 1].score < score) pos--;
      best.splice(pos, 0, { index: row, score });
      if (best.length > k) best.pop();
    }
  }
  return best;
}
