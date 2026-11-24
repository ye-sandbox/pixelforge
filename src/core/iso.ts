import type { IndexedSurface } from './surface.js';
import type { PaletteIndex } from './types.js';

export interface IsoPoint {
  readonly x: number;
  readonly y: number;
}

export interface IsoBoxOptions {
  readonly cx: number;
  readonly cy: number;
  readonly halfW: number;
  readonly halfH: number;
  readonly height: number;
  readonly topColor: PaletteIndex;
  readonly leftColor: PaletteIndex;
  readonly rightColor: PaletteIndex;
  readonly outlineColor?: PaletteIndex;
}

/**
 * Projects 3D world coordinates into 2:1 isometric integer screen coordinates.
 * Increasing x moves right-down; increasing y moves left-down; increasing z moves up.
 */
export function isoProject(x: number, y: number, z = 0, originX = 0, originY = 0): IsoPoint {
  const sx = (originX + (x - y) * 2) | 0;
  const sy = (originY + (x + y) - z) | 0;
  return { x: sx, y: sy };
}

/**
 * Draws a filled 2:1 isometric diamond centered at (cx, cy).
 */
export function isoTile(
  surface: IndexedSurface,
  cx: number,
  cy: number,
  halfW: number,
  halfH: number,
  color: PaletteIndex,
): void {
  const icx = cx | 0;
  const icy = cy | 0;
  const hw = halfW | 0;
  const hh = halfH | 0;
  if (hw <= 0 || hh <= 0) return;

  for (let dy = -hh; dy <= hh; dy++) {
    const span = ((hw * (hh - Math.abs(dy))) / hh) | 0;
    for (let dx = -span; dx <= span; dx++) {
      surface.put(icx + dx, icy + dy, color);
    }
  }
}

/**
 * Draws a 3-face 2:1 isometric box whose top face center is at (cx, cy).
 * Side faces extrude downward by `height` pixels.
 */
export function isoBox(surface: IndexedSurface, opts: IsoBoxOptions): void {
  const cx = opts.cx | 0;
  const cy = opts.cy | 0;
  const hw = opts.halfW | 0;
  const hh = opts.halfH | 0;
  const h = opts.height | 0;
  if (hw <= 0 || hh <= 0 || h <= 0) return;

  // Extrude left and right vertical faces from the lower V-edge of the top diamond
  for (let dx = -hw; dx <= hw; dx++) {
    const edgeY = cy + (((hh * (hw - Math.abs(dx))) / hw) | 0);
    const faceColor = dx < 0 ? opts.leftColor : opts.rightColor;
    for (let py = 1; py <= h; py++) {
      surface.put(cx + dx, edgeY + py, faceColor);
    }
  }

  isoTile(surface, cx, cy, hw, hh, opts.topColor);

  if (opts.outlineColor !== undefined) {
    drawIsoBoxOutline(surface, cx, cy, hw, hh, h, opts.outlineColor);
  }
}

function drawIsoBoxOutline(
  surface: IndexedSurface,
  cx: number,
  cy: number,
  hw: number,
  hh: number,
  h: number,
  color: PaletteIndex,
): void {
  // Top diamond perimeter
  surface.line(cx, cy - hh, cx + hw, cy, color);
  surface.line(cx + hw, cy, cx, cy + hh, color);
  surface.line(cx, cy + hh, cx - hw, cy, color);
  surface.line(cx - hw, cy, cx, cy - hh, color);
  // Vertical corners and bottom V-edge
  surface.line(cx - hw, cy, cx - hw, cy + h, color);
  surface.line(cx, cy + hh, cx, cy + hh + h, color);
  surface.line(cx + hw, cy, cx + hw, cy + h, color);
  surface.line(cx - hw, cy + h, cx, cy + hh + h, color);
  surface.line(cx, cy + hh + h, cx + hw, cy + h, color);
}
