"""16-tile cardinal autotile conduit/cable sheet for datacenter floor routing."""

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
    from styles.homelab_16bit_palette import Homelab16bitPalette

SPEC = AssetSpec(
    id="datacenter_cables_16",
    style_id="homelab-16bit",
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
        terrain_name="cable",
    ),
)


def render(a: Asset[Homelab16bitPalette]) -> None:
    """Render all 16 cardinal cable bitmask tiles in a 4x4 grid."""
    p = a.pal
    with a.layer("cables"):
        autotile_cables(
            a,
            AutotileStyle(
                fill=p.PCB_G,
                edge=p.INK,
                highlight=p.NEON_G,
                shadow=p.PCB_D,
                detail=p.LED_C,
            ),
            tile_w=16,
            tile_h=16,
            mode="cardinal16",
            columns=4,
            seed=a.seed,
        )
