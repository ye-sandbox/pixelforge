import { describe, expect, it } from 'vitest';
import { decodePngToRgba, generatePixelDiff, rgbaToPng } from '../../src/export/index.js';
import type { RgbaBuffer } from '../../src/export/png.js';

function makeSolidRgba(
  w: number,
  h: number,
  r: number,
  g: number,
  b: number,
  a: number,
): RgbaBuffer {
  const data = new Uint8Array(w * h * 4);
  for (let i = 0; i < w * h; i++) {
    const o = i * 4;
    data[o] = r;
    data[o + 1] = g;
    data[o + 2] = b;
    data[o + 3] = a;
  }
  return { width: w, height: h, data };
}

describe('generatePixelDiff', () => {
  it('reports 0 changed pixels for identical buffers and encodes valid PNG', () => {
    const a = makeSolidRgba(8, 8, 60, 120, 180, 255);
    const b = makeSolidRgba(8, 8, 60, 120, 180, 255);
    const diff = generatePixelDiff(a, b);

    expect(diff.changedPixels).toBe(0);
    expect(diff.totalPixels).toBe(64);
    expect(diff.png.slice(0, 4)).toEqual(Uint8Array.from([0x89, 0x50, 0x4e, 0x47]));
  });

  it('counts changed pixels accurately across decoded PNGs', () => {
    const base = makeSolidRgba(8, 8, 20, 30, 40, 255);
    const curr = makeSolidRgba(8, 8, 20, 30, 40, 255);
    // Flip 3 pixels
    for (let x = 0; x < 3; x++) {
      const o = x * 4;
      curr.data[o] = 255;
      curr.data[o + 1] = 0;
      curr.data[o + 2] = 0;
    }

    const decodedBase = decodePngToRgba(rgbaToPng(base));
    const diff = generatePixelDiff(decodedBase, curr);
    expect(diff.changedPixels).toBe(3);
    expect(diff.totalPixels).toBe(64);
  });
});
