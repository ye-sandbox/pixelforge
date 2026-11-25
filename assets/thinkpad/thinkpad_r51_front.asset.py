"""IBM ThinkPad R51 front-2.5D showcase (`48x48`) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="thinkpad_r51_front",
    style_id="homelab-16bit",
    width=48,
    height=48,
    perspective="front-2.5d",
    states=("healthy", "dusty", "faulty"),
    frames=2,
    fps=2,
    seed=511,
)


def _draw_lid(a: Asset, p: PaletteLookup) -> None:
    with a.layer("lid", outline=p.INK):
        # Matte black ThinkPad lid
        a.rect(8, 5, 32, 22, p.METAL_D)
        a.line(8, 5, 39, 5, p.METAL_L)
        a.line(8, 5, 8, 26, p.METAL_L)
        a.line(39, 6, 39, 26, p.VOID)

        # LCD screen (non-emissive WHITE/SMOKE page; emissive only on fault/cursor)
        bg = p.SCREEN_D if a.state == "faulty" else p.SMOKE if a.state == "dusty" else p.WHITE
        a.rect(11, 8, 26, 16, bg)

        # Browser header + XP taskbar
        a.rect(11, 8, 26, 2, p.LED_R if a.state == "faulty" else p.SOLAR_B)
        a.rect(11, 22, 26, 2, p.SHIRT_BLUE)
        a.rect(11, 22, 4, 2, p.SHIRT_EMER)

        if a.state == "faulty":
            a.line(13, 12, 30, 12, p.LED_R)
            a.line(13, 15, 26, 15, p.LED_A)
            if a.frame == 0:
                a.rect(13, 18, 5, 1, p.SPARK)
            return

        # Wikipedia globe + sidebar + article lines
        a.rect(12, 11, 5, 10, p.METAL_H)
        a.rect(13, 12, 3, 3, p.METAL_M if a.state == "dusty" else p.METAL_D)
        text_col = p.METAL_M if a.state == "dusty" else p.METAL_D
        a.line(19, 12, 33, 12, text_col)
        a.line(19, 15, 35, 15, text_col)
        a.line(19, 18, 29, 18, text_col)
        if a.frame == 0:
            a.put(31, 18, p.LED_C)


def _draw_deck(a: Asset, p: PaletteLookup) -> None:
    with a.layer("deck", outline=p.INK):
        # Hinge bar + LEDs
        a.rect(9, 27, 30, 2, p.METAL_L)
        a.rect(12, 27, 5, 2, p.VOID)
        a.rect(31, 27, 5, 2, p.VOID)
        led_col = (
            p.LED_R
            if a.state == "faulty"
            else p.LED_A
            if a.state == "dusty"
            else p.LED_G
            if a.frame == 0
            else p.LED_GD
        )
        a.put(22, 28, led_col)
        a.put(25, 28, p.LED_G if a.state == "healthy" else p.VOID)

        # Angled 2.5D keyboard deck (widens toward front)
        for r in range(11):
            pad = 2 if r < 4 else 1 if r < 8 else 0
            lx = 5 + pad
            rx = 42 - pad
            a.line(lx, 29 + r, rx, 29 + r, p.METAL_M)
            a.put(lx, 29 + r, p.METAL_L)
            a.put(rx, 29 + r, p.METAL_D)

        # Keyboard recess + keycaps
        a.rect(9, 30, 30, 5, p.VOID)
        for ky in range(31, 34, 2):
            for kx in range(10, 38, 2):
                a.put(kx, ky, p.METAL_D)

        # Non-emissive blue Enter key + red TrackPoint
        a.rect(36, 32, 2, 2, p.SHIRT_BLUE)
        a.put(23, 32, p.ORANGE)

        # TrackPoint mouse buttons + touchpad
        a.rect(19, 36, 10, 1, p.ORANGE)
        a.rect(19, 37, 10, 2, p.METAL_D)
        a.rect(20, 37, 8, 2, p.VOID)

        # Stickers (left) & IBM ThinkPad tri-color badge (right)
        a.put(8, 38, p.SHIRT_BLUE)
        a.put(10, 38, p.SHIRT_YEL)
        a.put(37, 38, p.ORANGE)
        a.put(38, 38, p.SHIRT_EMER)
        a.put(39, 38, p.SHIRT_BLUE)

        # Front chassis lip & rubber feet
        a.rect(5, 40, 38, 3, p.METAL_D)
        a.line(5, 40, 42, 40, p.METAL_L)
        a.rect(8, 43, 4, 1, p.VOID)
        a.rect(36, 43, 4, 1, p.VOID)


def _draw_overlays(a: Asset, p: PaletteLookup) -> None:
    if a.state == "dusty":
        a.scatter(
            count=14,
            colors=(p.DUST_L, p.DUST_D),
            mask="opaque",
            bounds=(8, 8, 32, 32),
        )
        return

    if a.state == "faulty":
        sy = 26 if a.frame == 0 else 25
        a.put(33, sy, p.SPARK)
        a.put(34, sy - 1, p.LED_R)
        a.put(32, sy + 1, p.SPARK)


def render(a: Asset) -> None:
    """Render the `thinkpad_r51_front` showcase asset."""
    p = a.pal
    _draw_lid(a, p)
    _draw_deck(a, p)
    _draw_overlays(a, p)

    a.anchor("foot", 24, 43)
    a.anchor("trackpoint", 23, 32)
    a.anchor("screen", 24, 16)
    a.anchor("led", 22, 28)
    a.hitbox("body", 4, 4, 40, 41)
