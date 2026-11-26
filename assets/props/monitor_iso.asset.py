"""Isometric workstation monitor micro-prop (`28x26` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="monitor_iso",
    style_id="homelab-16bit",
    width=28,
    height=26,
    perspective="iso-2:1",
    states=("idle", "active"),
    frames=2,
    fps=2,
    seed=502,
)


def _draw_stand(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        14,
        23,
        6,
        5,
        2,
        top=p.METAL_L,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        highlight=p.METAL_H,
        anchor="bottom",
    )
    with a.layer("neck", outline=p.INK):
        a.rect(13, 15, 2, 5, p.METAL_D)
        a.put(13, 16, p.METAL_M)
        a.put(13, 17, p.METAL_M)


def _draw_panel(a: Asset, p: PaletteLookup) -> None:
    is_active = a.state == "active"
    with a.layer("panel", outline=p.INK), a.plane(p0=(5, 2), p1=(23, 11), p2=(5, 12)) as screen:
        screen.rect(
            0.0,
            0.0,
            1.0,
            1.0,
            fill=p.METAL_M,
            bevel=(p.METAL_L, p.METAL_D),
            extrude_y=1,
            side=p.VOID,
        )
        screen.rect(0.10, 0.12, 0.80, 0.72, fill=p.SCREEN_D)

        if is_active:
            screen.line(0.18, 0.28, 0.76, 0.28, p.LED_G)
            screen.line(0.18, 0.44, 0.68, 0.44, p.SOLAR_L)
            screen.line(0.18, 0.60, 0.56, 0.60, p.LED_C)
            if a.frame == 0:
                screen.rect(0.60, 0.56, 0.10, 0.12, fill=p.SPARK)
        else:
            screen.line(0.18, 0.34, 0.64, 0.34, p.SCREEN_L)
            screen.line(0.18, 0.52, 0.48, 0.52, p.SCREEN_L)
            if a.frame == 0:
                screen.dot(0.54, 0.52, p.LED_C)

        led_col = p.LED_G if is_active else p.LED_A
        screen.dot(0.84, 0.90, led_col)
        screen.anchor("screen", 0.5, 0.48)


def render(a: Asset) -> None:
    """Render the `monitor_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_stand(a, p)
    _draw_panel(a, p)

    a.anchor("mount_bottom", 14, 23)
    a.hitbox("body", 3, 1, 22, 23)
