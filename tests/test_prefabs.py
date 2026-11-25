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
    assert len(py_files) == 4
    for path in py_files:
        assert infer_scope(path) == "core"
        violations = check_ast_file(path, scope="core")
        assert violations == [], f"AST guard violations in {path}: {violations}"
