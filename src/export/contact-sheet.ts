import type { AnchorPoint, AssetModule, StylePack } from '../core/types.js';
import { TRANSPARENT_INDEX } from '../core/types.js';
import { drawBitmapText, fillRgbaRect, putRgbaPixel, type RgbColor } from './bitmap-font.js';
import { type RenderedFrame, renderAssetFrames } from './bundle.js';
import { parseHexColor, type RgbaBuffer, rgbaToPng, surfaceToRgba } from './png.js';

export interface ContactSheetOptions {
  readonly zoom?: number;
  readonly variant?: string;
}

export interface ContactSheetResult {
  readonly width: number;
  readonly height: number;
  readonly data: Uint8Array;
  readonly png: Uint8Array;
}

const BG_MAIN: RgbColor = [18, 22, 29];
const BG_HEADER: RgbColor = [28, 34, 45];
const TEXT_LIGHT: RgbColor = [230, 237, 243];
const TEXT_MUTED: RgbColor = [139, 148, 158];
const GRID_LINE: RgbColor = [55, 65, 81];
const RULER_COLOR: RgbColor = [121, 192, 255];
const ANCHOR_COLOR: RgbColor = [255, 123, 114];
const CHECK_DARK_A: RgbColor = [13, 17, 23];
const CHECK_DARK_B: RgbColor = [24, 30, 40];
const CHECK_LIGHT_A: RgbColor = [230, 237, 243];
const CHECK_LIGHT_B: RgbColor = [208, 215, 222];

function chooseZoom(width: number, height: number): number {
  const maxDim = Math.max(width, height);
  if (maxDim <= 32) return 8;
  if (maxDim <= 96) return 4;
  if (maxDim <= 200) return 2;
  return 1;
}

function drawCheckerboard(
  buf: RgbaBuffer,
  x: number,
  y: number,
  w: number,
  h: number,
  colorA: RgbColor,
  colorB: RgbColor,
  tileSize = 4,
): void {
  for (let py = 0; py < h; py++) {
    for (let px = 0; px < w; px++) {
      const even = (((px / tileSize) | 0) + ((py / tileSize) | 0)) % 2 === 0;
      const [r, g, b] = even ? colorA : colorB;
      putRgbaPixel(buf, x + px, y + py, r, g, b, 255);
    }
  }
}

function compositeRgba(dest: RgbaBuffer, src: RgbaBuffer, dx: number, dy: number): void {
  for (let sy = 0; sy < src.height; sy++) {
    for (let sx = 0; sx < src.width; sx++) {
      const sIdx = (sy * src.width + sx) * 4;
      const alpha = src.data[sIdx + 3] ?? 0;
      if (alpha === 0) continue;
      putRgbaPixel(
        dest,
        dx + sx,
        dy + sy,
        src.data[sIdx] ?? 0,
        src.data[sIdx + 1] ?? 0,
        src.data[sIdx + 2] ?? 0,
        255,
      );
    }
  }
}

function drawZoomedGridAndAnchors(
  buf: RgbaBuffer,
  panelX: number,
  panelY: number,
  assetW: number,
  assetH: number,
  zoom: number,
  anchors: readonly AnchorPoint[],
): void {
  const zoomedW = assetW * zoom;
  const zoomedH = assetH * zoom;

  if (zoom >= 4) {
    for (let gx = 1; gx < assetW; gx++) {
      const px = panelX + gx * zoom;
      for (let py = 0; py < zoomedH; py++) {
        putRgbaPixel(buf, px, panelY + py, GRID_LINE[0], GRID_LINE[1], GRID_LINE[2]);
      }
    }
    for (let gy = 1; gy < assetH; gy++) {
      const py = panelY + gy * zoom;
      for (let px = 0; px < zoomedW; px++) {
        putRgbaPixel(buf, panelX + px, py, GRID_LINE[0], GRID_LINE[1], GRID_LINE[2]);
      }
    }
  }

  const tickStep = assetW > 96 || assetH > 96 ? 16 : 4;
  for (let x = 0; x <= assetW; x += tickStep) {
    const px = panelX + x * zoom;
    fillRgbaRect(buf, px, panelY - 3, 1, 3, RULER_COLOR);
    if (x < assetW) {
      drawBitmapText(buf, String(x), px, panelY - 10, RULER_COLOR, 1);
    }
  }
  for (let y = 0; y <= assetH; y += tickStep) {
    const py = panelY + y * zoom;
    fillRgbaRect(buf, panelX - 3, py, 3, 1, RULER_COLOR);
    if (y < assetH) {
      const label = String(y);
      drawBitmapText(buf, label, Math.max(2, panelX - 4 - label.length * 4), py, RULER_COLOR, 1);
    }
  }

  for (const anchor of anchors) {
    const ax = panelX + anchor.x * zoom + ((zoom / 2) | 0);
    const ay = panelY + anchor.y * zoom + ((zoom / 2) | 0);
    fillRgbaRect(buf, ax - 3, ay, 7, 1, ANCHOR_COLOR);
    fillRgbaRect(buf, ax, ay - 3, 1, 7, ANCHOR_COLOR);
  }
}

function collectUsedPaletteIndices(frames: readonly RenderedFrame[]): Set<number> {
  const used = new Set<number>();
  for (const frame of frames) {
    for (let i = 0; i < frame.surface.data.length; i++) {
      const idx = frame.surface.data[i] ?? TRANSPARENT_INDEX;
      if (idx !== TRANSPARENT_INDEX) {
        used.add(idx);
      }
    }
  }
  return used;
}

/**
 * Generates a diagnostic .contact.png with 1x dark/light previews,
 * 4x/8x zoomed grid with (x,y) ruler, state/frame matrix, and palette swatches.
 */
export function generateContactSheet<TState extends string>(
  asset: AssetModule<TState>,
  style: StylePack,
  options: ContactSheetOptions = {},
): ContactSheetResult {
  const frames = renderAssetFrames(asset, style);
  const primary = frames[0];
  if (!primary) {
    throw new Error(`Asset "${asset.id}" produced no rendered frames`);
  }

  const zoom = options.zoom ?? chooseZoom(asset.width, asset.height);
  const rgbaOpts = options.variant !== undefined ? { variant: options.variant } : {};

  const pad = 16;
  const headerH = 26;
  const rulerMarginLeft = 24;
  const rulerMarginTop = 16;
  const zoomedW = asset.width * zoom;
  const zoomedH = asset.height * zoom;
  const strip1xH = Math.max(asset.height + 16, 28);
  const cellW = Math.max(asset.width + 8, 44);
  const matrixCols =
    asset.frames + (style.palette.some((c) => c.flags?.includes('emissive')) ? 1 : 0);
  const matrixW = matrixCols * cellW + 48;
  const matrixH = asset.states.length * (asset.height + 14) + 18;
  const usedIndices = collectUsedPaletteIndices(frames);
  const swatchRows = Math.max(1, Math.ceil(usedIndices.size / 6));
  const swatchH = swatchRows * 16 + 20;

  const contentW = Math.max(
    rulerMarginLeft + zoomedW + pad,
    asset.width * 2 + pad * 3,
    matrixW + pad,
    360,
  );
  const sheetW = contentW + pad * 2;
  const sheetH =
    headerH + pad + strip1xH + pad + rulerMarginTop + zoomedH + pad + matrixH + pad + swatchH + pad;

  const canvas: RgbaBuffer = {
    width: sheetW,
    height: sheetH,
    data: new Uint8Array(sheetW * sheetH * 4),
  };
  fillRgbaRect(canvas, 0, 0, sheetW, sheetH, BG_MAIN);
  fillRgbaRect(canvas, 0, 0, sheetW, headerH, BG_HEADER);

  const headerText = `${asset.id} ${asset.width}x${asset.height} ${asset.styleId} ${asset.perspective} F:${asset.frames}`;
  drawBitmapText(canvas, headerText, pad, 10, TEXT_LIGHT, 1);

  // 1x Dark & Light Previews
  const stripY = headerH + pad;
  const primary1x = surfaceToRgba(primary.surface, style, rgbaOpts);
  drawBitmapText(canvas, '1X DARK', pad, stripY, TEXT_MUTED, 1);
  drawCheckerboard(canvas, pad, stripY + 8, asset.width, asset.height, CHECK_DARK_A, CHECK_DARK_B);
  compositeRgba(canvas, primary1x, pad, stripY + 8);

  const lightX = pad * 2 + Math.max(asset.width, 40);
  drawBitmapText(canvas, '1X LIGHT', lightX, stripY, TEXT_MUTED, 1);
  drawCheckerboard(
    canvas,
    lightX,
    stripY + 8,
    asset.width,
    asset.height,
    CHECK_LIGHT_A,
    CHECK_LIGHT_B,
  );
  compositeRgba(canvas, primary1x, lightX, stripY + 8);

  // Zoomed Panel + Ruler + Anchors
  const zoomPanelX = pad + rulerMarginLeft;
  const zoomPanelY = stripY + strip1xH + pad + rulerMarginTop;
  const zoomedRgba = surfaceToRgba(primary.surface, style, { ...rgbaOpts, scale: zoom });
  drawCheckerboard(
    canvas,
    zoomPanelX,
    zoomPanelY,
    zoomedW,
    zoomedH,
    CHECK_DARK_A,
    CHECK_DARK_B,
    zoom,
  );
  compositeRgba(canvas, zoomedRgba, zoomPanelX, zoomPanelY);
  drawZoomedGridAndAnchors(
    canvas,
    zoomPanelX,
    zoomPanelY,
    asset.width,
    asset.height,
    zoom,
    primary.anchors,
  );

  // State & Frame Matrix
  const matrixY = zoomPanelY + zoomedH + pad;
  drawBitmapText(canvas, 'STATES / FRAMES', pad, matrixY, TEXT_MUTED, 1);
  const hasEmissive = style.palette.some((c) => c.flags?.includes('emissive'));

  for (let sIdx = 0; sIdx < asset.states.length; sIdx++) {
    const state = asset.states[sIdx];
    if (!state) continue;
    const rowY = matrixY + 12 + sIdx * (asset.height + 14);
    drawBitmapText(canvas, state.slice(0, 10), pad, rowY + 2, TEXT_LIGHT, 1);

    for (let f = 0; f < asset.frames; f++) {
      const entry = frames.find((item) => item.state === state && item.frame === f);
      if (!entry) continue;
      const cellX = pad + 48 + f * cellW;
      drawCheckerboard(canvas, cellX, rowY, asset.width, asset.height, CHECK_DARK_A, CHECK_DARK_B);
      compositeRgba(canvas, surfaceToRgba(entry.surface, style, rgbaOpts), cellX, rowY);
    }

    if (hasEmissive) {
      const entry = frames.find((item) => item.state === state && item.frame === 0);
      if (entry) {
        const emX = pad + 48 + asset.frames * cellW;
        fillRgbaRect(canvas, emX, rowY, asset.width, asset.height, CHECK_DARK_A);
        compositeRgba(
          canvas,
          surfaceToRgba(entry.surface, style, { ...rgbaOpts, emissiveOnly: true }),
          emX,
          rowY,
        );
      }
    }
  }

  // Used Palette Swatches
  const swatchY = matrixY + matrixH + pad;
  drawBitmapText(canvas, `PALETTE USED (${usedIndices.size})`, pad, swatchY, TEXT_MUTED, 1);
  let swatchIdx = 0;
  for (const color of style.palette) {
    if (!usedIndices.has(color.index)) continue;
    const col = swatchIdx % 6;
    const row = (swatchIdx / 6) | 0;
    const sx = pad + col * 58;
    const sy = swatchY + 12 + row * 16;
    const hex = style.variants?.[options.variant ?? '']?.[color.name] ?? color.hex;
    fillRgbaRect(canvas, sx, sy, 10, 10, parseHexColor(hex));
    drawBitmapText(
      canvas,
      `${color.index}:${color.name.slice(0, 6)}`,
      sx + 13,
      sy + 2,
      TEXT_LIGHT,
      1,
    );
    swatchIdx++;
  }

  return {
    width: sheetW,
    height: sheetH,
    data: canvas.data,
    png: rgbaToPng(canvas),
  };
}
