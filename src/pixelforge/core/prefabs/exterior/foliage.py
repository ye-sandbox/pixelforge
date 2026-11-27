"""Deterministic exterior foliage and isometric tree prefabs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from pixelforge.core.builder import Asset
from pixelforge.core.prefabs.architecture.room import Canvas
from pixelforge.core.prng import mulberry32
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import TRANSPARENT_INDEX, LightingAngle

TreeSpecies = Literal["oak", "pine", "cypress"]


@dataclass(frozen=True)
class IsoTreeAnchors:
    """Semantic anchors emitted or computed for `iso_tree`."""

    foot: tuple[int, int]
    canopy_center: tuple[int, int]
    trunk_top: tuple[int, int]


def _resolve_lighting_angle(
    target: Canvas,
    lighting_angle: LightingAngle | None,
) -> LightingAngle:
    if lighting_angle is not None:
        return lighting_angle
    return target.style.lighting_angle if isinstance(target, Asset) else "top-left"


def _light_offset(angle: LightingAngle, dx: int, dy: int) -> tuple[int, int]:
    if angle == "top-left":
        return (-dx, -dy)
    if angle == "top-right":
        return (dx, -dy)
    return (0, -dy)


def _clip_and_blit_shade(base: IndexedSurface, shade: IndexedSurface) -> None:
    """Alpha-lock `shade` to opaque pixels of `base` (`clip='opaque'`) and composite."""
    opaque = base.data != TRANSPARENT_INDEX
    erase_mask = (shade.data != TRANSPARENT_INDEX) & (~opaque)
    if np.any(erase_mask):
        shade.data[erase_mask] = TRANSPARENT_INDEX
        if shade.maps is not None:
            shade.maps.write_global_mask(erase_mask, erase=True)
    base.blit_layer(shade, 0, 0)


def _scatter_on_opaque(
    patch: IndexedSurface,
    colors: Sequence[int],
    count: int,
    seed: int,
) -> None:
    """Deterministically scatter `count` pixels from `colors` onto opaque pixels."""
    if count <= 0 or not colors:
        return
    ys, xs = np.nonzero(patch.data != TRANSPARENT_INDEX)
    n_opaque = len(xs)
    if n_opaque == 0:
        return
    rng = mulberry32(seed ^ 0x51A7)
    palette = tuple(int(c) for c in colors)
    for _ in range(count):
        idx = int(rng() * n_opaque) % n_opaque
        color = palette[int(rng() * len(palette)) % len(palette)]
        patch.put(int(xs[idx]), int(ys[idx]), color)


def _draw_cluster_lobes(
    patch: IndexedSurface,
    lx: int,
    ly: int,
    rx: int,
    ry: int,
    *,
    fill: int,
    lobes: int,
    seed: int,
) -> None:
    patch.ellipse(lx, ly, rx, ry, fill, fill=True)
    if lobes <= 1:
        return
    rng = mulberry32(seed ^ 0x10B3)
    side_rx = max(2, round(rx * 0.62))
    side_ry = max(2, round(ry * 0.65))
    dx = max(1, round(rx * 0.45))
    dy = max(1, round(ry * 0.22))
    offsets: tuple[tuple[int, int, int, int], ...] = (
        (-dx, dy, side_rx, side_ry),
        (dx, dy, side_rx, side_ry),
        (0, -max(1, round(ry * 0.35)), max(2, round(rx * 0.68)), max(2, round(ry * 0.62))),
        (-max(1, dx // 2), -dy, max(2, round(rx * 0.52)), max(2, round(ry * 0.52))),
        (max(1, dx // 2), -dy, max(2, round(rx * 0.52)), max(2, round(ry * 0.52))),
    )
    for ox, oy, erx, ery in offsets[: lobes - 1]:
        jitter_x = round((rng() - 0.5) * 1.5)
        jitter_y = round((rng() - 0.5) * 1.5)
        patch.ellipse(lx + ox + jitter_x, ly + oy + jitter_y, erx, ery, fill, fill=True)


def foliage_cluster(
    target: Canvas,
    cx: int | float,
    cy: int | float,
    rx: int,
    ry: int,
    *,
    fill: int,
    highlight: int | None = None,
    shadow: int | None = None,
    outline: int | None = None,
    speckles: Sequence[int] | None = None,
    speckle_count: int = 8,
    lobes: int = 4,
    seed: int = 0,
    lighting_angle: LightingAngle | None = None,
    cleanup_jaggies: bool = True,
) -> None:
    """Draw a deterministic organic foliage cluster with `clip='opaque'` volume shading."""
    irx = max(2, int(rx))
    iry = max(2, int(ry))
    icx = round(cx)
    icy = round(cy)
    lobe_count = max(1, min(6, int(lobes)))
    angle = _resolve_lighting_angle(target, lighting_angle)

    pad = 4 + max(2, round(max(irx, iry) * 0.5))
    w = irx * 2 + pad * 2 + 1
    h = iry * 2 + pad * 2 + 1
    lx = w // 2
    ly = h // 2
    ox = icx - lx
    oy = icy - ly

    patch = IndexedSurface(w, h, track_maps=target.surface.has_maps)
    _draw_cluster_lobes(patch, lx, ly, irx, iry, fill=fill, lobes=lobe_count, seed=seed)

    if shadow is not None or highlight is not None:
        shade = IndexedSurface(w, h, track_maps=patch.has_maps)
        ldx, ldy = _light_offset(angle, max(1, irx // 3), max(1, iry // 3))
        if shadow is not None:
            shade.ellipse(
                lx - ldx,
                ly - ldy + max(1, iry // 4),
                max(2, round(irx * 0.92)),
                max(2, round(iry * 0.85)),
                shadow,
                fill=True,
            )
            # Re-carve main midtone center so shadow forms a crisp underside crescent.
            shade.ellipse(
                lx + ldx // 2,
                ly + ldy // 2,
                max(2, round(irx * 0.72)),
                max(2, round(iry * 0.68)),
                fill,
                fill=True,
            )
        if highlight is not None:
            shade.ellipse(
                lx + ldx,
                ly + ldy,
                max(1, round(irx * 0.58)),
                max(1, round(iry * 0.52)),
                highlight,
                fill=True,
            )
            shade.ellipse(
                lx + ldx - max(1, irx // 5),
                ly + ldy - max(1, iry // 5),
                max(1, round(irx * 0.32)),
                max(1, round(iry * 0.28)),
                highlight,
                fill=True,
            )
        _clip_and_blit_shade(patch, shade)

    if speckles and speckle_count > 0:
        _scatter_on_opaque(patch, speckles, speckle_count, seed)

    if cleanup_jaggies:
        patch.cleanup_jaggies()
    if outline is not None:
        patch.auto_outline(outline)
    target.surface.blit_layer(patch, ox, oy)


def _draw_tree_trunk(
    target: Canvas,
    icx: int,
    ify: int,
    trunk_top_y: int,
    trunk_r: int,
    *,
    trunk: int,
    trunk_lit: int | None,
    outline: int | None,
    angle: LightingAngle,
) -> None:
    pad = 4
    min_x = icx - trunk_r - pad
    min_y = trunk_top_y - trunk_r - pad
    w = (trunk_r + pad) * 2 + 1
    h = max(4, (ify - trunk_top_y) + trunk_r * 2 + pad * 2)
    surf = IndexedSurface(w, h, track_maps=target.surface.has_maps)
    lx = icx - min_x
    top_ly = trunk_top_y - min_y
    bot_ly = (ify - 1) - min_y

    surf.capsule(lx, top_ly, lx, bot_ly, trunk_r, trunk)
    if trunk_lit is not None:
        shade = IndexedSurface(w, h, track_maps=surf.has_maps)
        lit_dx = -1 if angle == "top-left" else (1 if angle == "top-right" else 0)
        strip_x = lx + lit_dx * max(1, trunk_r // 2)
        shade.line(strip_x, top_ly, strip_x, bot_ly, trunk_lit)
        _clip_and_blit_shade(surf, shade)
    if outline is not None:
        surf.auto_outline(outline)
    target.surface.blit_layer(surf, min_x, min_y)


def _draw_pine_canopy(
    target: Canvas,
    cx: int,
    base_y: int,
    rx: int,
    canopy_h: int,
    *,
    foliage: int,
    foliage_light: int | None,
    foliage_dark: int | None,
    outline: int | None,
    sway: int,
    seed: int,
    angle: LightingAngle,
) -> None:
    pad = 6 + abs(sway)
    w = rx * 2 + pad * 2 + 1
    h = canopy_h + pad * 2 + 2
    ox = cx - w // 2
    oy = (base_y - canopy_h) - pad
    patch = IndexedSurface(w, h, track_maps=target.surface.has_maps)
    lx = w // 2

    tiers: tuple[tuple[float, float, float, float], ...] = (
        (0.55, 1.0, 1.0, 0.0),
        (0.28, 0.72, 0.78, 0.5),
        (0.0, 0.45, 0.52, 1.0),
    )
    for top_frac, bot_frac, width_scale, sway_scale in tiers:
        ty = pad + round(top_frac * canopy_h)
        by = pad + round(bot_frac * canopy_h)
        half_w = max(2, round(rx * width_scale))
        sx = round(sway * sway_scale)
        patch.polygon(((lx + sx, ty), (lx + sx - half_w, by), (lx + sx + half_w, by)), foliage)

    if foliage_dark is not None or foliage_light is not None:
        shade = IndexedSurface(w, h, track_maps=patch.has_maps)
        lit_sign = -1 if angle == "top-left" else (1 if angle == "top-right" else 0)
        if foliage_dark is not None:
            sx0 = lx - lit_sign * (rx + 2) if lit_sign != 0 else lx
            shade.rect(sx0, 0, rx + 4, h, foliage_dark)
        if foliage_light is not None:
            for top_frac, bot_frac, width_scale, sway_scale in tiers:
                ty = pad + round(top_frac * canopy_h) + 1
                by = pad + round(bot_frac * canopy_h) - 1
                half_w = max(1, round(rx * width_scale * 0.45))
                sx = round(sway * sway_scale) + lit_sign * max(1, half_w // 2)
                tri = ((lx + sx, ty), (lx + sx - half_w, by), (lx + sx + half_w, by))
                shade.polygon(tri, foliage_light)
        _clip_and_blit_shade(patch, shade)

    speckles = tuple(c for c in (foliage_light, foliage_dark) if c is not None)
    if speckles:
        _scatter_on_opaque(patch, speckles, 6, seed)
    if outline is not None:
        patch.auto_outline(outline)
    target.surface.blit_layer(patch, ox, oy)


def iso_tree(
    target: Canvas,
    cx: int | float,
    foot_y: int | float,
    *,
    trunk: int,
    foliage: int,
    trunk_lit: int | None = None,
    foliage_light: int | None = None,
    foliage_dark: int | None = None,
    outline: int | None = None,
    shadow: int | None = None,
    species: TreeSpecies = "oak",
    height: int = 28,
    canopy_rx: int | None = None,
    canopy_ry: int | None = None,
    sway: int = 0,
    seed: int = 0,
    lighting_angle: LightingAngle | None = None,
    emit_anchor: bool = True,
    emit_hitbox: bool = False,
) -> IsoTreeAnchors:
    """Draw a grounded isometric tree (`oak`, `pine`, or `cypress`) with optional `foot` anchor."""
    icx = round(cx)
    ify = round(foot_y)
    total_h = max(12, int(height))
    angle = _resolve_lighting_angle(target, lighting_angle)

    if species == "pine":
        rx = canopy_rx if canopy_rx is not None else max(5, round(total_h * 0.34))
        ry = canopy_ry if canopy_ry is not None else max(8, round(total_h * 0.72))
        trunk_h = max(4, round(total_h * 0.28))
        trunk_r = max(1, round(total_h * 0.06))
        canopy_cy = ify - trunk_h - ry // 2
    elif species == "cypress":
        rx = canopy_rx if canopy_rx is not None else max(3, round(total_h * 0.20))
        ry = canopy_ry if canopy_ry is not None else max(8, round(total_h * 0.44))
        trunk_h = max(4, round(total_h * 0.24))
        trunk_r = max(1, round(total_h * 0.05))
        canopy_cy = ify - trunk_h - ry + 2
    else:
        rx = canopy_rx if canopy_rx is not None else max(5, round(total_h * 0.36))
        ry = canopy_ry if canopy_ry is not None else max(4, round(total_h * 0.28))
        trunk_h = max(5, round(total_h * 0.42))
        trunk_r = max(1, round(total_h * 0.07))
        canopy_cy = ify - trunk_h - max(2, ry // 2)

    trunk_top_y = ify - trunk_h

    if shadow is not None:
        s_rx = max(3, round(rx * 0.85))
        s_ry = max(2, round(s_rx * 0.45))
        target.ellipse(icx, ify, s_rx, s_ry, shadow, fill=True)

    _draw_tree_trunk(
        target,
        icx,
        ify,
        trunk_top_y,
        trunk_r,
        trunk=trunk,
        trunk_lit=trunk_lit,
        outline=outline,
        angle=angle,
    )

    speckles = tuple(c for c in (foliage_light, foliage_dark) if c is not None)
    if species == "pine":
        _draw_pine_canopy(
            target,
            icx,
            trunk_top_y + 3,
            rx,
            ry,
            foliage=foliage,
            foliage_light=foliage_light,
            foliage_dark=foliage_dark,
            outline=outline,
            sway=sway,
            seed=seed,
            angle=angle,
        )
    else:
        foliage_cluster(
            target,
            icx + sway,
            canopy_cy,
            rx,
            ry,
            fill=foliage,
            highlight=foliage_light,
            shadow=foliage_dark,
            outline=outline,
            speckles=speckles or None,
            speckle_count=max(4, (rx * ry) // 8),
            lobes=3 if species == "cypress" else 4,
            seed=seed,
            lighting_angle=angle,
        )

    if emit_anchor:
        target.anchor("foot", icx, ify, kind="ground")
    if emit_hitbox:
        hw = max(2, trunk_r + 1)
        hh = max(3, trunk_h // 2)
        target.hitbox("trunk", icx - hw, ify - hh, hw * 2, hh + 1)

    return IsoTreeAnchors(
        foot=(icx, ify),
        canopy_center=(icx + sway, canopy_cy),
        trunk_top=(icx, trunk_top_y),
    )
