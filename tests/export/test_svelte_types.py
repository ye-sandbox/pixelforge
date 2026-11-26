"""Tests for Svelte 5 `manifest.d.ts` TypeScript declaration generation."""

from __future__ import annotations

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack
from pixelforge.export.bundle import ExportBundleOptions, LoadedAsset, export_asset_bundle
from pixelforge.export.svelte_types import generate_svelte_manifest_dts


def _style() -> StylePack:
    return StylePack(
        id="svelte-test",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#101218", flags=("outline",)),
            PaletteColor(index=1, name="BODY", hex="#6b7280", flags=("surface",)),
            PaletteColor(index=2, name="GLOW", hex="#58a6ff", flags=("emissive",)),
        ),
    )


def test_generate_svelte_manifest_dts_contains_strict_unions() -> None:
    style = _style()
    spec = AssetSpec(
        id="thinkpad_r51_iso",
        style_id="svelte-test",
        width=16,
        height=16,
        perspective="iso-2:1",
        states=("healthy", "faulty"),
        frames=2,
        fps=4,
        frame_events={"faulty": {1: ("beep", "spark")}},
    )

    def render(a: Asset) -> None:
        a.rect(2, 2, 10, 10, a.pal.BODY)
        a.anchor("screen", 7 + a.frame, 6)
        a.hitbox("chassis", 2, 2, 10, 10)
        if a.state == "healthy" and a.frame == 0:
            a.event("footstep")

    bundle = export_asset_bundle(
        LoadedAsset(SPEC=spec, render=render),
        style,
        ExportBundleOptions(emissive=True, lut=True),
    )
    dts = generate_svelte_manifest_dts([bundle.manifest])

    assert 'export type PixelForgeAssetId = "thinkpad_r51_iso";' in dts
    assert 'export type ThinkpadR51IsoState = "healthy" | "faulty";' in dts
    assert 'export type ThinkpadR51IsoAnchorName = "screen";' in dts
    assert 'export type ThinkpadR51IsoHitboxName = "chassis";' in dts
    assert 'export type ThinkpadR51IsoEventName = "footstep" | "beep" | "spark";' in dts
    assert "readonly frameMetadata?:" in dts
    assert "readonly events?: readonly TEvent[];" in dts
    assert "PixelForgeAssetEvent<K extends PixelForgeAssetId>" in dts
    assert "readonly semantics: PixelForgeGameplaySemantics;" in dts
    assert "export interface PixelForgeGameplaySemantics {" in dts
    assert "readonly sheet: string;" in dts
    assert "readonly sheetEmissive: string;" in dts
    assert "readonly lut: string;" in dts
    assert "PixelForgeAssetState<K extends PixelForgeAssetId>" in dts
    assert "readonly kind?: string;" in dts
    assert "readonly dir?: readonly [number, number];" in dts
    assert ": any" not in dts


def test_generate_svelte_manifest_dts_handles_empty_entries() -> None:
    dts = generate_svelte_manifest_dts([])
    assert "export type PixelForgeAssetId = never;" in dts
    assert "export interface PixelForgeManifestMap {" in dts
