"""IBM ThinkPad R51 isometric showcase (`64x64` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="thinkpad_r51_iso",
    style_id="homelab-16bit",
    width=64,
    height=64,
    perspective="iso-2:1",
    states=("healthy", "dusty", "faulty"),
    frames=2,
    fps=2,
    seed=510,
)


def _draw_lid(a: Asset, p: PaletteLookup) -> None:
    with (
        a.layer("lid", outline=p.INK),
        a.plane(p0=(22, 4), p1=(57, 13), p2=(17, 30)) as lid,
    ):
        lid.rect(0.0, 0.0, 1.0, 1.0, fill=p.METAL_D, bevel=(p.METAL_L, p.VOID))

        lcd_bg = p.SCREEN_D if a.state == "faulty" else p.SMOKE if a.state == "dusty" else p.WHITE
        lid.rect(0.09, 0.11, 0.82, 0.77, fill=lcd_bg)

        # Browser title bar + Windows XP taskbar (non-emissive painted blues/greens)
        lid.rect(0.09, 0.11, 0.82, 0.09, fill=p.LED_R if a.state == "faulty" else p.SOLAR_B)
        lid.rect(0.09, 0.80, 0.82, 0.08, fill=p.SHIRT_BLUE)
        lid.rect(0.09, 0.80, 0.15, 0.08, fill=p.SHIRT_EMER)

        if a.state == "faulty":
            lid.line(0.16, 0.34, 0.74, 0.34, p.LED_R)
            lid.line(0.16, 0.48, 0.62, 0.48, p.LED_A)
            if a.frame == 0:
                lid.line(0.16, 0.62, 0.38, 0.62, p.SPARK)
        else:
            # Wikipedia globe + sidebar + article lines
            lid.rect(0.13, 0.25, 0.14, 0.46, fill=p.METAL_H)
            text_col = p.METAL_M if a.state == "dusty" else p.METAL_D
            lid.line(0.32, 0.31, 0.82, 0.31, text_col)
            lid.line(0.32, 0.45, 0.85, 0.45, text_col)
            lid.line(0.32, 0.59, 0.68, 0.59, text_col)
            if a.frame == 0:
                lid.dot(0.73, 0.59, p.LED_C)

        lid.anchor("screen", 0.5, 0.5)


def _draw_deck(a: Asset, p: PaletteLookup) -> None:
    with a.layer("deck", outline=p.INK):
        # Hinge bar
        with a.plane(p0=(18, 30), p1=(52, 39), p2=(18, 32)) as hinge:
            hinge.rect(0.0, 0.0, 1.0, 1.0, fill=p.METAL_L, bevel=(p.METAL_H, p.VOID))

        # Angled 3/4 keyboard deck with extruded front/right thickness
        with a.plane(p0=(17, 32), p1=(52, 41), p2=(5, 49)) as deck:
            deck.rect(
                0.0,
                0.0,
                1.0,
                1.0,
                fill=p.METAL_M,
                bevel=(p.METAL_L, p.METAL_D),
                extrude_y=3,
                side_left=p.METAL_D,
                side_right=p.VOID,
            )

            # Keyboard well + 4x13 keycap grid
            deck.grid(0.07, 0.08, 0.83, 0.46, cols=13, rows=4, color=p.METAL_D, bg=p.VOID)

            # Iconic IBM blue Enter key + red TrackPoint (strictly non-emissive tokens)
            deck.rect(0.80, 0.24, 0.08, 0.18, fill=p.SHIRT_BLUE)
            deck.dot(0.45, 0.29, p.ORANGE, anchor="trackpoint")

            # TrackPoint mouse buttons + red stripe + center blue scroll button
            deck.rect(0.32, 0.58, 0.24, 0.10, fill=p.METAL_D)
            deck.rect(0.32, 0.58, 0.24, 0.03, fill=p.ORANGE)
            deck.rect(0.42, 0.58, 0.04, 0.10, fill=p.SHIRT_BLUE)

            # Touchpad recess
            deck.rect(0.30, 0.72, 0.28, 0.21, fill=p.VOID)
            deck.rect(0.33, 0.76, 0.22, 0.13, fill=p.METAL_D)

            # Palmrest Centrino / XP stickers (left) & IBM ThinkPad tri-color badge (right)
            deck.dot(0.12, 0.78, p.SHIRT_BLUE)
            deck.dot(0.18, 0.78, p.SHIRT_YEL)
            deck.dot(0.72, 0.80, p.ORANGE)
            deck.dot(0.76, 0.80, p.SHIRT_EMER, anchor="badge")
            deck.dot(0.80, 0.80, p.SHIRT_BLUE)

        # Emissive hinge status LEDs placed after deck fill so they remain visible below lid seam
        led_col = (
            p.LED_R
            if a.state == "faulty"
            else p.LED_A
            if a.state == "dusty"
            else p.LED_G
            if a.frame == 0
            else p.LED_GD
        )
        a.put(33, 36, led_col)
        a.put(36, 37, p.LED_G if a.state == "healthy" else p.VOID)

        # Side port ticks on right chassis edge
        for step in (4, 8):
            a.put(40 + step, 58 - ((step * 17) // 12) + 1, p.METAL_L)


def _draw_overlays(a: Asset, p: PaletteLookup) -> None:
    if a.state == "dusty":
        a.scatter(
            count=16,
            colors=(p.DUST_L, p.DUST_D),
            mask="opaque",
            bounds=(10, 12, 42, 40),
        )
        return

    if a.state == "faulty":
        sy = 34 if a.frame == 0 else 33
        a.put(38, sy, p.SPARK)
        a.put(39, sy - 1, p.LED_R)
        a.put(37, sy + 1, p.SPARK)


def render(a: Asset) -> None:
    """Render the `thinkpad_r51_iso` showcase asset."""
    p = a.pal
    # INVARIANT: Draw deck before lid so the deck's top outline never clips the lid's XP taskbar.
    _draw_deck(a, p)
    _draw_lid(a, p)
    _draw_overlays(a, p)

    a.anchor("foot", 23, 58)
    a.anchor("led", 33, 36)
    a.hitbox("body", 4, 3, 55, 58)
