"""Hermetic unit and render tests for exterior foliage, tree, roof, and building prefabs."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from pixelforge import Asset, AssetSpec, PaletteColor, StylePack, prefabs
from pixelforge.cli.main import main
from pixelforge.core.types import TRANSPARENT_INDEX
from pixelforge.export.png import surface_to_rgba


def _second_style() -> StylePack:
    """Create a distinct 8-color `StylePack` to verify `StylePack`-agnosticism."""
    return StylePack(
        id="exterior-alt",
        perspective="front-2.5d",
        lighting_angle="top-right",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUT", hex="#101418", flags=("outline",)),
            PaletteColor(index=1, name="BARK", hex="#6b4423", flags=("surface",)),
            PaletteColor(index=2, name="LEAF_D", hex="#1e4d2b", flags=("shadow",)),
            PaletteColor(index=3, name="LEAF_M", hex="#2e7d32", flags=("surface",)),
            PaletteColor(index=4, name="LEAF_L", hex="#66bb6a", flags=("bright",)),
            PaletteColor(index=5, name="TILE_L", hex="#c62828", flags=("bright",)),
            PaletteColor(index=6, name="TILE_D", hex="#8e0000", flags=("shadow",)),
            PaletteColor(index=7, name="STONE", hex="#cfd8dc", flags=("surface",)),
        ),
    )


def test_foliage_cluster_clip_opaque_and_outline(make_asset: Callable[..., Asset]) -> None:
    """Verify `foliage_cluster` clips shading to opaque silhouette and applies `outline`."""
    plain = make_asset(48, 48)
    p = plain.pal
    prefabs.foliage_cluster(
        plain,
        24,
        24,
        10,
        7,
        fill=p.LED,
        highlight=p.SUN,
        shadow=p.FLOOR_D,
        outline=None,
        speckles=(p.SUN, p.FLOOR_D),
        seed=11,
    )
    used_plain = set(np.unique(plain.root_surface.data).tolist())
    assert used_plain <= {p.LED, p.SUN, p.FLOOR_D, TRANSPARENT_INDEX}
    assert p.INK not in used_plain
    assert np.any(plain.root_surface.data == p.SUN)
    assert np.any(plain.root_surface.data == p.FLOOR_D)

    outlined = make_asset(48, 48)
    prefabs.foliage_cluster(
        outlined,
        24,
        24,
        10,
        7,
        fill=p.LED,
        highlight=p.SUN,
        shadow=p.FLOOR_D,
        outline=p.INK,
        speckles=(p.SUN, p.FLOOR_D),
        seed=11,
    )
    assert np.any(outlined.root_surface.data == p.INK)
    # Outline pixels must only wrap the exterior without erasing interior shading.
    assert np.any(outlined.root_surface.data == p.LED)
    assert np.any(outlined.root_surface.data == p.SUN)
    # Interior shaded/fill pixels are identical where no outline was drawn.
    interior = outlined.root_surface.data != p.INK
    assert np.array_equal(
        outlined.root_surface.data[interior] != TRANSPARENT_INDEX,
        plain.root_surface.data[interior] != TRANSPARENT_INDEX,
    )


def test_iso_tree_species_determinism_and_layer_target(make_asset: Callable[..., Asset]) -> None:
    """Verify `iso_tree` renders `oak`, `pine`, `cypress` deterministically."""

    def _render_trees(asset: Asset) -> None:
        p = asset.pal
        oak = prefabs.iso_tree(
            asset,
            24,
            56,
            trunk=p.WOOD_M,
            trunk_lit=p.WOOD_L,
            foliage=p.LED,
            foliage_light=p.SUN,
            foliage_dark=p.FLOOR_D,
            outline=p.INK,
            shadow=p.FLOOR_D,
            species="oak",
            seed=5,
            emit_hitbox=True,
        )
        assert oak.foot == (24, 56)

        with asset.layer("pine_layer") as layer:
            pine = prefabs.iso_tree(
                layer,
                64,
                56,
                trunk=p.WOOD_M,
                foliage=p.LED,
                foliage_light=p.SUN,
                foliage_dark=p.FLOOR_D,
                outline=p.INK,
                species="pine",
                sway=1,
                seed=7,
            )
            assert pine.foot == (64, 56)

        cypress = prefabs.iso_tree(
            asset,
            100,
            56,
            trunk=p.WOOD_M,
            foliage=p.LED,
            foliage_light=p.SUN,
            foliage_dark=p.FLOOR_D,
            outline=p.INK,
            species="cypress",
            seed=9,
        )
        assert cypress.foot == (100, 56)

    first = make_asset(128, 72)
    second = make_asset(128, 72)
    _render_trees(first)
    _render_trees(second)

    assert np.array_equal(first.root_surface.data, second.root_surface.data)
    assert surface_to_rgba(first.root_surface, first.style).tobytes() == (
        surface_to_rgba(second.root_surface, second.style).tobytes()
    )
    assert len(first.anchors) == 3
    assert all(anchor.name == "foot" and anchor.kind == "ground" for anchor in first.anchors)
    assert len(first.hitboxes) == 1
    assert first.hitboxes[0].name == "trunk"


def test_pitched_roof_and_building_facade_perspectives(make_asset: Callable[..., Asset]) -> None:
    """Verify `pitched_roof` and `building_facade` in both `iso-2:1` and `front-2.5d`."""
    iso_asset = make_asset(128, 96)
    p = iso_asset.pal
    iso_anchors = prefabs.building_facade(
        iso_asset,
        52,
        36,
        32,
        24,
        wall=p.WALL_L,
        wall_shade=p.WALL_R,
        roof_lit=p.WOOD_L,
        roof_shade=p.WOOD_D,
        door_frame=p.WOOD_M,
        door_fill=p.WOOD_D,
        window_frame=p.METAL_M,
        window_sky=p.SKY,
        trim=p.CLOUD,
        outline=p.INK,
        perspective="iso-2:1",
        windows=2,
        door_side="left",
        roof_orientation="iso-left",
    )
    assert iso_anchors.roof_peak[1] < 36
    assert any(anchor.name == "foot" for anchor in iso_asset.anchors)
    assert np.any(iso_asset.root_surface.data == p.WOOD_L)
    assert np.any(iso_asset.root_surface.data == p.SKY)

    front_asset = make_asset(96, 80)
    fp = front_asset.pal
    with front_asset.layer("facade_layer") as layer:
        front_anchors = prefabs.building_facade(
            layer,
            20,
            26,
            48,
            34,
            wall=fp.WALL_L,
            roof_lit=fp.WOOD_L,
            roof_shade=fp.WOOD_D,
            door_frame=fp.WOOD_M,
            door_fill=fp.WOOD_D,
            window_frame=fp.METAL_M,
            window_sky=fp.SKY,
            trim=fp.CLOUD,
            outline=fp.INK,
            perspective="front-2.5d",
            windows=2,
            door_side="center",
        )
    assert front_anchors.foot == (44, 60)
    assert front_anchors.roof_peak[1] < 26
    assert np.any(front_asset.root_surface.data == fp.WOOD_L)
    assert np.any(front_asset.root_surface.data == fp.WOOD_D)


def test_exterior_prefabs_style_agnostic_and_inspect_category() -> None:
    """Verify exterior prefabs work with any `StylePack` and appear in `inspect prefabs`."""
    style = _second_style()
    spec = AssetSpec(
        id="ext_alt",
        style_id="exterior-alt",
        width=96,
        height=72,
        perspective="front-2.5d",
        states=("day",),
        seed=3,
    )
    asset = Asset(spec, style)
    p = asset.pal
    prefabs.iso_tree(
        asset,
        18,
        58,
        trunk=p.BARK,
        foliage=p.LEAF_M,
        foliage_light=p.LEAF_L,
        foliage_dark=p.LEAF_D,
        outline=p.OUT,
    )
    prefabs.pitched_roof(
        asset,
        42,
        28,
        36,
        24,
        12,
        lit_slope=p.TILE_L,
        shade_slope=p.TILE_D,
        trim=p.STONE,
        outline=p.OUT,
        shingle_step=3,
        orientation="front",
    )
    used = set(np.unique(asset.root_surface.data).tolist())
    assert used <= {0, 1, 2, 3, 4, 5, 6, 7, TRANSPARENT_INDEX}
    assert main(["inspect", "prefabs", "exterior"]) == 0
