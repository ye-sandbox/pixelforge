"""Isometric liquid-cooled 4U AI cluster node (`34x38` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="ai_cluster_node_iso",
    style_id="homelab-16bit",
    width=34,
    height=38,
    perspective="iso-2:1",
    states=("healthy", "dusty", "faulty"),
    frames=2,
    fps=4,
    seed=304,
)


def _draw_chassis(a: Asset, p: PaletteLookup) -> None:
    a.iso_box(
        17,
        34,
        14,
        14,
        18,
        top=p.METAL_L,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        highlight=p.SMOKE,
        anchor="bottom",
    )
    # Top vent grille
    a.iso_tile(17, 9, 14, p.METAL_D, height=7)


def _draw_blades_face(a: Asset, p: PaletteLookup) -> None:
    with a.plane(p0=(4, 10), p1=(16, 16), p2=(4, 26)) as left:
        for i in range(4):
            v0 = 0.08 + i * 0.19
            left.rect(0.08, v0, 0.84, 0.13, fill=p.METAL_D)
            left.line(0.14, v0 + 0.06, 0.60, v0 + 0.06, p.VOID)
            left.dot(0.70, v0 + 0.06, p.COPPER)

            if a.state == "faulty" and i == 2:
                led = p.LED_R
            elif a.state == "dusty":
                led = p.LED_A
            elif (i + a.frame) % 2 == 0:
                led = p.LED_G
            else:
                led = p.LED_C
            left.dot(0.84, v0 + 0.06, led)

        # Bottom telemetry strip
        left.rect(0.08, 0.86, 0.84, 0.09, fill=p.VOID)
        for step in range(4):
            u = 0.16 + step * 0.20
            if a.state == "faulty":
                col = p.LED_R if (step + a.frame) % 2 == 0 else p.SPARK
            elif a.state == "dusty":
                col = p.LED_A if step % 2 == 0 else p.SOLAR_B
            else:
                col = p.LED_C if step % 2 == a.frame else p.LED_G
            left.dot(u, 0.90, col)
        left.anchor("telemetry", 0.5, 0.90)


def _draw_manifold_face(a: Asset, p: PaletteLookup) -> None:
    with a.plane(p0=(18, 16), p1=(30, 10), p2=(18, 32)) as right:
        right.rect(0.14, 0.08, 0.72, 0.84, fill=p.VOID)
        right.rect(0.22, 0.10, 0.56, 0.09, fill=p.METAL_H)
        right.rect(0.22, 0.81, 0.56, 0.09, fill=p.METAL_L)

        dim_col = p.SOLAR_B if a.state in ("dusty", "faulty") else p.LED_C
        bright_col = p.LED_R if a.state == "faulty" else p.SOLAR_L
        right.rect(0.28, 0.19, 0.16, 0.62, fill=dim_col)
        right.rect(0.56, 0.19, 0.16, 0.62, fill=dim_col)

        pulse_v = 0.30 if a.frame == 0 else 0.60
        right.dot(0.36, pulse_v, bright_col)
        right.dot(0.64, 0.90 - pulse_v, bright_col)

        right.rect(0.22, 0.46, 0.56, 0.08, fill=p.METAL_H)
        right.line(0.26, 0.50, 0.74, 0.50, bright_col)
        right.anchor("manifold", 0.5, 0.50)


def _draw_overlays(a: Asset, p: PaletteLookup) -> None:
    if a.state == "dusty":
        a.scatter(
            count=12,
            colors=(p.DUST_L, p.DUST_D),
            mask="opaque",
            bounds=(4, 5, 26, 26),
        )
        return

    if a.state == "faulty":
        sy = 18 if a.frame == 0 else 20
        a.put(18, sy, p.SPARK)
        a.put(19, sy - 1, p.LED_R)


def render(a: Asset) -> None:
    """Render the `ai_cluster_node_iso` asset sized for the `bedroom_desk_iso` side rack."""
    p = a.pal
    with a.layer("chassis", outline=p.INK):
        _draw_chassis(a, p)
        _draw_blades_face(a, p)
        _draw_manifold_face(a, p)
        _draw_overlays(a, p)

    a.anchor("foot", 17, 27)
    a.hitbox("body", 2, 1, 30, 34)
