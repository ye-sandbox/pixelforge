"""1-bit side-view knight lantern showcase asset (`24x24`, `ink-1bit`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec

if TYPE_CHECKING:
    from styles.ink_1bit_palette import Ink1bitPalette

SPEC = AssetSpec(
    id="ink_1bit_knight",
    style_id="ink-1bit",
    width=24,
    height=24,
    perspective="side",
    states=("idle", "alert"),
    frames=2,
    fps=2,
    seed=401,
)


def render(a: Asset[Ink1bitPalette]) -> None:
    """Render 1-bit side-view knight helm & shield crest with zero emissives."""
    p = a.pal
    bob = 0 if a.frame == 0 else -1

    # Ground shadow bar
    a.rect(5, 20, 14, 2, p.INK)

    with a.layer("knight", outline=p.INK):
        # Plume / crest
        plume_x = 10 if a.state == "idle" else 9
        a.rect(plume_x, 3 + bob, 5, 3, p.PAPER)
        a.rect(plume_x - 2, 4 + bob, 3, 2, p.PAPER)

        # Helmet dome
        a.rect(7, 6 + bob, 10, 7, p.PAPER)
        # Visor slit
        visor_h = 2 if a.state == "idle" else 1
        a.rect(11, 9 + bob, 5, visor_h, p.INK)

        # Torso & kite shield
        a.rect(6, 13 + bob, 11, 7, p.PAPER)
        a.rect(12, 14 + bob, 5, 5, p.INK)
        a.rect(13, 15 + bob, 3, 3, p.PAPER)

    a.anchor("foot", 12, 21, kind="ground")
    a.anchor("visor", 13, 9 + bob, kind="center")
    a.hitbox("body", 5, 3, 14, 19)
