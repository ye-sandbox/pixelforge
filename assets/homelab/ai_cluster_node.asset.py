"""Liquid-cooled 4U AI cluster node (`64x48` front-2.5d) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="ai_cluster_node",
    style_id="homelab-16bit",
    width=64,
    height=48,
    perspective="front-2.5d",
    states=("healthy", "dusty", "faulty"),
    frames=2,
    fps=4,
    seed=303,
)


def _draw_rack_chassis(a: Asset, p: PaletteLookup) -> None:
    a.rect(6, 5, 52, 37, p.METAL_D)
    a.dither(7, 6, 50, 35, p.METAL_D, p.VOID, pattern="bayer4", ratio=0.2)
    a.line(6, 5, 57, 5, p.SMOKE)
    a.line(6, 5, 6, 41, p.METAL_H)
    a.line(57, 6, 57, 41, p.VOID)
    a.line(7, 41, 57, 41, p.VOID)

    # Rack ears and mounting bolts
    a.rect(4, 7, 2, 33, p.METAL_H)
    a.rect(58, 7, 2, 33, p.METAL_L)
    for by in (9, 19, 29, 38):
        a.put(5, by, p.SMOKE)
        a.put(58, by, p.METAL_H)

    # Feet
    a.rect(9, 42, 5, 1, p.VOID)
    a.rect(50, 42, 5, 1, p.VOID)


def _draw_compute_blades(a: Asset, p: PaletteLookup) -> None:
    for i in range(4):
        by = 8 + i * 7
        a.rect(9, by, 29, 6, p.METAL_M)
        a.line(9, by, 37, by, p.METAL_L)
        a.line(9, by + 5, 37, by + 5, p.VOID)

        for vx in range(11, 30, 3):
            a.rect(vx, by + 2, 2, 2, p.VOID)

        a.rect(32, by + 2, 2, 2, p.COPPER)
        if a.state == "faulty" and i == 2:
            blade_led = p.LED_R
        elif a.state == "dusty":
            blade_led = p.LED_A
        elif (i + a.frame) % 2 == 0:
            blade_led = p.LED_G
        else:
            blade_led = p.LED_C
        a.put(35, by + 2, blade_led)

    # Bottom telemetry LED strip
    a.rect(9, 37, 29, 3, p.VOID)
    for tx in range(11, 36, 3):
        if a.state == "faulty":
            color = p.LED_R if (tx + a.frame) % 2 == 0 else p.SPARK
        elif a.state == "dusty":
            color = p.LED_A if tx % 2 == 0 else p.SOLAR_B
        else:
            color = p.LED_C if (tx // 3) % 2 == a.frame else p.LED_G
        a.rect(tx, 38, 2, 1, color)


def _draw_cyan_manifold(a: Asset, p: PaletteLookup) -> None:
    a.rect(40, 8, 15, 32, p.VOID)
    a.line(40, 8, 54, 8, p.METAL_L)

    # Quick-disconnect fittings
    a.rect(43, 9, 9, 2, p.METAL_H)
    a.line(43, 9, 51, 9, p.SMOKE)
    a.rect(43, 37, 9, 2, p.METAL_L)

    dim_col = p.SOLAR_B if a.state in ("dusty", "faulty") else p.LED_C
    bright_col = p.LED_R if a.state == "faulty" else p.SOLAR_L

    a.rect(44, 11, 3, 26, dim_col)
    a.rect(48, 11, 3, 26, dim_col)

    offset = 0 if a.frame == 0 else 3
    for py in range(13 + offset, 35, 6):
        a.put(45, py, bright_col)
        a.put(49, py + 1, bright_col)

    # Center bridge manifold
    a.rect(43, 22, 9, 3, p.METAL_H)
    a.line(44, 23, 50, 23, p.LED_R if a.state == "faulty" else p.SOLAR_L)


def _draw_overlays(a: Asset, p: PaletteLookup) -> None:
    if a.state == "dusty":
        a.scatter(
            count=20,
            colors=(p.DUST_L, p.DUST_D),
            mask="opaque",
            bounds=(7, 6, 48, 34),
        )
        return

    if a.state == "faulty":
        sy = 22 if a.frame == 0 else 24
        a.put(39, sy, p.SPARK)
        a.put(40, sy - 1, p.LED_R)
        a.put(52, 34, p.LED_R if a.frame == 0 else p.SPARK)


def render(a: Asset) -> None:
    """Render the `ai_cluster_node` asset with blades, telemetry, and liquid manifold."""
    p = a.pal
    with a.layer("chassis", outline=p.INK):
        _draw_rack_chassis(a, p)
        _draw_compute_blades(a, p)
        _draw_cyan_manifold(a, p)
        _draw_overlays(a, p)

    a.anchor("foot", 32, 42)
    a.anchor("manifold", 47, 24)
    a.anchor("telemetry", 23, 38)
    a.hitbox("body", 4, 4, 56, 40)
