"""Isometric open-frame triple-GPU rig (`30x28` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="used_gpu_rig_iso",
    style_id="homelab-16bit",
    width=30,
    height=28,
    perspective="iso-2:1",
    states=("healthy", "dusty", "faulty"),
    frames=2,
    fps=4,
    seed=203,
)


def _draw_frame_and_deck(a: Asset, p: PaletteLookup) -> None:
    # Lower motherboard deck + PSU
    a.iso_box(
        15,
        22,
        12,
        8,
        2,
        top=p.PCB_G,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        anchor="center",
    )
    a.iso_box(
        20,
        21,
        4,
        4,
        3,
        top=p.METAL_L,
        left=p.METAL_D,
        right=p.VOID,
        anchor="center",
    )
    a.put(21, 22, p.LED_R if a.state == "faulty" and a.frame == 1 else p.LED_G)

    # Aluminum extrusion corner posts and top rail
    a.line(5, 8, 5, 20, p.METAL_H)
    a.line(13, 4, 13, 16, p.METAL_H)
    a.line(25, 10, 25, 22, p.METAL_L)
    a.line(17, 14, 17, 26, p.METAL_H)
    a.line(13, 4, 25, 10, p.SMOKE)
    a.line(5, 8, 17, 14, p.SMOKE)
    a.line(5, 8, 13, 4, p.METAL_L)


def _draw_gpus(a: Asset, p: PaletteLookup) -> None:
    gpu_origins = ((9, 13), (13, 15), (17, 17))
    for idx, (gx, gy) in enumerate(gpu_origins):
        a.iso_box(
            gx,
            gy,
            3,
            5,
            7,
            top=p.METAL_L,
            left=p.METAL_M,
            right=p.METAL_D,
            outline=p.INK,
            anchor="center",
        )
        # Copper heatpipe tick on top
        a.put(gx, gy - 2, p.COPPER)
        # Fan hub + animated blade glint
        stalled = a.state == "faulty" and idx == 1
        a.put(gx - 1, gy + 2, p.VOID)
        if not stalled:
            blade = p.DUST_L if a.state == "dusty" else p.METAL_H
            a.put(gx - 1 + (a.frame % 2), gy + 1, blade)
        # Status LED
        led = p.LED_G if a.frame == 0 else p.LED_C
        if a.state == "dusty" and idx == 1:
            led = p.LED_A
        if a.state == "faulty":
            led = p.LED_R if idx == 1 else p.LED_A
        a.put(gx + 1, gy, led)
        # Riser ribbon to motherboard
        a.line(gx, gy + 4, gx, gy + 6, p.WARM_AMBER)


def _draw_overlays(a: Asset, p: PaletteLookup) -> None:
    if a.state == "dusty":
        a.scatter(
            count=10,
            colors=(p.DUST_L, p.DUST_D),
            mask="opaque",
            bounds=(5, 6, 20, 18),
        )
        return

    if a.state == "faulty":
        sx = 14 if a.frame == 0 else 15
        sy = 11 if a.frame == 0 else 10
        a.put(sx, sy, p.SPARK)
        a.put(sx + 1, sy - 1, p.LED_R)


def render(a: Asset) -> None:
    """Render the `used_gpu_rig_iso` asset proportional to `bedroom_desk_iso`."""
    p = a.pal
    with a.layer("rig", outline=p.INK):
        _draw_frame_and_deck(a, p)
        _draw_gpus(a, p)
        _draw_overlays(a, p)

    a.anchor("foot", 15, 22)
    a.anchor("gpu_0", 9, 13)
    a.anchor("gpu_1", 13, 15)
    a.anchor("gpu_2", 17, 17)
    a.hitbox("body", 4, 3, 22, 24)
