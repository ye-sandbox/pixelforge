import {
  type AssetModule,
  type PaletteIndex,
  type Point2D,
  planeProject,
  type RenderContext,
} from '../../src/index.js';

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
    CYAN_BRIGHT: get('CYAN_BRIGHT'),
    AMBER_WARN: get('AMBER_WARN'),
    FAULT_RED: get('FAULT_RED'),
    SPARK_YELLOW: get('SPARK_YELLOW'),
    DUST_LIGHT: get('DUST_LIGHT'),
    DUST_DARK: get('DUST_DARK'),
    WINDOW_SKY: get('WINDOW_SKY'),
  };
}

type Pal = ReturnType<typeof buildPalette>;

const DECK_P0: Point2D = { x: 17, y: 32 };
const DECK_P1: Point2D = { x: 52, y: 41 };
const DECK_P2: Point2D = { x: 5, y: 49 };

/** Project normalized deck coordinates (u, v in [0, 1]) onto the angled 3/4 deck plane. */
function deckPoint(u: number, v: number): Point2D {
  return planeProject(DECK_P0, DECK_P1, DECK_P2, u, v);
}

/** Fill a sub-rectangle in (u, v) deck space without axis-aligned artifacts. */
function fillDeckQuad(
  ctx: RenderContext<LaptopState>,
  u0: number,
  v0: number,
  u1: number,
  v1: number,
  color: PaletteIndex,
): void {
  ctx.surface.quad(
    deckPoint(u0, v0),
    deckPoint(u1, v0),
    deckPoint(u1, v1),
    deckPoint(u0, v1),
    color,
  );
}

function drawLidAndScreen(ctx: RenderContext<LaptopState>, P: Pal): void {
  const { surface, state, frame } = ctx;

  // Angled 3/4 lid matching reference photo: top-left (22, 4) -> top-right (57, 13)
  // bottom-left (17, 30) -> bottom-right (52, 40)
  const lidH = 27;
  for (let dy = 0; dy < lidH; dy++) {
    const skewX = (-((dy * 5) / lidH)) | 0;
    const lx = (22 + skewX) | 0;
    const rx = (57 + skewX) | 0;
    for (let x = lx; x <= rx; x++) {
      const t = (x - lx) / Math.max(1, rx - lx);
      const py = (4 + dy + ((t * 9) | 0)) | 0;
      const isTopBevel = dy === 0;
      const isLeftBevel = x === lx;
      const isRightEdge = x === rx;
      let col = P.SLATE_DARK;
      if (isTopBevel || isLeftBevel) col = P.SLATE_LIGHT;
      else if (isRightEdge) col = P.SHADOW;
      surface.put(x, py, col);
    }
  }

  // Inner LCD panel (browser / Wikipedia look in healthy, BSOD/red in faulty)
  const lcdH = 21;
  for (let dy = 0; dy < lcdH; dy++) {
    const skewX = (-(((dy + 3) * 5) / lidH)) | 0;
    const lx = (25 + skewX) | 0;
    const rx = (54 + skewX) | 0;
    for (let x = lx; x <= rx; x++) {
      const t = (x - lx) / Math.max(1, rx - lx);
      const py = (7 + dy + ((t * 8) | 0)) | 0;
      let col = state === 'faulty' ? P.SCREEN_BG : state === 'dusty' ? P.METAL_DARK : P.METAL_LIGHT;
      if (dy <= 1) {
        // Browser title/toolbar
        col = state === 'faulty' ? P.FAULT_RED : P.CYAN_DIM;
      } else if (dy >= lcdH - 2) {
        // Windows XP taskbar + green Start button
        col = x < lx + 5 ? P.SCREEN_GREEN : P.WINDOW_SKY;
      } else if (state === 'faulty') {
        if (dy % 4 === 0 && x > lx + 2 && x < rx - 3) {
          col = dy === 8 ? P.FAULT_RED : P.AMBER_WARN;
        }
      } else {
        // Wikipedia sidebar + clean article lines
        if (x < lx + 6 && dy > 3) {
          col = P.METAL_MID;
        } else if ((dy === 5 || dy === 9 || dy === 13) && x > lx + 8 && x < rx - 3) {
          col = state === 'dusty' ? P.SLATE_MID : P.SLATE_DARK;
        }
      }
      surface.put(x, py, col);
    }
  }

  // Blinking cursor / browser activity dot
  if (state === 'healthy' && frame === 0) {
    surface.put(31, 14, P.CYAN_GLOW);
  }
}

function drawBaseAndKeyboard(ctx: RenderContext<LaptopState>, P: Pal): void {
  const { surface, state, frame } = ctx;

  // Hinge bar between lid and base
  for (let x = 18; x <= 51; x++) {
    const t = (x - 18) / 33;
    const py = (31 + ((t * 9) | 0)) | 0;
    surface.put(x, py, P.METAL_DARK);
    surface.put(x, py + 1, P.SHADOW);
  }

  // Hinge status LEDs (green in healthy, amber in dusty, red in faulty)
  const ledCol =
    state === 'faulty'
      ? P.FAULT_RED
      : state === 'dusty'
        ? P.AMBER_WARN
        : frame === 0
          ? P.LED_GREEN
          : P.SCREEN_GREEN;
  surface.put(33, 35, ledCol);
  surface.put(36, 36, state === 'healthy' ? P.LED_GREEN : P.SHADOW);

  // Lower deck (isometric/angled parallelogram from hinge down-left to front lip)
  // Top edge: (17, 32)..(52, 41), shifts left by -12 over 18 rows -> front edge (5, 49)..(40, 58)
  const deckRows = 18;
  for (let r = 0; r < deckRows; r++) {
    const t = r / (deckRows - 1);
    const lx = (17 - ((12 * t) | 0)) | 0;
    const rx = (52 - ((12 * t) | 0)) | 0;
    for (let x = lx; x <= rx; x++) {
      const u = (x - lx) / Math.max(1, rx - lx);
      const py = (32 + r + ((u * 9) | 0)) | 0;
      let col = P.SLATE_MID;
      if (x === lx) col = P.SLATE_LIGHT;
      else if (x === rx || r === deckRows - 1) col = P.SLATE_DARK;
      surface.put(x, py, col);
    }
  }

  // Front chassis thickness (3px vertical lip along front edge)
  for (let r = 0; r < 3; r++) {
    for (let x = 5; x <= 40; x++) {
      const u = (x - 5) / 35;
      const py = (50 + r + ((u * 9) | 0)) | 0;
      surface.put(x, py, r === 0 ? P.SLATE_DARK : P.SHADOW);
    }
  }

  // Right-side chassis thickness (visible side ports, sealed to deck edge)
  for (let step = 0; step <= 12; step++) {
    const x = (40 + step) | 0;
    const topY = (58 - (((step * 17) / 12) | 0)) | 0;
    for (let r = 0; r < 3; r++) {
      surface.put(x, topY + r, r === 1 && step % 4 === 0 ? P.METAL_DARK : P.SHADOW);
    }
  }

  // Keyboard recess + keycap rows projected onto the 3/4 deck plane
  fillDeckQuad(ctx, 0.07, 0.08, 0.90, 0.54, P.SHADOW);
  for (let r = 0; r < 4; r++) {
    const v = 0.14 + r * 0.10;
    for (let c = 0; c < 13; c++) {
      const u = 0.10 + c * 0.06;
      const kp = deckPoint(u, v);
      surface.put(kp.x, kp.y, P.SLATE_DARK);
    }
  }

  // Iconic IBM blue Enter key on right side of keyboard
  fillDeckQuad(ctx, 0.80, 0.24, 0.88, 0.42, P.WINDOW_SKY);

  // Iconic red TrackPoint in keyboard center
  const tp = deckPoint(0.45, 0.29);
  surface.put(tp.x, tp.y, P.FAULT_RED);

  // TrackPoint mouse buttons (with red stripe + center blue button) & Touchpad
  fillDeckQuad(ctx, 0.32, 0.58, 0.56, 0.68, P.SLATE_DARK);
  fillDeckQuad(ctx, 0.32, 0.58, 0.56, 0.61, P.FAULT_RED);
  fillDeckQuad(ctx, 0.42, 0.58, 0.46, 0.68, P.WINDOW_SKY);

  fillDeckQuad(ctx, 0.30, 0.72, 0.58, 0.93, P.SHADOW);
  fillDeckQuad(ctx, 0.33, 0.76, 0.55, 0.89, P.SLATE_DARK);

  // Left palmrest stickers (Centrino + Windows XP)
  const st1 = deckPoint(0.12, 0.78);
  const st2 = deckPoint(0.18, 0.78);
  surface.put(st1.x, st1.y, P.WINDOW_SKY);
  surface.put(st2.x, st2.y, P.AMBER_WARN);

  // Right palmrest IBM ThinkPad tri-color badge
  const b1 = deckPoint(0.72, 0.80);
  const b2 = deckPoint(0.76, 0.80);
  const b3 = deckPoint(0.80, 0.80);
  surface.put(b1.x, b1.y, P.FAULT_RED);
  surface.put(b2.x, b2.y, P.LED_GREEN);
  surface.put(b3.x, b3.y, P.WINDOW_SKY);
}

function drawStateOverlays(ctx: RenderContext<LaptopState>, P: Pal): void {
  const { surface, state, frame, rng } = ctx;

  if (state === 'dusty') {
    for (let i = 0; i < 16; i++) {
      const dx = 10 + ((rng() * 42) | 0);
      const dy = 12 + ((rng() * 40) | 0);
      if (surface.get(dx, dy) !== 255 && surface.get(dx, dy) !== P.SHADOW) {
        surface.put(dx, dy, i % 2 === 0 ? P.DUST_LIGHT : P.DUST_DARK);
      }
    }
    return;
  }

  if (state === 'faulty') {
    const sy = frame === 0 ? 34 : 33;
    surface.put(38, sy, P.SPARK_YELLOW);
    surface.put(39, sy - 1, P.FAULT_RED);
    surface.put(37, sy + 1, P.SPARK_YELLOW);
  }
}

export const thinkpadR51IsoAsset: AssetModule<LaptopState> = {
  id: 'thinkpad_r51_iso',
  styleId: 'homelab-16bit',
  width: 64,
  height: 64,
  perspective: 'iso-2:1',
  states: ['healthy', 'dusty', 'faulty'],
  frames: 2,
  fps: 2,
  seed: 510,

  render(ctx) {
    const P = buildPalette(ctx);
    drawLidAndScreen(ctx, P);
    drawBaseAndKeyboard(ctx, P);
    drawStateOverlays(ctx, P);

    ctx.surface.autoOutline(P.OUTLINE);

    const tp = deckPoint(0.45, 0.29);
    const badge = deckPoint(0.76, 0.80);

    ctx.anchor('foot', 23, 58);
    ctx.anchor('trackpoint', tp.x, tp.y);
    ctx.anchor('screen', 39, 19);
    ctx.anchor('led', 33, 35);
    ctx.anchor('badge', badge.x, badge.y);
    ctx.hitbox('body', 4, 3, 55, 58);
  },
};
