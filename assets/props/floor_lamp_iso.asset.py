"""Isometric standing floor lamp micro-prop (`20x42` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="floor_lamp_iso",
    style_id="homelab-16bit",
    width=20,
    height=42,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=518,
)


def _draw_base_and_pole(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        10,
        39,
        6,
        6,
        2,
        top=p.METAL_L,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        highlight=p.METAL_H,
        anchor="bottom",
    )
    with a.layer("pole", outline=p.INK):
        a.line(10, 36, 10, 12, p.METAL_M)
        a.put(10, 24, p.METAL_H)


def _draw_shade(a: Asset, p: PaletteLookup) -> None:
    is_night = a.state == "night"
    shade_top = p.DUST_L if is_night else p.WHITE
    shade_l = p.WARM_LAMP if is_night else p.DUST_L
    shade_r = p.WARM_AMBER if is_night else p.DUST_D

    a.iso_box(
        10,
        13,
        6,
        6,
        6,
        top=shade_top,
        left=shade_l,
        right=shade_r,
        outline=p.INK,
        highlight=p.WHITE,
        anchor="bottom",
    )
    if is_night:
        a.rect(9, 13, 3, 2, p.WARM_LAMP)
        a.rect(8, 36, 5, 1, p.WARM_AMBER)


def render(a: Asset) -> None:
    """Render the `floor_lamp_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_base_and_pole(a, p)
    _draw_shade(a, p)
    a.anchor("mount_bottom", 10, 39)
    a.anchor("bulb", 10, 11)
    a.hitbox("body", 3, 3, 14, 38)
