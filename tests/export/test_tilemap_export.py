"""Tests for `TilemapSpec` validation and Godot/Tiled/Phaser/Svelte/TS exports."""

from __future__ import annotations

import json
from typing import cast

import pytest
from pydantic import ValidationError

from pixelforge.core import (
    BLOB47_MASKS,
    CARDINAL16_MASKS,
    Asset,
    AssetSpec,
    AutotileStyle,
    PaletteColor,
    StylePack,
    TilemapSpec,
    autotile_cables,
)
from pixelforge.export import (
    ExportBundleOptions,
    LoadedAsset,
    build_aseprite_atlas,
    build_godot_tileset,
    build_manifest_document,
    build_phaser_tilemap_atlas,
    build_tiled_tileset,
    export_asset_bundle,
    generate_indexed_manifest_ts,
    generate_svelte_manifest_dts,
)


def _style() -> StylePack:
    return StylePack(
        id="tile-export-test",
        perspective="top-down",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="INK", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="FILL", hex="#2a3444", flags=("surface",)),
            PaletteColor(index=2, name="HIGH", hex="#4d5d73", flags=("bright",)),
            PaletteColor(index=3, name="SHAD", hex="#18202c", flags=("shadow",)),
        ),
    )


def test_tilemap_spec_validation() -> None:
    with pytest.raises(ValidationError, match="exceed grid capacity"):
        TilemapSpec(
            mode="cardinal16",
            tile_width=16,
            tile_height=16,
            columns=2,
            rows=2,
            bitmasks=CARDINAL16_MASKS,
        )

    with pytest.raises(ValidationError, match="out of range"):
        TilemapSpec(
            mode="cardinal16",
            tile_width=16,
            tile_height=16,
            columns=2,
            rows=2,
            bitmasks=(0, 16),
        )

    with pytest.raises(ValidationError, match="duplicate bitmask"):
        TilemapSpec(
            mode="blob47",
            tile_width=16,
            tile_height=16,
            columns=2,
            rows=2,
            bitmasks=(0, 1, 1),
        )

    with pytest.raises(ValidationError, match="exceed canvas"):
        AssetSpec(
            id="too_small",
            style_id="tile-export-test",
            width=32,
            height=32,
            perspective="top-down",
            tilemap=TilemapSpec(
                mode="cardinal16",
                tile_width=16,
                tile_height=16,
                columns=4,
                rows=4,
                bitmasks=CARDINAL16_MASKS,
            ),
        )


def test_tilemap_exports_tiled_godot_phaser_svelte_indexed_ts_and_aseprite() -> None:
    style = _style()
    spec = AssetSpec(
        id="cable_tiles",
        style_id="tile-export-test",
        width=64,
        height=64,
        perspective="top-down",
        tilemap=TilemapSpec(
            mode="cardinal16",
            tile_width=16,
            tile_height=16,
            columns=4,
            rows=4,
            bitmasks=CARDINAL16_MASKS,
            terrain_name="cable",
        ),
    )

    def render_tiles(a: Asset[object]) -> None:
        autotile_cables(
            a,
            AutotileStyle(fill=1, edge=0, highlight=2, shadow=3),
            tile_w=16,
            tile_h=16,
            mode="cardinal16",
            columns=4,
        )

    bundle = export_asset_bundle(
        LoadedAsset(SPEC=spec, render=render_tiles),
        style,
        ExportBundleOptions(emissive=False, atlas="all"),
    )

    assert "cable_tiles.tiled.json" in bundle.files
    assert "cable_tiles.godot.json" in bundle.files
    assert "cable_tiles.phaser.json" in bundle.files

    tiled = json.loads(bundle.files["cable_tiles.tiled.json"].decode("utf-8"))
    assert tiled["type"] == "tileset"
    assert tiled["tilecount"] == 16
    assert tiled["columns"] == 4
    assert tiled["wangsets"][0]["name"] == "cable"
    assert len(tiled["wangsets"][0]["wangtiles"]) == 16
    assert any(p["name"] == "y_sort_pivot_y" for p in tiled["properties"])
    assert any(p["name"] == "walkable" for p in tiled["tiles"][0]["properties"])

    godot = json.loads(bundle.files["cable_tiles.godot.json"].decode("utf-8"))
    assert godot["format"] == "godot-tileset-v1"
    assert godot["terrain_set_mode"] == "match_sides"
    assert "physics_layers" in godot
    assert "y_sort_origin" in godot
    assert "walkable" in godot["tiles"][0]
    assert godot["tiles"][15]["atlas_coords"] == [3, 3]
    assert godot["tiles"][15]["peering_bits"] == {
        "top": 1,
        "right": 1,
        "bottom": 1,
        "left": 1,
    }

    phaser = json.loads(bundle.files["cable_tiles.phaser.json"].decode("utf-8"))
    assert phaser["format"] == "phaser-tileset-v1"
    assert phaser["tileCount"] == 16
    assert phaser["bitmaskToTileIndex"]["15"] == 15
    assert phaser["tiles"][5]["x"] == 16
    assert phaser["tiles"][5]["y"] == 16

    doc = build_manifest_document({"cable_tiles": bundle.manifest})
    entry_doc = cast(dict[str, object], doc["cable_tiles"])
    assert "tilemap" in entry_doc

    dts = generate_svelte_manifest_dts([bundle.manifest])
    assert "export interface PixelForgeTilemap {" in dts
    assert "readonly tilemap: PixelForgeTilemap;" in dts

    indexed_ts = generate_indexed_manifest_ts([bundle])
    assert '"tilemap": {' in indexed_ts

    aseprite = build_aseprite_atlas(spec, bundle.rendered_frames)
    meta = cast(dict[str, object], aseprite["meta"])
    slices = cast(list[dict[str, object]], meta["slices"])
    assert any(s["name"] == "tile:0:0" for s in slices)
    assert any(s["name"] == "tile:15:15" for s in slices)


def test_blob47_tilemap_builders() -> None:
    spec = AssetSpec(
        id="wall_blob",
        style_id="tile-export-test",
        width=128,
        height=96,
        perspective="top-down",
        tilemap=TilemapSpec(
            mode="blob47",
            tile_width=16,
            tile_height=16,
            columns=8,
            rows=6,
            bitmasks=BLOB47_MASKS,
            terrain_name="wall",
        ),
    )
    godot = build_godot_tileset(spec, scale=2)
    assert godot["terrain_set_mode"] == "match_corners_and_sides"
    assert godot["texture_region_size"] == {"x": 32, "y": 32}

    tiled = build_tiled_tileset(spec)
    assert tiled["tilecount"] == 47
    wangsets = cast(list[dict[str, object]], tiled["wangsets"])
    assert wangsets[0]["type"] == "mixed"

    phaser = build_phaser_tilemap_atlas(spec)
    assert phaser["tileCount"] == 47
    bitmask_map = cast(dict[str, int], phaser["bitmaskToTileIndex"])
    assert bitmask_map["255"] == 46
