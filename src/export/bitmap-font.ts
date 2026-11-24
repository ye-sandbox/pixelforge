import type { RgbaBuffer } from './png.js';

/**
 * Minimal 3x5 bitmap font (each glyph is 5 rows of 3-bit masks) for headless contact-sheet labels.
 */
const FONT_3X5: Readonly<Record<string, readonly number[]>> = {
  '0': [0b111, 0b101, 0b101, 0b101, 0b111],
  '1': [0b010, 0b110, 0b010, 0b010, 0b111],
  '2': [0b111, 0b001, 0b111, 0b100, 0b111],
  '3': [0b111, 0b001, 0b111, 0b001, 0b111],
  '4': [0b101, 0b101, 0b111, 0b001, 0b001],
  '5': [0b111, 0b100, 0b111, 0b001, 0b111],
  '6': [0b111, 0b100, 0b111, 0b101, 0b111],
  '7': [0b111, 0b001, 0b001, 0b010, 0b010],
  '8': [0b111, 0b101, 0b111, 0b101, 0b111],
  '9': [0b111, 0b101, 0b111, 0b001, 0b111],
  A: [0b010, 0b101, 0b111, 0b101, 0b101],
  B: [0b110, 0b101, 0b110, 0b101, 0b110],
  C: [0b111, 0b100, 0b100, 0b100, 0b111],
  D: [0b110, 0b101, 0b101, 0b101, 0b110],
  E: [0b111, 0b100, 0b110, 0b100, 0b111],
  F: [0b111, 0b100, 0b110, 0b100, 0b100],
  G: [0b111, 0b100, 0b101, 0b101, 0b111],
  H: [0b101, 0b101, 0b111, 0b101, 0b101],
  I: [0b111, 0b010, 0b010, 0b010, 0b111],
  J: [0b001, 0b001, 0b001, 0b101, 0b111],
  K: [0b101, 0b101, 0b110, 0b101, 0b101],
  L: [0b100, 0b100, 0b100, 0b100, 0b111],
  M: [0b101, 0b111, 0b111, 0b101, 0b101],
  N: [0b111, 0b101, 0b101, 0b101, 0b101],
  O: [0b111, 0b101, 0b101, 0b101, 0b111],
  P: [0b111, 0b101, 0b111, 0b100, 0b100],
  Q: [0b111, 0b101, 0b101, 0b111, 0b001],
  R: [0b111, 0b101, 0b110, 0b101, 0b101],
  S: [0b111, 0b100, 0b111, 0b001, 0b111],
  T: [0b111, 0b010, 0b010, 0b010, 0b010],
  U: [0b101, 0b101, 0b101, 0b101, 0b111],
  V: [0b101, 0b101, 0b101, 0b101, 0b010],
  W: [0b101, 0b101, 0b111, 0b111, 0b101],
  X: [0b101, 0b101, 0b010, 0b101, 0b101],
  Y: [0b101, 0b101, 0b010, 0b010, 0b010],
  Z: [0b111, 0b001, 0b010, 0b100, 0b111],
  ':': [0b000, 0b010, 0b000, 0b010, 0b000],
  '-': [0b000, 0b000, 0b111, 0b000, 0b000],
  _: [0b000, 0b000, 0b000, 0b000, 0b111],
  '.': [0b000, 0b000, 0b000, 0b000, 0b010],
  ',': [0b000, 0b000, 0b000, 0b010, 0b100],
  '/': [0b001, 0b001, 0b010, 0b100, 0b100],
  '(': [0b010, 0b100, 0b100, 0b100, 0b010],
  ')': [0b010, 0b001, 0b001, 0b001, 0b010],
  '[': [0b110, 0b100, 0b100, 0b100, 0b110],
  ']': [0b011, 0b001, 0b001, 0b001, 0b011],
  '#': [0b101, 0b111, 0b101, 0b111, 0b101],
  ' ': [0b000, 0b000, 0b000, 0b000, 0b000],
};

export type RgbColor = readonly [number, number, number];

export function putRgbaPixel(
  buf: RgbaBuffer,
  x: number,
  y: number,
  r: number,
  g: number,
  b: number,
  a = 255,
): void {
  const ix = x | 0;
  const iy = y | 0;
  if (ix < 0 || ix >= buf.width || iy < 0 || iy >= buf.height) return;
  const idx = (iy * buf.width + ix) * 4;
  buf.data[idx] = r;
  buf.data[idx + 1] = g;
  buf.data[idx + 2] = b;
  buf.data[idx + 3] = a;
}

export function fillRgbaRect(
  buf: RgbaBuffer,
  x: number,
  y: number,
  w: number,
  h: number,
  color: RgbColor,
  a = 255,
): void {
  const x0 = Math.max(0, x | 0);
  const y0 = Math.max(0, y | 0);
  const x1 = Math.min(buf.width, (x | 0) + (w | 0));
  const y1 = Math.min(buf.height, (y | 0) + (h | 0));
  const [r, g, b] = color;
  for (let py = y0; py < y1; py++) {
    for (let px = x0; px < x1; px++) {
      const idx = (py * buf.width + px) * 4;
      buf.data[idx] = r;
      buf.data[idx + 1] = g;
      buf.data[idx + 2] = b;
      buf.data[idx + 3] = a;
    }
  }
}

export function drawBitmapText(
  buf: RgbaBuffer,
  text: string,
  x: number,
  y: number,
  color: RgbColor,
  scale = 1,
): void {
  const upper = text.toUpperCase();
  const s = Math.max(1, scale | 0);
  let cursorX = x | 0;
  const startY = y | 0;
  const [r, g, b] = color;

  for (const ch of upper) {
    const glyph = FONT_3X5[ch] ?? FONT_3X5[' '];
    if (glyph) {
      for (let row = 0; row < 5; row++) {
        const bits = glyph[row] ?? 0;
        for (let col = 0; col < 3; col++) {
          if ((bits >> (2 - col)) & 1) {
            fillRgbaRect(buf, cursorX + col * s, startY + row * s, s, s, [r, g, b]);
          }
        }
      }
    }
    cursorX += 4 * s;
  }
}

export function measureBitmapTextWidth(text: string, scale = 1): number {
  if (text.length === 0) return 0;
  const s = Math.max(1, scale | 0);
  return text.length * 4 * s - s;
}
