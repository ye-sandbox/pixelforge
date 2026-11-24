import { describe, expect, it } from 'vitest';
import type { AssetModule, StylePack } from '../../src/core/types.js';
import {
  checkAssetRuntime,
  checkStaticSource,
  formatGuardViolations,
} from '../../src/guard/index.js';

const testStyle: StylePack = {
  id: 'test-style',
  perspective: 'front-2.5d',
  lightingAngle: 'top-left',
  outlineIndex: 0,
  palette: [
    { index: 0, name: 'OUTLINE', hex: '#0d1117', flags: ['outline'] },
    { index: 1, name: 'BODY', hex: '#48525e', flags: ['surface'] },
  ],
};

describe('static guard rules', () => {
  it('flags Math.random in core, style, and asset scopes while ignoring comments', () => {
    const clean = `
      // Math.random() is forbidden
      /* Math.random() */
      export const x = 1;
    `;
    expect(checkStaticSource('src/core/a.ts', clean, 'core')).toEqual([]);

    const dirty = `export const n = Math.random();`;
    const violations = checkStaticSource('assets/a.asset.ts', dirty, 'asset');
    expect(violations).toHaveLength(1);
    expect(violations[0]?.rule).toBe('no-math-random');
    expect(violations[0]?.line).toBe(1);
  });

  it('flags external image imports and DOM/Canvas APIs in asset scope', () => {
    const src = [
      `import img from './sprite.png';`,
      `const c = document.createElement('canvas');`,
    ].join('\n');
    const violations = checkStaticSource('assets/bad.asset.ts', src, 'asset');
    expect(violations.map((v) => v.rule)).toEqual(['no-external-assets', 'no-external-assets']);
    expect(violations.map((v) => v.line)).toEqual([1, 2]);
  });

  it('flags raw hex color literals in asset scope but allows them in style scope', () => {
    const src = `const color = '#ff00aa';`;
    const assetViolations = checkStaticSource('assets/hex.asset.ts', src, 'asset');
    expect(assetViolations).toHaveLength(1);
    expect(assetViolations[0]?.rule).toBe('no-raw-hex');

    expect(checkStaticSource('styles/s.style.ts', src, 'style')).toEqual([]);
  });

  it('formats violations as file:line [rule] detail', () => {
    const formatted = formatGuardViolations(
      [
        {
          file: '/repo/assets/foo.asset.ts',
          line: 12,
          rule: 'no-raw-hex',
          detail: 'Raw hex forbidden',
        },
      ],
      '/repo',
    );
    expect(formatted).toBe('assets/foo.asset.ts:12 [no-raw-hex] Raw hex forbidden');
  });
});

describe('runtime guard rules', () => {
  it('passes a deterministic, closed-palette asset with valid anchors', () => {
    const asset: AssetModule<'idle'> = {
      id: 'valid_box',
      styleId: 'test-style',
      width: 8,
      height: 8,
      perspective: 'front-2.5d',
      states: ['idle'],
      frames: 1,
      seed: 42,
      render(ctx) {
        ctx.surface.rect(1, 1, 6, 6, 1);
        ctx.surface.autoOutline(0);
        ctx.anchor('foot', 4, 7);
        ctx.hitbox('body', 1, 1, 6, 6);
      },
    };
    expect(checkAssetRuntime(asset, testStyle, 'assets/valid.asset.ts')).toEqual([]);
  });

  it('flags undeclared palette indices (closed-palette)', () => {
    const asset: AssetModule<'idle'> = {
      id: 'bad_pal',
      styleId: 'test-style',
      width: 4,
      height: 4,
      perspective: 'front-2.5d',
      states: ['idle'],
      frames: 1,
      render(ctx) {
        ctx.surface.put(2, 2, 99);
      },
    };
    const violations = checkAssetRuntime(asset, testStyle, 'assets/bad_pal.asset.ts');
    expect(violations.some((v) => v.rule === 'closed-palette')).toBe(true);
  });

  it('flags non-deterministic rendering (bit-determinism)', () => {
    let counter = 0;
    const asset: AssetModule<'idle'> = {
      id: 'nondet',
      styleId: 'test-style',
      width: 4,
      height: 4,
      perspective: 'front-2.5d',
      states: ['idle'],
      frames: 1,
      render(ctx) {
        counter++;
        ctx.surface.put(counter % 4, 0, 1);
      },
    };
    const violations = checkAssetRuntime(asset, testStyle, 'assets/nondet.asset.ts');
    expect(violations.some((v) => v.rule === 'bit-determinism')).toBe(true);
  });

  it('flags out-of-bounds and duplicate anchors/hitboxes (valid-anchors)', () => {
    const asset: AssetModule<'idle'> = {
      id: 'bad_anchors',
      styleId: 'test-style',
      width: 8,
      height: 8,
      perspective: 'front-2.5d',
      states: ['idle'],
      frames: 1,
      render(ctx) {
        ctx.surface.put(1, 1, 1);
        ctx.anchor('foot', 12, 4);
        ctx.anchor('foot', 4, 4);
        ctx.hitbox('body', 0, 0, 10, 4);
      },
    };
    const violations = checkAssetRuntime(asset, testStyle, 'assets/bad_anchors.asset.ts');
    const anchorViolations = violations.filter((v) => v.rule === 'valid-anchors');
    expect(anchorViolations.length).toBeGreaterThanOrEqual(3);
  });
});
