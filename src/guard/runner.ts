import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import type { AssetModule, StylePack } from '../core/types.js';
import {
  checkAssetRuntime,
  checkStaticSource,
  type GuardViolation,
  type StaticSourceScope,
} from './rules.js';

export interface GuardRunOptions {
  readonly rootDir: string;
  readonly assetFilter?: string;
}

export interface GuardRunResult {
  readonly passed: boolean;
  readonly checkedFiles: number;
  readonly checkedAssets: number;
  readonly violations: readonly GuardViolation[];
}

async function walkTsFiles(dir: string): Promise<string[]> {
  let entries: import('node:fs').Dirent[];
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return [];
  }

  const files: string[] = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await walkTsFiles(full)));
    } else if (entry.isFile() && entry.name.endsWith('.ts')) {
      files.push(full);
    }
  }
  return files.sort();
}

function isStylePack(value: unknown): value is StylePack {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.id === 'string' &&
    Array.isArray(candidate.palette) &&
    typeof candidate.outlineIndex === 'number'
  );
}

function isAssetModule(value: unknown): value is AssetModule {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.id === 'string' &&
    typeof candidate.styleId === 'string' &&
    typeof candidate.width === 'number' &&
    typeof candidate.height === 'number' &&
    Array.isArray(candidate.states) &&
    typeof candidate.render === 'function'
  );
}

/**
 * Dynamically imports a TypeScript or JavaScript module and extracts matching export.
 */
async function importModuleExports(filePath: string): Promise<Record<string, unknown>> {
  const url = `${pathToFileURL(path.resolve(filePath)).href}?t=${Date.now()}`;
  return (await import(url)) as Record<string, unknown>;
}

export async function loadStylePackFromFile(filePath: string): Promise<StylePack | undefined> {
  const mod = await importModuleExports(filePath);
  for (const value of Object.values(mod)) {
    if (isStylePack(value)) return value;
  }
  return undefined;
}

export async function loadAssetModuleFromFile(filePath: string): Promise<AssetModule | undefined> {
  const mod = await importModuleExports(filePath);
  for (const value of Object.values(mod)) {
    if (isAssetModule(value)) return value;
  }
  return undefined;
}

export async function discoverStylePacks(rootDir: string): Promise<Map<string, StylePack>> {
  const stylesDir = path.join(rootDir, 'styles');
  const styleFiles = (await walkTsFiles(stylesDir)).filter((f) => f.endsWith('.style.ts'));
  const styles = new Map<string, StylePack>();

  for (const file of styleFiles) {
    const pack = await loadStylePackFromFile(file);
    if (pack) styles.set(pack.id, pack);
  }
  return styles;
}

export interface DiscoveredAsset {
  readonly filePath: string;
  readonly asset: AssetModule;
}

export async function discoverAssets(rootDir: string, filter?: string): Promise<DiscoveredAsset[]> {
  const assetsDir = path.join(rootDir, 'assets');
  const assetFiles = (await walkTsFiles(assetsDir)).filter((f) => f.endsWith('.asset.ts'));
  const discovered: DiscoveredAsset[] = [];

  for (const filePath of assetFiles) {
    const asset = await loadAssetModuleFromFile(filePath);
    if (!asset) continue;
    if (
      filter !== undefined &&
      asset.id !== filter &&
      path.relative(rootDir, filePath) !== filter &&
      path.resolve(filePath) !== path.resolve(filter)
    ) {
      continue;
    }
    discovered.push({ filePath, asset });
  }
  return discovered;
}

/**
 * Formats violations in canonical `file:line [rule] detail` format.
 */
export function formatGuardViolations(
  violations: readonly GuardViolation[],
  rootDir?: string,
): string {
  return violations
    .map((v) => {
      const displayPath = rootDir ? path.relative(rootDir, v.file) || v.file : v.file;
      return `${displayPath}:${v.line} [${v.rule}] ${v.detail}`;
    })
    .join('\n');
}

async function runStaticChecksForDir(
  dir: string,
  scope: StaticSourceScope,
  violations: GuardViolation[],
): Promise<number> {
  const files = await walkTsFiles(dir);
  for (const file of files) {
    const source = await readFile(file, 'utf8');
    violations.push(...checkStaticSource(file, source, scope));
  }
  return files.length;
}

/**
 * Executes static and runtime guard rules across `src/core/`, `styles/`, and `assets/`.
 */
export async function runGuards(options: GuardRunOptions): Promise<GuardRunResult> {
  const violations: GuardViolation[] = [];
  let checkedFiles = 0;

  checkedFiles += await runStaticChecksForDir(
    path.join(options.rootDir, 'src', 'core'),
    'core',
    violations,
  );
  checkedFiles += await runStaticChecksForDir(
    path.join(options.rootDir, 'styles'),
    'style',
    violations,
  );
  checkedFiles += await runStaticChecksForDir(
    path.join(options.rootDir, 'assets'),
    'asset',
    violations,
  );

  const styles = await discoverStylePacks(options.rootDir);
  const assets = await discoverAssets(options.rootDir, options.assetFilter);

  for (const { filePath, asset } of assets) {
    const style = styles.get(asset.styleId);
    if (!style) {
      violations.push({
        file: filePath,
        line: 1,
        rule: 'closed-palette',
        detail: `Missing StylePack "${asset.styleId}" for asset "${asset.id}"`,
      });
      continue;
    }
    violations.push(...checkAssetRuntime(asset, style, filePath));
  }

  return {
    passed: violations.length === 0,
    checkedFiles,
    checkedAssets: assets.length,
    violations,
  };
}
