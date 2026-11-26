"""Hermetic unit, determinism, palette-closure, and AST guard tests for prefabs."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pixelforge import Asset, AssetSpec, PaletteColor, StylePack, prefabs
from pixelforge.core import prefabs as core_prefabs
from pixelforge.core.types import TRANSPARENT_INDEX
from pixelforge.export.png import surface_to_rgba
from pixelforge.guard.ast_rules import check_ast_file, infer_scope

ROOT_DIR = Path(__file__).resolve().parent.parent
PREFABS_DIR = ROOT_DIR / "src" / "pixelforge" / "core" / "prefabs"


def _make_style() -> StylePack:
    return StylePack(
        id="prefab-test",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="INK", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="FLOOR", hex="#3b4252", flags=("surface",)),
            PaletteColor(index=2, name="FLOOR_D", hex="#2e3440", flags=("shadow",)),
            PaletteColor(index=3, name="WALL_L", hex="#4c566a", flags=("surface",)),
            PaletteColor(index=4, name="WALL_R", hex="#434c5e", flags=("surface",)),
            PaletteColor(index=5, name="WOOD_L", hex="#d08770", flags=("bright",)),
            PaletteColor(index=6, name="WOOD_M", hex="#bf616a", flags=("surface",)),
            PaletteColor(index=7, name="WOOD_D", hex="#8f434a", flags=("shadow",)),
            PaletteColor(index=8, name="METAL_H", hex="#d8dee9", flags=("bright",)),
            PaletteColor(index=9, name="METAL_M", hex="#81a1c1", flags=("surface",)),
            PaletteColor(index=10, name="METAL_D", hex="#4c566a", flags=("shadow",)),
            PaletteColor(index=11, name="SKY", hex="#88c0d0", flags=("surface",)),
            PaletteColor(index=12, name="LED", hex="#a3be8c", flags=("emissive",)),
            PaletteColor(index=13, name="SKY_DARK", hex="#1b263b", flags=("surface",)),
            PaletteColor(index=14, name="SUN", hex="#ebcb8b", flags=("bright",)),
            PaletteColor(index=15, name="CLOUD", hex="#eceff4", flags=("bright",)),
        ),
    )


def _make_asset(width: int = 160, height: int = 120) -> Asset:
    spec = AssetSpec(
        id="prefab_probe",
        style_id="prefab-test",
        width=width,
        height=height,
        perspective="iso-2:1",
        states=("day",),
        seed=7,
    )
    return Asset(spec, _make_style())


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


def test_prefabs_reexported_and_deterministic() -> None:
    """Verify `pixelforge.prefabs` and `pixelforge.core.prefabs` match and are deterministic."""
    assert prefabs is core_prefabs

    first = _make_asset()
    second = _make_asset()
    _render_all_prefabs(first)
    _render_all_prefabs(second)

    assert np.array_equal(first.root_surface.data, second.root_surface.data)
    assert np.any(first.root_surface.data != TRANSPARENT_INDEX)


def test_prefabs_palette_closure_and_binary_alpha() -> None:
    """Verify all rendered pixels use valid palette indices and produce binary alpha."""
    asset = _make_asset()
    _render_all_prefabs(asset)

    unique_indices = set(np.unique(asset.root_surface.data).tolist())
    allowed = {c.index for c in asset.style.palette} | {TRANSPARENT_INDEX}
    assert unique_indices <= allowed

    rgba = surface_to_rgba(asset.root_surface, asset.style)
    alpha_values = set(np.unique(rgba[:, :, 3]).tolist())
    assert alpha_values <= {0, 255}


def test_prefabs_bounds_safety_and_layer_compatibility() -> None:
    """Verify prefabs clip safely on tiny/OOB surfaces and compose cleanly inside Layers."""
    tiny = _make_asset(width=16, height=16)
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
    py_files = sorted(PREFABS_DIR.glob("*.py"))
    assert len(py_files) == 5
    for path in py_files:
        assert infer_scope(path) == "core"
        violations = check_ast_file(path, scope="core")
        assert violations == [], f"AST guard violations in {path}: {violations}"


def test_window_pane_clipping_and_mullion_integrity() -> None:
    """Verify oversized atmospheric primitives never bleed outside glass or overwrite mullions."""
    iso_asset = _make_asset(width=96, height=80)
    p = iso_asset.pal
    iso_asset.clear(p.WALL_L)

    def _oversized_vista(pane: prefabs.ClippedPane) -> None:
        prefabs.sky_backdrop(pane, bands=(p.SKY_DARK, p.SKY))
        prefabs.sun(pane, 0.05, 0.05, radius=18, color=p.SUN, halo=p.CLOUD, rays=True)
        prefabs.moon(pane, 0.95, 0.95, radius=16, color=p.CLOUD, crater_color=p.METAL_D)
        prefabs.clouds(pane, color=p.CLOUD, shade_color=p.METAL_H, count=3, phase=0.25, seed=9)
        prefabs.horizon_silhouette(pane, color=p.INK, mode="city", seed=9)
        prefabs.weather_rain(pane, color=p.SKY, splash_color=p.CLOUD, count=24, phase=0.5, seed=9)

    win_p0, win_p1, win_p2 = (20, 22), (62, 1), (20, 58)
    prefabs.iso_window(
        iso_asset,
        win_p0,
        win_p1,
        win_p2,
        frame=p.METAL_M,
        sky=p.SKY_DARK,
        outline=p.INK,
        mullion=p.METAL_H,
        cols=2,
        rows=2,
        glint=p.CLOUD,
        scene=_oversized_vista,
    )

    # Outer wall outside the window bounding polygon must remain untouched `WALL_L`.
    assert iso_asset.get(5, 5) == p.WALL_L
    assert iso_asset.get(18, 22) == p.WALL_L
    assert iso_asset.get(70, 50) == p.WALL_L
    # Mullion intersection center pixel must remain `METAL_H` (not overwritten by sun/rain).
    with iso_asset.plane(win_p0, win_p1, win_p2) as check_plane:
        mx, my = check_plane.project(0.5, 0.5)
        assert iso_asset.get(mx, my) == p.METAL_H

    # Front-2.5d window clipping check
    front_asset = _make_asset(width=64, height=48)
    fp = front_asset.pal
    front_asset.clear(fp.WALL_R)
    prefabs.front_window(
        front_asset,
        12,
        6,
        40,
        32,
        frame=fp.METAL_M,
        sky=fp.SKY_DARK,
        outline=fp.INK,
        mullion=fp.METAL_H,
        cols=2,
        rows=2,
        glint=fp.CLOUD,
        sill=fp.WOOD_M,
        scene=_oversized_vista,
    )
    assert front_asset.get(0, 0) == fp.WALL_R
    assert front_asset.get(11, 10) == fp.WALL_R
    assert front_asset.get(53, 10) == fp.WALL_R
    assert front_asset.get(12, 6) == fp.INK
    assert front_asset.get(32, 22) == fp.METAL_H
    assert front_asset.get(11, 37) == fp.WOOD_M


def test_atmosphere_weather_loops_and_day_night_cycle() -> None:
    """Verify periodic weather loops, crescent moon, horizon modes, and day-night cycle."""
    # Seamless periodic wrapping: phase=0.0 and phase=1.0 must produce identical pixels.
    for fn_name in ("rain", "snow", "clouds"):
        a0 = _make_asset(width=48, height=36)
        a_mid = _make_asset(width=48, height=36)
        a1 = _make_asset(width=48, height=36)
        for idx, asset in enumerate((a0, a_mid, a1)):
            p = asset.pal
            phase = (0.0, 0.5, 1.0)[idx]
            with prefabs.clipped_pane(asset, (4, 4, 40, 28)) as pane:
                prefabs.sky_backdrop(pane, bands=(p.SKY_DARK, p.SKY), pattern="bayer4")
                if fn_name == "rain":
                    prefabs.weather_rain(
                        pane, color=p.CLOUD, splash_color=p.SUN, count=14, phase=phase, seed=42
                    )
                elif fn_name == "snow":
                    prefabs.weather_snow(
                        pane, color=p.CLOUD, alt_color=p.METAL_H, count=16, phase=phase, seed=42
                    )
                else:
                    prefabs.clouds(
                        pane, color=p.CLOUD, shade_color=p.METAL_H, count=2, phase=phase, seed=42
                    )

        assert np.array_equal(a0.root_surface.data, a1.root_surface.data)
        assert not np.array_equal(a0.root_surface.data, a_mid.root_surface.data)

    # Multi-cloud vistas must span distinct vertical bands rather than collapsing to one height
    cloud_probe = _make_asset(width=64, height=48)
    cp = cloud_probe.pal
    with prefabs.clipped_pane(cloud_probe, (2, 2, 60, 44)) as pane:
        prefabs.clouds(
            pane,
            color=cp.CLOUD,
            shade_color=cp.METAL_H,
            count=3,
            phase=0.15,
            min_v=0.12,
            max_v=0.68,
            seed=1601,
        )
    cloud_ys, _ = np.nonzero(
        (cloud_probe.root_surface.data == cp.CLOUD) | (cloud_probe.root_surface.data == cp.METAL_H)
    )
    assert cloud_ys.size > 0
    assert int(cloud_ys.max() - cloud_ys.min()) >= 14

    # Day-night cycle progression across phases
    steps = [
        prefabs.eval_day_night_cycle(
            ph,
            day_bands=(11, 14),
            dusk_bands=(13, 6),
            night_bands=(0, 13),
        )
        for ph in (0.15, 0.45, 0.70, 0.90)
    ]
    assert steps[0].celestial_kind == "sun" and steps[0].star_visibility == 0.0
    assert steps[1].celestial_kind == "sun" and steps[1].star_visibility > 0.0
    assert steps[2].celestial_kind == "moon" and steps[2].star_visibility == 1.0
    assert steps[3].celestial_kind == "sun" and steps[3].spill_intensity > steps[2].spill_intensity

    # Crescent moon, starfield, horizon modes, and light_beam
    probe = _make_asset(width=64, height=64)
    pp = probe.pal
    probe.rect(0, 0, 64, 64, pp.FLOOR)
    for mode in ("city", "rooftops", "hills", "trees"):
        with prefabs.clipped_pane(probe, (8, 4, 48, 30)) as pane:
            prefabs.day_night_cycle(
                pane,
                phase=0.72,
                day_bands=(pp.SKY, pp.CLOUD),
                dusk_bands=(pp.WOOD_M, pp.SUN),
                night_bands=(pp.SKY_DARK, pp.FLOOR_D),
                sun_color=pp.SUN,
                moon_color=pp.CLOUD,
                star_color=pp.LED,
                horizon_color=pp.INK,
                horizon_accent=pp.SUN,
                horizon_mode=mode,
                frame=1,
                frames=4,
                seed=11,
            )
            prefabs.moon(pane, 0.25, 0.25, radius=3, color=pp.CLOUD, crescent=True)

    prefabs.light_beam(
        probe,
        (8, 4, 48, 30),
        color=pp.WOOD_L,
        secondary_color=pp.FLOOR_D,
        dx=0,
        dy=18,
        spread=6,
    )
    unique_indices = set(np.unique(probe.root_surface.data).tolist())
    allowed = {c.index for c in probe.style.palette} | {TRANSPARENT_INDEX}
    assert unique_indices <= allowed
    # Verify non-emissive light_beam did not introduce emissive LED index onto floor below y=34.
    assert pp.LED not in set(np.unique(probe.root_surface.data[35:, :]).tolist())


def test_iso_window_legacy_compatibility() -> None:
    """Verify `iso_window` preserves legacy 1x2 layout when new optional args are omitted."""
    asset = _make_asset(width=64, height=48)
    p = asset.pal
    prefabs.iso_window(
        asset,
        (10, 14),
        (42, 0),
        (10, 38),
        frame=p.METAL_M,
        sky=p.SKY,
        outline=p.INK,
        sky_alt=p.CLOUD,
        mullion=p.METAL_D,
        sill=p.WOOD_M,
    )
    assert np.any(asset.root_surface.data == p.SKY)
    assert np.any(asset.root_surface.data == p.METAL_D)
    assert np.any(asset.root_surface.data == p.WOOD_M)


def test_iso_room_geometry_projections_and_spill() -> None:
    """Verify `IsoRoomGeometry` wall planes, floor points, non-clipping bounds, and spill."""
    import pytest

    asset = _make_asset(width=120, height=100)
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

    # Out-of-range coordinates clamp safely to [0, 1] without exceeding wall bounds.
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
    import pytest

    room = prefabs.IsoRoomGeometry(cx=160, cy=136, hw=112, hh=56, wall_h=74)

    # Matches bedroom_desk_iso exact right-wall placement (74x28 desk, leg_h+top_h=19, margin=1).
    rx, ry = room.wall_box_center("right", 74, 28, 19, along=0.0, margin=1, corner_margin=4)
    assert (rx, ry) == (186, 89)

    # Left-wall placement mirrors the right-wall placement across cx=160.
    lx, ly = room.wall_box_center("left", 28, 74, 19, along=0.0, margin=1, corner_margin=4)
    assert (lx, ly) == (134, 89)

    # Sliding along the wall shifts along the wall slope (+dx, +dy for right; -dx, +dy for left)
    # while keeping exact `margin` px vertical separation from the baseboard.
    r_start = room.wall_box_center("right", 40, 20, 0, along=0.0, margin=2, corner_margin=4)
    r_mid = room.wall_box_center("right", 40, 20, 0, along=0.5, margin=2, corner_margin=4)
    r_end = room.wall_box_center("right", 40, 20, 0, along=1.0, margin=2, corner_margin=4)
    assert r_start[0] < r_mid[0] < r_end[0]
    assert r_start[1] < r_mid[1] < r_end[1]

    # Verify floor top corner sits `margin` px vertically below the baseboard line.
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

    # Height `h` lifts only the vertical Y coordinate.
    assert room.wall_box_center("right", 40, 20, 18, along=0.5, margin=2) == (
        r_mid[0],
        r_mid[1] - 18,
    )

    # Oversized furniture clamps safely to the wall center without raising.
    oversized = room.wall_box_center("left", 20, 140, 10, along=0.25, margin=2, corner_margin=8)
    assert oversized[0] < room.cx

    with pytest.raises(ValueError, match="Unsupported wall side"):
        room.wall_box_center("front", 20, 20, 10)  # type: ignore[arg-type]


def test_furniture_slots_and_rack_front_styles() -> None:
    """Verify `iso_desk`, `iso_rack`, and `iso_shelf` slot helpers and rack front styles."""
    asset = _make_asset(width=160, height=120)
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


def test_point_light_spill_radial_and_conical() -> None:
    asset = _make_asset(80, 60)
    p = asset.pal
    asset.rect(0, 0, 80, 60, p.FLOOR, fill=True)
    prefabs.point_light_spill(
        asset,
        40,
        30,
        16,
        8,
        color=p.SUN,
        secondary_color=p.WOOD_L,
        direction=(1.0, 0.0),
        cone_cos=0.3,
    )
    # Conical spill pointing right (+x) should not illuminate left of center
    assert not np.any(asset.root_surface.data[:, :38] == p.SUN)
    assert np.any(asset.root_surface.data[:, 41:56] == p.SUN)


def test_cast_shadow_respects_lighting_angle() -> None:
    for angle, expected_side in (("top-left", "right"), ("top-right", "left"), ("top", "center")):
        style = _make_style().model_copy(update={"lighting_angle": angle})
        spec = AssetSpec(
            id="shadow_probe",
            style_id="prefab-test",
            width=64,
            height=48,
            perspective="iso-2:1",
            states=("day",),
            seed=1,
        )
        asset = Asset(spec, style)
        p = asset.pal
        prefabs.cast_shadow(asset, 32, 24, 4, 2, color=p.FLOOR_D, length=10, dither_ratio=1.0)
        if expected_side == "right":
            assert np.any(asset.root_surface.data[26:, 37:] == p.FLOOR_D)
        elif expected_side == "left":
            assert np.any(asset.root_surface.data[26:, :28] == p.FLOOR_D)
        else:
            assert np.any(asset.root_surface.data[26:, 28:37] == p.FLOOR_D)
            assert not np.any(asset.root_surface.data[:, 40:] == p.FLOOR_D)


def test_floor_reflection_uses_style_reflections_lut() -> None:
    style = _make_style().model_copy(update={"reflections": {"SUN": "WOOD_L", "LED": "SKY"}})
    spec = AssetSpec(
        id="refl_probe",
        style_id="prefab-test",
        width=32,
        height=32,
        perspective="front-2.5d",
        states=("day",),
        seed=2,
    )
    asset = Asset(spec, style)
    p = asset.pal
    asset.rect(0, 16, 32, 16, p.FLOOR, fill=True)
    asset.rect(8, 8, 8, 8, p.SUN, fill=True)
    prefabs.floor_reflection(asset, (8, 8, 8, 8), y_floor=16, dither_ratio=1.0)
    assert np.all(asset.root_surface.data[16:24, 8:16] == p.WOOD_L)


def test_internal_atmospheric_and_telemetry_prefabs_loop_and_clip() -> None:
    asset_a = _make_asset(120, 90)
    asset_b = _make_asset(120, 90)
    for asset, phase in ((asset_a, 0.0), (asset_b, 1.0)):
        p = asset.pal
        region = (12, 10, 32, 24)
        with prefabs.clipped_pane(asset, region) as pane:
            prefabs.sky_backdrop(pane, bands=(p.SKY_DARK, p.SKY))
            prefabs.horizon_silhouette(pane, color=p.FLOOR_D, accent=p.CLOUD, mode="mountains")
            prefabs.horizon_silhouette(
                pane, color=p.INK, accent=p.LED, mode="industrial", base_v=0.82
            )
            prefabs.weather_lightning(pane, color=p.CLOUD, glow_color=p.SKY, phase=0.1, seed=5)
            prefabs.window_condensation(
                pane, color=p.METAL_H, droplet_color=p.SKY, phase=phase, seed=5
            )
            prefabs.dust_motes(pane, color=p.SUN, alt_color=p.CLOUD, phase=phase, seed=5)
        prefabs.rising_steam(asset, 64, 50, color=p.CLOUD, alt_color=p.METAL_H, phase=phase, seed=5)
        with asset.plane(p0=(60, 12), p1=(96, 12), p2=(60, 36)) as screen:
            prefabs.screen_telemetry(
                screen,
                color=p.LED,
                bg_color=p.SKY_DARK,
                accent=p.SUN,
                mode="waveform",
                phase=phase,
                seed=5,
            )
        with prefabs.clipped_pane(asset, (60, 44, 36, 20)) as pane2:
            prefabs.screen_telemetry(
                pane2,
                color=p.LED,
                bg_color=p.SKY_DARK,
                accent=p.SUN,
                mode="bars",
                phase=phase,
                seed=6,
            )
            prefabs.screen_telemetry(pane2, color=p.CLOUD, mode="sparkline", phase=phase, seed=7)
            prefabs.screen_telemetry(pane2, color=p.SUN, mode="grid_scan", phase=phase, seed=8)

    assert np.array_equal(asset_a.root_surface.data, asset_b.root_surface.data)
    # Lightning inactive outside active_window
    quiet = _make_asset(40, 30)
    prefabs.weather_lightning(quiet, color=quiet.pal.CLOUD, phase=0.8, region=(4, 4, 20, 20))
    assert np.all(quiet.root_surface.data == TRANSPARENT_INDEX)
    # Dust motes clipped to 4-vertex quad
    quad_asset = _make_asset(40, 30)
    prefabs.dust_motes(
        quad_asset,
        color=quad_asset.pal.SUN,
        count=20,
        points=((10, 5), (20, 5), (24, 20), (6, 20)),
    )
    assert np.all(quad_asset.root_surface.data[:, :5] == TRANSPARENT_INDEX)


def test_room_fill_and_architectural_prefabs_contracts() -> None:
    """Verify [19.1] architectural, furniture, and detail prefabs render and return slots."""
    asset = _make_asset(128, 96)
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

    # Catenary cable should sag below the straight chord y=80
    cat_asset = _make_asset(64, 48)
    prefabs.iso_cable_catenary(cat_asset, (10, 20), (50, 20), color=cat_asset.pal.INK, sag=8)
    assert np.any(cat_asset.root_surface.data[26:30, 25:35] == cat_asset.pal.INK)


def test_subroom_and_partition_plane_mount_wall_prefabs() -> None:
    import pytest

    asset = _make_asset(180, 140)
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

    # Rectangular 2-room split preserves exact parent floor corners
    sub_left = geom.subroom(0.0, 0.0, 0.5, 1.0)
    assert sub_left.floor_point(0.0, 0.0) == geom.floor_point(0.0, 0.0)
    assert sub_left.floor_point(1.0, 0.0) == geom.floor_point(0.5, 0.0)
    assert sub_left.floor_point(0.0, 1.0) == geom.floor_point(0.0, 1.0)
    assert sub_left.floor_point(1.0, 1.0) == geom.floor_point(0.5, 1.0)

    # partition_plane at=0.0 matches outer wall planes
    assert geom.partition_plane("left", 0.0) == geom.left_wall_plane()
    assert geom.partition_plane("right", 0.0) == geom.right_wall_plane()

    # Mount existing wall prefabs onto an interior partition plane
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


def test_floor_zones_thresholds_partitions_pillars_and_molding() -> None:
    asset = _make_asset(180, 140)
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

    # Multi-zone floors: planks, tiles, grid, carpet, solid
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

    # Partition walls with rectangular and arched cutouts + glass partition + pillar + molding
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

    # Determinism check across two independent renders
    second = _make_asset(180, 140)
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
    first_check = _make_asset(180, 140)
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


def test_living_and_workstation_furniture_prefabs() -> None:
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

    first = _make_asset(180, 145)
    second = _make_asset(180, 145)
    _render_furniture(first)
    _render_furniture(second)

    assert np.array_equal(first.root_surface.data, second.root_surface.data)
    assert np.any(first.root_surface.data == first.pal.SKY)
    assert np.any(first.root_surface.data == first.pal.LED)
    valid_indices = {c.index for c in first.style.palette} | {TRANSPARENT_INDEX}
    assert set(np.unique(first.root_surface.data).tolist()).issubset(valid_indices)


def test_wall_decor_and_emissive_detail_prefabs() -> None:
    """Verify [24.1] wall decor and emissive detail prefabs render deterministically."""

    def _render_wall_details(asset: Asset) -> None:
        p = asset.pal
        prefabs.wall_light_switch(
            asset,
            (8, 12),
            (14, 15),
            (8, 22),
            plate=p.CLOUD,
            toggle=p.METAL_M,
            outline=p.INK,
            led=p.LED,
            double=True,
        )
        prefabs.wall_thermostat(
            asset,
            (18, 14),
            (26, 18),
            (18, 24),
            body=p.METAL_H,
            screen=p.SKY,
            readout=p.LED,
            dial=p.METAL_D,
            outline=p.INK,
        )
        prefabs.wall_clock(
            asset,
            (32, 10),
            (44, 16),
            (32, 24),
            frame=p.METAL_D,
            face=p.CLOUD,
            hands=p.INK,
            accent=p.SUN,
            outline=p.INK,
        )
        prefabs.wall_corkboard(
            asset,
            (50, 12),
            (74, 24),
            (50, 32),
            frame=p.WOOD_M,
            cork=p.WOOD_L,
            note=p.CLOUD,
            note_alt=p.SUN,
            pin=p.LED,
            outline=p.INK,
        )
        prefabs.wall_pegboard(
            asset,
            (80, 14),
            (104, 26),
            (80, 34),
            board=p.METAL_M,
            hole=p.INK,
            frame=p.METAL_D,
            hook=p.METAL_H,
            accent=p.SUN,
            outline=p.INK,
        )
        prefabs.wall_neon_sign(
            asset,
            (14, 42),
            (38, 54),
            (14, 54),
            glow=p.LED,
            backing=p.FLOOR_D,
            accent=p.SUN,
            outline=p.INK,
        )
        prefabs.led_strip(
            asset,
            (46, 54),
            (78, 70),
            color=p.LED,
            backing=p.INK,
            accent=p.SUN,
            segments=4,
        )
        prefabs.wall_sconce(
            asset,
            (86, 48),
            (96, 53),
            (86, 62),
            bracket=p.METAL_D,
            shade=p.METAL_H,
            bulb=p.SUN,
            glow=p.SUN,
            outline=p.INK,
        )

    first = _make_asset(120, 84)
    second = _make_asset(120, 84)
    _render_wall_details(first)
    _render_wall_details(second)

    assert np.array_equal(first.root_surface.data, second.root_surface.data)
    assert np.any(first.root_surface.data == first.pal.LED)
    assert np.any(first.root_surface.data == first.pal.SUN)
    valid_indices = {c.index for c in first.style.palette} | {TRANSPARENT_INDEX}
    assert set(np.unique(first.root_surface.data).tolist()).issubset(valid_indices)
