"""47-tile blob autotile wall sheet for modular datacenter rooms."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge.core import (
    BLOB47_MASKS,
    Asset,
    AssetSpec,
    AutotileStyle,
    TilemapSpec,
    autotile_walls,
)

if TYPE_CHECKING:
    from styles.homelab_16bit_palette import Homelab16bitPalette

SPEC = AssetSpec(
    id="datacenter_wall_blob47",
    style_id="homelab-16bit",
    width=146,
    height=110,
    perspective="top-down",
    tilemap=TilemapSpec(
        mode="blob47",
        tile_width=16,
        tile_height=16,
        columns=8,
        rows=6,
        bitmasks=BLOB47_MASKS,
        terrain_name="wall",
        margin=2,
        spacing=2,
    ),
)


def render(a: Asset[Homelab16bitPalette]) -> None:
    """Render all 47 canonical blob autotile wall variants in an 8x6 grid."""
    p = a.pal
    with a.layer("walls"):
        autotile_walls(
            a,
            AutotileStyle(
                fill=p.WALL_M,
                edge=p.INK,
                highlight=p.WALL_L,
                shadow=p.WALL_D,
                detail=p.METAL_D,
                inner_corner=p.INK,
            ),
            tile_w=16,
            tile_h=16,
            mode="blob47",
            columns=8,
            margin=2,
            spacing=2,
            seed=a.seed,
        )
