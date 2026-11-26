"""Isometric headphones stand micro-prop (`18x24` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="headphones_stand_iso",
    style_id="homelab-16bit",
    width=18,
    height=24,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=514,
)


def _draw_stand(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        9,
        21,
        5,
        5,
        2,
        top=p.METAL_L,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        highlight=p.METAL_H,
        anchor="bottom",
    )
    with a.layer("stem", outline=p.INK):
        a.line(9, 18, 9, 6, p.METAL_M)
        a.rect(7, 5, 5, 2, p.METAL_H)


def _draw_headphones(a: Asset, p: PaletteLookup) -> None:
    band_col = p.METAL_D if a.state == "night" else p.METAL_L
    cup_col = p.SHIRT_IND if a.state == "night" else p.SOLAR_B
    with a.layer("headphones", outline=p.INK):
        # Curved headband
        a.line(6, 6, 12, 6, band_col)
        a.line(5, 7, 5, 11, band_col)
        a.line(13, 7, 13, 11, band_col)
        # Earcups
        a.rect(4, 11, 3, 4, cup_col)
        a.rect(11, 11, 3, 4, cup_col)
        a.rect(6, 12, 1, 2, p.VOID)
        a.rect(11, 12, 1, 2, p.VOID)


def render(a: Asset) -> None:
    """Render the `headphones_stand_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_stand(a, p)
    _draw_headphones(a, p)
    a.anchor("mount_bottom", 9, 21)
    a.anchor("top", 9, 5)
    a.hitbox("body", 3, 3, 12, 20)
