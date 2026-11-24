import { describe, expect, it } from 'vitest';
import { createPaletteLookup, type StylePack } from '../../src/core/index.js';

const TEST_STYLE: StylePack = {
  id: 'test-pack',
  perspective: 'front-2.5d',
  lightingAngle: 'top-left',
  outlineIndex: 0,
  palette: [
    { index: 0, name: 'OUTLINE', hex: '#0d1117', flags: ['outline'] },
    { index: 1, name: 'CHASSIS_DARK', hex: '#2b323b', flags: ['shadow'] },
    { index: 2, name: 'CHASSIS_MID', hex: '#48525e', flags: ['surface'] },
    { index: 5, name: 'LED_GREEN', hex: '#3fb950', flags: ['emissive'] },
  ],
};

describe('createPaletteLookup', () => {
  it('resolves requested tokens from a StylePack with strict key typing', () => {
    const pal = createPaletteLookup(TEST_STYLE, ['OUTLINE', 'CHASSIS_MID', 'LED_GREEN']);
    expect(pal.OUTLINE).toBe(0);
    expect(pal.CHASSIS_MID).toBe(2);
    expect(pal.LED_GREEN).toBe(5);
    expect(Object.keys(pal)).toEqual(['OUTLINE', 'CHASSIS_MID', 'LED_GREEN']);
  });

  it('resolves all StylePack tokens when called with a RenderContext-like object', () => {
    const pal = createPaletteLookup({ style: TEST_STYLE });
    expect(pal.OUTLINE).toBe(0);
    expect(pal.CHASSIS_DARK).toBe(1);
    expect(pal.CHASSIS_MID).toBe(2);
    expect(pal.LED_GREEN).toBe(5);
  });

  it('throws an explicit error when a requested token is missing at creation time', () => {
    expect(() => createPaletteLookup(TEST_STYLE, ['OUTLINE', 'NON_EXISTENT'])).toThrow(
      'Missing palette token: NON_EXISTENT (style: test-pack)',
    );
  });

  it('throws an explicit error when accessing an undeclared token on the lookup', () => {
    const pal = createPaletteLookup(TEST_STYLE);
    expect(() => pal.NON_EXISTENT).toThrow(
      'Missing palette token: NON_EXISTENT (style: test-pack)',
    );
  });

  it('does not treat lookup as a thenable when inspecting .then', () => {
    const pal = createPaletteLookup(TEST_STYLE);
    expect((pal as { then?: unknown }).then).toBeUndefined();
  });
});
