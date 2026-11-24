import { createHash } from 'node:crypto';
import type { AssetModule, StylePack } from '../core/types.js';
import { TRANSPARENT_INDEX } from '../core/types.js';
import { type RenderedFrame, renderAssetFrames } from '../export/bundle.js';
import { assertBinaryAlpha, surfaceToRgba } from '../export/png.js';

export type GuardRuleId =
  | 'no-math-random'
  | 'no-external-assets'
  | 'no-raw-hex'
  | 'closed-palette'
  | 'exact-dimensions'
  | 'binary-alpha'
  | 'bit-determinism'
  | 'valid-anchors';

export type StaticSourceScope = 'core' | 'style' | 'asset';

export interface GuardViolation {
  readonly file: string;
  readonly line: number;
  readonly rule: GuardRuleId;
  readonly detail: string;
}

const MATH_RANDOM_RE = /\bMath\s*\.\s*random\s*\(/;
const EXTERNAL_IMAGE_RE = /\.(?:png|jpe?g|webp|svg|gif)(?:['"`?#]|$)/i;
const DOM_CANVAS_RE =
  /\b(?:document|window|HTMLCanvasElement|CanvasRenderingContext2D|OffscreenCanvas|ImageBitmap|createImageBitmap)\b/;
const RAW_HEX_RE = /#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?(?:[0-9a-fA-F]{2})?\b/;

/**
 * Strips JS/TS comments while preserving string literals and exact line numbers.
 */
export function stripCommentsPreserveLines(source: string): string {
  const out: string[] = [];
  let i = 0;
  let mode: 'code' | 'line-comment' | 'block-comment' | 'single' | 'double' | 'template' = 'code';

  while (i < source.length) {
    const ch = source[i] ?? '';
    const next = source[i + 1] ?? '';

    if (mode === 'line-comment') {
      if (ch === '\n') {
        out.push('\n');
        mode = 'code';
      } else {
        out.push(' ');
      }
      i++;
      continue;
    }

    if (mode === 'block-comment') {
      if (ch === '*' && next === '/') {
        out.push('  ');
        i += 2;
        mode = 'code';
      } else {
        out.push(ch === '\n' ? '\n' : ' ');
        i++;
      }
      continue;
    }

    if (mode === 'single' || mode === 'double' || mode === 'template') {
      out.push(ch);
      if (ch === '\\' && i + 1 < source.length) {
        out.push(next);
        i += 2;
        continue;
      }
      if (
        (mode === 'single' && ch === "'") ||
        (mode === 'double' && ch === '"') ||
        (mode === 'template' && ch === '`')
      ) {
        mode = 'code';
      }
      i++;
      continue;
    }

    if (ch === '/' && next === '/') {
      out.push('  ');
      i += 2;
      mode = 'line-comment';
      continue;
    }
    if (ch === '/' && next === '*') {
      out.push('  ');
      i += 2;
      mode = 'block-comment';
      continue;
    }
    if (ch === "'") mode = 'single';
    else if (ch === '"') mode = 'double';
    else if (ch === '`') mode = 'template';

    out.push(ch);
    i++;
  }

  return out.join('');
}

/**
 * Runs static source guard rules (`no-math-random`, `no-external-assets`, `no-raw-hex`).
 */
export function checkStaticSource(
  filePath: string,
  source: string,
  scope: StaticSourceScope,
): GuardViolation[] {
  const violations: GuardViolation[] = [];
  const cleaned = stripCommentsPreserveLines(source);
  const lines = cleaned.split('\n');

  for (let idx = 0; idx < lines.length; idx++) {
    const lineNum = idx + 1;
    const line = lines[idx] ?? '';

    if (MATH_RANDOM_RE.test(line)) {
      violations.push({
        file: filePath,
        line: lineNum,
        rule: 'no-math-random',
        detail: 'Math.random() is forbidden; use ctx.rng() or seeded mulberry32',
      });
    }

    if (scope === 'asset') {
      if (EXTERNAL_IMAGE_RE.test(line) || DOM_CANVAS_RE.test(line)) {
        violations.push({
          file: filePath,
          line: lineNum,
          rule: 'no-external-assets',
          detail: 'External raster/SVG assets and DOM/Canvas APIs are forbidden in asset modules',
        });
      }

      if (RAW_HEX_RE.test(line)) {
        violations.push({
          file: filePath,
          line: lineNum,
          rule: 'no-raw-hex',
          detail: 'Raw hex color literals are forbidden in asset modules; use StylePack indices',
        });
      }
    }
  }

  return violations;
}

function hashFrameBuffer(data: Uint8Array): string {
  return createHash('sha256').update(data).digest('hex');
}

function checkFrameDimensions<TState extends string>(
  asset: AssetModule<TState>,
  frame: RenderedFrame<TState>,
  filePath: string,
): GuardViolation | undefined {
  if (
    !Number.isInteger(asset.width) ||
    !Number.isInteger(asset.height) ||
    asset.width < 1 ||
    asset.height < 1 ||
    frame.surface.width !== asset.width ||
    frame.surface.height !== asset.height
  ) {
    return {
      file: filePath,
      line: 1,
      rule: 'exact-dimensions',
      detail: `Expected ${asset.width}x${asset.height} for ${frame.state}#${frame.frame}, got ${frame.surface.width}x${frame.surface.height}`,
    };
  }
  return undefined;
}

function checkFramePaletteAndAlpha<TState extends string>(
  frame: RenderedFrame<TState>,
  style: StylePack,
  declared: ReadonlySet<number>,
  filePath: string,
): GuardViolation[] {
  const violations: GuardViolation[] = [];
  const { width, data } = frame.surface;

  for (let i = 0; i < data.length; i++) {
    const idx = data[i] ?? TRANSPARENT_INDEX;
    if (idx !== TRANSPARENT_INDEX && !declared.has(idx)) {
      const x = i % width;
      const y = Math.floor(i / width);
      violations.push({
        file: filePath,
        line: 1,
        rule: 'closed-palette',
        detail: `Undeclared palette index ${idx} at (${x}, ${y}) in ${frame.state}#${frame.frame}`,
      });
      return violations;
    }
  }

  try {
    const rgba = surfaceToRgba(frame.surface, style);
    assertBinaryAlpha(rgba);
  } catch (err) {
    violations.push({
      file: filePath,
      line: 1,
      rule: 'binary-alpha',
      detail: err instanceof Error ? err.message : String(err),
    });
  }

  return violations;
}

function checkFrameAnchors<TState extends string>(
  asset: AssetModule<TState>,
  frame: RenderedFrame<TState>,
  filePath: string,
): GuardViolation[] {
  const violations: GuardViolation[] = [];
  const seenAnchors = new Set<string>();
  const seenHitboxes = new Set<string>();

  for (const anchor of frame.anchors) {
    if (seenAnchors.has(anchor.name)) {
      violations.push({
        file: filePath,
        line: 1,
        rule: 'valid-anchors',
        detail: `Duplicate anchor "${anchor.name}" in ${frame.state}#${frame.frame}`,
      });
    }
    seenAnchors.add(anchor.name);

    if (anchor.x < 0 || anchor.x > asset.width || anchor.y < 0 || anchor.y > asset.height) {
      violations.push({
        file: filePath,
        line: 1,
        rule: 'valid-anchors',
        detail: `Anchor "${anchor.name}" (${anchor.x}, ${anchor.y}) out of bounds [0..${asset.width}]x[0..${asset.height}]`,
      });
    }
  }

  for (const box of frame.hitboxes) {
    if (seenHitboxes.has(box.name)) {
      violations.push({
        file: filePath,
        line: 1,
        rule: 'valid-anchors',
        detail: `Duplicate hitbox "${box.name}" in ${frame.state}#${frame.frame}`,
      });
    }
    seenHitboxes.add(box.name);

    if (
      box.w <= 0 ||
      box.h <= 0 ||
      box.x < 0 ||
      box.y < 0 ||
      box.x + box.w > asset.width ||
      box.y + box.h > asset.height
    ) {
      violations.push({
        file: filePath,
        line: 1,
        rule: 'valid-anchors',
        detail: `Hitbox "${box.name}" (${box.x},${box.y},${box.w}x${box.h}) out of bounds ${asset.width}x${asset.height}`,
      });
    }
  }

  return violations;
}

/**
 * Runs runtime guard rules (`exact-dimensions`, `closed-palette`, `binary-alpha`,
 * `bit-determinism`, `valid-anchors`) against a loaded AssetModule and StylePack.
 */
export function checkAssetRuntime<TState extends string>(
  asset: AssetModule<TState>,
  style: StylePack,
  filePath: string,
): GuardViolation[] {
  const violations: GuardViolation[] = [];
  const declared = new Set<number>(
    style.palette.filter((c) => c.index >= 0 && c.index < TRANSPARENT_INDEX).map((c) => c.index),
  );

  const firstRun = renderAssetFrames(asset, style);
  const secondRun = renderAssetFrames(asset, style);

  for (let i = 0; i < firstRun.length; i++) {
    const f1 = firstRun[i];
    const f2 = secondRun[i];
    if (!f1 || !f2) continue;

    const dimViolation = checkFrameDimensions(asset, f1, filePath);
    if (dimViolation) violations.push(dimViolation);

    violations.push(...checkFramePaletteAndAlpha(f1, style, declared, filePath));
    violations.push(...checkFrameAnchors(asset, f1, filePath));

    if (hashFrameBuffer(f1.surface.data) !== hashFrameBuffer(f2.surface.data)) {
      violations.push({
        file: filePath,
        line: 1,
        rule: 'bit-determinism',
        detail: `Non-deterministic pixel output for ${f1.state}#${f1.frame}`,
      });
    }
  }

  return violations;
}
