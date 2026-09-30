// The build-time example results must be exactly what the page would compute.
import { describe, expect, it } from 'vitest';
import { decodeFloat16, exampleResults } from './bundle-demo-data.mjs';
import { decodeFloat16 as pageDecode, normalize, topK } from '../src/demo/vectorMath';

function randomUnitVectors(n, dim, seed) {
  let x = seed;
  const rand = () => ((x = (x * 1103515245 + 12345) % 2 ** 31) / 2 ** 31) - 0.5;
  const out = new Float32Array(n * dim);
  for (let i = 0; i < n; i++) out.set(normalize(Float32Array.from({ length: dim }, rand)), i * dim);
  return out;
}

function toFloat16Buffer(values) {
  // Round through the page's own decoder's inverse via DataView-free bit maths.
  const buf = Buffer.alloc(values.length * 2);
  const f32 = new Float32Array(1);
  const u32 = new Uint32Array(f32.buffer);
  values.forEach((v, i) => {
    f32[0] = v;
    const bits = u32[0];
    const sign = (bits >>> 16) & 0x8000;
    const exp = ((bits >>> 23) & 0xff) - 127 + 15;
    const frac = (bits >>> 13) & 0x3ff;
    buf.writeUInt16LE(exp <= 0 ? sign : sign | (exp << 10) | frac, i * 2);
  });
  return buf;
}

describe('bundle-demo-data', () => {
  it('decodes float16 exactly as the page does', () => {
    const buf = toFloat16Buffer(randomUnitVectors(50, 64, 7));
    const bytes = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length);
    expect(Array.from(decodeFloat16(buf))).toEqual(Array.from(pageDecode(bytes)));
  });

  it('ranks example results exactly as the page does', () => {
    const dim = 32;
    const vectors = randomUnitVectors(400, dim, 1);
    const photos = Array.from({ length: 400 }, (_, i) => ({ file: `${i}.jpg`, caption: `photo ${i}` }));
    const queries = randomUnitVectors(5, dim, 2);
    const examples = Array.from({ length: 5 }, (_, i) => ({ key: `q${i}`, vector: Array.from(queries.subarray(i * dim, (i + 1) * dim)) }));
    const results = exampleResults(vectors, dim, examples, photos, 24);
    examples.forEach((e, i) => {
      const expected = topK(vectors, dim, queries.subarray(i * dim, (i + 1) * dim), 24).map(m => m.index);
      expect(results[e.key].map(r => r.index)).toEqual(expected);
      expect(results[e.key][0].file).toBe(`${expected[0]}.jpg`);
    });
  });
});
