"""16-color isometric crystal beacon showcase asset (`32x32`, `sweetie-16`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec

if TYPE_CHECKING:
    from styles.sweetie_16_palette import Sweetie16Palette

SPEC = AssetSpec(
    id="sweetie_beacon_iso",
    style_id="sweetie-16",
    width=32,
    height=32,
    perspective="iso-2:1",
    states=("idle", "active"),
    frames=2,
    fps=2,
    seed=403,
)


def render(a: Asset[Sweetie16Palette]) -> None:
    """Render isometric crystal beacon isolating emissive `CYAN` from painted trims."""
    p = a.pal
    glow = a.state == "active" or a.frame == 0

    with a.layer("pedestal", outline=p.INK):
        with a.plane(p0=(16, 17), p1=(26, 22), p2=(6, 22)) as base:
            base.rect(0.0, 0.0, 1.0, 1.0, fill=p.SLATE_M, extrude_y=4, side=p.SLATE_D)
            base.rect(0.18, 0.18, 0.64, 0.64, fill=p.CRIMSON)
        # Non-emissive painted gold corner trims
        a.rect(15, 25, 2, 2, p.GOLD)

    with a.layer("crystal", outline=p.INK):
        core_y = 9 if a.frame == 0 else 8
        a.rect(13, core_y, 6, 9, p.BLUE)
        a.rect(14, core_y - 2, 4, 2, p.SKY)
        # Only CYAN is emissive; SKY/BLUE/GOLD remain non-emissive paint
        core_color = p.CYAN if glow else p.SKY
        a.rect(14, core_y + 2, 4, 4, core_color)

    a.anchor("foot", 16, 28, kind="ground")
    a.anchor("crystal", 16, 13, kind="light")
    a.hitbox("body", 5, 6, 22, 24)
