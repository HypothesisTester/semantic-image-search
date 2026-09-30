import { describe, expect, it } from 'vitest';
import { decodeFloat16, normalize, topK } from './vectorMath';

// Half-precision bit patterns, as numpy's float16 writes them.
const halves = (values: number[]) => new Uint16Array(values).buffer;

describe('decodeFloat16', () => {
  it('decodes normal values, zero, negatives and powers of two', () => {
    // 0x3C00 = 1, 0xC000 = -2, 0x3800 = 0.5, 0x0000 = 0, 0x3555 ~ 0.33325, 0x7BFF = 65504 (max)
    const out = decodeFloat16(halves([0x3c00, 0xc000, 0x3800, 0x0000, 0x3555, 0x7bff]));
    expect(Array.from(out.slice(0, 4))).toEqual([1, -2, 0.5, 0]);
    expect(out[4]).toBeCloseTo(0.33325, 5);
    expect(out[5]).toBe(65504);
  });

  it('decodes subnormals, infinities and NaN', () => {
    const out = decodeFloat16(halves([0x0001, 0x7c00, 0xfc00, 0x7e00]));
    expect(out[0]).toBeCloseTo(5.960464e-8, 12); // smallest subnormal, 2^-24
    expect(out[1]).toBe(Infinity);
    expect(out[2]).toBe(-Infinity);
    expect(Number.isNaN(out[3])).toBe(true);
  });
});

describe('normalize', () => {
  it('scales to unit length', () => {
    expect(Array.from(normalize(new Float32Array([3, 4])))).toEqual([
      expect.closeTo(0.6, 6),
      expect.closeTo(0.8, 6),
    ]);
  });

  it('rejects a zero vector', () => {
    expect(() => normalize(new Float32Array([0, 0]))).toThrow();
  });
});

describe('topK', () => {
  // Four 2-d unit vectors at 0, 30, 60 and 90 degrees.
  const angles = [0, 30, 60, 90].map(d => (d * Math.PI) / 180);
  const vectors = new Float32Array(angles.flatMap(a => [Math.cos(a), Math.sin(a)]));

  it('returns the best matches in order, with cosine scores', () => {
    const query = new Float32Array([Math.cos(Math.PI / 4), Math.sin(Math.PI / 4)]); // 45 degrees
    const result = topK(vectors, 2, query, 3);
    expect(result.map(m => m.index)).toEqual([1, 2, 0]); // 30 and 60 tie at 15 degrees away; stable order
    expect(result[0].score).toBeCloseTo(Math.cos(Math.PI / 12), 5);
    expect(result[2].score).toBeCloseTo(Math.cos(Math.PI / 4), 5);
  });

  it('matches a brute-force sort on random data', () => {
    const n = 500, dim = 16, k = 7;
    let seed = 42;
    const random = () => ((seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31) - 0.5;
    const data = new Float32Array(n * dim).map(random);
    const query = normalize(new Float32Array(dim).map(random));
    const scores = Array.from({ length: n }, (_, row) =>
      query.reduce((sum, q, j) => sum + q * data[row * dim + j], 0),
    );
    const expected = scores.map((s, i) => [s, i]).sort((a, b) => b[0] - a[0]).slice(0, k).map(x => x[1]);
    expect(topK(data, dim, query, k).map(m => m.index)).toEqual(expected);
  });

  it('handles k larger than the collection, and rejects a wrong-sized query', () => {
    expect(topK(vectors, 2, new Float32Array([1, 0]), 10)).toHaveLength(4);
    expect(() => topK(vectors, 2, new Float32Array([1, 0, 0]), 1)).toThrow();
  });
});
