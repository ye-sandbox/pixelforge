"""Strict `tsc --noEmit` validation for generated TypeScript outputs."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack
from pixelforge.export.bundle import ExportBundleOptions, LoadedAsset, export_asset_bundle
from pixelforge.export.indexed_ts import export_indexed_ts, write_indexed_ts_bundle
from pixelforge.export.svelte_types import generate_svelte_manifest_dts

_TSC_BIN = shutil.which("tsc")
_TSC_FLAGS = (
    "--noEmit",
    "--strict",
    "--noUncheckedIndexedAccess",
    "--noUnusedLocals",
    "--noUnusedParameters",
    "--isolatedModules",
    "--target",
    "ES2022",
    "--module",
    "ESNext",
    "--moduleResolution",
    "bundler",
)


def _style() -> StylePack:
    return StylePack(
        id="ts-check",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="VOID", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="FLOOR", hex="#1f242c", flags=("surface",)),
            PaletteColor(index=2, name="FLOOR_REFL", hex="#161b22", flags=("shadow",)),
            PaletteColor(index=3, name="CHASSIS", hex="#586069", flags=("bright",)),
            PaletteColor(index=4, name="CYAN_GLOW", hex="#39c5cf", flags=("emissive", "bright")),
        ),
        reflections={
            "CHASSIS": "FLOOR_REFL",
            "CYAN_GLOW": "CYAN_GLOW",
        },
    )


def _run_tsc(files: list[Path], cwd: Path) -> None:
    assert _TSC_BIN is not None
    proc = subprocess.run(
        [_TSC_BIN, *_TSC_FLAGS, *(str(f) for f in files)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"tsc failed:\n{proc.stdout}\n{proc.stderr}"


@pytest.mark.skipif(_TSC_BIN is None, reason="tsc binary not installed on PATH")
def test_manifest_dts_typechecks_under_strict_tsc(tmp_path: Path) -> None:
    style = _style()
    spec = AssetSpec(
        id="thinkpad_r51_iso",
        style_id="ts-check",
        width=16,
        height=16,
        perspective="iso-2:1",
        states=("healthy", "faulty"),
        frames=2,
        fps=4,
    )

    def render(a: Asset) -> None:
        a.rect(2, 2, 10, 10, a.pal.CHASSIS)
        a.put(4, 4, a.pal.CYAN_GLOW)
        a.anchor("screen", 7 + a.frame, 6)
        a.hitbox("chassis", 2, 2, 10, 10)

    bundle = export_asset_bundle(
        LoadedAsset(SPEC=spec, render=render),
        style,
        ExportBundleOptions(emissive=True, lut=True),
    )
    dts_path = tmp_path / "manifest.d.ts"
    dts_path.write_text(generate_svelte_manifest_dts([bundle.manifest]), encoding="utf-8")

    consumer = tmp_path / "consumer.ts"
    consumer.write_text(
        "\n".join(
            [
                "import type {",
                "  PixelForgeAssetAnchor,",
                "  PixelForgeAssetHitbox,",
                "  PixelForgeAssetId,",
                "  PixelForgeAssetState,",
                "  PixelForgeManifest,",
                "  PixelForgeManifestEntry,",
                '} from "./manifest";',
                "",
                'const id: PixelForgeAssetId = "thinkpad_r51_iso";',
                'const state: PixelForgeAssetState<"thinkpad_r51_iso"> = "healthy";',
                'const anchor: PixelForgeAssetAnchor<"thinkpad_r51_iso"> = "screen";',
                'const hitbox: PixelForgeAssetHitbox<"thinkpad_r51_iso"> = "chassis";',
                "",
                "export function inspectManifest(",
                "  manifest: PixelForgeManifest,",
                '): PixelForgeManifestEntry<"thinkpad_r51_iso"> {',
                "  const entry = manifest[id];",
                "  void state;",
                "  void anchor;",
                "  void hitbox;",
                "  return entry;",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _run_tsc([dts_path, consumer], cwd=tmp_path)


@pytest.mark.skipif(_TSC_BIN is None, reason="tsc binary not installed on PATH")
def test_manifest_dts_empty_entries_typechecks_under_strict_tsc(tmp_path: Path) -> None:
    dts_path = tmp_path / "manifest.d.ts"
    dts_path.write_text(generate_svelte_manifest_dts([]), encoding="utf-8")
    _run_tsc([dts_path], cwd=tmp_path)


@pytest.mark.skipif(_TSC_BIN is None, reason="tsc binary not installed on PATH")
@pytest.mark.parametrize("lazy", [False, True])
def test_indexed_ts_typechecks_under_strict_tsc(tmp_path: Path, lazy: bool) -> None:
    style = _style()
    spec = AssetSpec(
        id="rack_node",
        style_id="ts-check",
        width=8,
        height=8,
        perspective="iso-2:1",
        states=("idle", "active"),
        frames=2,
        fps=4,
    )

    def render(a: Asset) -> None:
        a.rect(1, 1, 6, 6, a.pal.CHASSIS)
        if a.state == "active" or a.frame == 1:
            a.put(4, 3, a.pal.CYAN_GLOW)
        a.anchor("base", 4, 7)

    bundle = export_asset_bundle(LoadedAsset(SPEC=spec, render=render), style)
    result = export_indexed_ts([bundle], style, lazy=lazy)
    palette_path, sprites_path, manifest_path = write_indexed_ts_bundle(result, tmp_path)

    consumer = tmp_path / "consumer.ts"
    consumer.write_text(
        "\n".join(
            [
                'import { BRIGHT, EMISSIVE, PALETTE_HEX, REFL } from "./palette.generated";',
                'import { getIndexedSpriteFrame, INDEXED_SPRITES } from "./sprites.generated";',
                "import {",
                "  INDEXED_MANIFEST,",
                "  type IndexedAssetManifestEntry,",
                '} from "./manifest.generated";',
                "",
                "export function inspectIndexed(): {",
                "  hex: string | undefined;",
                "  emissive: boolean;",
                "  bright: boolean;",
                "  refl: number | undefined;",
                "  frameLen: number;",
                '  entry: IndexedAssetManifestEntry<"rack_node">;',
                "} {",
                '  const frame = getIndexedSpriteFrame("rack_node", "active", 1);',
                '  void INDEXED_SPRITES["rack_node"].idle;',
                "  return {",
                "    hex: PALETTE_HEX[3],",
                "    emissive: EMISSIVE.has(4),",
                "    bright: BRIGHT.has(3),",
                "    refl: REFL[3],",
                "    frameLen: frame.data.length,",
                '    entry: INDEXED_MANIFEST["rack_node"],',
                "  };",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _run_tsc([palette_path, sprites_path, manifest_path, consumer], cwd=tmp_path)
