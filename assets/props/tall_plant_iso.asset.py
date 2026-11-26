"""Isometric tall potted floor plant micro-prop (`24x38` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="tall_plant_iso",
    style_id="homelab-16bit",
    width=24,
    height=38,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=517,
)


def _draw_planter(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        12,
        35,
        6,
        6,
        8,
        top=p.WOOD_D,
        left=p.COPPER,
        right=p.WARM_AMBER,
        outline=p.INK,
        highlight=p.WOOD_L,
        anchor="bottom",
    )
    a.iso_tile(12, 26, 7, p.COPPER, height=2)
    a.iso_tile(12, 26, 4, p.VOID, height=1)


def _draw_stems_and_leaves(a: Asset, p: PaletteLookup) -> None:
    is_night = a.state == "night"
    dark_leaf = p.PCB_D
    mid_leaf = p.LED_GD if is_night else p.PCB_G
    light_leaf = p.PCB_G if is_night else p.SHIRT_EMER

    with a.layer("foliage", outline=p.INK):
        # Stems
        a.line(12, 25, 12, 10, p.WOOD_D)
        a.line(12, 20, 7, 14, p.WOOD_D)
        a.line(12, 18, 17, 13, p.WOOD_D)
        # Canopy fronds
        a.ellipse(12, 15, 6, 4, dark_leaf)
        a.ellipse(7, 13, 4, 2, mid_leaf)
        a.ellipse(17, 12, 4, 2, mid_leaf)
        a.ellipse(12, 8, 5, 3, mid_leaf)
        a.rect(10, 6, 3, 2, light_leaf)
        a.rect(5, 11, 2, 2, light_leaf)
        a.rect(16, 10, 2, 2, light_leaf)


def render(a: Asset) -> None:
    """Render the `tall_plant_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_planter(a, p)
    _draw_stems_and_leaves(a, p)
    a.anchor("mount_bottom", 12, 35)
    a.anchor("canopy", 12, 10)
    a.hitbox("body", 2, 4, 20, 33)
