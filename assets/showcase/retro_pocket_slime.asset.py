"""4-color top-down handheld RPG slime showcase asset (`24x24`, `retro-pocket-4`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec

if TYPE_CHECKING:
    from styles.retro_pocket_4_palette import RetroPocket4Palette

SPEC = AssetSpec(
    id="retro_pocket_slime",
    style_id="retro-pocket-4",
    width=24,
    height=24,
    perspective="top-down",
    states=("idle", "bounce"),
    frames=2,
    fps=4,
    seed=402,
)


def render(a: Asset[RetroPocket4Palette]) -> None:
    """Render 4-shade handheld RPG slime with squash-and-stretch animation."""
    p = a.pal
    squish = a.state == "bounce" and a.frame == 1
    rx = 8 if squish else 7
    ry = 5 if squish else 6
    cy = 14 if squish else 13

    # Ground shadow
    a.ellipse(12, 18, 7, 3, p.INK)

    with a.layer("slime", outline=p.INK):
        a.ellipse(12, cy, rx, ry, p.SHADE_D)
        a.ellipse(12, cy - 1, rx - 1, ry - 1, p.SHADE_L)
        # Top-left specular highlight
        a.rect(8, cy - 4, 3, 2, p.HIGHLIGHT)
        # Eyes (2px tall each)
        a.rect(9, cy, 2, 2, p.INK)
        a.rect(14, cy, 2, 2, p.INK)

    a.anchor("foot", 12, 19, kind="ground")
    a.anchor("core", 12, cy, kind="center")
    a.hitbox("body", 4, 7, 16, 14)
