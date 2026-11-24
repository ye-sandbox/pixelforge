import { describe, expect, it } from 'vitest';
import { hashf, mulberry32, xorshift32 } from '../../src/core/prng.js';

describe('deterministic PRNG', () => {
  it('mulberry32 produces identical sequences for identical seeds', () => {
    const a = mulberry32(42);
    const b = mulberry32(42);
    const seqA = Array.from({ length: 16 }, () => a());
    const seqB = Array.from({ length: 16 }, () => b());

    expect(seqA).toEqual(seqB);
    for (const value of seqA) {
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThan(1);
    }
  });

  it('mulberry32 diverges for different seeds', () => {
    const a = mulberry32(1);
    const b = mulberry32(2);
    expect(a()).not.toBe(b());
  });

  it('xorshift32 handles zero seed without collapsing to zeros', () => {
    const rng = xorshift32(0);
    const values = Array.from({ length: 8 }, () => rng());
    expect(new Set(values).size).toBeGreaterThan(1);
    for (const value of values) {
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThan(1);
    }
  });

  it('hashf is deterministic per (x, y, seed) and stays in [0, 1)', () => {
    expect(hashf(10, 20, 7)).toBe(hashf(10, 20, 7));
    expect(hashf(10.9, 20.4, 7)).toBe(hashf(10, 20, 7));
    expect(hashf(10, 20, 7)).not.toBe(hashf(11, 20, 7));

    for (let y = -4; y <= 4; y++) {
      for (let x = -4; x <= 4; x++) {
        const v = hashf(x, y, 99);
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThan(1);
      }
    }
  });
});
