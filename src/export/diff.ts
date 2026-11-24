import { decode } from 'fast-png';
import { type RgbaBuffer, rgbaToPng } from './png.js';

export interface DiffResult {
  readonly changedPixels: number;
  readonly totalPixels: number;
  readonly width: number;
  readonly height: number;
  readonly png: Uint8Array;
}

const GAP = 4;
const PADDING = 8;

function toRgba4Channel(decoded: ReturnType<typeof decode>): RgbaBuffer {
  const { width, height, channels, data } = decoded;
  if (channels === 4 && data instanceof Uint8Array) {
    return { width, height, data };
  }

  const out = new Uint8Array(width * height * 4);
  for (let i = 0; i < width * height; i++) {
    const src = i * channels;
    const dst = i * 4;
    if (channels === 1) {
      const v = data[src] ?? 0;
      out[dst] = v;
      out[dst + 1] = v;
      out[dst + 2] = v;
      out[dst + 3] = 255;
    } else if (channels === 3) {
      out[dst] = data[src] ?? 0;
      out[dst + 1] = data[src + 1] ?? 0;
      out[dst + 2] = data[src + 2] ?? 0;
      out[dst + 3] = 255;
    } else {
      out[dst] = data[src] ?? 0;
      out[dst + 1] = data[src + 1] ?? 0;
      out[dst + 2] = data[src + 2] ?? 0;
      out[dst + 3] = data[src + 3] ?? 255;
    }
  }
  return { width, height, data: out };
}

export function decodePngToRgba(pngBytes: Uint8Array): RgbaBuffer {
  return toRgba4Channel(decode(pngBytes));
}

function blitPanel(dest: RgbaBuffer, src: RgbaBuffer, destX: number, destY: number): void {
  for (let y = 0; y < src.height; y++) {
    for (let x = 0; x < src.width; x++) {
      const s = (y * src.width + x) * 4;
      const d = ((destY + y) * dest.width + (destX + x)) * 4;
      const alpha = src.data[s + 3] ?? 0;
      if (alpha === 0) continue;
      dest.data[d] = src.data[s] ?? 0;
      dest.data[d + 1] = src.data[s + 1] ?? 0;
      dest.data[d + 2] = src.data[s + 2] ?? 0;
      dest.data[d + 3] = alpha;
    }
  }
}

function fillCheckerBackground(
  buf: RgbaBuffer,
  x0: number,
  y0: number,
  w: number,
  h: number,
): void {
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const dark = ((x >> 2) + (y >> 2)) % 2 === 0;
      const v = dark ? 22 : 30;
      const d = ((y0 + y) * buf.width + (x0 + x)) * 4;
      buf.data[d] = v;
      buf.data[d + 1] = v + 2;
      buf.data[d + 2] = v + 6;
      buf.data[d + 3] = 255;
    }
  }
}

/**
 * Generates a side-by-side (baseline | current | pixel-diff) PNG comparing two RGBA buffers.
 * Changed pixels are highlighted in magenta (#ff2a85); unchanged pixels are dimmed.
 */
export function generatePixelDiff(baseline: RgbaBuffer, current: RgbaBuffer): DiffResult {
  const panelW = Math.max(baseline.width, current.width);
  const panelH = Math.max(baseline.height, current.height);
  const totalW = PADDING * 2 + panelW * 3 + GAP * 2;
  const totalH = PADDING * 2 + panelH;

  const canvas: RgbaBuffer = {
    width: totalW,
    height: totalH,
    data: new Uint8Array(totalW * totalH * 4),
  };

  // Fill dark slate frame background
  for (let i = 0; i < canvas.data.length; i += 4) {
    canvas.data[i] = 13;
    canvas.data[i + 1] = 17;
    canvas.data[i + 2] = 23;
    canvas.data[i + 3] = 255;
  }

  const baseX = PADDING;
  const currX = PADDING + panelW + GAP;
  const diffX = PADDING + (panelW + GAP) * 2;

  fillCheckerBackground(canvas, baseX, PADDING, panelW, panelH);
  fillCheckerBackground(canvas, currX, PADDING, panelW, panelH);
  fillCheckerBackground(canvas, diffX, PADDING, panelW, panelH);

  blitPanel(canvas, baseline, baseX, PADDING);
  blitPanel(canvas, current, currX, PADDING);

  let changedPixels = 0;
  for (let y = 0; y < panelH; y++) {
    for (let x = 0; x < panelW; x++) {
      const inBase = x < baseline.width && y < baseline.height;
      const inCurr = x < current.width && y < current.height;
      const bs = (y * baseline.width + x) * 4;
      const cs = (y * current.width + x) * 4;

      const br = inBase ? (baseline.data[bs] ?? 0) : 0;
      const bg = inBase ? (baseline.data[bs + 1] ?? 0) : 0;
      const bb = inBase ? (baseline.data[bs + 2] ?? 0) : 0;
      const ba = inBase ? (baseline.data[bs + 3] ?? 0) : 0;

      const cr = inCurr ? (current.data[cs] ?? 0) : 0;
      const cg = inCurr ? (current.data[cs + 1] ?? 0) : 0;
      const cb = inCurr ? (current.data[cs + 2] ?? 0) : 0;
      const ca = inCurr ? (current.data[cs + 3] ?? 0) : 0;

      const differs = br !== cr || bg !== cg || bb !== cb || ba !== ca;
      const d = ((PADDING + y) * totalW + (diffX + x)) * 4;

      if (differs) {
        changedPixels++;
        canvas.data[d] = 255;
        canvas.data[d + 1] = 42;
        canvas.data[d + 2] = 133;
        canvas.data[d + 3] = 255;
      } else if (ca > 0) {
        canvas.data[d] = cr >> 2;
        canvas.data[d + 1] = cg >> 2;
        canvas.data[d + 2] = cb >> 2;
        canvas.data[d + 3] = 255;
      }
    }
  }

  return {
    changedPixels,
    totalPixels: panelW * panelH,
    width: totalW,
    height: totalH,
    png: rgbaToPng(canvas),
  };
}
