"""Isometric UPS battery backup tower micro-prop (`20x26` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="ups_battery_iso",
    style_id="homelab-16bit",
    width=20,
    height=26,
    perspective="iso-2:1",
    states=("idle", "active"),
    frames=2,
    fps=2,
    seed=520,
)


def _draw_chassis(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        10,
        23,
        6,
        9,
        12,
        top=p.METAL_M,
        left=p.METAL_D,
        right=p.VOID,
        outline=p.INK,
        highlight=p.METAL_L,
        anchor="bottom",
    )


def _draw_front_panel(a: Asset, p: PaletteLookup) -> None:
    is_active = a.state == "active"
    with a.plane(p0=(3, 8), p1=(9, 11), p2=(3, 20)) as front:
        # Backlit LCD status window
        lcd_col = p.SCREEN_L if is_active else p.SCREEN_D
        front.rect(0.18, 0.14, 0.64, 0.24, fill=lcd_col)
        if is_active:
            bar_col = p.LED_G if a.frame == 0 else p.LED_C
            front.line(0.28, 0.26, 0.70, 0.26, bar_col)
        # Status LEDs
        front.dot(0.30, 0.48, p.LED_G if is_active else p.LED_A)
        front.dot(0.68, 0.48, p.LED_C if (is_active and a.frame == 1) else p.METAL_D)
        # Intake vents
        front.grid(0.20, 0.62, 0.60, 0.26, cols=3, rows=3, color=p.INK)


def render(a: Asset) -> None:
    """Render the `ups_battery_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_chassis(a, p)
    _draw_front_panel(a, p)
    a.anchor("mount_bottom", 10, 23)
    a.anchor("top", 10, 6)
    a.hitbox("body", 2, 2, 18, 23)
