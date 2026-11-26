"""Isometric 1U network switch micro-prop (`28x20` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="network_switch_iso",
    style_id="homelab-16bit",
    width=28,
    height=20,
    perspective="iso-2:1",
    states=("idle", "active"),
    frames=2,
    fps=2,
    seed=505,
)


def _draw_chassis(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        14,
        17,
        11,
        9,
        5,
        top=p.METAL_L,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        highlight=p.METAL_H,
        anchor="bottom",
    )
    a.iso_tile(14, 7, 6, p.METAL_M, height=3)


def _draw_ports(a: Asset, p: PaletteLookup) -> None:
    is_active = a.state == "active"
    with a.plane(p0=(4, 8), p1=(13, 12), p2=(4, 12)) as front:
        front.rect(0.06, 0.14, 0.88, 0.72, fill=p.METAL_D)
        for idx in range(5):
            u = 0.12 + idx * 0.16
            front.rect(u, 0.42, 0.10, 0.36, fill=p.VOID)
            if is_active:
                led = p.LED_G if (idx + a.frame) % 2 == 0 else p.LED_C
            else:
                led = p.LED_A if idx == 0 else p.LED_GD
            front.dot(u + 0.04, 0.24, led)
            front.anchor(f"port_{idx}", u + 0.05, 0.60, kind="rj45", dir=(-1, 1))
        front.anchor("ports", 0.5, 0.5)


def render(a: Asset) -> None:
    """Render the `network_switch_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_chassis(a, p)
    _draw_ports(a, p)

    a.anchor("mount_bottom", 14, 17)
    a.hitbox("body", 2, 2, 24, 16)
