"""Isometric HEPA air purifier micro-prop (`20x28` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="air_purifier_iso",
    style_id="homelab-16bit",
    width=20,
    height=28,
    perspective="iso-2:1",
    states=("idle", "active"),
    frames=2,
    fps=2,
    seed=521,
)


def _draw_body(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        10,
        25,
        6,
        6,
        14,
        top=p.WHITE,
        left=p.SMOKE,
        right=p.METAL_M,
        outline=p.INK,
        highlight=p.WHITE,
        anchor="bottom",
    )
    # Top exhaust fan grille
    a.iso_tile(10, 8, 4, p.METAL_D, height=2)


def _draw_intake_and_ring(a: Asset, p: PaletteLookup) -> None:
    is_active = a.state == "active"
    ring_col = (p.LED_C if a.frame == 0 else p.LED_G) if is_active else p.LED_A

    with a.plane(p0=(4, 10), p1=(9, 13), p2=(4, 22)) as front:
        # Air-quality status ring
        front.line(0.24, 0.14, 0.76, 0.14, ring_col)
        # Perforated HEPA intake grille
        front.grid(0.18, 0.34, 0.64, 0.54, cols=3, rows=4, color=p.METAL_D)


def render(a: Asset) -> None:
    """Render the `air_purifier_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_body(a, p)
    _draw_intake_and_ring(a, p)
    a.anchor("mount_bottom", 10, 25)
    a.anchor("top", 10, 8)
    a.hitbox("body", 3, 4, 14, 23)
