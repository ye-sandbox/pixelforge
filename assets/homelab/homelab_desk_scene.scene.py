"""Declarative animated homelab desk scene composing bedroom_desk_iso with props."""

from __future__ import annotations

from pixelforge import SceneMountSpec, ScenePortalSpec, SceneSpec

SCENE = SceneSpec(
    id="homelab_desk_scene",
    parent_id="bedroom_desk_iso",
    style_id="homelab-16bit",
    depth_sort="iso_y",
    strict_bounds=True,
    strict_perspective=True,
    portals=(
        ScenePortalSpec(
            id="to_multiroom_homelab",
            target_scene_id="multiroom_homelab_scene",
            anchor="portal_homelab",
            target_portal_id="to_bedroom_desk",
            bidirectional=True,
        ),
    ),
    mounts=(
        SceneMountSpec(
            prop_id="monitor_iso",
            anchor="hardware_0",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
        ),
        SceneMountSpec(
            prop_id="pc_tower_iso",
            anchor="desk_pc",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
        ),
        SceneMountSpec(
            prop_id="desk_lamp_iso",
            anchor="hardware_1",
            prop_anchor="mount_bottom",
        ),
        SceneMountSpec(
            prop_id="keyboard_iso",
            anchor="desk_keyboard",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
        ),
        SceneMountSpec(
            prop_id="mouse_iso",
            anchor="desk_mouse",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
        ),
        SceneMountSpec(
            prop_id="network_switch_iso",
            anchor="hardware_2",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
        ),
    ),
)
