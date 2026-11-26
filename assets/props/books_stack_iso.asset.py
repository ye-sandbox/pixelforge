"""Isometric stacked books micro-prop (`20x18` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="books_stack_iso",
    style_id="homelab-16bit",
    width=20,
    height=18,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=512,
)


def _draw_books(a: Asset, p: PaletteLookup) -> None:
    is_night = a.state == "night"
    bottom_spine = p.PCB_B if is_night else p.SOLAR_B
    mid_spine = p.WOOD_M if is_night else p.WARM_AMBER
    top_spine = p.PCB_G if is_night else p.SHIRT_TEAL

    # Bottom hardcover
    a.iso_box(
        10,
        15,
        8,
        6,
        3,
        top=bottom_spine,
        left=bottom_spine,
        right=p.WHITE,
        outline=p.INK,
        highlight=p.SMOKE,
        anchor="bottom",
    )
    # Middle book slightly offset
    a.iso_box(
        9,
        12,
        7,
        5,
        3,
        top=mid_spine,
        left=mid_spine,
        right=p.DUST_L,
        outline=p.INK,
        highlight=p.DUST_L,
        anchor="bottom",
    )
    # Top notebook
    a.iso_box(
        10,
        9,
        6,
        5,
        2,
        top=top_spine,
        left=top_spine,
        right=p.WHITE,
        outline=p.INK,
        highlight=p.SMOKE,
        anchor="bottom",
    )
    # Bookmark ribbon
    a.put(13, 8, p.ORANGE)
    a.put(13, 9, p.ORANGE)


def render(a: Asset) -> None:
    """Render the `books_stack_iso` micro-prop with `mount_bottom` anchor."""
    _draw_books(a, a.pal)
    a.anchor("mount_bottom", 10, 15)
    a.anchor("top", 10, 4)
    a.hitbox("body", 2, 2, 16, 15)
