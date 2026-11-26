"""Isometric mechanical keyboard micro-prop (`24x16` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="keyboard_iso",
    style_id="homelab-16bit",
    width=24,
    height=16,
    perspective="iso-2:1",
    states=("idle", "active"),
    frames=2,
    fps=2,
    seed=507,
)


def _draw_keyboard(a: Asset, p: PaletteLookup) -> None:
    is_active = a.state == "active"
    with (
        a.layer("chassis", outline=p.INK),
        a.plane(p0=(9, 3), p1=(21, 9), p2=(3, 6)) as deck,
    ):
        deck.rect(
            0.0,
            0.0,
            1.0,
            1.0,
            fill=p.METAL_D,
            bevel=(p.METAL_M, p.VOID),
            extrude_y=2,
            side_left=p.METAL_D,
            side_right=p.VOID,
        )
        # Keycap bed + rows
        deck.grid(0.08, 0.14, 0.84, 0.68, cols=6, rows=3, color=p.METAL_H, bg=p.VOID)
        # Painted accent Esc & Enter keys (non-emissive)
        deck.rect(0.08, 0.14, 0.12, 0.18, fill=p.ORANGE)
        deck.rect(0.78, 0.42, 0.14, 0.18, fill=p.SHIRT_BLUE)
        # Spacebar highlight
        deck.rect(0.28, 0.70, 0.40, 0.14, fill=p.METAL_L)

        # Status lock LED
        led_col = p.LED_C if (is_active and a.frame == 0) else p.LED_G if is_active else p.METAL_M
        deck.dot(0.88, 0.16, led_col)
        deck.anchor("keys", 0.5, 0.5)


def render(a: Asset) -> None:
    """Render the `keyboard_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_keyboard(a, p)

    a.anchor("mount_bottom", 12, 11)
    a.hitbox("body", 2, 2, 20, 12)
