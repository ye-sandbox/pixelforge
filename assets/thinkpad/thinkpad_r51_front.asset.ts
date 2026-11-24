import type { AssetModule, PaletteIndex, RenderContext } from '../../src/index.js';

type LaptopState = 'healthy' | 'dusty' | 'faulty';

function buildPalette(ctx: RenderContext<LaptopState>) {
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
    METAL_MID: get('METAL_MID'),
    METAL_LIGHT: get('METAL_LIGHT'),
    SCREEN_BG: get('SCREEN_BG'),
    SCREEN_GREEN: get('SCREEN_GREEN'),
    LED_GREEN: get('LED_GREEN'),
    CYAN_DIM: get('CYAN_DIM'),
    CYAN_GLOW: get('CYAN_GLOW'),
    AMBER_WARN: get('AMBER_WARN'),
    FAULT_RED: get('FAULT_RED'),
    SPARK_YELLOW: get('SPARK_YELLOW'),
    DUST_LIGHT: get('DUST_LIGHT'),
    DUST_DARK: get('DUST_DARK'),
    WINDOW_SKY: get('WINDOW_SKY'),
  };
}

type Pal = ReturnType<typeof buildPalette>;

function drawScreenLid(ctx: RenderContext<LaptopState>, P: Pal): void {
  const { surface, state, frame } = ctx;

  // Outer matte black ThinkPad lid
  surface.rect(8, 5, 32, 22, P.SLATE_DARK, true);
  surface.line(8, 5, 39, 5, P.SLATE_LIGHT);
  surface.line(8, 5, 8, 26, P.SLATE_LIGHT);
  surface.line(39, 6, 39, 26, P.SHADOW);

  // Inner LCD display
  const bg = state === 'faulty' ? P.SCREEN_BG : state === 'dusty' ? P.METAL_DARK : P.METAL_LIGHT;
  surface.rect(11, 8, 26, 16, bg, true);

  // Browser header + XP taskbar
  surface.rect(11, 8, 26, 2, state === 'faulty' ? P.FAULT_RED : P.CYAN_DIM, true);
  surface.rect(11, 22, 26, 2, P.WINDOW_SKY, true);
  surface.rect(11, 22, 4, 2, P.SCREEN_GREEN, true);

  if (state === 'faulty') {
    surface.line(13, 12, 30, 12, P.FAULT_RED);
    surface.line(13, 15, 26, 15, P.AMBER_WARN);
    if (frame === 0) {
      surface.rect(13, 18, 5, 1, P.SPARK_YELLOW, true);
    }
    return;
  }

  // Wikipedia globe + sidebar + article text lines
  surface.rect(12, 11, 5, 10, P.METAL_MID, true);
  surface.rect(13, 12, 3, 3, state === 'dusty' ? P.SLATE_MID : P.SLATE_DARK, true);
  const textCol = state === 'dusty' ? P.SLATE_MID : P.SLATE_DARK;
  surface.line(19, 12, 33, 12, textCol);
  surface.line(19, 15, 35, 15, textCol);
  surface.line(19, 18, 29, 18, textCol);
  if (frame === 0) {
    surface.put(31, 18, P.CYAN_GLOW);
  }
}

function drawKeyboardDeck(ctx: RenderContext<LaptopState>, P: Pal): void {
  const { surface, state, frame } = ctx;

  // Hinge bar + status LEDs
  surface.rect(9, 27, 30, 2, P.METAL_DARK, true);
  surface.rect(12, 27, 5, 2, P.SHADOW, true);
  surface.rect(31, 27, 5, 2, P.SHADOW, true);
  const ledCol =
    state === 'faulty'
      ? P.FAULT_RED
      : state === 'dusty'
        ? P.AMBER_WARN
        : frame === 0
          ? P.LED_GREEN
          : P.SCREEN_GREEN;
  surface.put(22, 28, ledCol);
  surface.put(25, 28, state === 'healthy' ? P.LED_GREEN : P.SHADOW);

  // Angled 2.5D keyboard deck (widens toward front)
  for (let r = 0; r < 11; r++) {
    const pad = r < 4 ? 2 : r < 8 ? 1 : 0;
    const lx = 5 + pad;
    const rx = 42 - pad;
    surface.line(lx, 29 + r, rx, 29 + r, P.SLATE_MID);
    surface.put(lx, 29 + r, P.SLATE_LIGHT);
    surface.put(rx, 29 + r, P.SLATE_DARK);
  }

  // Keyboard recess + keycaps
  surface.rect(9, 30, 30, 5, P.SHADOW, true);
  for (let ky = 31; ky <= 33; ky += 2) {
    for (let kx = 10; kx <= 37; kx += 2) {
      surface.put(kx, ky, P.SLATE_DARK);
    }
  }

  // Iconic blue Enter key + red TrackPoint
  surface.rect(36, 32, 2, 2, P.WINDOW_SKY, true);
  surface.put(23, 32, P.FAULT_RED);

  // TrackPoint buttons with red stripe + Touchpad
  surface.rect(19, 36, 10, 1, P.FAULT_RED, true);
  surface.rect(19, 37, 10, 2, P.SLATE_DARK, true);
  surface.rect(20, 37, 8, 2, P.SHADOW, true);

  // Stickers (left) & IBM ThinkPad badge (right)
  surface.put(8, 38, P.WINDOW_SKY);
  surface.put(10, 38, P.AMBER_WARN);
  surface.put(37, 38, P.FAULT_RED);
  surface.put(38, 38, P.LED_GREEN);
  surface.put(39, 38, P.WINDOW_SKY);

  // Front lip & rubber feet
  surface.rect(5, 40, 38, 3, P.SLATE_DARK, true);
  surface.line(5, 40, 42, 40, P.METAL_DARK);
  surface.rect(8, 43, 4, 1, P.SHADOW, true);
  surface.rect(36, 43, 4, 1, P.SHADOW, true);
}

function drawStateOverlays(ctx: RenderContext<LaptopState>, P: Pal): void {
  const { surface, state, frame, rng } = ctx;

  if (state === 'dusty') {
    for (let i = 0; i < 14; i++) {
      const dx = 8 + ((rng() * 32) | 0);
      const dy = 8 + ((rng() * 32) | 0);
      if (surface.get(dx, dy) !== 255 && surface.get(dx, dy) !== P.SHADOW) {
        surface.put(dx, dy, i % 2 === 0 ? P.DUST_LIGHT : P.DUST_DARK);
      }
    }
    return;
  }

  if (state === 'faulty') {
    const sy = frame === 0 ? 26 : 25;
    surface.put(33, sy, P.SPARK_YELLOW);
    surface.put(34, sy - 1, P.FAULT_RED);
    surface.put(32, sy + 1, P.SPARK_YELLOW);
  }
}

export const thinkpadR51FrontAsset: AssetModule<LaptopState> = {
  id: 'thinkpad_r51_front',
  styleId: 'homelab-16bit',
  width: 48,
  height: 48,
  perspective: 'front-2.5d',
  states: ['healthy', 'dusty', 'faulty'],
  frames: 2,
  fps: 2,
  seed: 511,

  render(ctx) {
    const P = buildPalette(ctx);
    drawScreenLid(ctx, P);
    drawKeyboardDeck(ctx, P);
    drawStateOverlays(ctx, P);

    ctx.surface.autoOutline(P.OUTLINE);

    ctx.anchor('foot', 24, 43);
    ctx.anchor('trackpoint', 23, 32);
    ctx.anchor('screen', 24, 16);
    ctx.anchor('led', 22, 28);
    ctx.hitbox('body', 4, 4, 40, 41);
  },
};
