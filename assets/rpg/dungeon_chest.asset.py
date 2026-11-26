"""Top-down fantasy dungeon chest (`32x32`, closed/open/locked)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec

if TYPE_CHECKING:
    from styles.topdown_rpg_palette import TopdownRpgPalette

SPEC = AssetSpec(
    id="dungeon_chest",
    style_id="topdown-rpg",
    width=32,
    height=32,
    perspective="top-down",
    states=("closed", "open", "locked"),
    frames=2,
    fps=2,
    seed=301,
)


def _bevel_box(
    a: Asset[TopdownRpgPalette],
    x: int,
    y: int,
    w: int,
    h: int,
    fill: int,
    hi: int,
    sh: int,
) -> None:
    """Draw a top-left lit beveled rectangle."""
    a.rect(x, y, w, h, fill)
    a.line(x, y, x + w - 1, y, hi)
    a.line(x, y, x, y + h - 1, hi)
    a.line(x, y + h - 1, x + w - 1, y + h - 1, sh)
    a.line(x + w - 1, y, x + w - 1, y + h - 1, sh)


def render(a: Asset[TopdownRpgPalette]) -> None:
    """Render top-down wooden chest with iron straps and state-driven treasure glow."""
    p = a.pal

    # Ground contact shadow
    a.rect(5, 22, 22, 5, p.VOID)

    with a.layer("chest_body", outline=p.INK):
        _bevel_box(a, 6, 10, 20, 14, p.BARK_M, p.BARK_L, p.BARK_D)
        # Iron corner straps
        a.rect(8, 10, 2, 14, p.IRON_M)
        a.rect(22, 10, 2, 14, p.IRON_M)
        a.put(8, 10, p.IRON_L)
        a.put(22, 10, p.IRON_L)

        if a.state == "open":
            # Recessed open interior with treasure and arcane gem
            a.rect(8, 12, 16, 7, p.VOID)
            a.rect(9, 14, 14, 4, p.GOLD_M)
            a.rect(10, 14, 4, 2, p.GOLD_L)
            a.rect(18, 15, 3, 2, p.GOLD_L)
            gem_color = p.MANA_CORE if a.frame == 0 else p.MANA_GLOW
            a.rect(14, 14, 4, 3, p.MANA_GLOW)
            a.put(15, 15, gem_color)
            a.put(16, 15, gem_color)
            # Folded-back lid lip at top
            _bevel_box(a, 6, 7, 20, 4, p.BARK_D, p.BARK_M, p.VOID)
        else:
            # Closed/locked arched top-down lid
            _bevel_box(a, 6, 9, 20, 8, p.BARK_L, p.BARK_L, p.BARK_D)
            a.rect(8, 9, 2, 8, p.IRON_L)
            a.rect(22, 9, 2, 8, p.IRON_L)
            # Front clasp
            a.rect(14, 15, 4, 4, p.GOLD_M)
            a.put(15, 16, p.GOLD_L)
            if a.state == "locked":
                a.rect(14, 15, 4, 4, p.RUBY_D)
                rune = p.RUNE_GOLD if a.frame == 0 else p.GOLD_L
                a.put(15, 16, rune)
                a.put(16, 16, rune)
            elif a.frame == 1:
                a.put(15, 11, p.GOLD_L)

    a.anchor("lid", 16, 12, kind="interact")
    a.anchor("foot", 16, 25, kind="ground")
    a.hitbox("body", 5, 7, 22, 20)
