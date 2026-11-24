import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { decode } from 'fast-png';
import { describe, expect, it } from 'vitest';
import type { AssetModule, StylePack } from '../../src/core/index.js';
import { exportAssetBundle, writeExportBundle } from '../../src/export/bundle.js';

const STYLE: StylePack = {
  id: 'bundle-style',
  perspective: 'front-2.5d',
  lightingAngle: 'top-left',
  outlineIndex: 0,
  palette: [
    { index: 0, name: 'OUTLINE', hex: '#0d1117', flags: ['outline'] },
    { index: 1, name: 'BODY', hex: '#64748b', flags: ['surface'] },
    { index: 2, name: 'LED', hex: '#22c55e', flags: ['emissive'] },
  ],
};

const MULTI_FRAME_ASSET: AssetModule<'healthy' | 'faulty'> = {
  id: 'test_node',
  styleId: 'bundle-style',
  width: 8,
  height: 8,
  perspective: 'front-2.5d',
  states: ['healthy', 'faulty'],
  frames: 2,
  fps: 4,
  seed: 42,
  render(ctx) {
    ctx.surface.rect(1, 1, 6, 6, 1);
    ctx.surface.autoOutline(0);
    if (ctx.frame === 0 || ctx.state === 'healthy') {
      ctx.surface.put(3, 3, 2);
    }
    if (ctx.rng() > 0.5) {
      ctx.surface.put(4, 3, 2);
    }
    ctx.anchor('foot', 4, 7);
    ctx.hitbox('body', 1, 1, 6, 6);
  },
};

describe('Asset bundle exporter', () => {
  it('produces deterministic SHA-256 digests and spritesheets for multi-frame assets', () => {
    const first = exportAssetBundle(MULTI_FRAME_ASSET, STYLE);
    const second = exportAssetBundle(MULTI_FRAME_ASSET, STYLE);

    expect(first.manifest.sha256).toBe(second.manifest.sha256);
    expect(first.manifest.sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(first.manifest.anchors).toEqual([{ name: 'foot', x: 4, y: 7 }]);
    expect(first.manifest.hitboxes).toEqual([{ name: 'body', x: 1, y: 1, w: 6, h: 6 }]);
    expect(first.manifest.files.states).toEqual({
      healthy: 'test_node_healthy.png',
      faulty: 'test_node_faulty.png',
    });
    expect(first.manifest.files.sheet).toBe('test_node_sheet.png');
    expect(first.manifest.files.emissive).toEqual({
      healthy: 'test_node_healthy_emissive.png',
      faulty: 'test_node_faulty_emissive.png',
    });

    const sheetBytes = first.files.get('test_node_sheet.png');
    expect(sheetBytes).toBeDefined();
    if (sheetBytes) {
      const decoded = decode(sheetBytes);
      // 2 frames wide (8*2=16), 2 states tall (8*2=16)
      expect(decoded.width).toBe(16);
      expect(decoded.height).toBe(16);
    }
  });

  it('writes sprites and manifest.json to disk cleanly', async () => {
    const dir = await mkdtemp(path.join(tmpdir(), 'pixelforge-bundle-'));
    try {
      const bundle = exportAssetBundle(MULTI_FRAME_ASSET, STYLE);
      const manifestPath = await writeExportBundle(bundle, dir);

      const rawManifest = JSON.parse(await readFile(manifestPath, 'utf8')) as Record<
        string,
        typeof bundle.manifest
      >;
      expect(rawManifest.test_node?.sha256).toBe(bundle.manifest.sha256);

      const spriteBytes = await readFile(path.join(dir, 'sprites', 'test_node_healthy.png'));
      const decoded = decode(spriteBytes);
      expect(decoded.width).toBe(8);
      expect(decoded.height).toBe(8);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});
