"""Isometric articulated desk lamp micro-prop (`20x24` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="desk_lamp_iso",
    style_id="homelab-16bit",
    width=20,
    height=24,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=501,
)


def _draw_base_and_arm(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        10,
        20,
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
    with a.layer("arm", outline=p.INK):
        a.line(10, 16, 6, 10, p.METAL_M)
        a.line(6, 10, 11, 5, p.METAL_L)
        a.rect(5, 9, 2, 2, p.METAL_H)


def _draw_shade(a: Asset, p: PaletteLookup) -> None:
    is_night = a.state == "night"
    with a.layer("shade", outline=p.INK):
        a.iso_box(
            13,
            10,
            4,
            4,
            3,
            top=p.METAL_H,
            left=p.METAL_M,
            right=p.METAL_D,
            outline=p.INK,
            highlight=p.WHITE,
            anchor="bottom",
        )
        bulb_color = p.WARM_LAMP if is_night else p.GLASS_L
        a.rect(12, 10, 3, 2, bulb_color)

    if is_night:
        a.rect(12, 12, 3, 2, p.WARM_LAMP)
        a.rect(9, 17, 3, 1, p.WARM_AMBER)


def render(a: Asset) -> None:
    """Render the `desk_lamp_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_base_and_arm(a, p)
    _draw_shade(a, p)

    a.anchor("mount_bottom", 10, 20)
    a.anchor("bulb", 13, 11)
    a.hitbox("body", 4, 1, 16, 21)
