"""Isometric coffee mug micro-prop (`16x18` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="coffee_mug_iso",
    style_id="homelab-16bit",
    width=16,
    height=18,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=506,
)


def _draw_mug(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        8,
        15,
        3,
        3,
        5,
        top=p.WHITE,
        left=p.WHITE,
        right=p.SMOKE,
        outline=p.INK,
        highlight=p.WHITE,
        anchor="bottom",
    )
    # Coffee surface inside rim
    a.iso_tile(8, 9, 2, p.WOOD_D, height=1)
    # Side handle
    with a.layer("handle", outline=p.INK):
        a.rect(11, 10, 2, 3, p.SMOKE)
        a.put(11, 11, p.INK)


def _draw_steam(a: Asset, p: PaletteLookup) -> None:
    steam_col = p.GLASS_L if a.state == "night" else p.SMOKE
    a.rect(7, 5, 1, 2, steam_col)
    a.rect(9, 4, 1, 2, steam_col)


def render(a: Asset) -> None:
    """Render the `coffee_mug_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_mug(a, p)
    _draw_steam(a, p)

    a.anchor("mount_bottom", 8, 15)
    a.anchor("rim", 8, 9)
    a.hitbox("body", 4, 4, 10, 13)
