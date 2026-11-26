"""Tests for `--indexed-ts` RLE/base64 Uint8Array and palette TS exporter."""

from __future__ import annotations

import base64
import re
from pathlib import Path

import numpy as np
import pytest

from pixelforge.core.builder import Asset
from pixelforge.core.types import TRANSPARENT_INDEX, AssetSpec, PaletteColor, StylePack
from pixelforge.export.bundle import LoadedAsset, export_asset_bundle
from pixelforge.export.indexed_ts import (
    decode_rle_bytes,
    encode_rle_bytes,
    export_indexed_ts,
    write_indexed_ts_bundle,
)


def _style() -> StylePack:
    return StylePack(
        id="homelab-16bit",
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


def test_rle_roundtrip_long_runs_and_mixed_pixels() -> None:
    arr = np.full((20, 30), TRANSPARENT_INDEX, dtype=np.uint8)  # 600 pixels > 256 max run
    arr[5, 10:15] = 4
    arr[6, ::2] = 1

    encoded = encode_rle_bytes(arr)
    decoded = decode_rle_bytes(encoded, arr.size)
    assert np.array_equal(decoded, arr.ravel())


def test_export_indexed_ts_emits_palette_sprites_and_manifest(tmp_path: Path) -> None:
    style = _style()
    spec = AssetSpec(
        id="rack_node",
        style_id="homelab-16bit",
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
    result = export_indexed_ts([bundle], style)

    # Verify palette.generated.ts
    assert "export const TRANSPARENT_INDEX = 255 as const;" in result.palette_ts
    assert "new Set<number>([4])" in result.palette_ts
    assert "new Set<number>([3, 4])" in result.palette_ts
    assert "{3: 2, 4: 4}" in result.palette_ts

    # Verify sprites.generated.ts contains valid RLE-base64 matching rendered framebuffers
    matches = re.findall(r'decodeRleSprite\("([A-Za-z0-9+/=]+)", 8, 8\)', result.sprites_ts)
    assert len(matches) == 4
    for rendered, b64_payload in zip(bundle.rendered_frames, matches, strict=True):
        decoded = decode_rle_bytes(base64.b64decode(b64_payload), 64).reshape((8, 8))
        assert np.array_equal(decoded, rendered.surface.data)

    # Verify manifest.generated.ts
    assert '"rack_node"' in result.manifest_ts
    assert "export const INDEXED_MANIFEST" in result.manifest_ts
    assert '"kind": null' not in result.manifest_ts
    assert '"dir": null' not in result.manifest_ts

    paths = write_indexed_ts_bundle(result, tmp_path / "indexed")
    assert all(p.exists() for p in paths)


def test_export_indexed_ts_rejects_mismatched_style() -> None:
    style = _style()
    other_style = style.model_copy(update={"id": "other-style"})
    spec = AssetSpec(
        id="box",
        style_id="other-style",
        width=4,
        height=4,
        perspective="side",
    )
    bundle = export_asset_bundle(
        LoadedAsset(SPEC=spec, render=lambda a: a.rect(0, 0, 2, 2, a.pal.CHASSIS)),
        other_style,
    )
    with pytest.raises(ValueError, match="expected 'homelab-16bit'"):
        export_indexed_ts([bundle], style)


def test_export_indexed_ts_lazy_defers_rle_decoding() -> None:
    style = _style()
    spec = AssetSpec(
        id="rack_node",
        style_id="homelab-16bit",
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

    bundle = export_asset_bundle(LoadedAsset(SPEC=spec, render=render), style)
    result = export_indexed_ts([bundle], style, lazy=True)

    assert "function createLazySpriteFrame(" in result.sprites_ts
    assert "get data(): Uint8Array {" in result.sprites_ts
    assert "if (cached === undefined) {" in result.sprites_ts
    assert "export function getIndexedSpriteFrame<" in result.sprites_ts

    lazy_calls = re.findall(
        r'createLazySpriteFrame\("([A-Za-z0-9+/=]+)", 8, 8\)',
        result.sprites_ts,
    )
    assert len(lazy_calls) == 4
    # Eager decodeRleSprite calls must not appear inside INDEXED_SPRITES entries
    sprites_body = result.sprites_ts.split("export const INDEXED_SPRITES = {", 1)[1]
    assert "decodeRleSprite(" not in sprites_body
    for rendered, b64_payload in zip(bundle.rendered_frames, lazy_calls, strict=True):
        decoded = decode_rle_bytes(base64.b64decode(b64_payload), 64).reshape((8, 8))
        assert np.array_equal(decoded, rendered.surface.data)
