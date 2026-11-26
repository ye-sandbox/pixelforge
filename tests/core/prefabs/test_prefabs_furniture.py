"""Hermetic tests for isometric workstation, seating, and storage furniture prefabs."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from pixelforge import Asset, prefabs
from pixelforge.core.types import TRANSPARENT_INDEX


def test_furniture_slots_and_rack_front_styles(make_asset: Callable[..., Asset]) -> None:
    """Verify `iso_desk`, `iso_rack`, and `iso_shelf` slot helpers and rack front styles."""
    asset = make_asset(width=160, height=120)
    p = asset.pal

    desk_slots = prefabs.iso_desk(
        asset,
        50,
        60,
        36,
        36,
        top=p.WOOD_L,
        left=p.WOOD_M,
        right=p.WOOD_D,
        leg_top=p.METAL_M,
        leg_left=p.METAL_D,
        leg_right=p.INK,
        outline=p.INK,
    )
    assert desk_slots.center == (50, 60)
    assert desk_slots.top_point(0.5, 0.5) == (50, 60)
    pair = desk_slots.slots(2)
    assert len(pair) == 2
    assert pair[0][0] < desk_slots.center[0] < pair[1][0]

    rack_bays = prefabs.iso_rack(
        asset,
        100,
        70,
        16,
        16,
        24,
        top=p.METAL_H,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        bay_color=p.INK,
        led_color=p.LED,
        bays=3,
        front_style="bays",
    )
    assert rack_bays.top_center == (100, 70)
    assert len(rack_bays.front_mounts) == 3

    rack_grille = prefabs.iso_rack(
        asset,
        125,
        70,
        16,
        16,
        24,
        top=p.METAL_H,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        bay_color=p.INK,
        led_color=p.LED,
        front_style="grille",
    )
    assert rack_grille.top_center == (125, 70)

    rack_door = prefabs.iso_rack(
        asset,
        145,
        70,
        16,
        16,
        24,
        top=p.METAL_H,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        highlight=p.METAL_H,
        bay_color=p.SKY_DARK,
        door_color=p.METAL_D,
        led_color=p.LED,
        bays=2,
        front_style="glass_door",
    )
    assert len(rack_door.front_mounts) == 2

    shelf_slots = prefabs.iso_shelf(
        asset,
        30,
        90,
        16,
        16,
        24,
        shelves=3,
        top=p.WOOD_L,
        left=p.WOOD_M,
        right=p.WOOD_D,
        post=p.METAL_D,
        outline=p.INK,
    )
    assert len(shelf_slots.tiers) == 3
    assert shelf_slots.tiers[0][1] < shelf_slots.tiers[1][1] < shelf_slots.tiers[2][1]
    assert shelf_slots.tier_point(0, 0.5, 0.5) == shelf_slots.top_center

    unique_indices = set(np.unique(asset.root_surface.data).tolist())
    allowed = {c.index for c in asset.style.palette} | {TRANSPARENT_INDEX}
    assert unique_indices <= allowed


def test_workstation_chair_and_shelf_prefabs(make_asset: Callable[..., Asset]) -> None:
    """Verify `iso_chair`, `iso_wall_shelf`, `iso_workbench`, and `iso_drawer_unit`."""
    asset = make_asset(128, 96)
    p = asset.pal

    for idx, facing in enumerate(("se", "sw", "nw", "ne")):
        cx, cy = prefabs.iso_chair(
            asset,
            40 + idx * 18,
            34,
            top=p.METAL_M,
            left=p.METAL_D,
            right=p.INK,
            back=p.WOOD_M,
            leg=p.INK,
            outline=p.INK,
            facing=facing,
        )
        assert 30 <= cx <= 110
        assert 20 <= cy <= 50

    shelf_slots = prefabs.iso_wall_shelf(
        asset,
        (72, 54),
        (96, 66),
        (72, 60),
        top=p.WOOD_L,
        front=p.WOOD_D,
        bracket=p.INK,
        outline=p.INK,
    )
    assert len(shelf_slots) == 3

    wb_slots = prefabs.iso_workbench(
        asset,
        36,
        72,
        top=p.WOOD_L,
        left=p.WOOD_M,
        right=p.WOOD_D,
        leg_top=p.METAL_M,
        leg_left=p.METAL_D,
        leg_right=p.INK,
        back_panel=p.METAL_D,
        pegboard_dot=p.METAL_H,
        lower_shelf=p.WOOD_D,
        outline=p.INK,
    )
    assert len(wb_slots.slots(2)) == 2

    drawer_top = prefabs.iso_drawer_unit(
        asset,
        92,
        74,
        top=p.METAL_H,
        left=p.METAL_M,
        right=p.METAL_D,
        drawer_face=p.FLOOR_D,
        handle=p.SUN,
        outline=p.INK,
    )
    assert drawer_top[0] > 70


def test_living_and_workstation_furniture_prefabs(make_asset: Callable[..., Asset]) -> None:
    """Verify living and workstation furniture prefabs render deterministically."""

    def _render_furniture(asset: Asset) -> None:
        p = asset.pal
        l_slots = prefabs.iso_l_desk(
            asset,
            42,
            38,
            w=32,
            d=28,
            wing_w=14,
            wing_d=12,
            top=p.WOOD_L,
            left=p.WOOD_M,
            right=p.WOOD_D,
            leg_top=p.METAL_M,
            leg_left=p.METAL_D,
            leg_right=p.INK,
            outline=p.INK,
            highlight=p.CLOUD,
            mat_color=p.METAL_D,
        )
        assert len(l_slots.slots(2)) == 2

        ns_top = prefabs.iso_nightstand(
            asset,
            92,
            32,
            top=p.WOOD_L,
            left=p.WOOD_M,
            right=p.WOOD_D,
            drawer_face=p.FLOOR_D,
            handle=p.SUN,
            outline=p.INK,
        )
        assert ns_top[0] > 70

        side_slots = prefabs.iso_side_table(
            asset,
            122,
            34,
            top=p.WOOD_L,
            left=p.WOOD_M,
            right=p.WOOD_D,
            leg_top=p.METAL_M,
            leg_left=p.METAL_D,
            leg_right=p.INK,
            lower_shelf=p.WOOD_D,
            outline=p.INK,
        )
        assert side_slots.center == (122, 34)

        for idx, facing in enumerate(("se", "sw", "nw", "ne")):
            sx, sy = prefabs.iso_sofa(
                asset,
                34 + idx * 32,
                76,
                top=p.METAL_M,
                left=p.METAL_D,
                right=p.FLOOR_D,
                back=p.WALL_L,
                arm=p.METAL_H,
                cushion_seam=p.INK,
                outline=p.INK,
                facing=facing,
            )
            assert 20 <= sx <= 145
            assert 60 <= sy <= 90

        arm_pt = prefabs.iso_armchair(
            asset,
            154,
            76,
            top=p.METAL_M,
            left=p.METAL_D,
            right=p.FLOOR_D,
            back=p.WALL_L,
            outline=p.INK,
            facing="se",
        )
        assert 140 <= arm_pt[0] <= 170

        coffee_slots = prefabs.iso_coffee_table(
            asset,
            40,
            114,
            top=p.WOOD_L,
            left=p.WOOD_M,
            right=p.WOOD_D,
            leg_top=p.METAL_M,
            leg_left=p.METAL_D,
            leg_right=p.INK,
            lower_shelf=p.WOOD_D,
            inlay_color=p.SKY,
            outline=p.INK,
        )
        assert coffee_slots.top_point(0.5, 0.5) != (0, 0)

        w_top = prefabs.iso_wardrobe(
            asset,
            78,
            114,
            top=p.WOOD_L,
            left=p.WOOD_M,
            right=p.WOOD_D,
            door=p.FLOOR_D,
            handle=p.SUN,
            outline=p.INK,
        )
        l_top = prefabs.iso_locker(
            asset,
            106,
            114,
            top=p.METAL_H,
            left=p.METAL_M,
            right=p.METAL_D,
            door=p.FLOOR,
            vent=p.INK,
            handle=p.SUN,
            badge_color=p.SUN,
            outline=p.INK,
        )
        f_top = prefabs.iso_mini_fridge(
            asset,
            132,
            114,
            top=p.METAL_H,
            left=p.METAL_M,
            right=p.METAL_D,
            door=p.CLOUD,
            handle=p.INK,
            vent=p.FLOOR_D,
            led_color=p.LED,
            outline=p.INK,
        )
        cab_top = prefabs.iso_filing_cabinet(
            asset,
            158,
            114,
            top=p.METAL_H,
            left=p.METAL_M,
            right=p.METAL_D,
            drawer_face=p.FLOOR_D,
            handle=p.SUN,
            label_color=p.CLOUD,
            outline=p.INK,
        )
        assert w_top[1] < l_top[1] + 20
        assert f_top[0] > 110 and cab_top[0] > 140

    first = make_asset(180, 145)
    second = make_asset(180, 145)
    _render_furniture(first)
    _render_furniture(second)

    assert np.array_equal(first.root_surface.data, second.root_surface.data)
    assert np.any(first.root_surface.data == first.pal.SKY)
    assert np.any(first.root_surface.data == first.pal.LED)
    valid_indices = {c.index for c in first.style.palette} | {TRANSPARENT_INDEX}
    assert set(np.unique(first.root_surface.data).tolist()).issubset(valid_indices)


def test_iso_desk_set_and_chair_point(make_asset: Callable[..., Asset]) -> None:
    """Verify `IsoDeskSlots.chair_point()` and `iso_desk_set()` snap a chair in front of desk."""
    asset = make_asset(width=140, height=110)
    p = asset.pal

    slots = prefabs.iso_desk_set(
        asset,
        74,
        52,
        52,
        22,
        leg_h=15,
        top_h=4,
        top=p.WOOD_L,
        left=p.WOOD_M,
        right=p.WOOD_D,
        leg_top=p.METAL_M,
        leg_left=p.METAL_D,
        leg_right=p.INK,
        outline=p.INK,
        mat_color=p.METAL_D,
        shadow_color=p.INK,
    )
    assert slots.leg_h == 15
    cx, cy = slots.chair_point()
    edge_x, edge_y = slots.top_point(0.45, 1.0)
    assert cx < edge_x
    assert cy > edge_y
    assert asset.root_surface.data[cy, cx] != TRANSPARENT_INDEX
