"""Isometric modular framed glass partition prop (`52x48` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup, prefabs

SPEC = AssetSpec(
    id="glass_partition_iso",
    style_id="homelab-16bit",
    width=52,
    height=48,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=511,
)


def render(a: Asset) -> None:
    """Render the `glass_partition_iso` modular divider with `mount_bottom` anchor."""
    p: PaletteLookup = a.pal
    is_night = a.state == "night"

    frame_col = p.METAL_D if is_night else p.METAL_M
    mullion_col = p.METAL_M if is_night else p.METAL_L
    glass_col = p.WINDOW_SKY if is_night else p.GLASS_D

    geom = prefabs.IsoRoomGeometry(cx=26, cy=34, hw=16, hh=8, wall_h=24)
    prefabs.iso_glass_partition(
        a,
        geom,
        "left",
        at=0.5,
        u0=0.0,
        u1=1.0,
        frame=frame_col,
        glass=glass_col,
        height=24,
        glint=p.GLASS_L,
        mullion=mullion_col,
        cols=2,
        rows=1,
        kickplate=p.METAL_D,
        kickplate_ratio=0.22,
        outline=p.INK,
    )

    bx, by = geom.floor_point(0.5, 0.5)
    a.anchor("mount_bottom", bx, by)
    a.anchor("cap_top", bx, by - 24)
    a.hitbox("body", 14, 8, 24, 34)
