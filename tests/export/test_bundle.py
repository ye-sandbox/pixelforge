"""Tests for asset bundle orchestration and manifest writing."""

from __future__ import annotations

import json
from pathlib import Path

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack
from pixelforge.export.bundle import (
    ExportBundleOptions,
    LoadedAsset,
    export_asset_bundle,
    write_export_bundle,
)
from pixelforge.export.png import decode_png_to_rgba


def _make_style() -> StylePack:
    return StylePack(
        id="homelab-test",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#101218", flags=("outline",)),
            PaletteColor(index=1, name="CHASSIS", hex="#3b4252", flags=("surface",)),
            PaletteColor(index=2, name="LED_GREEN", hex="#3fb950", flags=("emissive", "bright")),
            PaletteColor(index=3, name="LED_RED", hex="#f85149", flags=("emissive",)),
        ),
        variants={"warm": {"CHASSIS": "#504945"}},
    )


def _make_animated_asset() -> LoadedAsset:
    spec = AssetSpec(
        id="mini_server",
        style_id="homelab-test",
        width=8,
        height=6,
        perspective="iso-2:1",
        states=("healthy", "faulty"),
        frames=2,
        fps=2,
        seed=42,
    )

    def render(a: Asset) -> None:
        p = a.pal
        a.rect(1, 1, 6, 4, p.CHASSIS)
        led_color = p.LED_GREEN if a.state == "healthy" else p.LED_RED
        if a.frame == 0:
            a.put(2, 2, led_color)
            a.anchor("led", 2, 2)
        else:
            a.put(4, 2, led_color)
            a.anchor("led", 4, 2)
        a.hitbox("body", 1, 1, 6, 4)

    return LoadedAsset(SPEC=spec, render=render)


def test_export_asset_bundle_outputs_sheets_emissive_lut_and_previews() -> None:
    style = _make_style()
    asset = _make_animated_asset()
    opts = ExportBundleOptions(emissive=True, lut=True, animate=True, animate_format="gif")
    bundle = export_asset_bundle(asset, style, opts)

    assert "mini_server_healthy.png" in bundle.files
    assert "mini_server_faulty.png" in bundle.files
    assert "mini_server_sheet.png" in bundle.files
    assert "mini_server_healthy_emissive.png" in bundle.files
    assert "mini_server_faulty_emissive.png" in bundle.files
    assert "mini_server_sheet_emissive.png" in bundle.files
    assert "mini_server_healthy_idx.png" in bundle.files
    assert "homelab-test_lut.png" in bundle.files
    assert "mini_server_healthy.gif" in bundle.preview_files
    assert "mini_server_faulty.gif" in bundle.preview_files

    sheet = decode_png_to_rgba(bundle.files["mini_server_sheet.png"])
    assert sheet.shape == (12, 16, 4)
    # Row 0 (healthy): frame 0 LED at (2, 2), frame 1 LED at (8 + 4, 2)
    assert tuple(sheet[2, 2].tolist()) == (0x3F, 0xB9, 0x50, 255)
    assert tuple(sheet[2, 12].tolist()) == (0x3F, 0xB9, 0x50, 255)
    # Row 1 (faulty): frame 1 LED at (8 + 4, 6 + 2)
    assert tuple(sheet[8, 12].tolist()) == (0xF8, 0x51, 0x49, 255)

    sheet_em = decode_png_to_rgba(bundle.files["mini_server_sheet_emissive.png"])
    assert tuple(sheet_em[1, 1].tolist()) == (0, 0, 0, 0)
    assert tuple(sheet_em[2, 2].tolist()) == (0x3F, 0xB9, 0x50, 255)

    # Varying anchor coordinates across frames preserve per-frame metadata
    assert bundle.manifest.frameMetadata is not None
    assert bundle.manifest.frameMetadata["healthy"][0].anchors[0].x == 2
    assert bundle.manifest.frameMetadata["healthy"][1].anchors[0].x == 4

    # Deterministic digest
    bundle_repeat = export_asset_bundle(asset, style, opts)
    assert bundle.manifest.sha256 == bundle_repeat.manifest.sha256
    assert bundle.files == bundle_repeat.files


def test_uniform_metadata_omits_frame_metadata_and_writes_disk(tmp_path: Path) -> None:
    style = _make_style()
    spec = AssetSpec(
        id="static_box",
        style_id="homelab-test",
        width=6,
        height=6,
        perspective="front-2.5d",
        states=("default",),
        frames=1,
    )

    def render(a: Asset) -> None:
        a.rect(0, 0, 6, 6, a.pal.CHASSIS)
        a.anchor("center", 3, 3)

    bundle = export_asset_bundle(LoadedAsset(SPEC=spec, render=render), style)
    assert bundle.manifest.frameMetadata is None
    assert bundle.manifest.files.sheet is None

    out_dir = tmp_path / "dist"
    previews_dir = tmp_path / ".pixelforge" / "previews"
    manifest_path = write_export_bundle(bundle, out_dir, previews_dir=previews_dir)

    assert manifest_path.exists()
    assert (out_dir / "manifest.d.ts").exists()
    assert (out_dir / "sprites" / "static_box_default.png").exists()

    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "static_box" in parsed
    assert "frameMetadata" not in parsed["static_box"]
