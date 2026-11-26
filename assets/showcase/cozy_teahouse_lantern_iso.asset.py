"""16-color isometric cozy teahouse lantern showcase asset (`32x32`, `cozy-pastel`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec

if TYPE_CHECKING:
    from styles.cozy_pastel_palette import CozyPastelPalette

SPEC = AssetSpec(
    id="cozy_teahouse_lantern_iso",
    style_id="cozy-pastel",
    width=32,
    height=32,
    perspective="iso-2:1",
    states=("day", "evening"),
    frames=2,
    fps=2,
    seed=405,
)


def render(a: Asset[CozyPastelPalette]) -> None:
    """Render isometric wooden lantern isolating `WARM_GLOW` from painted `CREAM`/`BUTTER`."""
    p = a.pal

    with (
        a.layer("planter_base", outline=p.COCOA_OUTLINE),
        a.plane(p0=(16, 19), p1=(25, 24), p2=(7, 24)) as base,
    ):
        base.rect(0.0, 0.0, 1.0, 1.0, fill=p.OAK_M, extrude_y=3, side=p.ESPRESSO)
        base.rect(0.15, 0.15, 0.7, 0.7, fill=p.SAGE_L)

    with a.layer("lantern_body", outline=p.COCOA_OUTLINE):
        # Wooden frame & terracotta cap
        a.rect(11, 9, 10, 11, p.OAK_L)
        a.rect(10, 7, 12, 3, p.TERRACOTTA)
        a.rect(14, 5, 4, 2, p.PEBBLE)
        # Paper window: CREAM in day, emissive WARM_GLOW in evening
        if a.state == "evening":
            a.rect(13, 11, 6, 7, p.WARM_GLOW if a.frame == 0 else p.BUTTER)
            if a.frame == 1:
                a.rect(14, 12, 4, 4, p.WARM_GLOW)
        else:
            a.rect(13, 11, 6, 7, p.CREAM)
            a.rect(14, 12, 4, 2, p.BUTTER)

    a.anchor("foot", 16, 28, kind="ground")
    a.anchor("lamp", 16, 14, kind="light")
    a.hitbox("body", 6, 4, 20, 26)
