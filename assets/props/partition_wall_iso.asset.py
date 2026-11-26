"""Isometric modular half-wall partition prop (`52x44` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup, prefabs

SPEC = AssetSpec(
    id="partition_wall_iso",
    style_id="homelab-16bit",
    width=52,
    height=44,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=510,
)


def render(a: Asset) -> None:
    """Render the `partition_wall_iso` modular divider with `mount_bottom` anchor."""
    p: PaletteLookup = a.pal
    is_night = a.state == "night"

    face = p.WALL_M if is_night else p.WALL_L
    cap = p.WOOD_M if is_night else p.WOOD_L
    side = p.WALL_D if is_night else p.WALL_M

    geom = prefabs.IsoRoomGeometry(cx=26, cy=30, hw=16, hh=8, wall_h=20)
    wall_plane = prefabs.iso_partition_wall(
        a,
        geom,
        "left",
        at=0.5,
        u0=0.0,
        u1=1.0,
        face=face,
        cap=cap,
        side=side,
        height=20,
        thickness=4,
        baseboard=(p.WOOD_M, p.WOOD_D),
        outline=p.INK,
    )
    prefabs.wall_molding(
        a,
        wall_plane[0],
        wall_plane[1],
        wall_plane[2],
        primary=p.WOOD_M,
        highlight=p.WOOD_L,
        shadow=p.WOOD_D,
        style="chair_rail",
        v_pos=0.45,
        thickness=0.08,
    )

    bx, by = geom.floor_point(0.5, 0.5)
    a.anchor("mount_bottom", bx, by)
    a.anchor("cap_top", bx, by - 20)
    a.hitbox("body", 12, 8, 28, 30)
