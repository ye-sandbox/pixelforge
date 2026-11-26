"""Isometric refurbished laptop asset (`24x22` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="old_laptop_iso",
    style_id="homelab-16bit",
    width=24,
    height=22,
    perspective="iso-2:1",
    states=("healthy", "dusty", "faulty"),
    frames=2,
    fps=2,
    seed=102,
)


def _draw_lid(a: Asset, p: PaletteLookup) -> None:
    with a.plane(p0=(8, 2), p1=(20, 6), p2=(6, 11)) as lid:
        lid.rect(0.0, 0.0, 1.0, 1.0, fill=p.METAL_M, bevel=(p.METAL_L, p.METAL_D))
        lid.rect(0.12, 0.14, 0.76, 0.72, fill=p.SCREEN_D)

        if a.state == "faulty":
            lid.line(0.20, 0.30, 0.72, 0.30, p.LED_R)
            lid.line(0.20, 0.50, 0.62, 0.50, p.LED_A)
            if a.frame == 0:
                lid.dot(0.32, 0.70, p.SPARK)
        else:
            text_col = p.SCREEN_L if a.state == "dusty" else p.LED_G
            lid.line(0.20, 0.30, 0.74, 0.30, text_col)
            lid.line(0.20, 0.48, 0.68, 0.48, text_col)
            lid.line(0.20, 0.66, 0.52, 0.66, text_col)
            if a.frame == 0:
                lid.dot(0.64, 0.66, p.SOLAR_L)

        lid.anchor("screen", 0.5, 0.5)


def _draw_deck(a: Asset, p: PaletteLookup) -> None:
    with a.plane(p0=(6, 11), p1=(19, 15), p2=(2, 17)) as deck:
        deck.rect(
            0.0,
            0.0,
            1.0,
            1.0,
            fill=p.METAL_M,
            bevel=(p.METAL_L, p.METAL_D),
            extrude_y=2,
            side_left=p.METAL_D,
            side_right=p.VOID,
        )
        deck.grid(0.10, 0.12, 0.80, 0.45, cols=5, rows=2, color=p.METAL_D, bg=p.VOID)
        deck.rect(0.34, 0.66, 0.30, 0.22, fill=p.VOID)
        deck.anchor("foot", 0.5, 0.55)

    power_led = (
        p.LED_R
        if a.state == "faulty"
        else p.LED_A
        if a.state == "dusty"
        else p.LED_G
        if a.frame == 0
        else p.SCREEN_L
    )
    a.put(13, 18, power_led)
    a.anchor("led", 13, 18)


def _draw_overlays(a: Asset, p: PaletteLookup) -> None:
    if a.state == "dusty":
        a.scatter(
            count=6,
            colors=(p.DUST_L, p.DUST_D),
            mask="opaque",
            bounds=(3, 4, 17, 14),
        )
        return

    if a.state == "faulty":
        sy = 10 if a.frame == 0 else 9
        a.put(17, sy, p.SPARK)
        a.put(18, sy - 1, p.LED_R)


def render(a: Asset) -> None:
    """Render the `old_laptop_iso` asset aligned for isometric desk mounting."""
    p = a.pal
    with a.layer("chassis", outline=p.INK):
        _draw_lid(a, p)
        _draw_deck(a, p)
        _draw_overlays(a, p)

    a.hitbox("body", 1, 1, 21, 19)
