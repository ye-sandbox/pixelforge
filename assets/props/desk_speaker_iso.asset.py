"""Isometric studio desk speaker micro-prop (`18x22` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="desk_speaker_iso",
    style_id="homelab-16bit",
    width=18,
    height=22,
    perspective="iso-2:1",
    states=("idle", "active"),
    frames=2,
    fps=2,
    seed=513,
)


def _draw_cabinet(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        9,
        19,
        6,
        6,
        10,
        top=p.METAL_L,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        highlight=p.METAL_H,
        anchor="bottom",
    )


def _draw_drivers(a: Asset, p: PaletteLookup) -> None:
    is_active = a.state == "active"
    with a.plane(p0=(3, 7), p1=(8, 10), p2=(3, 17)) as front:
        front.rect(0.14, 0.10, 0.72, 0.80, fill=p.VOID)
        # Tweeter
        front.rect(0.36, 0.18, 0.28, 0.16, fill=p.METAL_H)
        # Woofer cone (pulses subtly on active frame 1)
        cone_col = p.COPPER if (is_active and a.frame == 1) else p.WARM_AMBER
        front.rect(0.24, 0.44, 0.52, 0.34, fill=p.METAL_M)
        front.rect(0.36, 0.52, 0.28, 0.18, fill=cone_col)
        led = p.LED_G if is_active else p.LED_A
        front.dot(0.74, 0.84, led)


def render(a: Asset) -> None:
    """Render the `desk_speaker_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_cabinet(a, p)
    _draw_drivers(a, p)
    a.anchor("mount_bottom", 9, 19)
    a.anchor("top", 9, 4)
    a.hitbox("body", 2, 2, 14, 19)
