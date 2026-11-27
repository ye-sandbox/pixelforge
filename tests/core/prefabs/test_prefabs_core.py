"""Hermetic determinism, palette-closure, bounds-safety, and AST guard tests for prefabs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from pixelforge import Asset, prefabs
from pixelforge.core import prefabs as core_prefabs
from pixelforge.core.types import TRANSPARENT_INDEX
from pixelforge.export.png import surface_to_rgba
from pixelforge.guard.ast_rules import check_ast_file, infer_scope

ROOT_DIR = Path(__file__).resolve().parents[3]
PREFABS_DIR = ROOT_DIR / "src" / "pixelforge" / "core" / "prefabs"


def _render_all_prefabs(asset: Asset) -> None:
    p = asset.pal
    prefabs.iso_room_shell(
        asset,
        80,
        84,
        56,
        28,
        38,
        floor=p.FLOOR,
        left_wall=p.WALL_L,
        right_wall=p.WALL_R,
        floor_alt=p.FLOOR_D,
        baseboard=(p.WOOD_M, p.WOOD_D),
        wall_seam=p.FLOOR_D,
        outline=p.INK,
    )
    prefabs.iso_floor_pattern(asset, 80, 84, 56, 28, color=p.FLOOR_D, step=16, mode="tiles")
    prefabs.iso_window(
        asset,
        (36, 40),
        (60, 28),
        (36, 62),
        frame=p.METAL_M,
        sky=p.SKY,
        outline=p.INK,
        sky_alt=p.METAL_H,
        mullion=p.METAL_M,
        sill=p.WOOD_M,
    )
    prefabs.wall_vent(
        asset,
        (92, 34),
        (106, 41),
        (92, 46),
        frame=p.METAL_M,
        slat=p.INK,
        outline=p.INK,
        slats=3,
    )
    prefabs.wall_panel(
        asset,
        (114, 42),
        (126, 48),
        (114, 62),
        frame=p.METAL_H,
        recess=p.METAL_D,
        slot=p.INK,
        outline=p.INK,
        status_led=p.LED,
    )
    prefabs.wall_poster(
        asset,
        (64, 30),
        (76, 24),
        (64, 44),
        border=p.WOOD_M,
        fill=p.METAL_H,
        accent=p.LED,
        outline=p.INK,
    )
    prefabs.contact_shadow(asset, 74, 86, 18, 8, color=p.FLOOR_D, dither_ratio=0.5)
    prefabs.iso_desk(
        asset,
        74,
        74,
        24,
        24,
        leg_h=12,
        top_h=4,
        top=p.WOOD_L,
        left=p.WOOD_M,
        right=p.WOOD_D,
        leg_top=p.METAL_M,
        leg_left=p.METAL_D,
        leg_right=p.INK,
        outline=p.INK,
        highlight=p.WOOD_L,
        mat_color=p.METAL_D,
    )
    prefabs.iso_rack(
        asset,
        112,
        88,
        14,
        14,
        22,
        top=p.METAL_H,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        bay_color=p.INK,
        led_color=p.LED,
        bays=3,
    )
    prefabs.iso_shelf(
        asset,
        44,
        84,
        14,
        14,
        20,
        shelves=3,
        top=p.WOOD_L,
        left=p.WOOD_M,
        right=p.WOOD_D,
        post=p.METAL_D,
        outline=p.INK,
    )
    prefabs.iso_cable_run(
        asset,
        ((82, 82), (96, 89), (104, 89)),
        color=p.INK,
        highlight=p.METAL_M,
    )
    prefabs.iso_raised_floor(
        asset,
        80,
        92,
        24,
        12,
        step_h=3,
        top=p.METAL_M,
        left=p.METAL_D,
        right=p.INK,
        grid_color=p.FLOOR_D,
        outline=p.INK,
    )
    prefabs.iso_rug(
        asset,
        62,
        90,
        16,
        8,
        fill=p.WOOD_M,
        border=p.WOOD_L,
        pattern=p.WOOD_D,
        fringe=p.CLOUD,
        outline=p.INK,
    )
    prefabs.iso_door(
        asset,
        (108, 42),
        (120, 48),
        (108, 70),
        frame=p.WOOD_D,
        panel=p.WOOD_M,
        recess=p.WOOD_D,
        handle=p.SUN,
        outline=p.INK,
        window=p.SKY,
        threshold=p.METAL_D,
    )
    prefabs.iso_cable_tray(
        asset, (28, 30), (64, 18), rail=p.METAL_M, rung=p.METAL_D, width=3, outline=p.INK
    )
    prefabs.window_blinds(
        asset,
        (36, 40),
        (60, 28),
        (36, 62),
        slat=p.METAL_H,
        shadow=p.METAL_D,
        cord=p.INK,
    )
    prefabs.window_curtains(
        asset,
        (36, 40),
        (60, 28),
        (36, 62),
        fabric=p.WOOD_M,
        fold=p.WOOD_D,
        rod=p.METAL_D,
        outline=p.INK,
    )
    prefabs.iso_chair(
        asset,
        64,
        84,
        top=p.METAL_M,
        left=p.METAL_D,
        right=p.INK,
        back=p.METAL_M,
        leg=p.INK,
        outline=p.INK,
    )
    prefabs.iso_wall_shelf(
        asset,
        (86, 26),
        (102, 34),
        (86, 30),
        top=p.WOOD_L,
        front=p.WOOD_D,
        bracket=p.INK,
        outline=p.INK,
    )
    prefabs.iso_bed(
        asset,
        42,
        68,
        frame=p.WOOD_L,
        frame_left=p.WOOD_M,
        frame_right=p.WOOD_D,
        mattress=p.CLOUD,
        blanket=p.SKY,
        blanket_shade=p.SKY_DARK,
        pillow=p.METAL_H,
        outline=p.INK,
    )
    prefabs.iso_workbench(
        asset,
        118,
        74,
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
    prefabs.iso_drawer_unit(
        asset,
        96,
        76,
        top=p.METAL_H,
        left=p.METAL_M,
        right=p.METAL_D,
        drawer_face=p.FLOOR_D,
        handle=p.SUN,
        outline=p.INK,
    )
    prefabs.wall_ac_unit(
        asset,
        (88, 16),
        (106, 25),
        (88, 22),
        body=p.CLOUD,
        shade=p.METAL_M,
        vent=p.INK,
        outline=p.INK,
        led=p.LED,
    )
    prefabs.wall_whiteboard(
        asset,
        (56, 24),
        (74, 15),
        (56, 38),
        frame=p.METAL_D,
        board=p.CLOUD,
        marker=p.SKY_DARK,
        accent=p.SUN,
        tray=p.METAL_M,
        outline=p.INK,
    )
    prefabs.power_strip(
        asset, (54, 96), (68, 102), body=p.METAL_H, socket=p.INK, switch=p.LED, outline=p.INK
    )
    prefabs.wall_outlet(
        asset, (74, 54), (78, 56), (74, 60), plate=p.CLOUD, socket=p.INK, outline=p.INK
    )
    prefabs.iso_cable_catenary(asset, (36, 62), (62, 74), color=p.INK, sag=5, highlight=p.METAL_M)


def test_prefabs_reexported_and_deterministic(make_asset: Callable[..., Asset]) -> None:
    """Verify `pixelforge.prefabs` and `pixelforge.core.prefabs` match and are deterministic."""
    assert prefabs is core_prefabs

    first = make_asset()
    second = make_asset()
    _render_all_prefabs(first)
    _render_all_prefabs(second)

    assert np.array_equal(first.root_surface.data, second.root_surface.data)
    assert np.any(first.root_surface.data != TRANSPARENT_INDEX)


def test_prefabs_palette_closure_and_binary_alpha(make_asset: Callable[..., Asset]) -> None:
    """Verify all rendered pixels use valid palette indices and produce binary alpha."""
    asset = make_asset()
    _render_all_prefabs(asset)

    unique_indices = set(np.unique(asset.root_surface.data).tolist())
    allowed = {c.index for c in asset.style.palette} | {TRANSPARENT_INDEX}
    assert unique_indices <= allowed

    rgba = surface_to_rgba(asset.root_surface, asset.style)
    alpha_values = set(np.unique(rgba[:, :, 3]).tolist())
    assert alpha_values <= {0, 255}


def test_prefabs_bounds_safety_and_layer_compatibility(make_asset: Callable[..., Asset]) -> None:
    """Verify prefabs clip safely on tiny/OOB surfaces and compose cleanly inside Layers."""
    tiny = make_asset(width=16, height=16)
    p = tiny.pal
    with tiny.layer("oob", offset=(-8, -8), outline=p.INK) as layer:
        prefabs.iso_room_shell(
            layer,
            8,
            10,
            12,
            6,
            10,
            floor=p.FLOOR,
            left_wall=p.WALL_L,
            right_wall=p.WALL_R,
        )
        prefabs.iso_desk(
            layer,
            8,
            8,
            12,
            12,
            top=p.WOOD_L,
            left=p.WOOD_M,
            right=p.WOOD_D,
            leg_top=p.METAL_M,
            leg_left=p.METAL_D,
            leg_right=p.INK,
        )
        prefabs.contact_shadow(layer, 8, 12, 10, 5, color=p.FLOOR_D, dither_ratio=0.5)
        prefabs.iso_cable_run(layer, ((0, 0), (24, 24)), color=p.INK)

    assert tiny.root_surface.data.shape == (16, 16)
    assert np.any(tiny.root_surface.data != TRANSPARENT_INDEX)


def test_prefabs_pass_core_ast_guard_rules() -> None:
    """Verify every module under `src/pixelforge/core/prefabs/` passes `core` AST guards."""
    py_files = sorted(PREFABS_DIR.rglob("*.py"))
    assert len(py_files) == 36
    for path in py_files:
        assert infer_scope(path) == "core"
        violations = check_ast_file(path, scope="core")
        assert violations == [], f"AST guard violations in {path}: {violations}"
