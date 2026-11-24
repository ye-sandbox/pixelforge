import { describe, expect, it } from 'vitest';
import { isoBox, isoProject, isoTile } from '../../src/core/iso.js';
import { createSurface } from '../../src/core/surface.js';
import { TRANSPARENT_INDEX } from '../../src/core/types.js';

describe('isometric 2:1 primitives', () => {
  it('isoProject maps world coordinates to integer 2:1 screen coordinates', () => {
    expect(isoProject(0, 0, 0, 100, 50)).toEqual({ x: 100, y: 50 });
    expect(isoProject(4, 0, 0, 100, 50)).toEqual({ x: 108, y: 54 });
    expect(isoProject(0, 4, 0, 100, 50)).toEqual({ x: 92, y: 54 });
    expect(isoProject(0, 0, 6, 100, 50)).toEqual({ x: 100, y: 44 });
  });

  it('isoTile renders a symmetric 2:1 diamond', () => {
    const surface = createSurface(17, 9);
    isoTile(surface, 8, 4, 6, 3, 3);

    expect(surface.get(8, 4)).toBe(3);
    expect(surface.get(8, 1)).toBe(3);
    expect(surface.get(8, 7)).toBe(3);
    expect(surface.get(2, 4)).toBe(3);
    expect(surface.get(14, 4)).toBe(3);
    expect(surface.get(0, 0)).toBe(TRANSPARENT_INDEX);
  });

  it('isoBox renders top, left, right faces and optional outline', () => {
    const surface = createSurface(24, 24);
    isoBox(surface, {
      cx: 12,
      cy: 6,
      halfW: 6,
      halfH: 3,
      height: 6,
      topColor: 2,
      leftColor: 3,
      rightColor: 4,
      outlineColor: 1,
    });

    expect(surface.get(12, 6)).toBe(2); // top face center
    expect(surface.get(9, 10)).toBe(3); // left face
    expect(surface.get(15, 10)).toBe(4); // right face
    expect(surface.get(12, 3)).toBe(1); // top apex outline
    expect(surface.get(12, 15)).toBe(1); // bottom center corner outline
  });
});
