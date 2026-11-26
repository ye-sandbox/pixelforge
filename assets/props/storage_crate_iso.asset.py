"""Isometric equipment storage crate micro-prop (`26x24` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="storage_crate_iso",
    style_id="homelab-16bit",
    width=26,
    height=24,
    perspective="iso-2:1",
    states=("idle", "active"),
    frames=1,
    fps=1,
    seed=504,
)


def _draw_crate(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        13,
        21,
        10,
        10,
        10,
        top=p.WOOD_L,
        left=p.WOOD_M,
        right=p.WOOD_D,
        outline=p.INK,
        highlight=p.DUST_L,
        anchor="bottom",
    )
    # Recessed top panel
    a.iso_tile(13, 6, 6, p.WOOD_M, height=3)


def _draw_hardware_trim(a: Asset, p: PaletteLookup) -> None:
    is_active = a.state == "active"
    with a.plane(p0=(4, 7), p1=(12, 11), p2=(4, 16)) as left:
        left.rect(0.10, 0.14, 0.80, 0.14, fill=p.METAL_M)
        left.rect(0.10, 0.72, 0.80, 0.14, fill=p.METAL_D)
        badge_col = p.SOLAR_B if is_active else p.METAL_H
        left.rect(0.32, 0.38, 0.36, 0.22, fill=badge_col)
        if is_active:
            left.dot(0.76, 0.48, p.LED_G)

    with a.plane(p0=(14, 11), p1=(22, 7), p2=(14, 20)) as right:
        right.rect(0.10, 0.14, 0.80, 0.14, fill=p.METAL_D)
        right.rect(0.10, 0.72, 0.80, 0.14, fill=p.VOID)


def render(a: Asset) -> None:
    """Render the `storage_crate_iso` micro-prop with `mount_bottom` anchor."""
    p = a.pal
    _draw_crate(a, p)
    _draw_hardware_trim(a, p)

    a.anchor("mount_bottom", 13, 21)
    a.anchor("top", 13, 6)
    a.hitbox("body", 2, 0, 23, 23)
