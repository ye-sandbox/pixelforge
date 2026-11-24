import type { AssetModule, PaletteIndex, RenderContext } from '../../src/index.js';

type ClusterState = 'healthy' | 'dusty' | 'faulty';

function buildPalette(ctx: RenderContext<ClusterState>) {
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
    CYAN_BRIGHT: get('CYAN_BRIGHT'),
    AMBER_WARN: get('AMBER_WARN'),
    FAULT_RED: get('FAULT_RED'),
    SPARK_YELLOW: get('SPARK_YELLOW'),
    COPPER_MID: get('COPPER_MID'),
    DUST_LIGHT: get('DUST_LIGHT'),
    DUST_DARK: get('DUST_DARK'),
  };
}

type Pal = ReturnType<typeof buildPalette>;

function drawRackChassis(ctx: RenderContext<ClusterState>, P: Pal): void {
  const { surface } = ctx;

  // Main 4U chassis body
  surface.rect(6, 5, 52, 37, P.SLATE_DARK, true);
  surface.line(6, 5, 57, 5, P.METAL_LIGHT);
  surface.line(6, 5, 6, 41, P.METAL_MID);
  surface.line(57, 6, 57, 41, P.SHADOW);
  surface.line(7, 41, 57, 41, P.SHADOW);

  // Rack ears & mounting bolts
  surface.rect(4, 7, 2, 33, P.METAL_MID, true);
  surface.rect(58, 7, 2, 33, P.METAL_DARK, true);
  for (const by of [9, 19, 29, 38]) {
    surface.put(5, by, P.METAL_LIGHT);
    surface.put(58, by, P.METAL_MID);
  }

  // Rubber/steel feet
  surface.rect(9, 42, 5, 1, P.SHADOW, true);
  surface.rect(50, 42, 5, 1, P.SHADOW, true);
}

function drawComputeBlades(ctx: RenderContext<ClusterState>, P: Pal): void {
  const { surface, state, frame } = ctx;

  // 4 horizontal tensor blade bays on left/center
  for (let i = 0; i < 4; i++) {
    const by = 8 + i * 7;
    surface.rect(9, by, 29, 6, P.SLATE_MID, true);
    surface.line(9, by, 37, by, P.SLATE_LIGHT);
    surface.line(9, by + 5, 37, by + 5, P.SHADOW);

    // Intake vent slits
    for (let vx = 11; vx <= 29; vx += 3) {
      surface.rect(vx, by + 2, 2, 2, P.SHADOW, true);
    }

    // Copper busbar & blade status LED
    surface.rect(32, by + 2, 2, 2, P.COPPER_MID, true);
    const bladeLed =
      state === 'faulty' && i === 2
        ? P.FAULT_RED
        : state === 'dusty'
          ? P.AMBER_WARN
          : (i + frame) % 2 === 0
            ? P.LED_GREEN
            : P.CYAN_GLOW;
    surface.put(35, by + 2, bladeLed);
  }

  // Bottom telemetry LED strip
  surface.rect(9, 37, 29, 3, P.SHADOW, true);
  for (let tx = 11; tx <= 35; tx += 3) {
    let color: number = P.LED_GREEN;
    if (state === 'faulty') {
      color = (tx + frame) % 2 === 0 ? P.FAULT_RED : P.SPARK_YELLOW;
    } else if (state === 'dusty') {
      color = tx % 2 === 0 ? P.AMBER_WARN : P.CYAN_DIM;
    } else {
      color = ((tx / 3) | 0) % 2 === frame ? P.CYAN_GLOW : P.LED_GREEN;
    }
    surface.rect(tx, 38, 2, 1, color, true);
  }
}

function drawCyanManifold(ctx: RenderContext<ClusterState>, P: Pal): void {
  const { surface, state, frame } = ctx;

  // Manifold recess bay
  surface.rect(40, 8, 15, 32, P.SHADOW, true);
  surface.line(40, 8, 54, 8, P.SLATE_LIGHT);

  // Top & bottom quick-disconnect fittings
  surface.rect(43, 9, 9, 2, P.METAL_MID, true);
  surface.line(43, 9, 51, 9, P.METAL_LIGHT);
  surface.rect(43, 37, 9, 2, P.METAL_DARK, true);

  // Dual vertical coolant columns
  const dimCol = state === 'dusty' ? P.CYAN_DIM : P.CYAN_GLOW;
  const brightCol = state === 'faulty' ? P.FAULT_RED : P.CYAN_BRIGHT;

  surface.rect(44, 11, 3, 26, state === 'faulty' ? P.CYAN_DIM : dimCol, true);
  surface.rect(48, 11, 3, 26, state === 'faulty' ? P.CYAN_DIM : dimCol, true);

  // Animated coolant pulse / bubbles
  const offset = frame === 0 ? 0 : 3;
  for (let py = 13 + offset; py <= 34; py += 6) {
    surface.put(45, py, brightCol);
    surface.put(49, py + 1, brightCol);
  }

  // Center bridge manifold
  surface.rect(43, 22, 9, 3, P.METAL_MID, true);
  surface.line(44, 23, 50, 23, state === 'faulty' ? P.FAULT_RED : P.CYAN_BRIGHT);
}

function drawClusterOverlays(ctx: RenderContext<ClusterState>, P: Pal): void {
  const { surface, state, frame, rng } = ctx;

  if (state === 'dusty') {
    for (let i = 0; i < 20; i++) {
      const dx = 7 + ((rng() * 48) | 0);
      const dy = 6 + ((rng() * 34) | 0);
      if (surface.get(dx, dy) !== P.SHADOW) {
        surface.put(dx, dy, i % 2 === 0 ? P.DUST_LIGHT : P.DUST_DARK);
      }
    }
    return;
  }

  if (state === 'faulty') {
    const sy = frame === 0 ? 22 : 24;
    surface.put(39, sy, P.SPARK_YELLOW);
    surface.put(40, sy - 1, P.FAULT_RED);
    surface.put(52, 34, frame === 0 ? P.FAULT_RED : P.SPARK_YELLOW);
  }
}

export const aiClusterNodeAsset: AssetModule<ClusterState> = {
  id: 'ai_cluster_node',
  styleId: 'homelab-16bit',
  width: 64,
  height: 48,
  perspective: 'front-2.5d',
  states: ['healthy', 'dusty', 'faulty'],
  frames: 2,
  fps: 4,
  seed: 303,

  render(ctx) {
    const P = buildPalette(ctx);
    drawRackChassis(ctx, P);
    drawComputeBlades(ctx, P);
    drawCyanManifold(ctx, P);
    drawClusterOverlays(ctx, P);

    ctx.surface.autoOutline(P.OUTLINE);

    ctx.anchor('foot', 32, 42);
    ctx.anchor('manifold', 47, 24);
    ctx.anchor('telemetry', 23, 38);
    ctx.hitbox('body', 4, 4, 56, 40);
  },
};
