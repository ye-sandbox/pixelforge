import { describe, expect, it } from 'vitest';
import { planeProject } from '../../src/core/plane.js';

describe('planeProject', () => {
  const p0 = { x: 17, y: 32 };
  const p1 = { x: 52, y: 41 };
  const p2 = { x: 5, y: 49 };

  it('maps basis corners (0,0), (1,0), (0,1), and (1,1) deterministically', () => {
    expect(planeProject(p0, p1, p2, 0, 0)).toEqual({ x: 17, y: 32 });
    expect(planeProject(p0, p1, p2, 1, 0)).toEqual({ x: 52, y: 41 });
    expect(planeProject(p0, p1, p2, 0, 1)).toEqual({ x: 5, y: 49 });
    expect(planeProject(p0, p1, p2, 1, 1)).toEqual({ x: 40, y: 58 });
  });

  it('rounds fractional coordinates to the nearest integer without -0', () => {
    expect(planeProject(p0, p1, p2, 0.45, 0.29)).toEqual({ x: 29, y: 41 });
    expect(planeProject({ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0, y: 1 }, -0.1, 0)).toEqual({
      x: 0,
      y: 0,
    });
  });

  it('supports arbitrary negative and >1 extrapolation coordinates', () => {
    expect(planeProject({ x: 10, y: 10 }, { x: 20, y: 10 }, { x: 10, y: 20 }, 1.5, -0.5)).toEqual({
      x: 25,
      y: 5,
    });
  });
});
