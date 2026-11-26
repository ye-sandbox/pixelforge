"""Unit tests for deterministic scene composition, anchor/bounds validation, and sheets."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pixelforge import Asset, AssetSpec, PaletteColor, StylePack
from pixelforge.core.types import PerspectiveMode
from pixelforge.export.bundle import ExportBundleOptions, LoadedAsset
from pixelforge.export.indexed_ts import export_indexed_ts
from pixelforge.export.scene import (
    SceneCompositionError,
    SceneCompositionSpec,
    SceneMountSpec,
    SceneSpec,
    compose_scene,
    compose_scene_frames,
    export_scene_bundle,
    generate_scene_sheet,
    resolve_scene_asset_spec,
)
from pixelforge.guard.runner import load_asset_module, load_scene_module, load_style_module


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
    perspective: PerspectiveMode = "iso-2:1",
    width: int = 12,
    height: int = 10,
) -> LoadedAsset:
    spec = AssetSpec(
        id=prop_id,
        style_id=style_id,
        width=width,
        height=height,
        perspective=perspective,
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


def test_compose_scene_warns_and_rejects_perspective_mismatch() -> None:
    style = _test_style()
    parent = _parent_asset()
    front_prop = _prop_asset("front_prop", perspective="front-2.5d")
    iso_prop = _prop_asset("iso_prop", perspective="iso-2:1")

    mismatch_spec = SceneCompositionSpec(
        parent_id="room",
        mounts=(SceneMountSpec(prop_id="front_prop", anchor="slot_a", prop_anchor="foot"),),
    )
    warn_res = compose_scene(
        parent,
        {"front_prop": front_prop},
        style,
        mismatch_spec,
        strict_perspective=False,
    )
    assert warn_res.placements[0].perspective == "front-2.5d"
    assert warn_res.placements[0].perspective_match is False
    assert any("differs from parent" in w for w in warn_res.warnings)

    sheet = generate_scene_sheet(warn_res, style)
    assert sheet.width > 64

    with pytest.raises(SceneCompositionError, match="differs from parent"):
        compose_scene(
            parent,
            {"front_prop": front_prop},
            style,
            mismatch_spec,
            strict_perspective=True,
        )

    match_spec = SceneCompositionSpec(
        parent_id="room",
        mounts=(SceneMountSpec(prop_id="iso_prop", anchor="slot_a", prop_anchor="foot"),),
    )
    ok_res = compose_scene(
        parent,
        {"iso_prop": iso_prop},
        style,
        match_spec,
        strict_perspective=True,
    )
    assert ok_res.placements[0].perspective == "iso-2:1"
    assert ok_res.placements[0].perspective_match is True
    assert ok_res.warnings == ()


def test_compose_homelab_bedroom_desk_iso_and_sheet() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    style = load_style_module(repo_root / "styles" / "homelab_16bit.style.py")
    parent = load_asset_module(repo_root / "assets" / "homelab" / "bedroom_desk_iso.asset.py")
    laptop = load_asset_module(repo_root / "assets" / "homelab" / "old_laptop_iso.asset.py")
    gpu_rig = load_asset_module(repo_root / "assets" / "homelab" / "used_gpu_rig_iso.asset.py")
    ai_node = load_asset_module(repo_root / "assets" / "homelab" / "ai_cluster_node_iso.asset.py")

    spec = SceneCompositionSpec(
        parent_id="bedroom_desk_iso",
        parent_state="night",
        mounts=(
            SceneMountSpec(prop_id="old_laptop_iso", anchor="hardware_0", prop_anchor="foot"),
            SceneMountSpec(prop_id="used_gpu_rig_iso", anchor="hardware_1", prop_anchor="foot"),
            SceneMountSpec(prop_id="ai_cluster_node_iso", anchor="hardware_2", prop_anchor="foot"),
        ),
    )
    res = compose_scene(
        parent,
        {
            "old_laptop_iso": laptop,
            "used_gpu_rig_iso": gpu_rig,
            "ai_cluster_node_iso": ai_node,
        },
        style,
        spec,
        strict_bounds=True,
        strict_perspective=True,
    )
    assert all(p.in_bounds for p in res.placements)
    assert all(p.perspective_match for p in res.placements)
    assert all(p.occluded_pixels == 0 for p in res.placements)
    assert res.warnings == ()

    sheet = generate_scene_sheet(res, style)
    assert sheet.width > 320
    assert sheet.height > 200
    with Image.open(io.BytesIO(sheet.png)) as img:
        assert img.size == (sheet.width, sheet.height)


def test_compose_scene_iso_y_depth_sort_with_z_index() -> None:
    """Verify `iso_y` sorts mounts back-to-front by anchor_y + offset_y, with z_index primary."""
    style = _test_style()

    def render_parent(a: Asset) -> None:
        a.rect(0, 0, 24, 24, a.pal.WALL)
        a.anchor("back_slot", 10, 10)
        a.anchor("front_slot", 10, 12)

    def render_prop_back(a: Asset) -> None:
        a.rect(0, 0, 6, 6, a.pal.ACCENT)
        a.anchor("foot", 3, 5)

    def render_prop_front(a: Asset) -> None:
        a.rect(0, 0, 6, 6, a.pal.WARN)
        a.anchor("foot", 3, 5)

    parent = LoadedAsset(
        SPEC=AssetSpec(
            id="room",
            style_id="test-style",
            perspective="iso-2:1",
            width=24,
            height=24,
        ),
        render=render_parent,
    )
    prop_back = LoadedAsset(
        SPEC=AssetSpec(
            id="prop_back",
            style_id="test-style",
            perspective="iso-2:1",
            width=6,
            height=6,
        ),
        render=render_prop_back,
    )
    prop_front = LoadedAsset(
        SPEC=AssetSpec(
            id="prop_front",
            style_id="test-style",
            perspective="iso-2:1",
            width=6,
            height=6,
        ),
        render=render_prop_front,
    )

    # Declare front_slot BEFORE back_slot; iso_y must still draw front_slot on top.
    iso_spec = SceneCompositionSpec(
        parent_id="room",
        depth_sort="iso_y",
        mounts=(
            SceneMountSpec(prop_id="prop_front", anchor="front_slot", prop_anchor="foot"),
            SceneMountSpec(prop_id="prop_back", anchor="back_slot", prop_anchor="foot"),
        ),
    )
    iso_res = compose_scene(
        parent,
        {"prop_back": prop_back, "prop_front": prop_front},
        style,
        iso_spec,
    )
    assert [p.prop_id for p in iso_res.placements] == ["prop_back", "prop_front"]
    assert iso_res.surface.get(10, 10) == 3  # WARN

    # Explicit z_index overrides iso_y ordering.
    z_override_spec = SceneCompositionSpec(
        parent_id="room",
        depth_sort="iso_y",
        mounts=(
            SceneMountSpec(prop_id="prop_front", anchor="front_slot", prop_anchor="foot"),
            SceneMountSpec(prop_id="prop_back", anchor="back_slot", prop_anchor="foot", z_index=1),
        ),
    )
    z_res = compose_scene(
        parent,
        {"prop_back": prop_back, "prop_front": prop_front},
        style,
        z_override_spec,
    )
    assert [p.prop_id for p in z_res.placements] == ["prop_front", "prop_back"]
    assert z_res.surface.get(10, 10) == 2  # ACCENT


def test_compose_scene_frames_synchronized_lcm_and_state_map() -> None:
    """Verify multi-frame LCM cycle synchronization, state_map, and bundle/indexed-ts export."""
    style = _test_style()

    def render_parent(a: Asset) -> None:
        a.rect(0, 0, 24, 24, a.pal.WALL)
        a.put(0, 0, a.pal.ACCENT if a.frame == 0 else a.pal.WARN)
        a.anchor("slot_a", 8, 12)
        a.anchor("slot_b", 18, 12)

    def render_prop_cycle(a: Asset) -> None:
        tok = (a.pal.ACCENT, a.pal.WARN, a.pal.INK)[a.frame]
        a.rect(0, 0, 4, 4, tok if a.state == "active" else a.pal.WALL)
        a.anchor("foot", 2, 3)

    def render_prop_pinned(a: Asset) -> None:
        a.rect(0, 0, 4, 4, a.pal.INK if a.frame == 1 else a.pal.ACCENT)
        a.anchor("foot", 2, 3)

    parent = LoadedAsset(
        SPEC=AssetSpec(
            id="room",
            style_id="test-style",
            perspective="iso-2:1",
            width=24,
            height=24,
            states=("day", "night"),
            frames=2,
            fps=6,
        ),
        render=render_parent,
    )
    prop_cycle = LoadedAsset(
        SPEC=AssetSpec(
            id="prop_cycle",
            style_id="test-style",
            perspective="iso-2:1",
            width=4,
            height=4,
            states=("idle", "active"),
            frames=3,
            fps=6,
        ),
        render=render_prop_cycle,
    )
    prop_pinned = LoadedAsset(
        SPEC=AssetSpec(
            id="prop_pinned",
            style_id="test-style",
            perspective="iso-2:1",
            width=4,
            height=4,
            states=("day", "night"),
            frames=2,
        ),
        render=render_prop_pinned,
    )

    scene_spec = SceneSpec(
        id="room_scene",
        parent_id="room",
        mounts=(
            SceneMountSpec(
                prop_id="prop_cycle",
                anchor="slot_a",
                prop_anchor="foot",
                state_map={"day": "idle", "night": "active"},
            ),
            SceneMountSpec(
                prop_id="prop_pinned",
                anchor="slot_b",
                prop_anchor="foot",
                frame=1,
            ),
        ),
    )
    props = {"prop_cycle": prop_cycle, "prop_pinned": prop_pinned}
    resolved = resolve_scene_asset_spec(scene_spec, parent, props)
    assert resolved.frames == 6  # lcm(2, 3) ignoring pinned frame=1
    assert resolved.states == ("day", "night")

    _, frames, warnings = compose_scene_frames(scene_spec, parent, props, style)
    assert warnings == ()
    assert len(frames) == 12
    night_frames = [f for f in frames if f.state == "night"]
    # prop_cycle cycles 0, 1, 2, 0, 1, 2 -> ACCENT(2), WARN(3), INK(0)
    assert night_frames[0].surface.get(8, 12) == 2
    assert night_frames[1].surface.get(8, 12) == 3
    assert night_frames[2].surface.get(8, 12) == 0
    assert night_frames[3].surface.get(8, 12) == 2
    # prop_pinned stays on frame 1 -> INK(0)
    assert all(f.surface.get(18, 12) == 0 for f in night_frames)

    bundle = export_scene_bundle(
        scene_spec,
        parent,
        props,
        style,
        ExportBundleOptions(animate=True),
    )
    assert bundle.manifest.id == "room_scene"
    assert bundle.manifest.frames == 6
    assert "room_scene_sheet.png" in bundle.files
    assert "room_scene_night.gif" in bundle.preview_files
    ts_out = export_indexed_ts([bundle], style)
    assert '"room_scene"' in ts_out.sprites_ts
    assert '"room_scene"' in ts_out.manifest_ts


def test_homelab_desk_scene_module_compiles_cleanly() -> None:
    """Verify `assets/homelab/homelab_desk_scene.scene.py` compiles with synchronized frames."""
    repo_root = Path(__file__).resolve().parents[2]
    style = load_style_module(repo_root / "styles" / "homelab_16bit.style.py")
    scene = load_scene_module(repo_root / "assets" / "homelab" / "homelab_desk_scene.scene.py")
    parent = load_asset_module(repo_root / "assets" / "homelab" / "bedroom_desk_iso.asset.py")
    props = {
        pid: load_asset_module(repo_root / "assets" / "props" / f"{pid}.asset.py")
        for pid in ("monitor_iso", "desk_lamp_iso", "network_switch_iso")
    }
    bundle = export_scene_bundle(scene.SCENE, parent, props, style)
    assert bundle.manifest.id == "homelab_desk_scene"
    assert bundle.manifest.states == ("day", "night")
    assert bundle.manifest.frames == 2
    assert "homelab_desk_scene_sheet.png" in bundle.files
