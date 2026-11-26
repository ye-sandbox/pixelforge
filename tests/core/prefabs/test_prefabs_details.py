"""Hermetic tests for shadows, reflections, cables, and wall decor detail prefabs."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from pixelforge import Asset, AssetSpec, StylePack, prefabs
from pixelforge.core.types import TRANSPARENT_INDEX


def test_cast_shadow_respects_lighting_angle(make_style: Callable[[], StylePack]) -> None:
    """Verify `cast_shadow` projects away from the configured `lighting_angle`."""
    for angle, expected_side in (("top-left", "right"), ("top-right", "left"), ("top", "center")):
        style = make_style().model_copy(update={"lighting_angle": angle})
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


def test_floor_reflection_uses_style_reflections_lut(make_style: Callable[[], StylePack]) -> None:
    """Verify `floor_reflection` maps source tokens through `StylePack.reflections`."""
    style = make_style().model_copy(update={"reflections": {"SUN": "WOOD_L", "LED": "SKY"}})
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


def test_cable_catenary_sag(make_asset: Callable[..., Asset]) -> None:
    """Verify `iso_cable_catenary` sags below the straight chord."""
    cat_asset = make_asset(64, 48)
    prefabs.iso_cable_catenary(cat_asset, (10, 20), (50, 20), color=cat_asset.pal.INK, sag=8)
    assert np.any(cat_asset.root_surface.data[26:30, 25:35] == cat_asset.pal.INK)


def test_wall_decor_and_emissive_detail_prefabs(make_asset: Callable[..., Asset]) -> None:
    """Verify wall decor and emissive detail prefabs render deterministically."""

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

    first = make_asset(120, 84)
    second = make_asset(120, 84)
    _render_wall_details(first)
    _render_wall_details(second)

    assert np.array_equal(first.root_surface.data, second.root_surface.data)
    assert np.any(first.root_surface.data == first.pal.LED)
    assert np.any(first.root_surface.data == first.pal.SUN)
    valid_indices = {c.index for c in first.style.palette} | {TRANSPARENT_INDEX}
    assert set(np.unique(first.root_surface.data).tolist()).issubset(valid_indices)
