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
    SCREEN_BG: get('SCREEN_BG'),
    SCREEN_GREEN: get('SCREEN_GREEN'),
    LED_GREEN: get('LED_GREEN'),
    CYAN_DIM: get('CYAN_DIM'),
    CYAN_GLOW: get('CYAN_GLOW'),
    CYAN_BRIGHT: get('CYAN_BRIGHT'),
    AMBER_WARN: get('AMBER_WARN'),
    FAULT_RED: get('FAULT_RED'),
    SPARK_YELLOW: get('SPARK_YELLOW'),
    DUST_LIGHT: get('DUST_LIGHT'),
    DUST_DARK: get('DUST_DARK'),
  };
}

type Pal = ReturnType<typeof buildPalette>;

function drawScreen(ctx: RenderContext<LaptopState>, P: Pal): void {
  const { surface, state, frame } = ctx;

  // Screen lid chassis (top-left bevel highlight, right/bottom shadow)
  surface.rect(5, 4, 22, 15, P.SLATE_MID, true);
  surface.line(5, 4, 26, 4, P.SLATE_LIGHT);
  surface.line(5, 4, 5, 18, P.SLATE_LIGHT);
  surface.line(26, 5, 26, 18, P.SLATE_DARK);
  surface.line(6, 18, 26, 18, P.SLATE_DARK);

  // Inner LCD bezel & dark terminal background
  surface.rect(7, 6, 18, 11, P.SCREEN_BG, true);
  surface.line(7, 6, 24, 6, P.SHADOW);
  surface.line(7, 6, 7, 16, P.SHADOW);

  // Terminal prompt lines
  if (state === 'faulty') {
    surface.line(9, 8, 18, 8, P.FAULT_RED);
    surface.line(9, 10, 21, 10, P.AMBER_WARN);
    surface.line(9, 12, 15, 12, P.FAULT_RED);
    if (frame === 0) {
      surface.rect(9, 14, 4, 1, P.SPARK_YELLOW, true);
    }
    return;
  }

  const textColor = state === 'dusty' ? P.CYAN_DIM : P.SCREEN_GREEN;
  surface.line(9, 8, 17, 8, textColor);
  surface.line(9, 10, 21, 10, textColor);
  surface.line(9, 12, 15, 12, textColor);
  surface.line(9, 14, 12, 14, textColor);

  // Blinking terminal cursor
  if (frame === 0) {
    surface.rect(14, 14, 2, 1, P.CYAN_BRIGHT, true);
  }
}

function drawBaseAndKeyboard(ctx: RenderContext<LaptopState>, P: Pal): void {
  const { surface, state, frame } = ctx;

  // Hinge bar
  surface.rect(6, 19, 20, 1, P.METAL_DARK, true);
  surface.rect(8, 19, 4, 1, P.SHADOW, true);
  surface.rect(20, 19, 4, 1, P.SHADOW, true);

  // Keyboard deck (angled 2.5D step)
  surface.rect(4, 20, 24, 5, P.SLATE_MID, true);
  surface.line(4, 20, 27, 20, P.SLATE_LIGHT);
  surface.line(4, 20, 4, 24, P.SLATE_LIGHT);

  // Keycap rows
  for (let kx = 6; kx <= 24; kx += 2) {
    surface.put(kx, 21, P.SLATE_DARK);
    surface.put(kx, 22, P.SLATE_DARK);
  }
  // Trackpad recess
  surface.rect(13, 23, 6, 2, P.SHADOW, true);

  // Front chassis lip & rubber feet
  surface.rect(3, 25, 26, 3, P.SLATE_DARK, true);
  surface.line(3, 25, 28, 25, P.METAL_DARK);
  surface.rect(5, 28, 3, 1, P.SHADOW, true);
  surface.rect(24, 28, 3, 1, P.SHADOW, true);

  // Status LEDs on front-right lip
  const powerLed =
    state === 'faulty'
      ? P.FAULT_RED
      : state === 'dusty'
        ? P.AMBER_WARN
        : frame === 0
          ? P.LED_GREEN
          : P.CYAN_DIM;
  surface.put(23, 26, powerLed);
  surface.put(25, 26, state === 'healthy' ? P.CYAN_GLOW : P.SHADOW);
}

function drawStateOverlays(ctx: RenderContext<LaptopState>, P: Pal): void {
  const { surface, state, frame, rng } = ctx;

  if (state === 'dusty') {
    for (let i = 0; i < 10; i++) {
      const dx = 5 + ((rng() * 22) | 0);
      const dy = 6 + ((rng() * 20) | 0);
      if (surface.get(dx, dy) !== P.SHADOW) {
        surface.put(dx, dy, i % 2 === 0 ? P.DUST_LIGHT : P.DUST_DARK);
      }
    }
    return;
  }

  if (state === 'faulty') {
    const sy = frame === 0 ? 18 : 17;
    surface.put(23, sy, P.SPARK_YELLOW);
    surface.put(24, sy - 1, P.FAULT_RED);
    surface.put(22, sy + 1, P.SPARK_YELLOW);
  }
}

export const oldLaptopAsset: AssetModule<LaptopState> = {
  id: 'old_laptop',
  styleId: 'homelab-16bit',
  width: 32,
  height: 32,
  perspective: 'front-2.5d',
  states: ['healthy', 'dusty', 'faulty'],
  frames: 2,
  fps: 2,
  seed: 101,

  render(ctx) {
    const P = buildPalette(ctx);
    drawScreen(ctx, P);
    drawBaseAndKeyboard(ctx, P);
    drawStateOverlays(ctx, P);

    ctx.surface.autoOutline(P.OUTLINE);

    ctx.anchor('foot', 16, 28);
    ctx.anchor('screen', 16, 11);
    ctx.anchor('led', 23, 26);
    ctx.hitbox('body', 2, 3, 28, 26);
  },
};
