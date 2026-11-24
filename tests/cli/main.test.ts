import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { runCli } from '../../src/cli/main.js';

const tempDirs: string[] = [];

async function makeTempWorkspace(): Promise<string> {
  const dir = await mkdtemp(path.join(tmpdir(), 'pixelforge-cli-'));
  tempDirs.push(dir);
  return dir;
}

afterEach(async () => {
  await Promise.all(tempDirs.splice(0).map((d) => rm(d, { recursive: true, force: true })));
});

describe('pixelforge CLI', () => {
  it('scaffolds, checks, renders with contact sheet, and diffs against baseline', async () => {
    const ws = await makeTempWorkspace();

    expect(await runCli(['init', '--style', 'demo-pack'], { cwd: ws })).toBe(0);
    expect(await runCli(['check'], { cwd: ws })).toBe(0);
    expect(await runCli(['render', 'sample_box', '--out', 'dist', '--sheet'], { cwd: ws })).toBe(0);

    const manifestRaw = await readFile(path.join(ws, 'dist', 'manifest.json'), 'utf8');
    const manifest = JSON.parse(manifestRaw) as Record<string, { id: string; width: number }>;
    expect(manifest.sample_box?.id).toBe('sample_box');
    expect(manifest.sample_box?.width).toBe(16);

    const sheetBytes = await readFile(
      path.join(ws, '.pixelforge', 'sheets', 'sample_box.contact.png'),
    );
    expect(sheetBytes.subarray(0, 4)).toEqual(Buffer.from([0x89, 0x50, 0x4e, 0x47]));

    expect(await runCli(['diff', 'sample_box', '--base', 'dist'], { cwd: ws })).toBe(0);
    const diffBytes = await readFile(
      path.join(ws, '.pixelforge', 'diffs', 'sample_box_healthy.diff.png'),
    );
    expect(diffBytes.subarray(0, 4)).toEqual(Buffer.from([0x89, 0x50, 0x4e, 0x47]));
  });

  it('returns non-zero exit code when guard check detects a violation', async () => {
    const ws = await makeTempWorkspace();
    expect(await runCli(['init', '--style', 'demo-pack'], { cwd: ws })).toBe(0);

    const badAsset = path.join(ws, 'assets', 'demo-pack', 'sample_box.asset.ts');
    await writeFile(
      badAsset,
      `export const bad = { id: 'bad', styleId: 'demo-pack', width: 4, height: 4, perspective: 'front-2.5d', states: ['a'], frames: 1, render() { const c = '#ff0000'; void c; Math.random(); } };\n`,
      'utf8',
    );

    expect(await runCli(['check'], { cwd: ws })).toBe(1);
  });
});
