"""Unit tests for vectorized 16-tile and 47-tile blob autotile generators."""

from __future__ import annotations

import numpy as np
import pytest

from pixelforge.core import (
    BLOB47_MASKS,
    BLOB_E,
    BLOB_N,
    BLOB_NE,
    BLOB_NW,
    BLOB_S,
    BLOB_SE,
    BLOB_SW,
    BLOB_W,
    CARDINAL16_MASKS,
    CARDINAL_E,
    CARDINAL_N,
    CARDINAL_S,
    CARDINAL_W,
    TRANSPARENT_INDEX,
    Asset,
    AssetSpec,
    AutotileStyle,
    IndexedSurface,
    PaletteColor,
    StylePack,
    autotile_cables,
    autotile_floors,
    autotile_terrain,
    autotile_walls,
    canonical_blob47_masks,
    compute_grid_bitmasks,
    reduce_blob_mask,
    render_autotile_cell,
)


def _style() -> StylePack:
    return StylePack(
        id="tile-test",
        perspective="top-down",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="INK", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="FILL", hex="#2a3444", flags=("surface",)),
            PaletteColor(index=2, name="HIGH", hex="#4d5d73", flags=("bright",)),
            PaletteColor(index=3, name="SHAD", hex="#18202c", flags=("shadow",)),
            PaletteColor(index=4, name="DETAIL", hex="#39d353", flags=("accent",)),
        ),
    )


def _tile_style() -> AutotileStyle:
    return AutotileStyle(
        fill=1,
        edge=0,
        highlight=2,
        shadow=3,
        detail=4,
        inner_corner=0,
    )


def test_canonical_blob47_and_cardinal16_masks() -> None:
    assert len(CARDINAL16_MASKS) == 16
    assert len(BLOB47_MASKS) == 47
    assert canonical_blob47_masks() == BLOB47_MASKS
    assert 0 in BLOB47_MASKS
    assert 255 in BLOB47_MASKS

    # Diagonal bit NE is stripped unless both N and E are present.
    assert reduce_blob_mask(BLOB_NE) == 0
    assert reduce_blob_mask(BLOB_N | BLOB_NE) == BLOB_N
    assert reduce_blob_mask(BLOB_N | BLOB_E | BLOB_NE) == (BLOB_N | BLOB_E | BLOB_NE)
    assert reduce_blob_mask(BLOB_SW | BLOB_NW | BLOB_SE) == 0


def test_compute_grid_bitmasks_cardinal16_and_blob47() -> None:
    grid = np.array(
        [
            [True, True, False],
            [True, True, True],
            [False, True, False],
        ],
        dtype=bool,
    )
    card = compute_grid_bitmasks(grid, mode="cardinal16")
    assert card[0, 0] == (CARDINAL_E | CARDINAL_S)
    assert card[0, 2] == -1
    assert card[1, 1] == (CARDINAL_N | CARDINAL_E | CARDINAL_S | CARDINAL_W)
    assert card[2, 1] == CARDINAL_N

    blob = compute_grid_bitmasks(grid, mode="blob47")
    assert blob[0, 0] == (BLOB_E | BLOB_SE | BLOB_S)
    assert blob[0, 2] == -1
    # Center (1,1) has all 4 cardinals and only NW diagonal (0,0) occupied.
    assert blob[1, 1] == (BLOB_N | BLOB_E | BLOB_S | BLOB_W | BLOB_NW)
    assert blob[1, 2] == BLOB_W
    # Every occupied mask must belong to canonical BLOB47_MASKS.
    occupied_masks = {int(v) for v in blob[grid]}
    assert occupied_masks.issubset(set(BLOB47_MASKS))


def test_compute_grid_bitmasks_wrap_and_validation() -> None:
    grid = np.array(
        [
            [True, False, True],
            [False, False, False],
        ],
        dtype=bool,
    )
    wrapped = compute_grid_bitmasks(grid, mode="cardinal16", wrap=True)
    assert wrapped[0, 0] == CARDINAL_W
    assert wrapped[0, 2] == CARDINAL_E

    with pytest.raises(ValueError, match="2D"):
        compute_grid_bitmasks(np.array([True, False]))


def test_autotile_generators_render_deterministically() -> None:
    style = _style()
    tstyle = _tile_style()

    wall_spec = AssetSpec(id="w", style_id=style.id, width=128, height=96, perspective="top-down")
    a1 = Asset(wall_spec, style)
    a2 = Asset(wall_spec, style)
    tm1 = autotile_walls(a1, tstyle, tile_w=16, tile_h=16, mode="blob47", columns=8)
    tm2 = autotile_walls(a2, tstyle, tile_w=16, tile_h=16, mode="blob47", columns=8)
    assert tm1 == tm2
    assert len(tm1.bitmasks) == 47
    assert np.array_equal(a1.surface.data, a2.surface.data)

    # Floors, terrain, and cables render without error and preserve palette closure.
    floor_surf = IndexedSurface(64, 64)
    tm_floor = autotile_floors(floor_surf, tstyle, mode="cardinal16", columns=4)
    assert len(tm_floor.bitmasks) == 16
    assert int(floor_surf.data.max()) <= 4

    terrain_surf = IndexedSurface(128, 96)
    tm_terrain = autotile_terrain(terrain_surf, tstyle, mode="blob47", columns=8)
    assert len(tm_terrain.bitmasks) == 47
    # Isolated terrain tile (mask=0 at col=0,row=0) has rounded transparent corners.
    assert terrain_surf.get(0, 0) == TRANSPARENT_INDEX

    cable_surf = IndexedSurface(64, 64)
    tm_cable = autotile_cables(cable_surf, tstyle, mode="cardinal16", columns=4)
    assert len(tm_cable.bitmasks) == 16
    # Isolated cable hub has transparent corners and center detail pixel.
    assert cable_surf.get(0, 0) == TRANSPARENT_INDEX
    assert cable_surf.get(8, 8) == 4


def test_render_autotile_cell_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        render_autotile_cell(0, 0, 16, kind="wall", style=_tile_style())
