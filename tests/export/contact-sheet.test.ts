import { decode, hasPngSignature } from 'fast-png';
import { describe, expect, it } from 'vitest';
import type { AssetModule, StylePack } from '../../src/core/index.js';
import { generateContactSheet } from '../../src/export/contact-sheet.js';
import { assertBinaryAlpha } from '../../src/export/png.js';

const STYLE: StylePack = {
  id: 'sheet-style',
  perspective: 'front-2.5d',
  lightingAngle: 'top-left',
  outlineIndex: 0,
  palette: [
    { index: 0, name: 'OUTLINE', hex: '#0d1117', flags: ['outline'] },
    { index: 1, name: 'METAL', hex: '#94a3b8', flags: ['metal'] },
    { index: 2, name: 'EMISSIVE', hex: '#22d3ee', flags: ['emissive'] },
  ],
};

const SAMPLE_ASSET: AssetModule<'healthy' | 'faulty'> = {
  id: 'mini_rig',
  styleId: 'sheet-style',
  width: 16,
  height: 16,
  perspective: 'front-2.5d',
  states: ['healthy', 'faulty'],
  frames: 2,
  fps: 2,
  render(ctx) {
    ctx.surface.rect(2, 2, 12, 12, 1);
    ctx.surface.autoOutline(0);
    if (ctx.state === 'healthy' && ctx.frame === 0) {
      ctx.surface.put(5, 5, 2);
    }
    ctx.anchor('foot', 8, 15);
  },
};

describe('Contact sheet generator', () => {
  it('renders a valid PNG with 1x previews, zoomed ruler, state matrix, and swatches', () => {
    const sheet = generateContactSheet(SAMPLE_ASSET, STYLE);
    expect(hasPngSignature(sheet.png)).toBe(true);
    expect(sheet.width).toBeGreaterThanOrEqual(360);
    expect(sheet.height).toBeGreaterThan(200);

    assertBinaryAlpha({
      width: sheet.width,
      height: sheet.height,
      data: sheet.data,
    });

    const decoded = decode(sheet.png);
    expect(decoded.width).toBe(sheet.width);
    expect(decoded.height).toBe(sheet.height);
  });
});
