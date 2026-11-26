"""Declarative multi-room homelab + bedroom scene composing zone-ordered props and partitions."""

from __future__ import annotations

from pixelforge.export.scene import SceneMountSpec, SceneSpec

SCENE = SceneSpec(
    id="multiroom_homelab_scene",
    parent_id="multiroom_homelab_iso",
    style_id="homelab-16bit",
    depth_sort="iso_y",
    strict_bounds=True,
    strict_perspective=True,
    mounts=(
        # Zone 0: Bedroom props (back zone)
        SceneMountSpec(
            prop_id="potted_plant_iso",
            anchor="bed_plant",
            prop_anchor="mount_bottom",
            z_index=0,
        ),
        SceneMountSpec(
            prop_id="storage_crate_iso",
            anchor="bed_crate",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
            z_index=0,
        ),
        # Zone 1: Center partition divider along at=0.50 (sorted by iso_y within z_index=1)
        SceneMountSpec(
            prop_id="partition_wall_iso",
            anchor="div_wall_back",
            prop_anchor="mount_bottom",
            z_index=1,
        ),
        SceneMountSpec(
            prop_id="pillar_iso",
            anchor="div_pillar",
            prop_anchor="mount_bottom",
            z_index=1,
        ),
        SceneMountSpec(
            prop_id="glass_partition_iso",
            anchor="div_glass",
            prop_anchor="mount_bottom",
            z_index=1,
        ),
        # Zone 2: Homelab workstation props (front zone, sorted by iso_y within z_index=2)
        SceneMountSpec(
            prop_id="monitor_iso",
            anchor="desk_monitor",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
            z_index=2,
        ),
        SceneMountSpec(
            prop_id="desk_lamp_iso",
            anchor="desk_lamp",
            prop_anchor="mount_bottom",
            z_index=2,
        ),
        SceneMountSpec(
            prop_id="pc_tower_iso",
            anchor="desk_pc",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
            z_index=2,
        ),
        SceneMountSpec(
            prop_id="keyboard_iso",
            anchor="desk_keyboard",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
            z_index=2,
        ),
        SceneMountSpec(
            prop_id="mouse_iso",
            anchor="desk_mouse",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
            z_index=2,
        ),
        SceneMountSpec(
            prop_id="network_switch_iso",
            anchor="rack_switch",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
            z_index=2,
        ),
    ),
)
