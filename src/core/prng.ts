/**
 * Deterministic 32-bit PRNG (mulberry32).
 * Returns floats in [0, 1) without touching Math.random().
 */
export function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Deterministic 32-bit xorshift PRNG.
 * Falls back to a non-zero seed when 0 is passed (xorshift32 fixed-point guard).
 */
export function xorshift32(seed: number): () => number {
  // INVARIANT: xorshift32 degenerates to an all-zero sequence if state === 0
  let state = seed >>> 0 || 0x9e3779b9;
  return () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return (state >>> 0) / 4294967296;
  };
}

/**
 * Stateless coordinate-seeded deterministic hash returning a float in [0, 1).
 */
export function hashf(x: number, y: number, seed = 0): number {
  let h =
    (Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263) + Math.imul(seed | 0, 1442695041)) |
    0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
