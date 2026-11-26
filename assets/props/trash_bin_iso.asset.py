"""Isometric mesh office trash bin micro-prop (`18x22` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="trash_bin_iso",
    style_id="homelab-16bit",
    width=18,
    height=22,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=519,
)


def _draw_bin(a: Asset, p: PaletteLookup) -> None:
    top_rim = p.METAL_M if a.state == "night" else p.METAL_H
    body_l = p.METAL_D if a.state == "night" else p.METAL_M
    body_r = p.VOID if a.state == "night" else p.METAL_D

    a.iso_box(
        9,
        19,
        5,
        5,
        9,
        top=top_rim,
        left=body_l,
        right=body_r,
        outline=p.INK,
        highlight=p.METAL_H,
        anchor="bottom",
    )
    # Open hollow interior
    a.iso_tile(9, 8, 4, p.VOID, height=2)
    # Mesh perforations on left & right faces
    a.dither(4, 11, 5, 6, body_l, p.VOID, pattern="checker", ratio=0.35, mask="opaque")
    a.dither(9, 11, 5, 6, body_r, p.INK, pattern="checker", ratio=0.35, mask="opaque")


def render(a: Asset) -> None:
    """Render the `trash_bin_iso` micro-prop with `mount_bottom` anchor."""
    _draw_bin(a, a.pal)
    a.anchor("mount_bottom", 9, 19)
    a.anchor("top", 9, 8)
    a.hitbox("body", 3, 4, 12, 17)
