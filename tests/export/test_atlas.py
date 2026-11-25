"""Hermetic unit tests for Aseprite JSON and TexturePacker atlas export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack
from pixelforge.export.atlas import (
    build_aseprite_atlas,
    build_texturepacker_atlas,
    resolve_atlas_image_name,
)
from pixelforge.export.bundle import (
    ExportBundleOptions,
    LoadedAsset,
    export_asset_bundle,
    render_asset_frames,
    write_export_bundle,
)


def _make_style() -> StylePack:
    return StylePack(
        id="atlas-test",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#101218", flags=("outline",)),
            PaletteColor(index=1, name="BODY", hex="#3b4252", flags=("surface",)),
            PaletteColor(index=2, name="LED", hex="#3fb950", flags=("emissive",)),
        ),
    )


def _make_animated_asset() -> LoadedAsset:
    spec = AssetSpec(
        id="rack_unit",
        style_id="atlas-test",
        width=8,
        height=6,
        perspective="iso-2:1",
        states=("healthy", "faulty"),
        frames=3,
        fps=5,
        seed=7,
    )

    def render(a: Asset) -> None:
        a.rect(1, 1, 6, 4, a.pal.BODY)
        a.put(2 + a.frame, 2, a.pal.LED)
        a.anchor("pivot", 4, 3)
        a.anchor("led", 2 + a.frame, 2)
        a.hitbox("body", 1, 1, 6, 4)

    return LoadedAsset(SPEC=spec, render=render)


def test_aseprite_atlas_frames_tags_slices_and_scale() -> None:
    style = _make_style()
    asset = _make_animated_asset()
    rendered = render_asset_frames(asset, style)

    doc = cast(dict[str, Any], build_aseprite_atlas(asset.SPEC, rendered, scale=2))
    meta = doc["meta"]
    frames = doc["frames"]

    assert meta["image"] == "rack_unit_sheet.png"
    assert meta["format"] == "RGBA8888"
    assert meta["size"] == {"w": 48, "h": 24}
    assert meta["scale"] == "2"

    # 2 states * 3 frames = 6 frames with exact scaled rectangles
    assert len(frames) == 6
    assert frames["rack_unit_healthy_0"]["frame"] == {"x": 0, "y": 0, "w": 16, "h": 12}
    assert frames["rack_unit_healthy_2"]["frame"] == {"x": 32, "y": 0, "w": 16, "h": 12}
    assert frames["rack_unit_faulty_1"]["frame"] == {"x": 16, "y": 12, "w": 16, "h": 12}
    assert frames["rack_unit_faulty_1"]["duration"] == 200
    assert frames["rack_unit_faulty_1"]["rotated"] is False
    assert frames["rack_unit_faulty_1"]["trimmed"] is False

    assert meta["frameTags"] == [
        {"name": "healthy", "from": 0, "to": 2, "direction": "forward"},
        {"name": "faulty", "from": 3, "to": 5, "direction": "forward"},
    ]

    slices = {entry["name"]: entry for entry in meta["slices"]}
    assert set(slices.keys()) == {"anchor:led", "anchor:pivot", "hitbox:body"}
    assert slices["anchor:led"]["keys"][1] == {
        "frame": 1,
        "bounds": {"x": 6, "y": 4, "w": 2, "h": 2},
    }
    assert slices["hitbox:body"]["keys"][0] == {
        "frame": 0,
        "bounds": {"x": 2, "y": 2, "w": 12, "h": 8},
    }


def test_texturepacker_atlas_frames_animations_and_pivot() -> None:
    style = _make_style()
    asset = _make_animated_asset()
    rendered = render_asset_frames(asset, style)

    doc = cast(dict[str, Any], build_texturepacker_atlas(asset.SPEC, rendered, scale=1))
    assert doc["meta"]["image"] == "rack_unit_sheet.png"
    assert doc["meta"]["size"] == {"w": 24, "h": 12}
    assert doc["animations"] == {
        "healthy": ["rack_unit/healthy/0", "rack_unit/healthy/1", "rack_unit/healthy/2"],
        "faulty": ["rack_unit/faulty/0", "rack_unit/faulty/1", "rack_unit/faulty/2"],
    }
    frame_entry = doc["frames"]["rack_unit/faulty/2"]
    assert frame_entry["frame"] == {"x": 16, "y": 6, "w": 8, "h": 6}
    assert frame_entry["pivot"] == {"x": 0.5, "y": 0.5}


def test_single_state_single_frame_atlas_references_state_png() -> None:
    style = _make_style()
    spec = AssetSpec(
        id="crate",
        style_id="atlas-test",
        width=6,
        height=6,
        perspective="front-2.5d",
        states=("idle",),
        frames=1,
    )

    def render(a: Asset) -> None:
        a.rect(0, 0, 6, 6, a.pal.BODY)

    asset = LoadedAsset(SPEC=spec, render=render)
    assert resolve_atlas_image_name(spec) == "crate_idle.png"

    bundle = export_asset_bundle(asset, style, ExportBundleOptions(atlas="all"))
    assert "crate.aseprite.json" in bundle.files
    assert "crate.texturepacker.json" in bundle.files
    assert "crate_sheet.png" not in bundle.files

    aseprite = json.loads(bundle.files["crate.aseprite.json"].decode("utf-8"))
    assert aseprite["meta"]["image"] == "crate_idle.png"
    assert aseprite["meta"]["size"] == {"w": 6, "h": 6}


def test_multistate_single_frame_atlas_emits_sheet_without_altering_manifest(
    tmp_path: Path,
) -> None:
    style = _make_style()
    spec = AssetSpec(
        id="lamp",
        style_id="atlas-test",
        width=4,
        height=4,
        perspective="front-2.5d",
        states=("off", "on"),
        frames=1,
    )

    def render(a: Asset) -> None:
        a.rect(0, 0, 4, 4, a.pal.BODY if a.state == "off" else a.pal.LED)

    asset = LoadedAsset(SPEC=spec, render=render)
    baseline = export_asset_bundle(asset, style, ExportBundleOptions())
    with_atlas = export_asset_bundle(asset, style, ExportBundleOptions(atlas="all"))

    # Existing manifest.json contract and sha256 remain identical
    assert with_atlas.manifest == baseline.manifest
    assert "lamp_sheet.png" in with_atlas.files
    assert "lamp.aseprite.json" in with_atlas.files
    assert "lamp.texturepacker.json" in with_atlas.files

    write_export_bundle(with_atlas, tmp_path)
    assert (tmp_path / "sprites" / "lamp_sheet.png").is_file()
    assert (tmp_path / "sprites" / "lamp.aseprite.json").is_file()
    assert (tmp_path / "sprites" / "lamp.texturepacker.json").is_file()


def test_atlas_rejects_invalid_scale() -> None:
    style = _make_style()
    asset = _make_animated_asset()
    rendered = render_asset_frames(asset, style)

    with pytest.raises(ValueError, match="scale must be >= 1"):
        build_aseprite_atlas(asset.SPEC, rendered, scale=0)
    with pytest.raises(ValueError, match="scale must be >= 1"):
        build_texturepacker_atlas(asset.SPEC, rendered, scale=0)
