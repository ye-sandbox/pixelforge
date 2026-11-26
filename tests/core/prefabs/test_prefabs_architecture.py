"""Hermetic tests for architectural room geometry, floor zones, openings, and partitions."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from pixelforge import Asset, prefabs


def test_iso_room_geometry_projections_and_spill(make_asset: Callable[..., Asset]) -> None:
    """Verify `IsoRoomGeometry` wall planes, floor points, non-clipping bounds, and spill."""
    asset = make_asset(width=120, height=100)
    p = asset.pal
    room = prefabs.iso_room_shell(
        asset,
        60,
        70,
        40,
        20,
        36,
        floor=p.FLOOR,
        left_wall=p.WALL_L,
        right_wall=p.WALL_R,
        outline=p.INK,
    )
    assert room.lighting_angle == "top-left"
    assert room.floor_point(0.0, 0.0) == (60, 50)
    assert room.floor_point(1.0, 0.0) == (100, 70)
    assert room.floor_point(0.0, 1.0) == (20, 70)
    assert room.floor_point(0.5, 0.5) == (60, 70)

    lp0, lp1, lp2 = room.left_wall_plane(0.25, 0.25, 0.75, 0.75)
    assert lp0[0] >= room.left_x and lp1[0] <= room.cx
    assert lp2[1] <= room.cy

    rp0, rp1, rp2 = room.right_wall_plane(0.2, 0.2, 0.8, 0.8)
    assert rp0[0] >= room.cx and rp1[0] <= room.right_x
    assert rp2[1] <= room.cy

    clamped_l = room.left_wall_plane(-0.5, -0.5, 1.5, 1.5)
    assert clamped_l == room.left_wall_plane(0.0, 0.0, 1.0, 1.0)

    with pytest.raises(ValueError, match="Invalid left wall sub-region"):
        room.left_wall_plane(0.5, 0.2, 0.5, 0.8)

    spill_tl = room.window_spill_quad(0.2, 0.8, wall="left", depth=0.4)
    spill_tr = prefabs.IsoRoomGeometry(
        cx=60, cy=70, hw=40, hh=20, wall_h=36, lighting_angle="top-right"
    ).window_spill_quad(0.2, 0.8, wall="left", depth=0.4)
    assert spill_tl[2] != spill_tr[2]

    right_spill = room.window_spill_quad(0.2, 0.8, wall="right", depth=0.4)
    assert all(0 <= pt[0] < 120 and 0 <= pt[1] < 100 for pt in right_spill)


def test_iso_room_geometry_wall_box_center() -> None:
    """Verify `wall_box_center` places furniture flush against left/right walls at `margin`."""
    room = prefabs.IsoRoomGeometry(cx=160, cy=136, hw=112, hh=56, wall_h=74)

    rx, ry = room.wall_box_center("right", 74, 28, 19, along=0.0, margin=1, corner_margin=4)
    assert (rx, ry) == (186, 89)

    lx, ly = room.wall_box_center("left", 28, 74, 19, along=0.0, margin=1, corner_margin=4)
    assert (lx, ly) == (134, 89)

    r_start = room.wall_box_center("right", 40, 20, 0, along=0.0, margin=2, corner_margin=4)
    r_mid = room.wall_box_center("right", 40, 20, 0, along=0.5, margin=2, corner_margin=4)
    r_end = room.wall_box_center("right", 40, 20, 0, along=1.0, margin=2, corner_margin=4)
    assert r_start[0] < r_mid[0] < r_end[0]
    assert r_start[1] < r_mid[1] < r_end[1]

    for wall, w, d, pt in (
        ("right", 40, 20, r_mid),
        ("left", 20, 40, room.wall_box_center("left", 20, 40, 0, along=0.5, margin=3)),
    ):
        tx = round(pt[0] - (w - d) * 0.5)
        ty = round(pt[1] - (w // 2 + d // 2) * 0.5)
        if wall == "right":
            wall_y = room.apex_y + (tx - room.cx) * 0.5
            assert abs((ty - wall_y) - 2.0) <= 0.5
        else:
            wall_y = room.apex_y + (room.cx - tx) * 0.5
            assert abs((ty - wall_y) - 3.0) <= 0.5

    assert room.wall_box_center("right", 40, 20, 18, along=0.5, margin=2) == (
        r_mid[0],
        r_mid[1] - 18,
    )

    oversized = room.wall_box_center("left", 20, 140, 10, along=0.25, margin=2, corner_margin=8)
    assert oversized[0] < room.cx

    with pytest.raises(ValueError, match="Unsupported wall side"):
        room.wall_box_center("front", 20, 20, 10)  # type: ignore[arg-type]


def test_front_door_renders_vision_glass(make_asset: Callable[..., Asset]) -> None:
    """Verify `front_door` renders frame, panel, vision glass, and handle."""
    asset = make_asset(48, 64)
    p = asset.pal
    prefabs.front_door(
        asset,
        8,
        16,
        18,
        34,
        frame=p.WOOD_D,
        panel=p.WOOD_M,
        recess=p.WOOD_D,
        handle=p.SUN,
        outline=p.INK,
        window=p.SKY,
        threshold=p.METAL_D,
    )
    assert np.any(asset.root_surface.data[16:50, 8:26] == p.SKY)


def test_subroom_and_partition_plane_mount_wall_prefabs(
    make_asset: Callable[..., Asset],
) -> None:
    """Verify `subroom()` and `partition_plane()` mount wall prefabs cleanly."""
    asset = make_asset(180, 140)
    p = asset.pal
    geom = prefabs.iso_room_shell(
        asset,
        90,
        96,
        64,
        32,
        40,
        floor=p.FLOOR,
        left_wall=p.WALL_L,
        right_wall=p.WALL_R,
        outline=p.INK,
    )

    sub_left = geom.subroom(0.0, 0.0, 0.5, 1.0)
    assert sub_left.floor_point(0.0, 0.0) == geom.floor_point(0.0, 0.0)
    assert sub_left.floor_point(1.0, 0.0) == geom.floor_point(0.5, 0.0)
    assert sub_left.floor_point(0.0, 1.0) == geom.floor_point(0.0, 1.0)
    assert sub_left.floor_point(1.0, 1.0) == geom.floor_point(0.5, 1.0)

    assert geom.partition_plane("left", 0.0) == geom.left_wall_plane()
    assert geom.partition_plane("right", 0.0) == geom.right_wall_plane()

    part = geom.partition_plane("left", 0.5, u0=0.05, v0=0.0, u1=0.95, v1=1.0)
    prefabs.iso_partition_wall(
        asset,
        geom,
        "left",
        0.5,
        u0=0.05,
        u1=0.95,
        face=p.WALL_L,
        cap=p.METAL_H,
        side=p.WALL_R,
        baseboard=(p.WOOD_M, p.WOOD_D),
        outline=p.INK,
    )
    door_plane = geom.partition_plane("left", 0.5, u0=0.15, v0=0.25, u1=0.38, v1=1.0)
    prefabs.iso_door(
        asset,
        *door_plane,
        frame=p.WOOD_D,
        panel=p.WOOD_M,
        handle=p.SUN,
        outline=p.INK,
    )
    panel_plane = geom.partition_plane("left", 0.5, u0=0.45, v0=0.22, u1=0.65, v1=0.58)
    prefabs.wall_panel(
        asset, *panel_plane, frame=p.METAL_D, recess=p.FLOOR_D, slot=p.METAL_M, status_led=p.LED
    )
    poster_plane = geom.partition_plane("left", 0.5, u0=0.70, v0=0.20, u1=0.86, v1=0.55)
    prefabs.wall_poster(asset, *poster_plane, border=p.INK, fill=p.SKY, accent=p.SUN)
    outlet_plane = geom.partition_plane("left", 0.5, u0=0.46, v0=0.75, u1=0.54, v1=0.88)
    prefabs.wall_outlet(asset, *outlet_plane, plate=p.METAL_H, socket=p.INK, outline=p.INK)

    assert len(part) == 3
    assert np.any(asset.root_surface.data == p.LED)
    assert np.any(asset.root_surface.data == p.SUN)

    with pytest.raises(ValueError, match="Invalid subroom bounds"):
        geom.subroom(0.5, 0.0, 0.5, 1.0)
    with pytest.raises(ValueError, match="Invalid left wall sub-region"):
        geom.partition_plane("left", 0.5, u0=0.8, u1=0.2)


def test_floor_zones_thresholds_partitions_pillars_and_molding(
    make_asset: Callable[..., Asset],
) -> None:
    """Verify floor zones, thresholds, arched/glass partitions, pillars, and wall moldings."""
    asset = make_asset(180, 140)
    p = asset.pal
    geom = prefabs.iso_room_shell(
        asset,
        90,
        96,
        64,
        32,
        40,
        floor=p.FLOOR,
        left_wall=p.WALL_L,
        right_wall=p.WALL_R,
        outline=p.INK,
    )

    prefabs.iso_floor_zone(
        asset,
        geom,
        0.0,
        0.0,
        0.5,
        0.5,
        fill=p.WOOD_M,
        alt=p.WOOD_D,
        pattern_color=p.WOOD_L,
        mode="planks",
        step=8,
    )
    prefabs.iso_floor_zone(
        asset,
        geom,
        0.5,
        0.0,
        1.0,
        0.5,
        fill=p.METAL_D,
        alt=p.FLOOR_D,
        pattern_color=p.METAL_M,
        mode="tiles",
        step=8,
    )
    prefabs.iso_floor_zone(
        asset,
        geom,
        0.0,
        0.5,
        0.5,
        1.0,
        fill=p.FLOOR,
        pattern_color=p.SKY,
        mode="carpet",
        border=p.SUN,
    )
    prefabs.iso_floor_zone(
        asset,
        geom,
        0.5,
        0.5,
        1.0,
        1.0,
        fill=p.FLOOR_D,
        mode="grid",
        pattern_color=p.WALL_R,
        step=8,
    )
    prefabs.iso_floor_threshold(
        asset,
        geom,
        "left",
        0.5,
        (0.05, 0.95),
        fill=p.METAL_H,
        highlight=p.SUN,
        outline=p.INK,
    )
    prefabs.iso_floor_threshold(
        asset,
        geom,
        "right",
        0.5,
        (0.05, 0.95),
        fill=p.WOOD_L,
        outline=p.INK,
    )

    prefabs.iso_partition_wall(
        asset,
        geom,
        "left",
        0.5,
        u0=0.0,
        u1=0.6,
        face=p.WALL_L,
        cap=p.METAL_H,
        height=24,
        doorway=(0.30, 0.70),
        doorway_style="arch",
        outline=p.INK,
    )
    prefabs.iso_glass_partition(
        asset,
        geom,
        "right",
        0.5,
        u0=0.1,
        u1=0.9,
        frame=p.METAL_D,
        glass=p.SKY,
        glint=p.CLOUD,
        mullion=p.METAL_H,
        cols=3,
        rows=2,
        kickplate=p.FLOOR_D,
        outline=p.INK,
    )
    px, py = geom.floor_point(0.5, 0.5)
    prefabs.iso_pillar(
        asset,
        px,
        py - 32,
        w=8,
        d=8,
        h=32,
        top=p.METAL_H,
        left=p.METAL_M,
        right=p.METAL_D,
        cap_color=p.SUN,
        base_color=p.INK,
        outline=p.INK,
    )
    prefabs.wall_molding(
        asset,
        *geom.right_wall_plane(0.05, 0.0, 0.95, 1.0),
        primary=p.WOOD_L,
        highlight=p.CLOUD,
        shadow=p.WOOD_D,
        style="wainscot",
    )
    prefabs.wall_molding(
        asset,
        *geom.left_wall_plane(0.05, 0.0, 0.95, 1.0),
        primary=p.WOOD_M,
        style="crown",
    )

    assert np.any(asset.root_surface.data == p.SKY)
    assert np.any(asset.root_surface.data == p.SUN)
    assert np.any(asset.root_surface.data == p.WOOD_L)

    second = make_asset(180, 140)
    sp = second.pal
    sgeom = prefabs.iso_room_shell(
        second,
        90,
        96,
        64,
        32,
        40,
        floor=sp.FLOOR,
        left_wall=sp.WALL_L,
        right_wall=sp.WALL_R,
        outline=sp.INK,
    )
    prefabs.iso_floor_zone(second, sgeom, 0.0, 0.0, 0.5, 0.5, fill=sp.WOOD_M, alt=sp.WOOD_D)
    first_check = make_asset(180, 140)
    fp = first_check.pal
    fgeom = prefabs.iso_room_shell(
        first_check,
        90,
        96,
        64,
        32,
        40,
        floor=fp.FLOOR,
        left_wall=fp.WALL_L,
        right_wall=fp.WALL_R,
        outline=fp.INK,
    )
    prefabs.iso_floor_zone(first_check, fgeom, 0.0, 0.0, 0.5, 0.5, fill=fp.WOOD_M, alt=fp.WOOD_D)
    assert np.array_equal(second.root_surface.data, first_check.root_surface.data)
