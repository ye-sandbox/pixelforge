import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { exportAssetBundle } from '../src/export/bundle.js';
import { discoverAssets, discoverStylePacks, runGuards } from '../src/guard/runner.js';

const ROOT_DIR = path.resolve(import.meta.dirname, '..');

describe('homelab-16bit pilot pack', () => {
  it('passes all static and runtime guard rules across all 4 pilot assets', async () => {
    const result = await runGuards({ rootDir: ROOT_DIR });
    expect(result.violations).toEqual([]);
    expect(result.passed).toBe(true);
    expect(result.checkedAssets).toBeGreaterThanOrEqual(4);
  });

  it('exports all 4 pilot assets with expected dimensions, anchors, and emissive masks', async () => {
    const styles = await discoverStylePacks(ROOT_DIR);
    const style = styles.get('homelab-16bit');
    expect(style).toBeDefined();

    const discovered = (await discoverAssets(ROOT_DIR)).filter((d) =>
      d.filePath.includes(`${path.sep}homelab${path.sep}`),
    );
    const byId = new Map(discovered.map((d) => [d.asset.id, d.asset]));

    expect([...byId.keys()].sort()).toEqual([
      'ai_cluster_node',
      'bedroom_desk_iso',
      'old_laptop',
      'used_gpu_rig',
    ]);

    if (!style) return;

    const cluster = byId.get('ai_cluster_node');
    expect(cluster).toBeDefined();
    if (cluster) {
      const bundle = exportAssetBundle(cluster, style, { emissive: true });
      expect(bundle.manifest.width).toBe(64);
      expect(bundle.manifest.height).toBe(48);
      expect(bundle.manifest.frames).toBe(2);
      expect(Object.keys(bundle.manifest.files.emissive ?? {})).toHaveLength(3);
    }

    const room = byId.get('bedroom_desk_iso');
    expect(room).toBeDefined();
    if (room) {
      const bundle = exportAssetBundle(room, style);
      expect(bundle.manifest.width).toBe(320);
      expect(bundle.manifest.height).toBe(200);
      expect(bundle.manifest.states).toEqual(['day', 'night']);
      const anchorNames = bundle.manifest.anchors.map((a) => a.name);
      expect(anchorNames).toEqual(['hardware_0', 'hardware_1', 'hardware_2', 'breaker']);
    }
  });
});
