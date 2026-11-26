"""Isometric potted desk plant micro-prop (`20x24` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="potted_plant_iso",
    style_id="homelab-16bit",
    width=20,
    height=24,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=503,
)


def _draw_pot(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        10,
        20,
        4,
        4,
        5,
        top=p.WOOD_D,
        left=p.COPPER,
        right=p.WARM_AMBER,
        outline=p.INK,
        highlight=p.WOOD_L,
        anchor="bottom",
    )
    a.iso_tile(10, 14, 5, p.COPPER, height=2)
    a.iso_tile(10, 14, 3, p.VOID, height=1)


def _draw_foliage(a: Asset, p: PaletteLookup) -> None:
    is_night = a.state == "night"
    dark_leaf = p.PCB_D
    mid_leaf = p.LED_GD if is_night else p.PCB_G
    light_leaf = p.PCB_G if is_night else p.SHIRT_EMER

    with a.layer("foliage", outline=p.INK):
        a.ellipse(10, 11, 5, 3, dark_leaf)
        a.ellipse(7, 9, 3, 2, mid_leaf)
        a.ellipse(13, 10, 3, 2, mid_leaf)
        a.ellipse(10, 7, 3, 3, mid_leaf)
        a.rect(9, 5, 2, 2, light_leaf)
        a.rect(6, 8, 2, 2, light_leaf)


def render(a: Asset) -> None:
    """Render the `potted_plant_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_pot(a, p)
    _draw_foliage(a, p)

    a.anchor("mount_bottom", 10, 20)
    a.anchor("canopy", 10, 8)
    a.hitbox("body", 4, 3, 13, 19)
