"""Isometric optical mouse micro-prop (`12x12` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="mouse_iso",
    style_id="homelab-16bit",
    width=12,
    height=12,
    perspective="iso-2:1",
    states=("idle", "active"),
    frames=1,
    fps=1,
    seed=508,
)


def _draw_mouse(a: Asset, p: PaletteLookup) -> None:
    is_active = a.state == "active"
    # Rear cord leading NE toward the back of the desk
    a.line(7, 4, 9, 3, p.METAL_D)
    a.iso_box(
        6,
        9,
        2,
        4,
        2,
        top=p.METAL_L,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        highlight=p.METAL_H,
        anchor="bottom",
    )
    # Scroll wheel near front (NE) + subtle active DPI indicator
    a.put(7, 4, p.LED_C if is_active else p.METAL_H)
    a.put(5, 5, p.WHITE)


def render(a: Asset) -> None:
    """Render the `mouse_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_mouse(a, p)

    a.anchor("mount_bottom", 6, 8)
    a.hitbox("body", 2, 2, 8, 8)
