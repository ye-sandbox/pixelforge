"""Isometric desktop PC tower micro-prop (`24x30` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="pc_tower_iso",
    style_id="homelab-16bit",
    width=24,
    height=30,
    perspective="iso-2:1",
    states=("idle", "active"),
    frames=2,
    fps=2,
    seed=509,
)


def _draw_chassis(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        11,
        26,
        7,
        11,
        15,
        top=p.METAL_L,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        highlight=p.METAL_H,
        anchor="bottom",
    )
    # Top mesh dust filter centered on top face
    a.iso_tile(11, 6, 5, p.METAL_D, height=3)


def _draw_front_and_glass(a: Asset, p: PaletteLookup) -> None:
    is_active = a.state == "active"

    # Front intake mesh & power LED (facing SW toward user)
    with a.plane(p0=(2, 8), p1=(9, 12), p2=(2, 23)) as front:
        front.rect(0.14, 0.14, 0.72, 0.72, fill=p.VOID)
        front.line(0.24, 0.08, 0.56, 0.08, p.METAL_H)
        led = p.LED_G if is_active else p.LED_A
        front.dot(0.76, 0.08, led)
        if is_active:
            fan_col = p.LED_C if a.frame == 0 else p.SOLAR_L
            front.dot(0.50, 0.34, fan_col)
            front.dot(0.50, 0.64, fan_col)
        else:
            front.dot(0.50, 0.34, p.METAL_M)
            front.dot(0.50, 0.64, p.METAL_M)
        front.anchor("front_io", 0.50, 0.10)

    # Tempered glass side panel showing motherboard & GPU (facing SE)
    with a.plane(p0=(9, 12), p1=(20, 6), p2=(9, 27)) as glass:
        glass.rect(0.10, 0.08, 0.80, 0.80, fill=p.GLASS_D)
        glass.rect(0.18, 0.14, 0.64, 0.68, fill=p.SCREEN_D)
        # Motherboard & horizontal GPU shroud
        glass.rect(0.24, 0.18, 0.38, 0.44, fill=p.PCB_G)
        glass.rect(0.22, 0.48, 0.56, 0.12, fill=p.METAL_H)
        # Bottom PSU shroud
        glass.rect(0.18, 0.72, 0.64, 0.10, fill=p.METAL_D)
        if is_active:
            accent = p.LED_C if a.frame == 0 else p.LED_G
            glass.line(0.28, 0.52, 0.64, 0.52, accent)
            glass.dot(0.46, 0.28, p.SOLAR_L)


def render(a: Asset) -> None:
    """Render the `pc_tower_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_chassis(a, p)
    _draw_front_and_glass(a, p)

    a.anchor("mount_bottom", 11, 23)
    a.hitbox("body", 1, 1, 20, 26)
