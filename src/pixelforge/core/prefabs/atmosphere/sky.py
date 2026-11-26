"""Sky gradients, celestial bodies, clouds, horizon silhouettes, and day-night cycle."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from pixelforge.core.prefabs.atmosphere._pane import (
    ClippedPane,
    HorizonMode,
    PaneRegion,
    TargetCanvas,
    open_pane,
    wrap_phase,
)
from pixelforge.core.prng import mulberry32
from pixelforge.core.surface import (
    DitherPattern,
    IndexedSurface,
    compute_dither_thresholds,
)
from pixelforge.core.types import TRANSPARENT_INDEX


@dataclass(frozen=True)
class CycleStep:
    """Resolved atmospheric parameters for one frame of a day-night cycle."""

    phase: float
    sky_bands: tuple[int, ...]
    celestial_kind: Literal["sun", "moon"]
    celestial_u: float
    celestial_v: float
    star_visibility: float
    spill_intensity: float


def sky_backdrop(
    target: TargetCanvas,
    *,
    bands: Sequence[int],
    region: PaneRegion | None = None,
    pattern: DitherPattern = "bayer4",
    dither_width: float = 0.65,
) -> None:
    """Render a multi-band ordered-dither sky gradient inside a clipped window pane."""
    if not bands:
        msg = "sky_backdrop requires at least one palette index in bands"
        raise ValueError(msg)

    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        if len(bands) == 1:
            pane.surface.data[pane.mask] = int(bands[0])
            return

        n_seg = len(bands) - 1
        pos = np.clip(pane.v_grid * n_seg, 0.0, float(n_seg))
        seg = np.minimum(pos.astype(np.int64), n_seg - 1)
        frac = pos - seg

        width = max(0.05, min(1.0, float(dither_width)))
        half_w = 0.5 * width
        ratio = np.clip((frac - (0.5 - half_w)) / width, 0.0, 1.0)

        thresholds = compute_dither_thresholds(
            pane.ox,
            pane.oy,
            pane.ox + pane.width,
            pane.oy + pane.height,
            pattern=pattern,
        )
        choose_next = (ratio >= 1.0) | ((ratio > 0.0) & (thresholds < ratio))
        band_arr = np.asarray([int(c) for c in bands], dtype=np.uint8)
        idx_map = np.where(choose_next, seg + 1, seg)
        rendered = band_arr[idx_map]
        pane.surface.data[pane.mask] = rendered[pane.mask]


def _draw_checker_halo(
    pane: ClippedPane,
    cx: int,
    cy: int,
    outer_r: int,
    inner_r: int,
    halo_color: int,
) -> None:
    ly, lx = np.mgrid[0 : pane.height, 0 : pane.width]
    dist2 = (lx - cx) * (lx - cx) + (ly - cy) * (ly - cy)
    ring = pane.mask & (dist2 <= outer_r * outer_r) & (dist2 > inner_r * inner_r)
    checker = ((pane.xx + pane.yy) & 1) == 0
    pane.surface.data[ring & checker] = int(halo_color)


def sun(
    target: TargetCanvas,
    u: float = 0.28,
    v: float = 0.28,
    *,
    radius: int = 3,
    color: int,
    halo: int | None = None,
    rays: bool = False,
    ray_color: int | None = None,
    region: PaneRegion | None = None,
) -> None:
    """Render a crisp pixel-art sun with optional checker halo and cardinal/diagonal rays."""
    ir = max(0, int(radius))
    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        cx, cy = pane.project(u, v)
        if halo is not None:
            _draw_checker_halo(pane, cx, cy, ir + 2, ir, halo)
        if rays:
            rc = int(ray_color if ray_color is not None else (halo if halo is not None else color))
            ray_start = ir + 1
            ray_end = ir + 3
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                pane.surface.line(
                    cx + dx * ray_start,
                    cy + dy * ray_start,
                    cx + dx * ray_end,
                    cy + dy * ray_end,
                    rc,
                )
            diag = ir + 2
            for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                pane.surface.put(cx + dx * diag, cy + dy * diag, rc)
        pane.surface.circle(cx, cy, ir, color, fill=True)


def moon(
    target: TargetCanvas,
    u: float = 0.72,
    v: float = 0.28,
    *,
    radius: int = 3,
    color: int,
    crater_color: int | None = None,
    shadow_color: int | None = None,
    crescent: bool = False,
    halo: int | None = None,
    region: PaneRegion | None = None,
) -> None:
    """Render a full moon (with pixel craters) or crescent moon clipped inside a pane."""
    ir = max(1, int(radius))
    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        cx, cy = pane.project(u, v)
        if halo is not None:
            _draw_checker_halo(pane, cx, cy, ir + 1, ir, halo)

        if crescent:
            moon_buf = IndexedSurface(pane.width, pane.height)
            moon_buf.circle(cx, cy, ir, color, fill=True)
            cut_x = cx + max(1, (ir + 1) // 2)
            cut_y = cy - max(0, ir // 3)
            cut_r = max(1, ir - 1) if ir >= 2 else 1
            carve_color = TRANSPARENT_INDEX if shadow_color is None else int(shadow_color)
            if shadow_color is None:
                moon_buf.circle(cut_x, cut_y, cut_r, carve_color, fill=True)
            else:
                carve_mask = IndexedSurface(pane.width, pane.height)
                carve_mask.circle(cut_x, cut_y, cut_r, 0, fill=True)
                overlap = (moon_buf.data != TRANSPARENT_INDEX) & (
                    carve_mask.data != TRANSPARENT_INDEX
                )
                moon_buf.data[overlap] = carve_color
            pane.surface.blit_layer(moon_buf, 0, 0)
            return

        pane.surface.circle(cx, cy, ir, color, fill=True)
        if crater_color is not None and ir >= 2:
            craters = (
                (-max(1, ir // 2), -max(1, ir // 3)),
                (max(1, ir // 3), max(0, ir // 4)),
                (-max(0, ir // 4), max(1, ir // 2)),
            )
            limit2 = max(1, (ir - 1) * (ir - 1))
            for ox, oy in craters:
                if ox * ox + oy * oy <= limit2:
                    pane.surface.put(cx + ox, cy + oy, crater_color)


def starfield(
    target: TargetCanvas,
    *,
    count: int = 12,
    color: int,
    twinkle_color: int | None = None,
    frame: int = 0,
    frames: int = 1,
    seed: int = 0,
    max_v: float = 0.78,
    region: PaneRegion | None = None,
) -> None:
    """Render deterministic fixed-position stars with smooth periodic frame twinkling."""
    if count <= 0:
        return
    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0x51A7F1E1)
        phase_base = (int(frame) % max(1, int(frames))) / float(max(1, int(frames)))
        v_cap = max(0.15, min(0.95, float(max_v)))

        for idx in range(int(count)):
            su = 0.06 + rng() * 0.88
            sv = 0.06 + rng() * (v_cap - 0.06)
            star_phase = rng()
            t = (phase_base + star_phase) % 1.0

            star_col = color
            if twinkle_color is not None and int(frames) > 1:
                if t < 0.22:
                    star_col = twinkle_color
                elif t > 0.86 and idx % 3 == 0:
                    continue
            pane.put_uv(su, sv, star_col)


def clouds(
    target: TargetCanvas,
    *,
    color: int,
    shade_color: int | None = None,
    count: int = 2,
    phase: float = 0.0,
    min_v: float = 0.14,
    max_v: float = 0.48,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render seamlessly looping drifting clouds in `(u, v)` pane space."""
    if count <= 0:
        return
    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0xC10D5EED)
        p = wrap_phase(phase)
        v_lo = max(0.05, min(0.85, float(min_v)))
        v_hi = max(v_lo + 0.05, min(0.92, float(max_v)))

        cloud_mask = np.zeros_like(pane.mask, dtype=bool)
        shade_mask = np.zeros_like(pane.mask, dtype=bool)

        # INVARIANT: Stratify vertical bands across `count` and permute deterministically
        # so multi-cloud vistas never collapse onto the same height or identical silhouette.
        n_clouds = int(count)
        band_h = (v_hi - v_lo) / float(n_clouds)
        slots = list(range(n_clouds))
        for idx in range(n_clouds - 1, 0, -1):
            swap_idx = int(rng() * (idx + 1))
            slots[idx], slots[swap_idx] = slots[swap_idx], slots[idx]

        for idx in range(n_clouds):
            u0 = rng()
            slot = slots[idx]
            v0 = v_lo + (slot + 0.15 + 0.70 * rng()) * band_h
            size_t = (idx + 0.20 + 0.65 * rng()) / float(max(1, n_clouds))
            rx = 0.09 + size_t * 0.16
            ry = 0.05 + size_t * 0.09
            left_scale = 0.58 + rng() * 0.22
            right_scale = 0.60 + rng() * 0.24
            uc = ((u0 + p) % 1.0) * 1.56 - 0.28

            puff_a = (((pane.u_grid - uc) / rx) ** 2 + ((pane.v_grid - v0) / ry) ** 2) <= 1.0
            puff_b = (
                ((pane.u_grid - (uc - 0.55 * rx)) / (left_scale * rx)) ** 2
                + ((pane.v_grid - (v0 + 0.14 * ry)) / (0.76 * ry)) ** 2
            ) <= 1.0
            puff_c = (
                ((pane.u_grid - (uc + 0.58 * rx)) / (right_scale * rx)) ** 2
                + ((pane.v_grid - (v0 + 0.10 * ry)) / (0.80 * ry)) ** 2
            ) <= 1.0
            flat_base = pane.v_grid <= (v0 + 0.58 * ry)
            body = (puff_a | puff_b | puff_c) & flat_base
            cloud_mask |= body
            if shade_color is not None:
                shade_mask |= body & (pane.v_grid >= (v0 + 0.22 * ry))

        pane.surface.data[pane.mask & cloud_mask] = int(color)
        if shade_color is not None:
            pane.surface.data[pane.mask & shade_mask] = int(shade_color)


def _horizon_city_rooftops(
    pane: ClippedPane,
    rng: object,
    bv: float,
    color: int,
    accent: int | None,
    mode: Literal["city", "rooftops"],
) -> None:
    from collections.abc import Callable

    rand: Callable[[], float] = rng  # type: ignore[assignment]
    u = pane.u_grid
    v = pane.v_grid
    cols = 7 if mode == "city" else 5
    ridge = np.full_like(v, bv)
    for idx in range(cols):
        u0 = idx / float(cols)
        u1 = (idx + 1) / float(cols)
        h_off = (rand() - 0.45) * (0.20 if mode == "city" else 0.14)
        top_v = max(0.42, min(0.92, bv - abs(h_off)))
        in_col = (u >= u0) & (u <= u1)
        if mode == "rooftops":
            center = 0.5 * (u0 + u1)
            span = 0.5 * (u1 - u0)
            slope = np.abs(u - center) / max(1e-6, span)
            col_v = top_v + slope * 0.08
            ridge = np.where(in_col, np.minimum(ridge, col_v), ridge)
        else:
            ridge = np.where(in_col, np.minimum(ridge, top_v), ridge)
    pane.surface.data[pane.mask & (v >= ridge)] = int(color)
    if accent is not None:
        for _ in range(cols):
            pane.put_uv(0.08 + rand() * 0.84, min(0.94, bv + 0.04 + rand() * 0.14), accent)


def _horizon_industrial(
    pane: ClippedPane,
    rng: object,
    bv: float,
    color: int,
    accent: int | None,
) -> None:
    from collections.abc import Callable

    rand: Callable[[], float] = rng  # type: ignore[assignment]
    u = pane.u_grid
    v = pane.v_grid
    ridge = np.full_like(v, bv)
    bays = 4
    for idx in range(bays):
        u0 = idx / float(bays)
        u1 = (idx + 1) / float(bays)
        in_bay = (u >= u0) & (u <= u1)
        local_u = (u - u0) / max(1e-6, u1 - u0)
        roof_v = (bv - 0.10) + local_u * 0.08
        ridge = np.where(in_bay, np.minimum(ridge, roof_v), ridge)
    for stack_idx in range(2):
        su = 0.18 + stack_idx * 0.48 + (rand() - 0.5) * 0.08
        sw = 0.05
        in_stack = (u >= su) & (u <= su + sw)
        stack_top = max(0.28, bv - 0.24 - rand() * 0.08)
        ridge = np.where(in_stack, np.minimum(ridge, stack_top), ridge)
        if accent is not None:
            pane.put_uv(su + sw * 0.5, stack_top + 0.02, accent)
    pane.surface.data[pane.mask & (v >= ridge)] = int(color)
    if accent is not None:
        for _ in range(3):
            pane.put_uv(0.12 + rand() * 0.76, min(0.92, bv + 0.03 + rand() * 0.08), accent)


def horizon_silhouette(
    target: TargetCanvas,
    *,
    color: int,
    accent: int | None = None,
    mode: HorizonMode = "city",
    base_v: float = 0.74,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render a city, rooftop, hill, or pine-tree horizon silhouette clipped to a window pane."""
    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0x40A1204E)
        bv = max(0.35, min(0.95, float(base_v)))
        u = pane.u_grid
        v = pane.v_grid

        if mode in ("city", "rooftops"):
            _horizon_city_rooftops(pane, rng, bv, color, accent, mode)
            return
        if mode == "hills":
            phase_a, phase_b = rng() * math.tau, rng() * math.tau
            ridge_a = bv + 0.07 * np.sin(u * math.tau * 1.3 + phase_a)
            if accent is not None:
                ridge_b = (bv - 0.06) + 0.05 * np.sin(u * math.tau * 1.9 + phase_b)
                pane.surface.data[pane.mask & (v >= ridge_b)] = int(accent)
            pane.surface.data[pane.mask & (v >= ridge_a)] = int(color)
            return
        if mode == "trees":
            saw = np.abs(((u * 9) % 1.0) - 0.5) * 2.0
            jitter = 0.03 * np.sin(u * math.tau * 3.0 + rng() * math.tau)
            ridge = (bv - 0.08) + saw * 0.13 + jitter
            if accent is not None:
                pane.surface.data[pane.mask & (v >= (ridge - 0.04))] = int(accent)
            pane.surface.data[pane.mask & (v >= ridge)] = int(color)
            return
        if mode == "mountains":
            p_a, p_b = rng() * math.tau, rng() * math.tau
            tri_a = np.abs(((u * 2.5 + p_a / math.tau) % 1.0) - 0.5) * 2.0
            tri_b = np.abs(((u * 4.5 + p_b / math.tau) % 1.0) - 0.5) * 2.0
            ridge = (bv - 0.20) + tri_a * 0.22 + tri_b * 0.07
            sil = pane.mask & (v >= ridge)
            pane.surface.data[sil] = int(color)
            if accent is not None:
                pane.surface.data[sil & (v <= (bv - 0.09))] = int(accent)
            return
        if mode == "industrial":
            _horizon_industrial(pane, rng, bv, color, accent)
            return

        msg = f"Unsupported horizon mode: {mode!r}"
        raise ValueError(msg)


def eval_day_night_cycle(
    phase: float,
    *,
    day_bands: Sequence[int],
    dusk_bands: Sequence[int],
    night_bands: Sequence[int],
    dawn_bands: Sequence[int] | None = None,
) -> CycleStep:
    """Compute interpolated sky bands, sun/moon arc, star visibility, and spill intensity."""
    if not day_bands or not dusk_bands or not night_bands:
        msg = "day_bands, dusk_bands, and night_bands must each contain at least one color"
        raise ValueError(msg)

    p = wrap_phase(phase)
    dawn = tuple(dawn_bands if dawn_bands is not None else dusk_bands)
    day = tuple(day_bands)
    dusk = tuple(dusk_bands)
    night = tuple(night_bands)

    if p < 0.35:
        local = p / 0.35
        return CycleStep(
            phase=p,
            sky_bands=day,
            celestial_kind="sun",
            celestial_u=0.22 + 0.56 * local,
            celestial_v=0.42 - 0.20 * math.sin(local * math.pi),
            star_visibility=0.0,
            spill_intensity=0.85,
        )
    if p < 0.55:
        local = (p - 0.35) / 0.20
        return CycleStep(
            phase=p,
            sky_bands=dusk,
            celestial_kind="sun",
            celestial_u=0.78 + 0.08 * local,
            celestial_v=0.42 + 0.22 * local,
            star_visibility=0.35 * local,
            spill_intensity=0.45 * (1.0 - 0.5 * local),
        )
    if p < 0.80:
        local = (p - 0.55) / 0.25
        return CycleStep(
            phase=p,
            sky_bands=night,
            celestial_kind="moon",
            celestial_u=0.24 + 0.52 * local,
            celestial_v=0.38 - 0.14 * math.sin(local * math.pi),
            star_visibility=1.0,
            spill_intensity=0.22,
        )

    local = (p - 0.80) / 0.20
    return CycleStep(
        phase=p,
        sky_bands=dawn,
        celestial_kind="sun",
        celestial_u=0.16 + 0.08 * local,
        celestial_v=0.60 - 0.18 * local,
        star_visibility=0.45 * (1.0 - local),
        spill_intensity=0.45 + 0.35 * local,
    )


def day_night_cycle(
    target: TargetCanvas,
    *,
    phase: float,
    day_bands: Sequence[int],
    dusk_bands: Sequence[int],
    night_bands: Sequence[int],
    sun_color: int,
    moon_color: int,
    star_color: int,
    dawn_bands: Sequence[int] | None = None,
    sun_halo: int | None = None,
    moon_crater: int | None = None,
    cloud_color: int | None = None,
    cloud_shade: int | None = None,
    horizon_color: int | None = None,
    horizon_accent: int | None = None,
    horizon_mode: HorizonMode = "city",
    star_count: int = 12,
    frame: int = 0,
    frames: int = 1,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> CycleStep:
    """Render an animated day-dusk-night-dawn vista inside a clipped pane and return `CycleStep`."""
    step = eval_day_night_cycle(
        phase,
        day_bands=day_bands,
        dusk_bands=dusk_bands,
        night_bands=night_bands,
        dawn_bands=dawn_bands,
    )
    with open_pane(target, region) as pane:
        sky_backdrop(pane, bands=step.sky_bands)
        if step.star_visibility > 0.05:
            visible_stars = max(1, round(star_count * step.star_visibility))
            starfield(
                pane,
                count=visible_stars,
                color=star_color,
                twinkle_color=moon_color,
                frame=frame,
                frames=frames,
                seed=seed,
            )
        if step.celestial_kind == "sun":
            sun(
                pane,
                step.celestial_u,
                step.celestial_v,
                radius=3,
                color=sun_color,
                halo=sun_halo,
                rays=step.spill_intensity > 0.6,
            )
        else:
            moon(
                pane,
                step.celestial_u,
                step.celestial_v,
                radius=3,
                color=moon_color,
                crater_color=moon_crater,
                halo=sun_halo if step.star_visibility < 0.5 else None,
            )
        if cloud_color is not None:
            clouds(
                pane,
                color=cloud_color,
                shade_color=cloud_shade,
                count=2,
                phase=step.phase,
                seed=seed + 17,
            )
        if horizon_color is not None:
            horizon_silhouette(
                pane,
                color=horizon_color,
                accent=horizon_accent if step.celestial_kind == "moon" else None,
                mode=horizon_mode,
                seed=seed + 31,
            )
    return step
