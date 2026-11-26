"""16-color front-2.5D cyberpunk neon terminal showcase asset (`32x32`, `scifi-neon`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec

if TYPE_CHECKING:
    from styles.scifi_neon_palette import ScifiNeonPalette

SPEC = AssetSpec(
    id="scifi_neon_terminal",
    style_id="scifi-neon",
    width=32,
    height=32,
    perspective="front-2.5d",
    states=("idle", "overdrive"),
    frames=2,
    fps=4,
    seed=406,
)


def render(a: Asset[ScifiNeonPalette]) -> None:
    """Render front-2.5D neon terminal isolating `NEON_*`/`CORE_WHITE` from `TRIM_*`."""
    p = a.pal

    # Ground shadow
    a.rect(6, 27, 20, 2, p.VOID)

    with a.layer("chassis", outline=p.INK):
        # Main hull
        a.rect(6, 5, 20, 22, p.HULL_D)
        a.rect(7, 6, 18, 19, p.HULL_M)
        a.rect(8, 6, 16, 3, p.HULL_L)
        # Non-emissive painted trims (MUST stay out of emissive bloom mask)
        a.rect(7, 22, 18, 3, p.TRIM_BLUE)
        a.rect(8, 19, 16, 2, p.TRIM_PURPLE)

        # Recessed CRT / holo screen
        a.rect(9, 9, 14, 9, p.GLASS_D)
        a.rect(10, 10, 12, 7, p.GLASS_L)

        # Emissive neon readouts
        if a.state == "overdrive":
            a.rect(11, 11, 10, 2, p.NEON_MAGENTA)
            a.rect(11, 14, 6 if a.frame == 0 else 9, 2, p.CORE_WHITE)
            a.rect(20, 20, 3, 2, p.NEON_AMBER)
        else:
            a.rect(11, 11, 8 if a.frame == 0 else 10, 2, p.NEON_CYAN)
            a.rect(11, 14, 5, 2, p.NEON_LIME)
            a.rect(20, 20, 3, 2, p.NEON_CYAN)

    a.anchor("foot", 16, 28, kind="ground")
    a.anchor("screen", 16, 13, kind="light")
    a.hitbox("body", 5, 4, 22, 25)
