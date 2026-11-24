import type { AssetModule, PaletteIndex, RenderContext } from '../../src/index.js';

type RigState = 'healthy' | 'dusty' | 'faulty';

function buildPalette(ctx: RenderContext<RigState>) {
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
    LED_GREEN: get('LED_GREEN'),
    CYAN_DIM: get('CYAN_DIM'),
    CYAN_GLOW: get('CYAN_GLOW'),
    AMBER_WARN: get('AMBER_WARN'),
    FAULT_RED: get('FAULT_RED'),
    SPARK_YELLOW: get('SPARK_YELLOW'),
    COPPER_DARK: get('COPPER_DARK'),
    COPPER_MID: get('COPPER_MID'),
    PCB_DARK: get('PCB_DARK'),
    PCB_MID: get('PCB_MID'),
    DUST_LIGHT: get('DUST_LIGHT'),
    DUST_DARK: get('DUST_DARK'),
  };
}

type Pal = ReturnType<typeof buildPalette>;

function drawOpenFrame(ctx: RenderContext<RigState>, P: Pal): void {
  const { surface } = ctx;

  // Aluminum extrusion rails (left/top lit, right/bottom shaded)
  surface.rect(5, 6, 54, 3, P.METAL_MID, true);
  surface.line(5, 6, 58, 6, P.METAL_LIGHT);

  surface.rect(4, 39, 56, 3, P.METAL_MID, true);
  surface.line(4, 39, 59, 39, P.METAL_LIGHT);
  surface.line(4, 41, 59, 41, P.METAL_DARK);

  surface.rect(5, 6, 3, 35, P.METAL_MID, true);
  surface.line(5, 6, 5, 40, P.METAL_LIGHT);

  surface.rect(56, 6, 3, 35, P.METAL_DARK, true);
  surface.line(56, 6, 56, 39, P.METAL_MID);

  // Rubber feet
  surface.rect(6, 42, 4, 1, P.SHADOW, true);
  surface.rect(54, 42, 4, 1, P.SHADOW, true);
}

function drawSingleGpu(
  ctx: RenderContext<RigState>,
  P: Pal,
  x: number,
  gpuIndex: number,
): void {
  const { surface, state, frame } = ctx;
  const w = 13;
  const h = 17;
  const y = 10;

  // GPU shroud
  surface.rect(x, y, w, h, P.SLATE_MID, true);
  surface.line(x, y, x + w - 1, y, P.METAL_LIGHT);
  surface.line(x, y, x, y + h - 1, P.METAL_MID);
  surface.line(x + w - 1, y + 1, x + w - 1, y + h - 1, P.SLATE_DARK);
  surface.line(x + 1, y + h - 1, x + w - 1, y + h - 1, P.SLATE_DARK);

  // Copper heatpipes peeking at top
  surface.rect(x + 2, y - 1, 3, 1, P.COPPER_MID, true);
  surface.rect(x + 8, y - 1, 3, 1, P.COPPER_DARK, true);

  // Fan housing
  const fcx = x + 6;
  const fcy = y + 9;
  surface.circle(fcx, fcy, 4, P.SHADOW, true);
  surface.circle(fcx, fcy, 4, P.METAL_DARK, false);

  // Fan blades (stalled on GPU 1 when faulty)
  const stalled = state === 'faulty' && gpuIndex === 1;
  if (!stalled) {
    const bladeColor = state === 'dusty' ? P.DUST_LIGHT : P.METAL_MID;
    if (frame === 0) {
      surface.line(fcx - 3, fcy, fcx + 3, fcy, bladeColor);
      surface.line(fcx, fcy - 3, fcx, fcy + 3, bladeColor);
    } else {
      surface.line(fcx - 2, fcy - 2, fcx + 2, fcy + 2, bladeColor);
      surface.line(fcx - 2, fcy + 2, fcx + 2, fcy - 2, bladeColor);
    }
  }
  surface.put(fcx, fcy, P.METAL_LIGHT);

  // Top status LED
  let led: number = frame === 0 ? P.LED_GREEN : P.CYAN_GLOW;
  if (state === 'dusty' && gpuIndex === 1) led = P.AMBER_WARN;
  if (state === 'faulty') led = gpuIndex === 1 ? P.FAULT_RED : P.AMBER_WARN;
  surface.put(x + 10, y + 2, led);

  // Riser cable dropping to motherboard
  const rx = x + 6;
  surface.line(rx, y + h, rx, 33, P.COPPER_DARK);
  surface.line(rx + 1, y + h, rx + 1, 33, P.CYAN_DIM);
}

function drawLowerDeck(ctx: RenderContext<RigState>, P: Pal): void {
  const { surface, state, frame } = ctx;

  // Motherboard tray
  surface.rect(9, 34, 31, 5, P.PCB_MID, true);
  surface.line(9, 34, 39, 34, P.PCB_DARK);
  surface.rect(14, 32, 6, 3, P.METAL_MID, true);
  surface.line(14, 32, 19, 32, P.METAL_LIGHT);
  surface.line(23, 35, 36, 35, P.COPPER_MID);

  // PSU brick on bottom-right
  surface.rect(42, 30, 13, 9, P.SLATE_DARK, true);
  surface.line(42, 30, 54, 30, P.SLATE_LIGHT);
  surface.line(42, 30, 42, 38, P.SLATE_LIGHT);
  surface.rect(44, 32, 5, 5, P.SHADOW, true);
  surface.rect(50, 32, 3, 2, P.COPPER_MID, true);
  surface.put(52, 36, state === 'faulty' && frame === 1 ? P.FAULT_RED : P.LED_GREEN);
}

function drawRigStateOverlays(ctx: RenderContext<RigState>, P: Pal): void {
  const { surface, state, frame, rng } = ctx;

  if (state === 'dusty') {
    for (let i = 0; i < 24; i++) {
      const dx = 6 + ((rng() * 52) | 0);
      const dy = 7 + ((rng() * 33) | 0);
      if (surface.get(dx, dy) !== P.SHADOW) {
        surface.put(dx, dy, i % 3 === 0 ? P.DUST_LIGHT : P.DUST_DARK);
      }
    }
    return;
  }

  if (state === 'faulty') {
    const sx = frame === 0 ? 31 : 33;
    const sy = frame === 0 ? 28 : 27;
    surface.put(sx, sy, P.SPARK_YELLOW);
    surface.put(sx + 1, sy - 1, P.FAULT_RED);
    surface.put(sx - 1, sy + 1, P.SPARK_YELLOW);
    surface.put(44, 29, frame === 0 ? P.FAULT_RED : P.SPARK_YELLOW);
  }
}

export const usedGpuRigAsset: AssetModule<RigState> = {
  id: 'used_gpu_rig',
  styleId: 'homelab-16bit',
  width: 64,
  height: 48,
  perspective: 'front-2.5d',
  states: ['healthy', 'dusty', 'faulty'],
  frames: 2,
  fps: 4,
  seed: 202,

  render(ctx) {
    const P = buildPalette(ctx);
    drawOpenFrame(ctx, P);
    drawLowerDeck(ctx, P);
    drawSingleGpu(ctx, P, 9, 0);
    drawSingleGpu(ctx, P, 25, 1);
    drawSingleGpu(ctx, P, 41, 2);
    drawRigStateOverlays(ctx, P);

    ctx.surface.autoOutline(P.OUTLINE);

    ctx.anchor('foot', 32, 42);
    ctx.anchor('gpu_0', 15, 19);
    ctx.anchor('gpu_1', 31, 19);
    ctx.anchor('gpu_2', 47, 19);
    ctx.anchor('psu', 48, 34);
    ctx.hitbox('body', 3, 5, 58, 38);
  },
};
