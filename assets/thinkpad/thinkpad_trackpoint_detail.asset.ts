import type { AssetModule, PaletteIndex, RenderContext } from '../../src/index.js';

type DeckState = 'healthy' | 'dusty' | 'faulty';

function buildPalette(ctx: RenderContext<DeckState>) {
  const byName = new Map<string, PaletteIndex>();
  for (const entry of ctx.style.palette) {
    byName.set(entry.name, entry.index);
  }
  const get = (name: string): PaletteIndex => {
    const idx = byName.get(name);
    if (idx === undefined) throw new Error(`Missing palette token: ${name}`);
    return idx;
  };
  return {
    OUTLINE: get('OUTLINE'),
    SHADOW: get('SHADOW'),
    SLATE_DARK: get('SLATE_DARK'),
    SLATE_MID: get('SLATE_MID'),
    SLATE_LIGHT: get('SLATE_LIGHT'),
    METAL_DARK: get('METAL_DARK'),
    LED_GREEN: get('LED_GREEN'),
    AMBER_WARN: get('AMBER_WARN'),
    FAULT_RED: get('FAULT_RED'),
    SPARK_YELLOW: get('SPARK_YELLOW'),
    DUST_LIGHT: get('DUST_LIGHT'),
    DUST_DARK: get('DUST_DARK'),
    WINDOW_SKY: get('WINDOW_SKY'),
  };
}

export const thinkpadTrackpointDetailAsset: AssetModule<DeckState> = {
  id: 'thinkpad_trackpoint_detail',
  styleId: 'homelab-16bit',
  width: 32,
  height: 32,
  perspective: 'top-down',
  states: ['healthy', 'dusty', 'faulty'],
  frames: 2,
  fps: 2,
  seed: 512,

  render(ctx) {
    const P = buildPalette(ctx);
    const { surface, state, frame, rng } = ctx;

    // Top-down ThinkPad palmrest & keyboard deck (1px margin for autoOutline)
    surface.rect(2, 2, 28, 28, P.SLATE_MID, true);
    surface.line(2, 2, 29, 2, P.SLATE_LIGHT);
    surface.line(2, 2, 2, 29, P.SLATE_LIGHT);
    surface.line(29, 3, 29, 29, P.SLATE_DARK);
    surface.line(3, 29, 29, 29, P.SLATE_DARK);

    // Top hinge strip + status LED
    surface.rect(2, 2, 28, 2, P.METAL_DARK, true);
    const ledColor =
      state === 'faulty'
        ? P.FAULT_RED
        : state === 'dusty'
          ? P.AMBER_WARN
          : frame === 0
            ? P.LED_GREEN
            : P.SHADOW;
    surface.put(16, 3, ledColor);

    // Keyboard well
    surface.rect(4, 5, 24, 12, P.SHADOW, true);
    for (let ky = 6; ky <= 14; ky += 2) {
      for (let kx = 5; kx <= 26; kx += 2) {
        surface.put(kx, ky, P.SLATE_DARK);
      }
    }

    // Blue Enter key + blue Access IBM key
    surface.rect(25, 10, 2, 3, P.WINDOW_SKY, true);
    surface.rect(5, 6, 3, 1, P.WINDOW_SKY, true);

    // Iconic red TrackPoint nub (G/H/B cluster)
    surface.rect(14, 10, 2, 2, P.FAULT_RED, true);

    // TrackPoint mouse buttons with red stripes
    surface.rect(11, 18, 3, 2, P.SLATE_DARK, true);
    surface.rect(14, 18, 2, 2, P.WINDOW_SKY, true);
    surface.rect(16, 18, 3, 2, P.SLATE_DARK, true);
    surface.line(11, 18, 13, 18, P.FAULT_RED);
    surface.line(16, 18, 18, 18, P.FAULT_RED);

    // Touchpad + lower buttons
    surface.rect(10, 21, 10, 6, P.SHADOW, true);
    surface.rect(11, 22, 8, 4, P.SLATE_DARK, true);
    surface.rect(10, 27, 4, 2, P.SLATE_DARK, true);
    surface.rect(16, 27, 4, 2, P.SLATE_DARK, true);

    // Centrino / XP stickers (left) & IBM ThinkPad badge (right)
    surface.rect(4, 25, 2, 2, P.WINDOW_SKY, true);
    surface.rect(7, 25, 2, 2, P.AMBER_WARN, true);
    surface.put(24, 26, P.FAULT_RED);
    surface.put(25, 26, P.LED_GREEN);
    surface.put(26, 26, P.WINDOW_SKY);

    if (state === 'dusty') {
      for (let i = 0; i < 10; i++) {
        const dx = 4 + ((rng() * 24) | 0);
        const dy = 5 + ((rng() * 22) | 0);
        surface.put(dx, dy, i % 2 === 0 ? P.DUST_LIGHT : P.DUST_DARK);
      }
    } else if (state === 'faulty') {
      const sy = frame === 0 ? 11 : 10;
      surface.put(21, sy, P.SPARK_YELLOW);
      surface.put(22, sy - 1, P.FAULT_RED);
    }

    surface.autoOutline(P.OUTLINE);

    ctx.anchor('trackpoint', 14, 10);
    ctx.anchor('enter_key', 25, 11);
    ctx.anchor('touchpad', 15, 24);
    ctx.anchor('badge', 25, 26);
    ctx.hitbox('body', 1, 1, 30, 30);
  },
};
