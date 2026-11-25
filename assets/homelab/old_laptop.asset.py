"""Old refurbished laptop asset (`32x32` front-2.5d) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="old_laptop",
    style_id="homelab-16bit",
    width=32,
    height=32,
    perspective="front-2.5d",
    states=("healthy", "dusty", "faulty"),
    frames=2,
    fps=2,
    seed=101,
)


def _draw_screen(a: Asset, p: PaletteLookup) -> None:
    # Lid housing with top-left highlight and bottom-right shade
    a.rect(5, 4, 22, 15, p.METAL_M)
    a.line(5, 4, 26, 4, p.METAL_L)
    a.line(5, 4, 5, 18, p.METAL_L)
    a.line(26, 5, 26, 18, p.METAL_D)
    a.line(6, 18, 26, 18, p.METAL_D)

    # Inner LCD bezel + subtle dithered terminal backdrop
    a.rect(7, 6, 18, 11, p.SCREEN_D)
    a.dither(8, 7, 16, 9, p.SCREEN_D, p.VOID, pattern="bayer4", ratio=0.25)
    a.line(7, 6, 24, 6, p.VOID)
    a.line(7, 6, 7, 16, p.VOID)

    if a.state == "faulty":
        a.line(9, 8, 18, 8, p.LED_R)
        a.line(9, 10, 21, 10, p.LED_A)
        a.line(9, 12, 15, 12, p.LED_R)
        if a.frame == 0:
            a.rect(9, 14, 4, 1, p.SPARK)
        return

    text_color = p.SCREEN_L if a.state == "dusty" else p.LED_G
    a.line(9, 8, 17, 8, text_color)
    a.line(9, 10, 21, 10, text_color)
    a.line(9, 12, 15, 12, text_color)
    a.line(9, 14, 12, 14, text_color)

    if a.frame == 0:
        a.rect(14, 14, 2, 1, p.SOLAR_L)


def _draw_deck(a: Asset, p: PaletteLookup) -> None:
    # Hinge bar with twin dark hinge cutouts
    a.rect(6, 19, 20, 1, p.METAL_H)
    a.rect(8, 19, 4, 1, p.VOID)
    a.rect(20, 19, 4, 1, p.VOID)

    # Keyboard deck (angled 2.5D step)
    a.rect(4, 20, 24, 5, p.METAL_M)
    a.line(4, 20, 27, 20, p.METAL_L)
    a.line(4, 20, 4, 24, p.METAL_L)

    # Keycap grid + trackpad recess
    for kx in range(6, 25, 2):
        a.put(kx, 21, p.METAL_D)
        a.put(kx, 22, p.METAL_D)
    a.rect(13, 23, 6, 2, p.VOID)

    # Front lip and rubber feet
    a.rect(3, 25, 26, 3, p.METAL_D)
    a.line(3, 25, 28, 25, p.METAL_H)
    a.rect(5, 28, 3, 1, p.VOID)
    a.rect(24, 28, 3, 1, p.VOID)

    # Emissive status LEDs
    power_led = (
        p.LED_R
        if a.state == "faulty"
        else p.LED_A
        if a.state == "dusty"
        else p.LED_G
        if a.frame == 0
        else p.SCREEN_L
    )
    a.put(23, 26, power_led)
    a.put(25, 26, p.LED_C if a.state == "healthy" else p.VOID)


def _draw_overlays(a: Asset, p: PaletteLookup) -> None:
    if a.state == "dusty":
        a.scatter(
            count=10,
            colors=(p.DUST_L, p.DUST_D),
            mask="opaque",
            bounds=(5, 6, 22, 20),
        )
        return

    if a.state == "faulty":
        sy = 18 if a.frame == 0 else 17
        a.put(23, sy, p.SPARK)
        a.put(24, sy - 1, p.LED_R)
        a.put(22, sy + 1, p.SPARK)


def render(a: Asset) -> None:
    """Render the `old_laptop` asset with state and frame variations."""
    p = a.pal
    with a.layer("chassis", outline=p.INK):
        _draw_screen(a, p)
        _draw_deck(a, p)
        _draw_overlays(a, p)

    a.anchor("foot", 16, 28)
    a.anchor("screen", 16, 11)
    a.anchor("led", 23, 26)
    a.hitbox("body", 2, 3, 28, 26)
