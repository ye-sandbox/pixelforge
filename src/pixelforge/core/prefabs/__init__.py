"""Deterministic, StylePack-agnostic 2:1 isometric prefab kits."""

from pixelforge.core.prefabs.architecture import (
    FloorPatternMode,
    iso_floor_pattern,
    iso_room_shell,
    iso_window,
    wall_vent,
)
from pixelforge.core.prefabs.details import (
    contact_shadow,
    iso_cable_run,
    wall_panel,
    wall_poster,
)
from pixelforge.core.prefabs.furniture import (
    iso_desk,
    iso_rack,
    iso_shelf,
)

__all__ = [
    "FloorPatternMode",
    "contact_shadow",
    "iso_cable_run",
    "iso_desk",
    "iso_floor_pattern",
    "iso_rack",
    "iso_room_shell",
    "iso_shelf",
    "iso_window",
    "wall_panel",
    "wall_poster",
    "wall_vent",
]
