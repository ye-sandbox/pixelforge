"""Tests for deterministic gameplay semantics derivation (`Asset`, `Layer`, `Tilemap`, `Scene`)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pixelforge.core import (
    CARDINAL16_MASKS,
    Asset,
    AssetSpec,
    AutotileStyle,
    PaletteColor,
    SemanticGrid,
    StylePack,
    TilemapSpec,
    autotile_walls,
    derive_gameplay_semantics,
)


def _style() -> StylePack:
    return StylePack(
        id="sem-test",
        perspective="front-2.5d",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="INK", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="WALL", hex="#30363d", flags=("surface",)),
            PaletteColor(index=2, name="FLOOR", hex="#1f2937", flags=("surface",)),
            PaletteColor(index=3, name="ROOF", hex="#4b5563", flags=("bright",)),
            PaletteColor(index=4, name="GLOW", hex="#58a6ff", flags=("emissive",)),
        ),
    )


def test_semantic_grid_validation() -> None:
    with pytest.raises(ValidationError, match="does not match"):
        SemanticGrid(cell_width=8, cell_height=8, columns=2, rows=2, cells=(0, 1, 0))

    with pytest.raises(ValidationError, match="must be 0 or 1"):
        SemanticGrid(cell_width=8, cell_height=8, columns=2, rows=2, cells=(0, 2, 0, 1))


def test_derive_semantics_from_layers_hitboxes_and_anchors() -> None:
    style = _style()
    spec = AssetSpec(
        id="kiosk",
        style_id="sem-test",
        width=32,
        height=32,
        perspective="front-2.5d",
    )
    a = Asset(spec, style)
    with a.layer("floor"):
        a.rect(0, 16, 32, 16, a.pal["FLOOR"])
    with a.layer("walls"):
        a.rect(8, 16, 16, 8, a.pal["WALL"])
    with a.layer("roof"):
        a.rect(8, 2, 16, 14, a.pal["ROOF"])
    a.anchor("base", 16, 24, kind="pivot")
    a.anchor("terminal_btn", 16, 20, kind="interact")

    semantics = derive_gameplay_semantics(
        spec,
        a.root_surface,
        anchors=a.anchors,
        hitboxes=a.hitboxes,
        layer_spans=a.layer_spans,
    )

    assert semantics.y_sort_pivot.x == 16
    assert semantics.y_sort_pivot.y == 24
    assert semantics.collision_grid.columns == 4
    assert semantics.collision_grid.rows == 4
    # Row 2 (y=16..23), cols 1..2 (x=8..23) are colliding; row 3 (y=24..31) is walkable floor
    assert semantics.collision_grid.cells[2 * 4 + 1] == 1
    assert semantics.collision_grid.cells[2 * 4 + 2] == 1
    assert semantics.collision_grid.cells[3 * 4 + 0] == 0
    assert semantics.walkable_mask.cells[3 * 4 + 0] == 1
    assert semantics.walkable_mask.cells[2 * 4 + 1] == 0

    assert len(semantics.occlusion_zones) == 1
    assert semantics.occlusion_zones[0].name == "roof"
    assert (
        semantics.occlusion_zones[0].x,
        semantics.occlusion_zones[0].y,
        semantics.occlusion_zones[0].w,
        semantics.occlusion_zones[0].h,
    ) == (8, 2, 16, 14)

    assert len(semantics.interact_zones) == 1
    assert semantics.interact_zones[0].name == "terminal_btn"
    assert semantics.interact_zones[0].kind == "interact"


def test_derive_semantics_fallback_footprint_and_upper_occlusion() -> None:
    style = _style()
    spec = AssetSpec(
        id="pillar",
        style_id="sem-test",
        width=24,
        height=32,
        perspective="front-2.5d",
    )
    a = Asset(spec, style)
    a.rect(6, 4, 12, 24, a.pal["WALL"])

    semantics = derive_gameplay_semantics(spec, a.root_surface)
    assert semantics.y_sort_pivot.x == 12
    assert semantics.y_sort_pivot.y == 28
    # Fallback base footprint marks bottom row of sprite as collision
    assert sum(semantics.collision_grid.cells) > 0
    assert any(z.name == "upper_silhouette" for z in semantics.occlusion_zones)


def test_derive_semantics_for_wall_tilemap() -> None:
    style = _style()
    spec = AssetSpec(
        id="wall_tiles",
        style_id="sem-test",
        width=64,
        height=64,
        perspective="top-down",
        tilemap=TilemapSpec(
            mode="cardinal16",
            tile_width=16,
            tile_height=16,
            columns=4,
            rows=4,
            bitmasks=CARDINAL16_MASKS,
            terrain_name="wall",
        ),
    )
    a = Asset(spec, style)
    autotile_walls(
        a,
        AutotileStyle(fill=1, edge=0, highlight=3, shadow=2),
        tile_w=16,
        tile_h=16,
        mode="cardinal16",
        columns=4,
    )

    semantics = derive_gameplay_semantics(spec, a.root_surface)
    assert semantics.collision_grid.cell_width == 16
    assert semantics.collision_grid.cell_height == 16
    assert semantics.collision_grid.columns == 4
    assert semantics.collision_grid.rows == 4
    assert all(cell == 1 for cell in semantics.collision_grid.cells)
    assert all(cell == 0 for cell in semantics.walkable_mask.cells)
