"""Isometric modular architectural pillar prop (`20x46` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup, prefabs

SPEC = AssetSpec(
    id="pillar_iso",
    style_id="homelab-16bit",
    width=20,
    height=46,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=512,
)


def render(a: Asset) -> None:
    """Render the `pillar_iso` architectural column with `mount_bottom` anchor."""
    p: PaletteLookup = a.pal
    is_night = a.state == "night"

    top_col = p.METAL_M if is_night else p.METAL_H
    left_col = p.WALL_M if is_night else p.WALL_L
    right_col = p.WALL_D if is_night else p.WALL_M

    prefabs.iso_pillar(
        a,
        10,
        6,
        w=8,
        d=8,
        h=30,
        top=top_col,
        left=left_col,
        right=right_col,
        cap_color=p.METAL_H,
        base_color=p.METAL_D,
        outline=p.INK,
    )

    a.anchor("mount_bottom", 10, 45)
    a.anchor("cap_top", 10, 6)
    a.hitbox("body", 0, 5, 20, 41)
