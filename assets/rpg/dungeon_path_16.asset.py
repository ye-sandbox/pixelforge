"""16-tile cardinal autotile dungeon stone path sheet for `topdown-rpg`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge.core import (
    CARDINAL16_MASKS,
    Asset,
    AssetSpec,
    AutotileStyle,
    TilemapSpec,
    autotile_cables,
)

if TYPE_CHECKING:
    from styles.topdown_rpg_palette import TopdownRpgPalette

SPEC = AssetSpec(
    id="dungeon_path_16",
    style_id="topdown-rpg",
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
        terrain_name="dungeon_path",
    ),
    seed=303,
)


def render(a: Asset[TopdownRpgPalette]) -> None:
    """Render 16 cardinal stone-rimmed dungeon path tiles in a 4x4 grid."""
    p = a.pal
    with a.layer("paths"):
        autotile_cables(
            a,
            AutotileStyle(
                fill=p.STONE_M,
                edge=p.INK,
                highlight=p.STONE_H,
                shadow=p.STONE_D,
                detail=p.RUNE_GOLD,
            ),
            tile_w=16,
            tile_h=16,
            mode="cardinal16",
            columns=4,
            seed=a.seed,
        )
