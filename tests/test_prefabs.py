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
