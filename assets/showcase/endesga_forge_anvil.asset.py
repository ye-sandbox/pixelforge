"""32-color top-down blacksmith forge anvil showcase asset (`32x32`, `endesga-32`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec

if TYPE_CHECKING:
    from styles.endesga_32_palette import Endesga32Palette

SPEC = AssetSpec(
    id="endesga_forge_anvil",
    style_id="endesga-32",
    width=32,
    height=32,
    perspective="top-down",
    states=("idle", "heated"),
    frames=2,
    fps=4,
    seed=404,
)


def render(a: Asset[Endesga32Palette]) -> None:
    """Render top-down forge anvil isolating `GLOW_GOLD`/`GLOW_CYAN` from painted metals."""
    p = a.pal

    # Wooden stump base
    with a.layer("stump", outline=p.INK):
        a.ellipse(16, 19, 10, 7, p.WOOD_D)
        a.ellipse(16, 18, 8, 5, p.WOOD_M)
        a.rect(11, 16, 10, 3, p.WOOD_L)

    # Steel anvil top
    with a.layer("anvil", outline=p.INK):
        a.rect(7, 10, 18, 8, p.STEEL_D)
        a.rect(8, 10, 16, 6, p.STEEL_M)
        a.rect(9, 11, 13, 3, p.STEEL_L)
        # Horn on left
        a.rect(4, 12, 4, 4, p.SILVER)
        # Non-emissive painted crest on right
        a.rect(21, 11, 2, 3, p.RED)

        if a.state == "heated":
            ember = p.GLOW_GOLD if a.frame == 0 else p.GLOW_CYAN
            a.rect(13, 12, 4, 2, ember)
        else:
            a.rect(13, 12, 4, 2, p.GOLD)

    a.anchor("foot", 16, 25, kind="ground")
    a.anchor("work_top", 16, 13, kind="mount")
    a.hitbox("body", 3, 9, 23, 18)
