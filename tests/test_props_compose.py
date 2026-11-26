"""Scene composition and contract tests for `assets/props/*.asset.py`."""

from __future__ import annotations

from pathlib import Path

from pixelforge.export.bundle import LoadedAsset, export_asset_bundle
from pixelforge.export.scene import (
    SceneCompositionSpec,
    SceneMountSpec,
    compose_scene,
    generate_scene_sheet,
)
from pixelforge.guard.runner import load_asset_module, load_style_module

ROOT_DIR = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT_DIR / "assets" / "props"

EXPECTED_PROP_IDS = (
    "air_purifier_iso",
    "books_stack_iso",
    "coffee_mug_iso",
    "desk_lamp_iso",
    "desk_speaker_iso",
    "floor_lamp_iso",
    "glass_partition_iso",
    "headphones_stand_iso",
    "keyboard_iso",
    "monitor_iso",
    "mouse_iso",
    "network_switch_iso",
    "partition_wall_iso",
    "pc_tower_iso",
    "pillar_iso",
    "potted_plant_iso",
    "router_iso",
    "soda_can_iso",
    "storage_crate_iso",
    "tall_plant_iso",
    "trash_bin_iso",
    "ups_battery_iso",
)


def _load_props() -> dict[str, LoadedAsset]:
    props: dict[str, LoadedAsset] = {}
    for prop_id in EXPECTED_PROP_IDS:
        loaded = load_asset_module(PROPS_DIR / f"{prop_id}.asset.py")
        props[loaded.SPEC.id] = loaded
    return props


def test_props_library_contracts_and_metadata() -> None:
    """Verify all starter micro-props declare iso-2:1, multi-state, mount_bottom, and hitboxes."""
    style = load_style_module(ROOT_DIR / "styles" / "homelab_16bit.style.py")
    props = _load_props()
    assert tuple(sorted(props.keys())) == EXPECTED_PROP_IDS

    parent = load_asset_module(ROOT_DIR / "assets" / "homelab" / "bedroom_desk_iso.asset.py")
    for prop_id, prop in props.items():
        assert prop.SPEC.style_id == "homelab-16bit"
        assert prop.SPEC.perspective == "iso-2:1"
        assert len(prop.SPEC.states) >= 2

        res = compose_scene(
            parent,
            {prop_id: prop},
            style,
            SceneCompositionSpec(
                parent_id="bedroom_desk_iso",
                parent_state="day",
                mounts=(
                    SceneMountSpec(
                        prop_id=prop_id,
                        anchor="hardware_0",
                        prop_anchor="mount_bottom",
                    ),
                ),
            ),
            strict_bounds=True,
            strict_perspective=True,
        )
        assert len(res.placements) == 1
        assert res.placements[0].in_bounds is True
        assert res.placements[0].clipped_pixels == 0
        assert res.placements[0].perspective_match is True


def test_props_compose_onto_bedroom_desk_iso_with_zero_clipping() -> None:
    """Verify multiple micro-props mount onto `bedroom_desk_iso` anchors cleanly."""
    style = load_style_module(ROOT_DIR / "styles" / "homelab_16bit.style.py")
    parent = load_asset_module(ROOT_DIR / "assets" / "homelab" / "bedroom_desk_iso.asset.py")
    props = _load_props()

    desk_pack_a = SceneCompositionSpec(
        parent_id="bedroom_desk_iso",
        parent_state="night",
        mounts=(
            SceneMountSpec(
                prop_id="monitor_iso",
                anchor="hardware_0",
                prop_anchor="mount_bottom",
                state="active",
                frame=0,
            ),
            SceneMountSpec(
                prop_id="desk_lamp_iso",
                anchor="hardware_1",
                prop_anchor="mount_bottom",
                state="night",
            ),
            SceneMountSpec(
                prop_id="network_switch_iso",
                anchor="hardware_2",
                prop_anchor="mount_bottom",
                state="active",
                frame=1,
            ),
        ),
    )
    res_a = compose_scene(
        parent,
        props,
        style,
        desk_pack_a,
        strict_bounds=True,
        strict_perspective=True,
    )
    assert all(p.in_bounds for p in res_a.placements)
    assert all(p.clipped_pixels == 0 for p in res_a.placements)
    assert all(p.perspective_match for p in res_a.placements)
    assert all(p.occluded_pixels == 0 for p in res_a.placements)
    assert res_a.warnings == ()

    sheet = generate_scene_sheet(res_a, style)
    assert sheet.width > 320
    assert len(sheet.png) > 0

    desk_pack_b = SceneCompositionSpec(
        parent_id="bedroom_desk_iso",
        parent_state="day",
        mounts=(
            SceneMountSpec(
                prop_id="potted_plant_iso",
                anchor="hardware_0",
                prop_anchor="mount_bottom",
                state="day",
            ),
            SceneMountSpec(
                prop_id="coffee_mug_iso",
                anchor="hardware_1",
                prop_anchor="mount_bottom",
                state="day",
            ),
            SceneMountSpec(
                prop_id="storage_crate_iso",
                anchor="hardware_2",
                prop_anchor="mount_bottom",
                state="active",
            ),
        ),
    )
    res_b = compose_scene(
        parent,
        props,
        style,
        desk_pack_b,
        strict_bounds=True,
        strict_perspective=True,
    )
    assert all(p.in_bounds for p in res_b.placements)
    assert all(p.clipped_pixels == 0 for p in res_b.placements)
    assert all(p.perspective_match for p in res_b.placements)
    assert all(p.occluded_pixels == 0 for p in res_b.placements)
    assert res_b.warnings == ()

    full_desk = SceneCompositionSpec(
        parent_id="bedroom_desk_iso",
        parent_state="night",
        depth_sort="iso_y",
        mounts=(
            SceneMountSpec(
                prop_id="monitor_iso",
                anchor="hardware_0",
                prop_anchor="mount_bottom",
                state="active",
                frame=0,
            ),
            SceneMountSpec(
                prop_id="pc_tower_iso",
                anchor="desk_pc",
                prop_anchor="mount_bottom",
                state="active",
                frame=0,
            ),
            SceneMountSpec(
                prop_id="desk_lamp_iso",
                anchor="hardware_1",
                prop_anchor="mount_bottom",
                state="night",
            ),
            SceneMountSpec(
                prop_id="keyboard_iso",
                anchor="desk_keyboard",
                prop_anchor="mount_bottom",
                state="active",
                frame=0,
            ),
            SceneMountSpec(
                prop_id="mouse_iso",
                anchor="desk_mouse",
                prop_anchor="mount_bottom",
                state="active",
            ),
            SceneMountSpec(
                prop_id="network_switch_iso",
                anchor="hardware_2",
                prop_anchor="mount_bottom",
                state="active",
                frame=1,
            ),
        ),
    )
    res_full = compose_scene(
        parent,
        props,
        style,
        full_desk,
        strict_bounds=True,
        strict_perspective=True,
    )
    assert all(p.in_bounds for p in res_full.placements)
    assert all(p.clipped_pixels == 0 for p in res_full.placements)
    assert all(p.perspective_match for p in res_full.placements)
    assert all(p.occluded_pixels == 0 for p in res_full.placements)
    assert res_full.warnings == ()


def test_network_switch_iso_exposes_individual_port_anchors() -> None:
    """Verify `network_switch_iso` emits `port_0..port_4` with `kind` and `dir`."""
    style = load_style_module(ROOT_DIR / "styles" / "homelab_16bit.style.py")
    switch_mod = load_asset_module(PROPS_DIR / "network_switch_iso.asset.py")
    bundle = export_asset_bundle(switch_mod, style)

    ports = [a for a in bundle.manifest.anchors if a.name.startswith("port_")]
    assert [p.name for p in ports] == [f"port_{idx}" for idx in range(5)]
    assert all(p.kind == "rj45" for p in ports)
    assert all(p.dir == (-1, 1) for p in ports)
    # Ports are ordered left-to-right across the front isometric face
    assert [p.x for p in ports] == sorted(p.x for p in ports)


def test_multiroom_homelab_scene_zone_ordered_depth_sorting() -> None:
    """Verify `multiroom_homelab_scene` sorts by `(z_index, iso_y)` with zero clipping."""
    from pixelforge.export.scene import compose_scene_frames
    from pixelforge.guard.runner import load_scene_module

    style = load_style_module(ROOT_DIR / "styles" / "homelab_16bit.style.py")
    parent = load_asset_module(ROOT_DIR / "assets" / "homelab" / "multiroom_homelab_iso.asset.py")
    scene_mod = load_scene_module(
        ROOT_DIR / "assets" / "homelab" / "multiroom_homelab_scene.scene.py"
    )
    props = _load_props()

    _scene_asset_spec, frames, _warnings = compose_scene_frames(
        scene_mod.SCENE, parent, props, style
    )
    assert len(frames) == 4  # 2 states (day, night) x 2 synced frames

    day_res = compose_scene(
        parent,
        props,
        style,
        SceneCompositionSpec(
            parent_id=scene_mod.SCENE.parent_id,
            parent_state="day",
            mounts=scene_mod.SCENE.mounts,
            depth_sort=scene_mod.SCENE.depth_sort,
        ),
        strict_bounds=True,
        strict_perspective=True,
    )
    assert all(p.in_bounds for p in day_res.placements)
    assert all(p.clipped_pixels == 0 for p in day_res.placements)
    assert all(p.perspective_match for p in day_res.placements)

    # Placements are sorted by z_index (zones 0 -> 1 -> 2)
    z_indices = [p.z_index for p in day_res.placements]
    assert z_indices == sorted(z_indices)
    # Divider zone (z_index=1) is ordered back-to-front by iso_y
    div_ids = [p.prop_id for p in day_res.placements if p.z_index == 1]
    assert div_ids == ["partition_wall_iso", "pillar_iso", "glass_partition_iso"]
