"""Top-down stone dungeon brazier (`24x24`, lit/unlit animated fire)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec

if TYPE_CHECKING:
    from styles.topdown_rpg_palette import TopdownRpgPalette

SPEC = AssetSpec(
    id="stone_brazier",
    style_id="topdown-rpg",
    width=24,
    height=24,
    perspective="top-down",
    states=("lit", "unlit"),
    frames=2,
    fps=4,
    seed=302,
)


def render(a: Asset[TopdownRpgPalette]) -> None:
    """Render top-down carved stone brazier with animated emissive flame."""
    p = a.pal

    # Ground shadow
    a.ellipse(12, 15, 7, 5, p.VOID)

    with a.layer("basin", outline=p.INK):
        a.ellipse(12, 13, 6, 5, p.STONE_M)
        a.ellipse(12, 12, 5, 4, p.STONE_L)
        # Inner fire bowl
        a.ellipse(12, 12, 3, 2, p.VOID)
        # Corner rivets
        a.put(7, 11, p.IRON_L)
        a.put(17, 11, p.IRON_D)

        if a.state == "lit":
            shift = -1 if a.frame == 0 else 1
            a.ellipse(12, 11, 3, 2, p.TORCH_GLOW)
            a.rect(11, 8, 2, 4, p.TORCH_GLOW)
            a.put(12 + shift, 7, p.TORCH_GLOW)
            a.put(11, 10, p.TORCH_CORE)
            a.put(12, 9, p.TORCH_CORE)
            a.put(12, 11, p.TORCH_CORE)
        else:
            a.put(11, 12, p.STONE_D)
            a.put(13, 12, p.STONE_D)

    a.anchor("flame", 12, 9, kind="light")
    a.anchor("foot", 12, 19, kind="ground")
    a.hitbox("body", 5, 7, 14, 13)
