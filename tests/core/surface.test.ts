import { describe, expect, it } from 'vitest';
import { createSurface, IndexedSurface } from '../../src/core/surface.js';
import { TRANSPARENT_INDEX } from '../../src/core/types.js';

describe('IndexedSurface', () => {
  it('initializes with TRANSPARENT_INDEX (255) across width * height', () => {
    const surface = createSurface(8, 6);
    expect(surface.width).toBe(8);
    expect(surface.height).toBe(6);
    expect(surface.data.length).toBe(48);
    expect(surface.data.every((px) => px === TRANSPARENT_INDEX)).toBe(true);
  });

  it('truncates fractional coordinates and clamps out-of-bounds writes silently', () => {
    const surface = new IndexedSurface(4, 4);
    surface.put(1.9, 2.8, 3);
    surface.put(-1, 0, 5);
    surface.put(4, 0, 5);
    surface.put(0, -1, 5);
    surface.put(0, 4, 5);

    expect(surface.get(1, 2)).toBe(3);
    expect(surface.get(-1, 0)).toBe(TRANSPARENT_INDEX);
    expect(surface.get(4, 0)).toBe(TRANSPARENT_INDEX);
    // Ensure no scanline wrap occurred at (0, 1) or (3, 1)
    expect(surface.get(0, 1)).toBe(TRANSPARENT_INDEX);
    expect(surface.get(3, 1)).toBe(TRANSPARENT_INDEX);
  });

  it('rejects invalid dimensions and out-of-range palette indices', () => {
    expect(() => createSurface(0, 4)).toThrow(RangeError);
    expect(() => createSurface(4, -2)).toThrow(RangeError);

    const surface = createSurface(4, 4);
    expect(() => surface.put(0, 0, -1)).toThrow(RangeError);
    expect(() => surface.put(0, 0, 256)).toThrow(RangeError);
  });

  it('draws filled and stroked rectangles with clipping', () => {
    const surface = createSurface(6, 6);
    surface.rect(-1, -1, 4, 4, 2, true);
    expect(surface.get(0, 0)).toBe(2);
    expect(surface.get(2, 2)).toBe(2);
    expect(surface.get(3, 3)).toBe(TRANSPARENT_INDEX);

    surface.clear();
    surface.rect(1, 1, 4, 4, 7, false);
    expect(surface.get(1, 1)).toBe(7);
    expect(surface.get(4, 4)).toBe(7);
    expect(surface.get(2, 2)).toBe(TRANSPARENT_INDEX);
  });

  it('draws integer Bresenham lines and midpoint circles', () => {
    const surface = createSurface(9, 9);
    surface.line(0, 0, 8, 8, 1);
    for (let i = 0; i <= 8; i++) {
      expect(surface.get(i, i)).toBe(1);
    }

    surface.clear();
    surface.circle(4, 4, 2, 4, true);
    expect(surface.get(4, 4)).toBe(4);
    expect(surface.get(4, 2)).toBe(4);
    expect(surface.get(6, 4)).toBe(4);
    expect(surface.get(0, 0)).toBe(TRANSPARENT_INDEX);
  });

  it('flood-fills contiguous regions without leaking across borders', () => {
    const surface = createSurface(7, 7);
    surface.rect(1, 1, 5, 5, 1, false);
    surface.fill(3, 3, 9);

    expect(surface.get(3, 3)).toBe(9);
    expect(surface.get(2, 2)).toBe(9);
    expect(surface.get(1, 1)).toBe(1);
    expect(surface.get(0, 0)).toBe(TRANSPARENT_INDEX);
  });

  it('blits ASCII sprite grids and layered surfaces skipping transparent pixels', () => {
    const base = createSurface(6, 6);
    base.clear(10);

    const overlay = createSurface(4, 4);
    overlay.spr(['.#.', '###', '.#.'], 1, 1, { '#': 12 });

    expect(overlay.get(2, 1)).toBe(12);
    expect(overlay.get(1, 1)).toBe(TRANSPARENT_INDEX);

    base.blitLayer(overlay, 1, 1);
    expect(base.get(3, 2)).toBe(12);
    expect(base.get(2, 2)).toBe(10);
  });

  it('applies 4-neighbor autoOutline and top/bottom edgeMask', () => {
    const surface = createSurface(5, 5);
    surface.put(2, 2, 5);
    surface.autoOutline(1);

    expect(surface.get(2, 2)).toBe(5);
    expect(surface.get(2, 1)).toBe(1);
    expect(surface.get(3, 2)).toBe(1);
    expect(surface.get(2, 3)).toBe(1);
    expect(surface.get(1, 2)).toBe(1);
    expect(surface.get(1, 1)).toBe(TRANSPARENT_INDEX);

    const block = createSurface(5, 5);
    block.rect(1, 1, 3, 3, 4, true);
    block.edgeMask(8, 2);
    expect(block.get(2, 1)).toBe(8);
    expect(block.get(2, 2)).toBe(4);
    expect(block.get(2, 3)).toBe(2);
  });

  it('fills angled quadrilaterals with integer rounding and bounds clamping', () => {
    const surface = createSurface(12, 12);
    surface.quad({ x: 2.2, y: 1.8 }, { x: 8.7, y: 3.1 }, { x: 6.9, y: 9.2 }, { x: 0.8, y: 7.9 }, 6);

    // Rounded vertices: (2,2), (9,3), (7,9), (1,8)
    expect(surface.get(2, 2)).toBe(6);
    expect(surface.get(9, 3)).toBe(6);
    expect(surface.get(7, 9)).toBe(6);
    expect(surface.get(1, 8)).toBe(6);
    // Interior point
    expect(surface.get(5, 5)).toBe(6);
    // Outside points remain transparent
    expect(surface.get(0, 0)).toBe(TRANSPARENT_INDEX);
    expect(surface.get(11, 11)).toBe(TRANSPARENT_INDEX);

    // Out-of-bounds quad clips silently without scanline wrap
    const clipped = createSurface(6, 6);
    clipped.quad({ x: -2, y: 1 }, { x: 3, y: 1 }, { x: 3, y: 7 }, { x: -2, y: 7 }, 4);
    expect(clipped.get(0, 1)).toBe(4);
    expect(clipped.get(3, 5)).toBe(4);
    expect(clipped.get(4, 1)).toBe(TRANSPARENT_INDEX);
    expect(clipped.get(5, 1)).toBe(TRANSPARENT_INDEX);
  });
});
