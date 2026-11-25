"""IBM ThinkPad TrackPoint & keyboard close-up (`32x32` top-down) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec

SPEC = AssetSpec(
    id="thinkpad_trackpoint_detail",
    style_id="homelab-16bit",
    width=32,
    height=32,
    perspective="top-down",
    states=("healthy", "dusty", "faulty"),
    frames=2,
    fps=2,
    seed=512,
)


def render(a: Asset) -> None:
    """Render the top-down `thinkpad_trackpoint_detail` keyboard and palmrest."""
    p = a.pal

    with a.layer("deck", outline=p.INK):
        # Palmrest & keyboard chassis (1px margin for auto-outline)
        a.rect(2, 2, 28, 28, p.METAL_M)
        a.line(2, 2, 29, 2, p.METAL_L)
        a.line(2, 2, 2, 29, p.METAL_L)
        a.line(29, 3, 29, 29, p.METAL_D)
        a.line(3, 29, 29, 29, p.METAL_D)

        # Top hinge strip + status LED
        a.rect(2, 2, 28, 2, p.METAL_L)
        led_col = (
            p.LED_R
            if a.state == "faulty"
            else p.LED_A
            if a.state == "dusty"
            else p.LED_G
            if a.frame == 0
            else p.VOID
        )
        a.put(16, 3, led_col)

        # Keyboard well + keycaps
        a.rect(4, 5, 24, 12, p.VOID)
        for ky in range(6, 15, 2):
            for kx in range(5, 27, 2):
                a.put(kx, ky, p.METAL_D)

        # Non-emissive IBM blue Enter key & Access IBM key
        a.rect(25, 10, 2, 3, p.SHIRT_BLUE)
        a.rect(5, 6, 3, 1, p.SHIRT_BLUE)

        # Iconic red TrackPoint nub (G/H/B cluster)
        a.rect(14, 10, 2, 2, p.ORANGE)

        # TrackPoint mouse buttons with red stripes & center blue scroll button
        a.rect(11, 18, 3, 2, p.METAL_D)
        a.rect(14, 18, 2, 2, p.SHIRT_BLUE)
        a.rect(16, 18, 3, 2, p.METAL_D)
        a.line(11, 18, 13, 18, p.ORANGE)
        a.line(16, 18, 18, 18, p.ORANGE)

        # Touchpad + lower buttons
        a.rect(10, 21, 10, 6, p.VOID)
        a.rect(11, 22, 8, 4, p.METAL_D)
        a.rect(10, 27, 4, 2, p.METAL_D)
        a.rect(16, 27, 4, 2, p.METAL_D)

        # Centrino / XP stickers (left) & IBM ThinkPad badge (right)
        a.rect(4, 25, 2, 2, p.SHIRT_BLUE)
        a.rect(7, 25, 2, 2, p.SHIRT_YEL)
        a.put(24, 26, p.ORANGE)
        a.put(25, 26, p.SHIRT_EMER)
        a.put(26, 26, p.SHIRT_BLUE)

        if a.state == "dusty":
            a.scatter(
                count=10,
                colors=(p.DUST_L, p.DUST_D),
                mask="opaque",
                bounds=(4, 5, 24, 22),
            )
        elif a.state == "faulty":
            sy = 11 if a.frame == 0 else 10
            a.put(21, sy, p.SPARK)
            a.put(22, sy - 1, p.LED_R)

    a.anchor("trackpoint", 14, 10)
    a.anchor("enter_key", 25, 11)
    a.anchor("touchpad", 15, 24)
    a.anchor("badge", 25, 26)
    a.hitbox("body", 1, 1, 30, 30)
