import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { hashf, mulberry32 } from '../core/prng.js';
import { createSurface, IndexedSurface } from '../core/surface.js';
import type {
  AnchorPoint,
  AssetModule,
  HitboxRect,
  RenderContext,
  StylePack,
} from '../core/types.js';
import { rgbaToPng, surfaceToPng, surfaceToRgba } from './png.js';

export interface ExportedAssetFiles {
  readonly states: Readonly<Record<string, string>>;
  readonly sheet?: string;
  readonly emissive?: Readonly<Record<string, string>>;
}

export interface ExportedAssetManifestEntry {
  readonly id: string;
  readonly styleId: string;
  readonly perspective: string;
  readonly width: number;
  readonly height: number;
  readonly states: readonly string[];
  readonly frames: number;
  readonly fps: number;
  readonly files: ExportedAssetFiles;
  readonly anchors: readonly AnchorPoint[];
  readonly hitboxes: readonly HitboxRect[];
  readonly sha256: string;
}

export interface RenderedFrame<TState extends string = string> {
  readonly state: TState;
  readonly frame: number;
  readonly surface: IndexedSurface;
  readonly anchors: readonly AnchorPoint[];
  readonly hitboxes: readonly HitboxRect[];
}

export interface ExportBundleOptions {
  readonly variant?: string;
  readonly scale?: number;
  readonly emissive?: boolean;
}

export interface ExportBundleResult<TState extends string = string> {
  readonly manifest: ExportedAssetManifestEntry;
  readonly files: ReadonlyMap<string, Uint8Array>;
  readonly renderedFrames: readonly RenderedFrame<TState>[];
}

function deriveFrameSeed(baseSeed: number, stateIndex: number, frame: number): number {
  const mixed = hashf(stateIndex, frame, baseSeed);
  return (mixed * 0x1_0000_0000) >>> 0;
}

/**
 * Renders every (state, frame) of an AssetModule deterministically.
 */
export function renderAssetFrames<TState extends string>(
  asset: AssetModule<TState>,
  style: StylePack,
): RenderedFrame<TState>[] {
  if (asset.frames < 1 || !Number.isInteger(asset.frames)) {
    throw new RangeError(`Asset "${asset.id}" frames must be an integer >= 1, got ${asset.frames}`);
  }
  if (asset.states.length === 0) {
    throw new RangeError(`Asset "${asset.id}" must declare at least one state`);
  }

  const baseSeed = asset.seed ?? 0;
  const results: RenderedFrame<TState>[] = [];

  for (let stateIdx = 0; stateIdx < asset.states.length; stateIdx++) {
    const state = asset.states[stateIdx];
    if (state === undefined) continue;

    for (let frame = 0; frame < asset.frames; frame++) {
      const surface = createSurface(asset.width, asset.height);
      const anchors: AnchorPoint[] = [];
      const hitboxes: HitboxRect[] = [];
      const rng = mulberry32(deriveFrameSeed(baseSeed, stateIdx, frame));

      const ctx: RenderContext<TState> = {
        surface,
        style,
        state,
        frame,
        frameCount: asset.frames,
        rng,
        anchor(name, x, y) {
          anchors.push({ name, x: x | 0, y: y | 0 });
        },
        hitbox(name, x, y, w, h) {
          hitboxes.push({ name, x: x | 0, y: y | 0, w: w | 0, h: h | 0 });
        },
      };

      asset.render(ctx);
      results.push({ state, frame, surface, anchors, hitboxes });
    }
  }

  return results;
}

function computeBundleDigest<TState extends string>(
  asset: AssetModule<TState>,
  frames: readonly RenderedFrame<TState>[],
  anchors: readonly AnchorPoint[],
  hitboxes: readonly HitboxRect[],
): string {
  const hash = createHash('sha256');
  hash.update(
    JSON.stringify({
      id: asset.id,
      styleId: asset.styleId,
      width: asset.width,
      height: asset.height,
      states: asset.states,
      frames: asset.frames,
      anchors,
      hitboxes,
    }),
  );
  for (const item of frames) {
    hash.update(item.state);
    hash.update(Uint8Array.from([item.frame & 0xff, (item.frame >> 8) & 0xff]));
    hash.update(item.surface.data);
  }
  return hash.digest('hex');
}

function buildSpritesheetSurface<TState extends string>(
  asset: AssetModule<TState>,
  renderedFrames: readonly RenderedFrame<TState>[],
): IndexedSurface {
  const sheetW = asset.width * asset.frames;
  const sheetH = asset.height * asset.states.length;
  const sheet = new IndexedSurface(sheetW, sheetH);

  for (let stateIdx = 0; stateIdx < asset.states.length; stateIdx++) {
    const state = asset.states[stateIdx];
    for (let frame = 0; frame < asset.frames; frame++) {
      const entry = renderedFrames.find((f) => f.state === state && f.frame === frame);
      if (entry) {
        sheet.blitLayer(entry.surface, frame * asset.width, stateIdx * asset.height);
      }
    }
  }

  return sheet;
}

function hasEmissiveColors(style: StylePack): boolean {
  return style.palette.some((color) => color.flags?.includes('emissive'));
}

/**
 * Exports an AssetModule into 1x state PNGs, optional horizontal spritesheet,
 * optional emissive masks, and a deterministic manifest entry.
 */
export function exportAssetBundle<TState extends string>(
  asset: AssetModule<TState>,
  style: StylePack,
  options: ExportBundleOptions = {},
): ExportBundleResult<TState> {
  const renderedFrames = renderAssetFrames(asset, style);
  const scale = options.scale ?? 1;
  const includeEmissive = options.emissive ?? hasEmissiveColors(style);

  const files = new Map<string, Uint8Array>();
  const stateFiles: Record<string, string> = {};
  const emissiveFiles: Record<string, string> = {};

  const pngOpts = {
    scale,
    ...(options.variant !== undefined ? { variant: options.variant } : {}),
  };

  for (const state of asset.states) {
    const primaryFrame = renderedFrames.find((f) => f.state === state && f.frame === 0);
    if (!primaryFrame) continue;

    const stateFilename = `${asset.id}_${state}.png`;
    stateFiles[state] = stateFilename;
    files.set(stateFilename, surfaceToPng(primaryFrame.surface, style, pngOpts));

    if (includeEmissive) {
      const emissiveFilename = `${asset.id}_${state}_emissive.png`;
      emissiveFiles[state] = emissiveFilename;
      files.set(
        emissiveFilename,
        surfaceToPng(primaryFrame.surface, style, { ...pngOpts, emissiveOnly: true }),
      );
    }
  }

  let sheetFilename: string | undefined;
  if (asset.frames > 1) {
    sheetFilename = `${asset.id}_sheet.png`;
    const sheetSurface = buildSpritesheetSurface(asset, renderedFrames);
    const sheetRgba = surfaceToRgba(sheetSurface, style, pngOpts);
    files.set(sheetFilename, rgbaToPng(sheetRgba));
  }

  const canonicalFrame = renderedFrames[0];
  const anchors = canonicalFrame?.anchors ?? [];
  const hitboxes = canonicalFrame?.hitboxes ?? [];
  const sha256 = computeBundleDigest(asset, renderedFrames, anchors, hitboxes);

  const exportFiles: ExportedAssetFiles = {
    states: stateFiles,
    ...(sheetFilename !== undefined ? { sheet: sheetFilename } : {}),
    ...(includeEmissive ? { emissive: emissiveFiles } : {}),
  };

  const manifest: ExportedAssetManifestEntry = {
    id: asset.id,
    styleId: asset.styleId,
    perspective: asset.perspective,
    width: asset.width,
    height: asset.height,
    states: [...asset.states],
    frames: asset.frames,
    fps: asset.fps ?? 1,
    files: exportFiles,
    anchors,
    hitboxes,
    sha256,
  };

  return { manifest, files, renderedFrames };
}

/**
 * Writes exported sprite PNGs to `<outDir>/sprites/` and updates `<outDir>/manifest.json`.
 */
export async function writeExportBundle(
  bundle: ExportBundleResult,
  outDir: string,
): Promise<string> {
  const spritesDir = path.join(outDir, 'sprites');
  await mkdir(spritesDir, { recursive: true });

  for (const [filename, bytes] of bundle.files) {
    await writeFile(path.join(spritesDir, filename), bytes);
  }

  const manifestPath = path.join(outDir, 'manifest.json');
  let existing: Record<string, ExportedAssetManifestEntry> = {};
  try {
    const raw = await readFile(manifestPath, 'utf8');
    existing = JSON.parse(raw) as Record<string, ExportedAssetManifestEntry>;
  } catch {
    existing = {};
  }

  existing[bundle.manifest.id] = bundle.manifest;
  await writeFile(manifestPath, `${JSON.stringify(existing, null, 2)}\n`, 'utf8');
  return manifestPath;
}
