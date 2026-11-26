"""Isometric soda can micro-prop (`12x16` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="soda_can_iso",
    style_id="homelab-16bit",
    width=12,
    height=16,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=516,
)


def _draw_can(a: Asset, p: PaletteLookup) -> None:
    label_l = p.SHIRT_TEAL if a.state == "night" else p.ORANGE
    label_r = p.PCB_G if a.state == "night" else p.WARM_AMBER
    a.iso_box(
        6,
        14,
        2,
        2,
        6,
        top=p.METAL_H,
        left=label_l,
        right=label_r,
        outline=p.INK,
        highlight=p.WHITE,
        anchor="bottom",
    )
    # Metallic top rim & pull-tab
    a.iso_tile(6, 7, 2, p.SMOKE, height=1)
    a.put(6, 7, p.METAL_D)
    # Label stripe
    a.put(5, 10, p.WHITE)
    a.put(6, 11, p.WHITE)


def render(a: Asset) -> None:
    """Render the `soda_can_iso` micro-prop with `mount_bottom` anchor."""
    _draw_can(a, a.pal)
    a.anchor("mount_bottom", 6, 14)
    a.anchor("top", 6, 6)
    a.hitbox("body", 3, 5, 7, 10)
