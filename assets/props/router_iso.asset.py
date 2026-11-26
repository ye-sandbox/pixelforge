"""Isometric Wi-Fi router micro-prop (`22x18` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="router_iso",
    style_id="homelab-16bit",
    width=22,
    height=18,
    perspective="iso-2:1",
    states=("idle", "active"),
    frames=2,
    fps=2,
    seed=515,
)


def _draw_antennas(a: Asset, p: PaletteLookup) -> None:
    with a.layer("antennas", outline=p.INK):
        a.line(7, 8, 6, 2, p.METAL_M)
        a.line(15, 8, 16, 2, p.METAL_M)


def _draw_body(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        11,
        15,
        8,
        5,
        3,
        top=p.METAL_L,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        highlight=p.METAL_H,
        anchor="bottom",
    )
    is_active = a.state == "active"
    with a.plane(p0=(4, 10), p1=(10, 13), p2=(4, 13)) as front:
        front.rect(0.10, 0.25, 0.80, 0.50, fill=p.VOID)
        pwr = p.LED_G if is_active else p.LED_A
        wan = (p.LED_C if a.frame == 0 else p.SOLAR_L) if is_active else p.METAL_D
        wifi = (p.LED_G if a.frame == 1 else p.LED_C) if is_active else p.METAL_D
        front.dot(0.24, 0.50, pwr)
        front.dot(0.50, 0.50, wan)
        front.dot(0.76, 0.50, wifi)


def render(a: Asset) -> None:
    """Render the `router_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_antennas(a, p)
    _draw_body(a, p)
    a.anchor("mount_bottom", 11, 15)
    a.anchor("top", 11, 8)
    a.hitbox("body", 2, 1, 18, 16)
