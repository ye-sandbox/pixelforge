"""Hermetic tests for atmospheric, celestial, weather, and light-spill prefabs."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from pixelforge import Asset, prefabs
from pixelforge.core.types import TRANSPARENT_INDEX


def test_window_pane_clipping_and_mullion_integrity(make_asset: Callable[..., Asset]) -> None:
    """Verify oversized atmospheric primitives never bleed outside glass or overwrite mullions."""
    iso_asset = make_asset(width=96, height=80)
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

    assert iso_asset.get(5, 5) == p.WALL_L
    assert iso_asset.get(18, 22) == p.WALL_L
    assert iso_asset.get(70, 50) == p.WALL_L
    with iso_asset.plane(win_p0, win_p1, win_p2) as check_plane:
        mx, my = check_plane.project(0.5, 0.5)
        assert iso_asset.get(mx, my) == p.METAL_H

    front_asset = make_asset(width=64, height=48)
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


def test_atmosphere_weather_loops_and_day_night_cycle(make_asset: Callable[..., Asset]) -> None:
    """Verify periodic weather loops, crescent moon, horizon modes, and day-night cycle."""
    for fn_name in ("rain", "snow", "clouds"):
        a0 = make_asset(width=48, height=36)
        a_mid = make_asset(width=48, height=36)
        a1 = make_asset(width=48, height=36)
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

    cloud_probe = make_asset(width=64, height=48)
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

    probe = make_asset(width=64, height=64)
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
    assert pp.LED not in set(np.unique(probe.root_surface.data[35:, :]).tolist())


def test_iso_window_legacy_compatibility(make_asset: Callable[..., Asset]) -> None:
    """Verify `iso_window` preserves legacy 1x2 layout when new optional args are omitted."""
    asset = make_asset(width=64, height=48)
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


def test_point_light_spill_radial_and_conical(make_asset: Callable[..., Asset]) -> None:
    """Verify conical `point_light_spill` illuminates only along the specified direction."""
    asset = make_asset(80, 60)
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
    assert not np.any(asset.root_surface.data[:, :38] == p.SUN)
    assert np.any(asset.root_surface.data[:, 41:56] == p.SUN)


def test_internal_atmospheric_and_telemetry_prefabs_loop_and_clip(
    make_asset: Callable[..., Asset],
) -> None:
    """Verify mountain/industrial horizons, lightning, condensation, motes, steam, and telemetry."""
    asset_a = make_asset(120, 90)
    asset_b = make_asset(120, 90)
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
    quiet = make_asset(40, 30)
    prefabs.weather_lightning(quiet, color=quiet.pal.CLOUD, phase=0.8, region=(4, 4, 20, 20))
    assert np.all(quiet.root_surface.data == TRANSPARENT_INDEX)

    quad_asset = make_asset(40, 30)
    prefabs.dust_motes(
        quad_asset,
        color=quad_asset.pal.SUN,
        count=20,
        points=((10, 5), (20, 5), (24, 20), (6, 20)),
    )
    assert np.all(quad_asset.root_surface.data[:, :5] == TRANSPARENT_INDEX)
