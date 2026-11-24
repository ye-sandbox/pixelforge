import { type AssetModule, isoBox, isoTile, type PaletteIndex, type RenderContext } from 'pixelforge';

type RoomState = 'day' | 'night';

function buildPalette(ctx: RenderContext<RoomState>) {
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
    METAL_MID: get('METAL_MID'),
    METAL_LIGHT: get('METAL_LIGHT'),
    SCREEN_BG: get('SCREEN_BG'),
    LED_GREEN: get('LED_GREEN'),
    CYAN_DIM: get('CYAN_DIM'),
    CYAN_BRIGHT: get('CYAN_BRIGHT'),
    AMBER_WARN: get('AMBER_WARN'),
    WOOD_DARK: get('WOOD_DARK'),
    WOOD_MID: get('WOOD_MID'),
    WOOD_LIGHT: get('WOOD_LIGHT'),
    WALL_DARK: get('WALL_DARK'),
    WALL_MID: get('WALL_MID'),
    WALL_LIGHT: get('WALL_LIGHT'),
    FLOOR_DARK: get('FLOOR_DARK'),
    FLOOR_MID: get('FLOOR_MID'),
    WINDOW_SKY: get('WINDOW_SKY'),
    BREAKER_GREY: get('BREAKER_GREY'),
  };
}

type Pal = ReturnType<typeof buildPalette>;

const FLOOR_CX = 160;
const FLOOR_CY = 136;
const FLOOR_HW = 112;
const FLOOR_HH = 56;
const WALL_H = 74;

function drawFloorAndWalls(ctx: RenderContext<RoomState>, P: Pal): void {
  const { surface, state } = ctx;
  const isNight = state === 'night';

  // Isometric floor diamond
  isoTile(surface, FLOOR_CX, FLOOR_CY, FLOOR_HW, FLOOR_HH, isNight ? P.FLOOR_DARK : P.FLOOR_MID);

  // Subtle floor plank grid lines
  for (let i = -3; i <= 3; i++) {
    const off = i * 16;
    surface.line(
      FLOOR_CX - FLOOR_HW + Math.abs(off),
      FLOOR_CY + (off >> 1),
      FLOOR_CX + Math.abs(off) - 8,
      FLOOR_CY - FLOOR_HH + (off >> 1) + 4,
      P.FLOOR_DARK,
    );
  }

  // Back-left wall (top-left edge to top apex)
  const leftWallColor = isNight ? P.WALL_DARK : P.WALL_LIGHT;
  for (let dx = -FLOOR_HW; dx <= 0; dx++) {
    const edgeY = FLOOR_CY - (((FLOOR_HH * (FLOOR_HW + dx)) / FLOOR_HW) | 0);
    for (let py = 0; py < WALL_H; py++) {
      surface.put(FLOOR_CX + dx, edgeY - py, leftWallColor);
    }
    surface.put(FLOOR_CX + dx, edgeY, P.WOOD_DARK);
    surface.put(FLOOR_CX + dx, edgeY - 1, P.WOOD_MID);
    surface.put(FLOOR_CX + dx, edgeY - WALL_H, P.OUTLINE);
  }

  // Back-right wall (top apex to right corner)
  const rightWallColor = isNight ? P.WALL_DARK : P.WALL_MID;
  for (let dx = 1; dx <= FLOOR_HW; dx++) {
    const edgeY = FLOOR_CY - (((FLOOR_HH * (FLOOR_HW - dx)) / FLOOR_HW) | 0);
    for (let py = 0; py < WALL_H; py++) {
      surface.put(FLOOR_CX + dx, edgeY - py, rightWallColor);
    }
    surface.put(FLOOR_CX + dx, edgeY, P.WOOD_DARK);
    surface.put(FLOOR_CX + dx, edgeY - 1, P.WOOD_MID);
    surface.put(FLOOR_CX + dx, edgeY - WALL_H, P.OUTLINE);
  }

  // Corner seam, outer wall verticals, and front floor outline
  surface.line(FLOOR_CX, FLOOR_CY - FLOOR_HH, FLOOR_CX, FLOOR_CY - FLOOR_HH - WALL_H, P.WALL_DARK);
  surface.line(FLOOR_CX - FLOOR_HW, FLOOR_CY, FLOOR_CX - FLOOR_HW, FLOOR_CY - WALL_H, P.OUTLINE);
  surface.line(FLOOR_CX + FLOOR_HW, FLOOR_CY, FLOOR_CX + FLOOR_HW, FLOOR_CY - WALL_H, P.OUTLINE);
  surface.line(FLOOR_CX - FLOOR_HW, FLOOR_CY, FLOOR_CX, FLOOR_CY + FLOOR_HH, P.OUTLINE);
  surface.line(FLOOR_CX, FLOOR_CY + FLOOR_HH, FLOOR_CX + FLOOR_HW, FLOOR_CY, P.OUTLINE);
}

function drawWindow(ctx: RenderContext<RoomState>, P: Pal): void {
  const { surface, state } = ctx;
  const isNight = state === 'night';

  // Skewed isometric window on back-left wall
  const wx0 = 76;
  const wx1 = 122;
  const wh = 34;
  for (let x = wx0; x <= wx1; x++) {
    const baseY = 98 - (((x - wx0) * 23) / (wx1 - wx0) | 0);
    for (let dy = 0; dy < wh; dy++) {
      const isFrame = x <= wx0 + 2 || x >= wx1 - 2 || dy <= 2 || dy >= wh - 3 || dy === 16;
      const color = isFrame ? P.SLATE_MID : isNight ? P.SCREEN_BG : P.WINDOW_SKY;
      surface.put(x, baseY - dy, color);
    }
  }

  // Moon/stars in night mode or sunlit floor patch in day mode
  if (isNight) {
    surface.rect(92, 74, 3, 3, P.CYAN_BRIGHT, true);
    surface.put(108, 70, P.METAL_LIGHT);
    surface.put(85, 82, P.METAL_LIGHT);
  } else {
    isoTile(surface, 118, 126, 20, 10, P.WALL_LIGHT);
  }
}

function drawDeskAndHardwareSlots(ctx: RenderContext<RoomState>, P: Pal): void {
  const { surface, state } = ctx;
  const isNight = state === 'night';

  // Desk legs
  isoBox(surface, {
    cx: 120,
    cy: 112,
    halfW: 4,
    halfH: 2,
    height: 18,
    topColor: P.SLATE_MID,
    leftColor: P.SLATE_DARK,
    rightColor: P.SHADOW,
  });
  isoBox(surface, {
    cx: 184,
    cy: 112,
    halfW: 4,
    halfH: 2,
    height: 18,
    topColor: P.SLATE_MID,
    leftColor: P.SLATE_DARK,
    rightColor: P.SHADOW,
  });

  // Main wooden desk top (2:1 isometric)
  isoBox(surface, {
    cx: 152,
    cy: 108,
    halfW: 44,
    halfH: 22,
    height: 5,
    topColor: P.WOOD_LIGHT,
    leftColor: P.WOOD_MID,
    rightColor: P.WOOD_DARK,
    outlineColor: P.OUTLINE,
  });

  // Desk mat
  isoTile(surface, 148, 108, 22, 11, P.SLATE_DARK);

  // Side floor rack stand for AI cluster node
  isoBox(surface, {
    cx: 218,
    cy: 138,
    halfW: 18,
    halfH: 9,
    height: 6,
    topColor: P.METAL_MID,
    leftColor: P.SLATE_MID,
    rightColor: P.SLATE_DARK,
    outlineColor: P.OUTLINE,
  });

  // Small desk lamp on back corner of desk (glows warm amber at night)
  surface.rect(149, 86, 2, 7, P.METAL_MID, true);
  surface.rect(147, 84, 6, 3, P.SLATE_MID, true);
  if (isNight) {
    surface.rect(148, 86, 4, 1, P.AMBER_WARN, true);
  }
}

function drawBreakerPanel(ctx: RenderContext<RoomState>, P: Pal): void {
  const { surface, state } = ctx;
  // Breaker box mounted on back-right wall
  const bx = 224;
  const bw = 18;
  const bh = 26;
  for (let x = bx; x < bx + bw; x++) {
    const baseY = 92 + (((x - bx) * 9) / bw | 0);
    for (let dy = 0; dy < bh; dy++) {
      const isBorder = x === bx || x === bx + bw - 1 || dy === 0 || dy === bh - 1;
      const color = isBorder ? P.OUTLINE : P.BREAKER_GREY;
      surface.put(x, baseY - dy, color);
    }
  }
  // Breaker switches & status LED
  surface.rect(bx + 5, 76, 8, 10, P.SLATE_DARK, true);
  surface.put(bx + 13, 74, state === 'night' ? P.AMBER_WARN : P.LED_GREEN);
}

export const bedroomDeskIsoAsset: AssetModule<RoomState> = {
  id: 'bedroom_desk_iso',
  styleId: 'homelab-16bit',
  width: 320,
  height: 200,
  perspective: 'iso-2:1',
  states: ['day', 'night'],
  frames: 1,
  seed: 42,

  render(ctx) {
    const P = buildPalette(ctx);
    drawFloorAndWalls(ctx, P);
    drawWindow(ctx, P);
    drawDeskAndHardwareSlots(ctx, P);
    drawBreakerPanel(ctx, P);

    // Hardware slot anchors (desk left, desk right, floor rack stand) + breaker anchor
    ctx.anchor('hardware_0', 136, 104);
    ctx.anchor('hardware_1', 168, 112);
    ctx.anchor('hardware_2', 218, 136);
    ctx.anchor('breaker', 233, 81);

    ctx.hitbox('desk', 108, 86, 88, 49);
    ctx.hitbox('breaker', 224, 66, 18, 35);
    ctx.hitbox('room', 48, 6, 224, 186);
  },
};
