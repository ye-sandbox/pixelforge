import { encode } from 'fast-png';
import type { IndexedSurface } from '../core/surface.js';
import { type PaletteIndex, type StylePack, TRANSPARENT_INDEX } from '../core/types.js';

export interface RgbaBuffer {
  readonly width: number;
  readonly height: number;
  readonly data: Uint8Array;
}

export interface SurfaceToRgbaOptions {
  readonly variant?: string;
  readonly scale?: number;
  readonly emissiveOnly?: boolean;
}

interface PaletteLookup {
  readonly rgb: Uint8Array; // 256 * 3
  readonly declared: Uint8Array; // 256 (1 = declared, 0 = undeclared)
  readonly emissive: Uint8Array; // 256 (1 = emissive flag, 0 = non-emissive)
}

const HEX_6_RE = /^#([0-9a-fA-F]{6})$/;

export function parseHexColor(hex: string): readonly [number, number, number] {
  const match = HEX_6_RE.exec(hex);
  if (!match?.[1]) {
    throw new Error(`Invalid #rrggbb hex color: "${hex}"`);
  }
  const value = Number.parseInt(match[1], 16);
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff];
}

function buildPaletteLookup(style: StylePack, variant?: string): PaletteLookup {
  const rgb = new Uint8Array(256 * 3);
  const declared = new Uint8Array(256);
  const emissive = new Uint8Array(256);

  let variantOverrides: Readonly<Record<string, `#${string}`>> | undefined;
  if (variant !== undefined) {
    variantOverrides = style.variants?.[variant];
    if (!variantOverrides) {
      throw new Error(`Unknown variant "${variant}" in style "${style.id}"`);
    }
  }

  for (const entry of style.palette) {
    if (entry.index < 0 || entry.index >= TRANSPARENT_INDEX) {
      throw new RangeError(
        `Style "${style.id}" color "${entry.name}" has invalid index ${entry.index} (must be 0..254)`,
      );
    }
    const hex = variantOverrides?.[entry.name] ?? entry.hex;
    const [r, g, b] = parseHexColor(hex);
    const offset = entry.index * 3;
    rgb[offset] = r;
    rgb[offset + 1] = g;
    rgb[offset + 2] = b;
    declared[entry.index] = 1;
    if (entry.flags?.includes('emissive')) {
      emissive[entry.index] = 1;
    }
  }

  return { rgb, declared, emissive };
}

/**
 * Converts an IndexedSurface into a binary-alpha RGBA buffer (alpha is strictly 0 or 255).
 */
export function surfaceToRgba(
  surface: IndexedSurface,
  style: StylePack,
  options: SurfaceToRgbaOptions = {},
): RgbaBuffer {
  const scale = options.scale === undefined ? 1 : options.scale | 0;
  if (scale < 1) {
    throw new RangeError(`Scale must be an integer >= 1, got ${options.scale}`);
  }
  const emissiveOnly = options.emissiveOnly ?? false;
  const lut = buildPaletteLookup(style, options.variant);

  const outW = surface.width * scale;
  const outH = surface.height * scale;
  const data = new Uint8Array(outW * outH * 4);

  for (let sy = 0; sy < surface.height; sy++) {
    for (let sx = 0; sx < surface.width; sx++) {
      const idx: PaletteIndex = surface.data[sy * surface.width + sx] ?? TRANSPARENT_INDEX;
      if (idx === TRANSPARENT_INDEX) continue;

      if (lut.declared[idx] !== 1) {
        throw new Error(`Undeclared palette index ${idx} in style "${style.id}" at (${sx}, ${sy})`);
      }

      if (emissiveOnly && lut.emissive[idx] !== 1) continue;

      const rgbOffset = idx * 3;
      const r = lut.rgb[rgbOffset] ?? 0;
      const g = lut.rgb[rgbOffset + 1] ?? 0;
      const b = lut.rgb[rgbOffset + 2] ?? 0;

      // INVARIANT: Binary alpha only — opaque palette indices always write alpha 255
      writeScaledPixel(data, outW, sx, sy, scale, r, g, b, 255);
    }
  }

  return { width: outW, height: outH, data };
}

function writeScaledPixel(
  data: Uint8Array,
  outW: number,
  sx: number,
  sy: number,
  scale: number,
  r: number,
  g: number,
  b: number,
  a: number,
): void {
  if (scale === 1) {
    const outIdx = (sy * outW + sx) * 4;
    data[outIdx] = r;
    data[outIdx + 1] = g;
    data[outIdx + 2] = b;
    data[outIdx + 3] = a;
    return;
  }

  const baseX = sx * scale;
  const baseY = sy * scale;
  for (let dy = 0; dy < scale; dy++) {
    const rowStart = ((baseY + dy) * outW + baseX) * 4;
    for (let dx = 0; dx < scale; dx++) {
      const outIdx = rowStart + dx * 4;
      data[outIdx] = r;
      data[outIdx + 1] = g;
      data[outIdx + 2] = b;
      data[outIdx + 3] = a;
    }
  }
}

/**
 * Verifies that every pixel in an RGBA buffer has binary alpha (0 or 255).
 */
export function assertBinaryAlpha(rgba: RgbaBuffer): void {
  for (let i = 3; i < rgba.data.length; i += 4) {
    const alpha = rgba.data[i];
    if (alpha !== 0 && alpha !== 255) {
      const pixelIndex = (i - 3) / 4;
      const x = pixelIndex % rgba.width;
      const y = Math.floor(pixelIndex / rgba.width);
      throw new Error(`Non-binary alpha ${alpha} at (${x}, ${y})`);
    }
  }
}

/**
 * Encodes an RGBA buffer into a PNG byte buffer using fast-png.
 */
export function rgbaToPng(rgba: RgbaBuffer): Uint8Array {
  return encode({
    width: rgba.width,
    height: rgba.height,
    data: rgba.data,
    channels: 4,
    depth: 8,
  });
}

/**
 * Converts an IndexedSurface directly to a PNG byte buffer.
 */
export function surfaceToPng(
  surface: IndexedSurface,
  style: StylePack,
  options: SurfaceToRgbaOptions = {},
): Uint8Array {
  return rgbaToPng(surfaceToRgba(surface, style, options));
}
