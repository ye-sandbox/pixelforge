"""Unit tests for deterministic scene composition, anchor/bounds validation, and sheets."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pixelforge import Asset, AssetSpec, PaletteColor, StylePack
from pixelforge.export.bundle import LoadedAsset
from pixelforge.export.scene import (
    SceneCompositionError,
    SceneCompositionSpec,
    SceneMountSpec,
    compose_scene,
    generate_scene_sheet,
)
from pixelforge.guard.runner import load_asset_module, load_style_module


def _test_style(style_id: str = "test-style") -> StylePack:
    return StylePack(
        id=style_id,
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="INK", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="WALL", hex="#30363d", flags=("surface",)),
            PaletteColor(index=2, name="ACCENT", hex="#38bdf8", flags=("emissive",)),
            PaletteColor(index=3, name="WARN", hex="#f85149", flags=("accent",)),
        ),
    )


def _parent_asset(style_id: str = "test-style") -> LoadedAsset:
    spec = AssetSpec(
        id="room",
        style_id=style_id,
        width=64,
        height=48,
        perspective="iso-2:1",
        states=("day", "night"),
    )

    def render(a: Asset) -> None:
        a.rect(4, 4, 56, 40, a.pal.WALL)
        a.anchor("slot_a", 20, 30)
        a.anchor("slot_b", 22, 30)
        a.anchor("edge", 2, 10)

    return LoadedAsset(SPEC=spec, render=render)


def _prop_asset(
    prop_id: str,
    *,
    palette_key: str = "ACCENT",
    style_id: str = "test-style",
    width: int = 12,
    height: int = 10,
) -> LoadedAsset:
    spec = AssetSpec(
        id=prop_id,
        style_id=style_id,
        width=width,
        height=height,
        perspective="front-2.5d",
        states=("day",),
    )

    def render(a: Asset) -> None:
        color = int(a.pal[palette_key])
        a.rect(1, 1, width - 2, height - 2, color)
        a.anchor("foot", width // 2, height - 2)

    return LoadedAsset(SPEC=spec, render=render)


def test_compose_scene_mounts_props_deterministically() -> None:
    style = _test_style()
    parent = _parent_asset()
    prop_a = _prop_asset("prop_a", palette_key="ACCENT")
    spec = SceneCompositionSpec(
        parent_id="room",
        parent_state="night",
        mounts=(SceneMountSpec(prop_id="prop_a", anchor="slot_a", prop_anchor="foot"),),
    )

    first = compose_scene(parent, {"prop_a": prop_a}, style, spec)
    second = compose_scene(parent, {"prop_a": prop_a}, style, spec)

    assert np.array_equal(first.surface.data, second.surface.data)
    assert first.parent_state == "night"
    assert len(first.placements) == 1
    p0 = first.placements[0]
    assert p0.dest_x == 20 - 6
    assert p0.dest_y == 30 - 8
    assert p0.in_bounds is True
    assert p0.clipped_pixels == 0
    assert p0.occluded_pixels == 0
    assert first.surface.get(20, 29) == 2


def test_compose_scene_rejects_missing_anchors_and_style_mismatch() -> None:
    style = _test_style()
    parent = _parent_asset()
    prop_a = _prop_asset("prop_a")

    missing_parent_anchor = SceneCompositionSpec(
        parent_id="room",
        mounts=(SceneMountSpec(prop_id="prop_a", anchor="missing"),),
    )
    with pytest.raises(SceneCompositionError, match="Anchor 'missing' not found on asset 'room'"):
        compose_scene(parent, {"prop_a": prop_a}, style, missing_parent_anchor)

    missing_prop_anchor = SceneCompositionSpec(
        parent_id="room",
        mounts=(SceneMountSpec(prop_id="prop_a", anchor="slot_a", prop_anchor="nope"),),
    )
    with pytest.raises(SceneCompositionError, match="Anchor 'nope' not found on asset 'prop_a'"):
        compose_scene(parent, {"prop_a": prop_a}, style, missing_prop_anchor)

    wrong_style_prop = _prop_asset("prop_b", style_id="other-style")
    with pytest.raises(SceneCompositionError, match="cannot compose onto"):
        compose_scene(
            parent,
            {"prop_b": wrong_style_prop},
            style,
            SceneCompositionSpec(
                parent_id="room",
                mounts=(SceneMountSpec(prop_id="prop_b", anchor="slot_a"),),
            ),
        )


def test_compose_scene_detects_bounds_clipping_and_occlusion() -> None:
    style = _test_style()
    parent = _parent_asset()
    prop_a = _prop_asset("prop_a", palette_key="ACCENT")
    prop_b = _prop_asset("prop_b", palette_key="WARN")

    oob_spec = SceneCompositionSpec(
        parent_id="room",
        mounts=(SceneMountSpec(prop_id="prop_a", anchor="edge"),),
    )
    oob_res = compose_scene(parent, {"prop_a": prop_a}, style, oob_spec, strict_bounds=False)
    assert oob_res.placements[0].in_bounds is False
    assert oob_res.placements[0].clipped_pixels > 0
    assert any("exceeds canvas" in w for w in oob_res.warnings)

    with pytest.raises(SceneCompositionError, match="exceeds canvas"):
        compose_scene(parent, {"prop_a": prop_a}, style, oob_spec, strict_bounds=True)

    occ_spec = SceneCompositionSpec(
        parent_id="room",
        mounts=(
            SceneMountSpec(prop_id="prop_b", anchor="slot_b", prop_anchor="foot", z_index=10),
            SceneMountSpec(prop_id="prop_a", anchor="slot_a", prop_anchor="foot", z_index=1),
        ),
    )
    occ_res = compose_scene(
        parent,
        {"prop_a": prop_a, "prop_b": prop_b},
        style,
        occ_spec,
    )
    assert [p.prop_id for p in occ_res.placements] == ["prop_a", "prop_b"]
    assert occ_res.placements[0].occluded_by == ("prop_b@slot_b",)
    assert occ_res.placements[0].occluded_pixels > 0
    assert occ_res.placements[1].occluded_pixels == 0


def test_compose_homelab_bedroom_desk_iso_and_sheet() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    style = load_style_module(repo_root / "styles" / "homelab_16bit.style.py")
    parent = load_asset_module(repo_root / "assets" / "homelab" / "bedroom_desk_iso.asset.py")
    laptop = load_asset_module(repo_root / "assets" / "homelab" / "old_laptop.asset.py")
    gpu_rig = load_asset_module(repo_root / "assets" / "homelab" / "used_gpu_rig.asset.py")
    ai_node = load_asset_module(repo_root / "assets" / "homelab" / "ai_cluster_node.asset.py")

    spec = SceneCompositionSpec(
        parent_id="bedroom_desk_iso",
        parent_state="night",
        mounts=(
            SceneMountSpec(prop_id="old_laptop", anchor="hardware_0", prop_anchor="foot"),
            SceneMountSpec(prop_id="used_gpu_rig", anchor="hardware_1"),
            SceneMountSpec(prop_id="ai_cluster_node", anchor="hardware_2"),
        ),
    )
    res = compose_scene(
        parent,
        {
            "old_laptop": laptop,
            "used_gpu_rig": gpu_rig,
            "ai_cluster_node": ai_node,
        },
        style,
        spec,
        strict_bounds=True,
    )
    assert all(p.in_bounds for p in res.placements)

    sheet = generate_scene_sheet(res, style)
    assert sheet.width > 320
    assert sheet.height > 200
    with Image.open(io.BytesIO(sheet.png)) as img:
        assert img.size == (sheet.width, sheet.height)
