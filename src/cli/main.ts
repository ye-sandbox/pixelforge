#!/usr/bin/env node
import { execFile } from 'node:child_process';
import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs, promisify } from 'node:util';
import {
  decodePngToRgba,
  exportAssetBundle,
  generateContactSheet,
  generatePixelDiff,
  surfaceToRgba,
  writeExportBundle,
} from '../export/index.js';
import {
  discoverAssets,
  discoverStylePacks,
  formatGuardViolations,
  runGuards,
} from '../guard/index.js';

const execFileAsync = promisify(execFile);

export type CliCommand = 'init' | 'render' | 'check' | 'diff';

export interface ParsedCli {
  readonly command: CliCommand | undefined;
  readonly help: boolean;
  readonly version: boolean;
  readonly positionals: readonly string[];
  readonly style: string;
  readonly out: string | undefined;
  readonly sheet: boolean;
  readonly scale: number;
  readonly emissive: boolean;
  readonly variant: string | undefined;
  readonly base: string;
  readonly force: boolean;
}

export interface CliRunOptions {
  readonly cwd?: string;
}

const VALID_COMMANDS = new Set<string>(['init', 'render', 'check', 'diff']);

export const CLI_VERSION = '0.1.0';

export function formatHelp(): string {
  return [
    'pixelforge — Code-drawn indexed pixel art engine & visual critic CLI',
    '',
    'Usage:',
    '  pixelforge <command> [options]',
    '',
    'Commands:',
    '  init     Scaffold a new style pack and sample asset module',
    '  render   Render asset module(s) to PNG, spritesheet, manifest, and contact sheet',
    '  check    Run static and runtime guard checks',
    '  diff     Compare rendered output against a baseline',
    '',
    'Options:',
    '  -h, --help          Show help',
    '  -v, --version       Show version',
    '  --style <id>        StylePack id for init (default: homelab-16bit)',
    '  --out <dir>         Output directory',
    '  --sheet             Generate .pixelforge/sheets/<id>.contact.png',
    '  --scale <n>         Integer upscale factor for exported PNGs (default: 1)',
    '  --emissive          Export emissive mask PNGs',
    '  --variant <name>    Apply a StylePack color variant',
    '  --base <ref|dir>    Baseline git ref or directory for diff (default: HEAD)',
    '  --force             Overwrite existing scaffolded files in init',
  ].join('\n');
}

export function parseCliArgs(argv: readonly string[]): ParsedCli {
  const { values, positionals } = parseArgs({
    args: [...argv],
    allowPositionals: true,
    strict: false,
    options: {
      help: { type: 'boolean', short: 'h', default: false },
      version: { type: 'boolean', short: 'v', default: false },
      style: { type: 'string', default: 'homelab-16bit' },
      out: { type: 'string' },
      sheet: { type: 'boolean', default: false },
      scale: { type: 'string', default: '1' },
      emissive: { type: 'boolean', default: false },
      variant: { type: 'string' },
      base: { type: 'string', default: 'HEAD' },
      force: { type: 'boolean', default: false },
    },
  });

  const [first, ...rest] = positionals;
  const command =
    first !== undefined && VALID_COMMANDS.has(first) ? (first as CliCommand) : undefined;
  const parsedScale = Number.parseInt(String(values.scale ?? '1'), 10);

  return {
    command,
    help: Boolean(values.help),
    version: Boolean(values.version),
    positionals: command !== undefined ? rest : positionals,
    style: typeof values.style === 'string' ? values.style : 'homelab-16bit',
    out: typeof values.out === 'string' ? values.out : undefined,
    sheet: Boolean(values.sheet),
    scale: Number.isFinite(parsedScale) && parsedScale >= 1 ? parsedScale : 1,
    emissive: Boolean(values.emissive),
    variant: typeof values.variant === 'string' ? values.variant : undefined,
    base: typeof values.base === 'string' ? values.base : 'HEAD',
    force: Boolean(values.force),
  };
}

function buildStarterStyleSource(styleId: string): string {
  return `import type { StylePack } from 'pixelforge';

export const stylePack: StylePack = {
  id: '${styleId}',
  perspective: 'front-2.5d',
  lightingAngle: 'top-left',
  outlineIndex: 0,
  palette: [
    { index: 0, name: 'OUTLINE', hex: '#0d1117', flags: ['outline'] },
    { index: 1, name: 'CHASSIS_DARK', hex: '#2b323b', flags: ['shadow'] },
    { index: 2, name: 'CHASSIS_MID', hex: '#48525e', flags: ['surface'] },
    { index: 3, name: 'CHASSIS_LIGHT', hex: '#768390', flags: ['metal'] },
    { index: 4, name: 'LED_GREEN', hex: '#3fb950', flags: ['emissive', 'accent'] },
  ],
};
`;
}

function buildStarterAssetSource(styleId: string): string {
  return `import type { AssetModule } from 'pixelforge';

const PAL = {
  OUTLINE: 0,
  DARK: 1,
  MID: 2,
  LIGHT: 3,
  LED_GREEN: 4,
} as const;

export const sampleBoxAsset: AssetModule<'healthy'> = {
  id: 'sample_box',
  styleId: '${styleId}',
  width: 16,
  height: 16,
  perspective: 'front-2.5d',
  states: ['healthy'],
  frames: 1,
  seed: 1,
  render(ctx) {
    ctx.surface.rect(2, 2, 12, 12, PAL.MID);
    ctx.surface.rect(2, 2, 12, 2, PAL.LIGHT);
    ctx.surface.rect(2, 12, 12, 2, PAL.DARK);
    ctx.surface.put(11, 5, PAL.LED_GREEN);
    ctx.surface.autoOutline(PAL.OUTLINE);
    ctx.anchor('foot', 8, 14);
  },
};
`;
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function handleInit(parsed: ParsedCli, cwd: string): Promise<number> {
  const styleId = parsed.style;
  const stylePath = path.join(cwd, 'styles', `${styleId}.style.ts`);
  const assetPath = path.join(cwd, 'assets', styleId, 'sample_box.asset.ts');

  if (!parsed.force && ((await fileExists(stylePath)) || (await fileExists(assetPath)))) {
    process.stderr.write('Target style or asset already exists. Pass --force to overwrite.\n');
    return 1;
  }

  await mkdir(path.dirname(stylePath), { recursive: true });
  await mkdir(path.dirname(assetPath), { recursive: true });
  await writeFile(stylePath, buildStarterStyleSource(styleId), 'utf8');
  await writeFile(assetPath, buildStarterAssetSource(styleId), 'utf8');

  process.stdout.write(`Initialized style "${styleId}":\n  ${stylePath}\n  ${assetPath}\n`);
  return 0;
}

async function handleCheck(parsed: ParsedCli, cwd: string): Promise<number> {
  const result = await runGuards({
    rootDir: cwd,
    ...(parsed.positionals[0] !== undefined ? { assetFilter: parsed.positionals[0] } : {}),
  });

  if (!result.passed) {
    process.stderr.write(`${formatGuardViolations(result.violations, cwd)}\n`);
    return 1;
  }

  process.stdout.write(
    `Guard check passed (${result.checkedFiles} file(s), ${result.checkedAssets} asset(s)).\n`,
  );
  return 0;
}

async function handleRender(parsed: ParsedCli, cwd: string): Promise<number> {
  const styles = await discoverStylePacks(cwd);
  const assets = await discoverAssets(cwd, parsed.positionals[0]);

  if (assets.length === 0) {
    process.stderr.write('No matching asset modules found.\n');
    return 1;
  }

  const outDir = path.resolve(cwd, parsed.out ?? 'dist');
  for (const { asset } of assets) {
    const style = styles.get(asset.styleId);
    if (!style) {
      process.stderr.write(`Missing StylePack "${asset.styleId}" for asset "${asset.id}".\n`);
      return 1;
    }

    const bundle = exportAssetBundle(asset, style, {
      scale: parsed.scale,
      emissive: parsed.emissive,
      ...(parsed.variant !== undefined ? { variant: parsed.variant } : {}),
    });
    const manifestPath = await writeExportBundle(bundle, outDir);
    process.stdout.write(`Rendered ${asset.id} -> ${manifestPath}\n`);

    if (parsed.sheet) {
      const sheetDir = path.join(cwd, '.pixelforge', 'sheets');
      await mkdir(sheetDir, { recursive: true });
      const sheetPath = path.join(sheetDir, `${asset.id}.contact.png`);
      const sheet = generateContactSheet(
        asset,
        style,
        parsed.variant !== undefined ? { variant: parsed.variant } : {},
      );
      await writeFile(sheetPath, sheet.png);
      process.stdout.write(`Contact sheet -> ${sheetPath}\n`);
    }
  }

  return 0;
}

async function loadBaselinePng(
  cwd: string,
  base: string,
  filename: string,
): Promise<Uint8Array | undefined> {
  const dirCandidates = [
    path.resolve(cwd, base, 'sprites', filename),
    path.resolve(cwd, base, filename),
  ];
  for (const candidate of dirCandidates) {
    if (await fileExists(candidate)) {
      return new Uint8Array(await readFile(candidate));
    }
  }

  try {
    const { stdout } = await execFileAsync('git', ['show', `${base}:dist/sprites/${filename}`], {
      cwd,
      encoding: 'buffer',
    });
    return new Uint8Array(stdout);
  } catch {
    return undefined;
  }
}

async function handleDiff(parsed: ParsedCli, cwd: string): Promise<number> {
  const target = parsed.positionals[0];
  if (!target) {
    process.stderr.write('Usage: pixelforge diff <asset-id> [--base HEAD] [--out dir]\n');
    return 1;
  }

  const styles = await discoverStylePacks(cwd);
  const assets = await discoverAssets(cwd, target);
  const entry = assets[0];
  if (!entry) {
    process.stderr.write(`Asset "${target}" not found.\n`);
    return 1;
  }

  const style = styles.get(entry.asset.styleId);
  if (!style) {
    process.stderr.write(`Missing StylePack "${entry.asset.styleId}".\n`);
    return 1;
  }

  const bundle = exportAssetBundle(entry.asset, style, { scale: parsed.scale });
  const outDir = path.resolve(cwd, parsed.out ?? path.join('.pixelforge', 'diffs'));
  await mkdir(outDir, { recursive: true });

  let compared = 0;
  for (const state of entry.asset.states) {
    const filename = `${entry.asset.id}_${state}.png`;
    const baselineBytes = await loadBaselinePng(cwd, parsed.base, filename);
    const frame = bundle.renderedFrames.find((f) => f.state === state && f.frame === 0);
    if (!baselineBytes || !frame) continue;

    const baselineRgba = decodePngToRgba(baselineBytes);
    const currentRgba = surfaceToRgba(frame.surface, style, { scale: parsed.scale });
    const diff = generatePixelDiff(baselineRgba, currentRgba);
    const diffPath = path.join(outDir, `${entry.asset.id}_${state}.diff.png`);
    await writeFile(diffPath, diff.png);
    process.stdout.write(
      `${entry.asset.id} (${state}): ${diff.changedPixels} changed pixel(s) -> ${diffPath}\n`,
    );
    compared++;
  }

  if (compared === 0) {
    process.stderr.write(`No baseline PNGs found for "${entry.asset.id}" at "${parsed.base}".\n`);
    return 1;
  }

  return 0;
}

export async function runCli(
  argv: readonly string[],
  options: CliRunOptions = {},
): Promise<number> {
  const parsed = parseCliArgs(argv);
  const cwd = options.cwd ?? process.cwd();

  if (parsed.version) {
    process.stdout.write(`${CLI_VERSION}\n`);
    return 0;
  }

  if (parsed.help || parsed.command === undefined) {
    process.stdout.write(`${formatHelp()}\n`);
    return parsed.help || parsed.positionals.length === 0 ? 0 : 1;
  }

  switch (parsed.command) {
    case 'init':
      return handleInit(parsed, cwd);
    case 'check':
      return handleCheck(parsed, cwd);
    case 'render':
      return handleRender(parsed, cwd);
    case 'diff':
      return handleDiff(parsed, cwd);
  }
}

const entryHref = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (import.meta.url === entryHref) {
  runCli(process.argv.slice(2))
    .then((code) => {
      process.exitCode = code;
    })
    .catch((err: unknown) => {
      process.stderr.write(`${err instanceof Error ? err.message : String(err)}\n`);
      process.exitCode = 1;
    });
}
