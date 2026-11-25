"""Open-frame triple-GPU mining/compute rig (`64x48` front-2.5d) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

SPEC = AssetSpec(
    id="used_gpu_rig",
    style_id="homelab-16bit",
    width=64,
    height=48,
    perspective="front-2.5d",
    states=("healthy", "dusty", "faulty"),
    frames=2,
    fps=4,
    seed=202,
)


def _draw_open_frame(a: Asset, p: PaletteLookup) -> None:
    # Aluminum extrusion rails (top-left lit, right-bottom shaded)
    a.rect(5, 6, 54, 3, p.METAL_H)
    a.line(5, 6, 58, 6, p.SMOKE)

    a.rect(4, 39, 56, 3, p.METAL_H)
    a.line(4, 39, 59, 39, p.SMOKE)
    a.line(4, 41, 59, 41, p.METAL_L)

    a.rect(5, 6, 3, 35, p.METAL_H)
    a.line(5, 6, 5, 40, p.SMOKE)

    a.rect(56, 6, 3, 35, p.METAL_L)
    a.line(56, 6, 56, 39, p.METAL_H)

    # Rubber feet
    a.rect(6, 42, 4, 1, p.VOID)
    a.rect(54, 42, 4, 1, p.VOID)


def _draw_lower_deck(a: Asset, p: PaletteLookup) -> None:
    # Motherboard tray
    a.rect(9, 34, 31, 5, p.PCB_G)
    a.dither(9, 35, 31, 4, p.PCB_G, p.PCB_D, pattern="bayer2", ratio=0.35)
    a.line(9, 34, 39, 34, p.PCB_D)
    a.rect(14, 32, 6, 3, p.METAL_H)
    a.line(14, 32, 19, 32, p.SMOKE)
    a.line(23, 35, 36, 35, p.COPPER)

    # PSU brick on bottom-right
    a.rect(42, 30, 13, 9, p.METAL_D)
    a.line(42, 30, 54, 30, p.METAL_L)
    a.line(42, 30, 42, 38, p.METAL_L)
    a.rect(44, 32, 5, 5, p.VOID)
    a.rect(50, 32, 3, 2, p.COPPER)
    a.put(52, 36, p.LED_R if a.state == "faulty" and a.frame == 1 else p.LED_G)


def _draw_single_gpu(a: Asset, p: PaletteLookup, x: int, gpu_index: int) -> None:
    w = 13
    h = 17
    y = 10

    # Shroud body + top-left bevel
    a.rect(x, y, w, h, p.METAL_M)
    a.dither(x + 1, y + 1, w - 2, h - 2, p.METAL_M, p.METAL_D, pattern="bayer4", ratio=0.25)
    a.line(x, y, x + w - 1, y, p.SMOKE)
    a.line(x, y, x, y + h - 1, p.METAL_H)
    a.line(x + w - 1, y + 1, x + w - 1, y + h - 1, p.METAL_D)
    a.line(x + 1, y + h - 1, x + w - 1, y + h - 1, p.METAL_D)

    # Copper heatpipes peeking above shroud
    a.rect(x + 2, y - 1, 3, 1, p.COPPER)
    a.rect(x + 8, y - 1, 3, 1, p.WARM_AMBER)

    # Fan housing
    fcx = x + 6
    fcy = y + 9
    a.circle(fcx, fcy, 4, p.VOID, fill=True)
    a.circle(fcx, fcy, 4, p.METAL_L, fill=False)

    # Animated fan blades (stalled on GPU 1 when faulty)
    stalled = a.state == "faulty" and gpu_index == 1
    if not stalled:
        blade_col = p.DUST_L if a.state == "dusty" else p.METAL_H
        if a.frame == 0:
            a.line(fcx - 3, fcy, fcx + 3, fcy, blade_col)
            a.line(fcx, fcy - 3, fcx, fcy + 3, blade_col)
        else:
            a.line(fcx - 2, fcy - 2, fcx + 2, fcy + 2, blade_col)
            a.line(fcx - 2, fcy + 2, fcx + 2, fcy - 2, blade_col)
    a.put(fcx, fcy, p.SMOKE)

    # Top status LED
    led = p.LED_G if a.frame == 0 else p.LED_C
    if a.state == "dusty" and gpu_index == 1:
        led = p.LED_A
    if a.state == "faulty":
        led = p.LED_R if gpu_index == 1 else p.LED_A
    a.put(x + 10, y + 2, led)

    # Riser cable dropping to motherboard
    rx = x + 6
    a.line(rx, y + h, rx, 33, p.WARM_AMBER)
    a.line(rx + 1, y + h, rx + 1, 33, p.SOLAR_B)


def _draw_overlays(a: Asset, p: PaletteLookup) -> None:
    if a.state == "dusty":
        a.scatter(
            count=24,
            colors=(p.DUST_L, p.DUST_D),
            mask="opaque",
            bounds=(6, 8, 52, 32),
        )
        return

    if a.state == "faulty":
        sx = 31 if a.frame == 0 else 33
        sy = 28 if a.frame == 0 else 27
        a.put(sx, sy, p.SPARK)
        a.put(sx + 1, sy - 1, p.LED_R)
        a.put(sx - 1, sy + 1, p.SPARK)
        a.put(44, 29, p.LED_R if a.frame == 0 else p.SPARK)


def render(a: Asset) -> None:
    """Render the `used_gpu_rig` asset with 3 GPUs, fan rotation, and fault states."""
    p = a.pal
    with a.layer("rig", outline=p.INK):
        _draw_open_frame(a, p)
        _draw_lower_deck(a, p)
        _draw_single_gpu(a, p, 9, 0)
        _draw_single_gpu(a, p, 25, 1)
        _draw_single_gpu(a, p, 41, 2)
        _draw_overlays(a, p)

    a.anchor("foot", 32, 42)
    a.anchor("gpu_0", 15, 19)
    a.anchor("gpu_1", 31, 19)
    a.anchor("gpu_2", 47, 19)
    a.anchor("psu", 48, 34)
    a.hitbox("body", 3, 5, 58, 38)
