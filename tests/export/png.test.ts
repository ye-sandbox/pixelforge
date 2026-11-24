import { decode, hasPngSignature } from 'fast-png';
import { describe, expect, it } from 'vitest';
import { createSurface, type StylePack, TRANSPARENT_INDEX } from '../../src/core/index.js';
import {
  assertBinaryAlpha,
  parseHexColor,
  surfaceToPng,
  surfaceToRgba,
} from '../../src/export/png.js';

const TEST_STYLE: StylePack = {
  id: 'test-pack',
  perspective: 'front-2.5d',
  lightingAngle: 'top-left',
  outlineIndex: 0,
  palette: [
    { index: 0, name: 'OUTLINE', hex: '#0d1117', flags: ['outline'] },
    { index: 1, name: 'CHASSIS', hex: '#4b5563', flags: ['surface'] },
    { index: 2, name: 'LED_CYAN', hex: '#38bdf8', flags: ['emissive', 'accent'] },
  ],
  variants: {
    night: {
      CHASSIS: '#1f2937',
    },
  },
};

describe('PNG & RGBA exporter', () => {
  it('parses #rrggbb hex colors and rejects malformed values', () => {
    expect(parseHexColor('#38bdf8')).toEqual([0x38, 0xbd, 0xf8]);
    expect(() => parseHexColor('#fff')).toThrow();
    expect(() => parseHexColor('red')).toThrow();
  });

  it('enforces binary alpha (0 or 255) and roundtrips through fast-png', () => {
    const surface = createSurface(4, 4);
    surface.put(1, 1, 0);
    surface.put(2, 1, 1);
    surface.put(2, 2, 2);

    const rgba = surfaceToRgba(surface, TEST_STYLE);
    expect(rgba.width).toBe(4);
    expect(rgba.height).toBe(4);
    assertBinaryAlpha(rgba);

    const png = surfaceToPng(surface, TEST_STYLE);
    expect(hasPngSignature(png)).toBe(true);

    const decoded = decode(png);
    expect(decoded.width).toBe(4);
    expect(decoded.height).toBe(4);
    expect(decoded.channels).toBe(4);

    // (0,0) is transparent
    expect(decoded.data[3]).toBe(0);
    // (1,1) is OUTLINE (#0d1117, alpha 255)
    const p11 = (1 * 4 + 1) * 4;
    expect([
      decoded.data[p11],
      decoded.data[p11 + 1],
      decoded.data[p11 + 2],
      decoded.data[p11 + 3],
    ]).toEqual([0x0d, 0x11, 0x17, 255]);
  });

  it('assertBinaryAlpha throws on semi-transparent alpha values', () => {
    const bad = {
      width: 2,
      height: 1,
      data: new Uint8Array([255, 0, 0, 255, 0, 255, 0, 128]),
    };
    expect(() => assertBinaryAlpha(bad)).toThrow(/Non-binary alpha 128 at \(1, 0\)/);
  });

  it('supports nearest-neighbor integer scaling without mixels', () => {
    const surface = createSurface(2, 2);
    surface.put(0, 0, 2);
    const rgba = surfaceToRgba(surface, TEST_STYLE, { scale: 3 });
    expect(rgba.width).toBe(6);
    expect(rgba.height).toBe(6);
    assertBinaryAlpha(rgba);

    // Top-left 3x3 block should be LED_CYAN, (3,0) should be transparent
    expect(rgba.data[(2 * 6 + 2) * 4 + 3]).toBe(255);
    expect(rgba.data[3 * 4 + 3]).toBe(0);
  });

  it('filters to emissive-only pixels when emissiveOnly is true', () => {
    const surface = createSurface(3, 1);
    surface.put(0, 0, 0); // outline (non-emissive)
    surface.put(1, 0, 1); // chassis (non-emissive)
    surface.put(2, 0, 2); // LED_CYAN (emissive)

    const rgba = surfaceToRgba(surface, TEST_STYLE, { emissiveOnly: true });
    assertBinaryAlpha(rgba);
    expect(rgba.data[3]).toBe(0);
    expect(rgba.data[4 + 3]).toBe(0);
    expect(rgba.data[8 + 3]).toBe(255);
    expect(rgba.data[8]).toBe(0x38);
  });

  it('applies named StylePack variants and rejects undeclared indices', () => {
    const surface = createSurface(2, 1);
    surface.put(0, 0, 1);
    const night = surfaceToRgba(surface, TEST_STYLE, { variant: 'night' });
    expect([night.data[0], night.data[1], night.data[2]]).toEqual([0x1f, 0x29, 0x37]);

    expect(() => surfaceToRgba(surface, TEST_STYLE, { variant: 'missing' })).toThrow();

    surface.put(1, 0, 99);
    expect(() => surfaceToRgba(surface, TEST_STYLE)).toThrow(/Undeclared palette index 99/);
    expect(TRANSPARENT_INDEX).toBe(255);
  });
});
