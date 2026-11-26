"""Deterministic weather, condensation, dust mote, and steam prefabs."""

from __future__ import annotations

import math

import numpy as np

from pixelforge.core.plane import Point2D
from pixelforge.core.prefabs.atmosphere._pane import (
    Canvas,
    ClippedPane,
    PaneRegion,
    TargetCanvas,
    open_pane,
    wrap_phase,
)
from pixelforge.core.prng import mulberry32
from pixelforge.core.surface import IndexedSurface, compute_dither_thresholds
from pixelforge.core.types import TRANSPARENT_INDEX


def weather_rain(
    target: TargetCanvas,
    *,
    color: int,
    splash_color: int | None = None,
    count: int = 16,
    phase: float = 0.0,
    slant: float = -0.14,
    length: float = 0.14,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render deterministic looping rain streaks (`phase = frame / frames`)."""
    if count <= 0:
        return
    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0xFA110001)
        p = wrap_phase(phase)
        streak_len = max(0.04, min(0.45, float(length)))

        for _ in range(int(count)):
            u0 = rng()
            v0 = rng()
            speed = 1 if rng() < 0.55 else 2
            t = (v0 + p * speed) % 1.0
            v_head = -0.08 + t * 1.18
            u_head = (u0 + slant * (v_head - 0.5)) % 1.0
            v_tail = v_head - streak_len
            u_tail = u_head - slant * streak_len

            x0, y0 = pane.project(u_tail, v_tail)
            x1, y1 = pane.project(u_head, v_head)
            pane.surface.line(x0, y0, x1, y1, color)
            if splash_color is not None and v_head >= 0.90:
                pane.put_uv(u_head, 0.95, splash_color)


def weather_snow(
    target: TargetCanvas,
    *,
    color: int,
    alt_color: int | None = None,
    count: int = 18,
    phase: float = 0.0,
    drift: float = 0.08,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render deterministic looping swaying snowflakes (`phase = frame / frames`)."""
    if count <= 0:
        return
    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0x590BF1A3)
        p = wrap_phase(phase)

        for _ in range(int(count)):
            u0 = rng()
            v0 = rng()
            sway_phase = rng()
            is_bg = rng() < 0.45
            speed = 1 if is_bg else 2
            t = (v0 + p * speed) % 1.0
            v_pos = -0.04 + t * 1.08
            u_pos = (u0 + drift * math.sin(math.tau * (p + sway_phase))) % 1.0
            flake_col = alt_color if (is_bg and alt_color is not None) else color
            pane.put_uv(u_pos, v_pos, flake_col)


def weather_lightning(
    target: TargetCanvas,
    *,
    color: int,
    glow_color: int | None = None,
    phase: float = 0.0,
    active_window: tuple[float, float] = (0.0, 0.25),
    branches: int = 2,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render a clip-safe jagged lightning bolt inside a window pane during `active_window`."""
    p = wrap_phase(phase)
    start, end = active_window
    is_active = start <= p < end if start <= end else p >= start or p < end
    if not is_active:
        return

    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0x11647001)
        u_cur = 0.30 + rng() * 0.40
        v_cur = 0.02
        segments = 6
        pts: list[tuple[float, float]] = [(u_cur, v_cur)]
        for step_idx in range(1, segments + 1):
            v_next = 0.02 + (0.84 * step_idx) / float(segments)
            u_next = max(0.08, min(0.92, u_cur + (rng() - 0.5) * 0.24))
            pts.append((u_next, v_next))
            u_cur, v_cur = u_next, v_next

        branch_segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for _ in range(max(0, int(branches))):
            anchor_idx = 1 + int(rng() * max(1, len(pts) - 2))
            bu0, bv0 = pts[anchor_idx]
            bu1 = max(0.05, min(0.95, bu0 + (-0.18 if rng() < 0.5 else 0.18)))
            bv1 = min(0.95, bv0 + 0.16)
            branch_segs.append(((bu0, bv0), (bu1, bv1)))

        if glow_color is not None:
            for idx in range(len(pts) - 1):
                x0, y0 = pane.project(pts[idx][0], pts[idx][1])
                x1, y1 = pane.project(pts[idx + 1][0], pts[idx + 1][1])
                pane.surface.line(x0 + 1, y0, x1 + 1, y1, glow_color)

        for idx in range(len(pts) - 1):
            x0, y0 = pane.project(pts[idx][0], pts[idx][1])
            x1, y1 = pane.project(pts[idx + 1][0], pts[idx + 1][1])
            pane.surface.line(x0, y0, x1, y1, color)

        for (bu0, bv0), (bu1, bv1) in branch_segs:
            bx0, by0 = pane.project(bu0, bv0)
            bx1, by1 = pane.project(bu1, bv1)
            pane.surface.line(bx0, by0, bx1, by1, color)


def window_condensation(
    target: TargetCanvas,
    *,
    color: int,
    droplet_color: int | None = None,
    edge_thickness: float = 0.18,
    density: float = 0.45,
    droplets: int = 4,
    phase: float = 0.0,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render frosted edge condensation and slow-creeping droplets inside a window pane."""
    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        u = pane.u_grid
        v = pane.v_grid
        edge_dist = np.minimum(np.minimum(u, 1.0 - u), np.minimum(v, 1.0 - v))
        thick = max(1e-4, float(edge_thickness))
        ratio = np.clip(1.0 - edge_dist / thick, 0.0, 1.0) * float(density)
        thresholds = compute_dither_thresholds(
            pane.ox,
            pane.oy,
            pane.ox + pane.width,
            pane.oy + pane.height,
            pattern="bayer4",
        )
        frost_mask = pane.mask & (ratio > 0.0) & (thresholds < ratio)
        pane.surface.data[frost_mask] = int(color)

        if droplets > 0:
            rng = mulberry32(int(seed) ^ 0xC0AD0001)
            p = wrap_phase(phase)
            drop_col = droplet_color if droplet_color is not None else color
            for _ in range(int(droplets)):
                du = 0.12 + rng() * 0.76
                dv0 = rng()
                dv = 0.10 + ((dv0 + p) % 1.0) * 0.78
                pane.put_uv(du, dv, drop_col)
                pane.put_uv(du, min(0.96, dv + 0.04), drop_col)


def dust_motes(
    target: TargetCanvas,
    *,
    color: int,
    alt_color: int | None = None,
    count: int = 12,
    phase: float = 0.0,
    drift: float = 0.06,
    seed: int = 0,
    region: PaneRegion | None = None,
    points: tuple[Point2D, Point2D, Point2D, Point2D] | None = None,
) -> None:
    """Render deterministic looping dust motes clipped to a light beam, spill quad, or pane."""
    if count <= 0:
        return
    rng = mulberry32(int(seed) ^ 0xD0570001)
    p = wrap_phase(phase)

    if points is not None:
        if isinstance(target, ClippedPane):
            msg = "points cannot be combined with a ClippedPane target"
            raise ValueError(msg)
        verts = [(round(pt[0]), round(pt[1])) for pt in points]
        min_x = max(0, min(px for px, _ in verts))
        min_y = max(0, min(py for _, py in verts))
        max_x = min(target.surface.width - 1, max(px for px, _ in verts))
        max_y = min(target.surface.height - 1, max(py for _, py in verts))
        if min_x > max_x or min_y > max_y:
            return
        w = max_x - min_x + 1
        h = max_y - min_y + 1
        quad_surf = IndexedSurface(w, h)
        shifted = tuple((px - min_x, py - min_y) for px, py in verts)
        quad_surf.quad(shifted[0], shifted[1], shifted[2], shifted[3], 0, fill=True)
        in_quad = quad_surf.data != TRANSPARENT_INDEX
        for idx in range(int(count)):
            u0 = rng()
            v0 = rng()
            ph = rng()
            u = (u0 + drift * math.sin(math.tau * (p + ph))) % 1.0
            v = (v0 + drift * 0.7 * math.cos(math.tau * (p + ph * 1.3))) % 1.0
            lx = min(w - 1, max(0, round(u * (w - 1))))
            ly = min(h - 1, max(0, round(v * (h - 1))))
            if bool(in_quad[ly, lx]):
                col = alt_color if (alt_color is not None and idx % 2 == 1) else color
                target.surface.put(min_x + lx, min_y + ly, col)
        return

    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        for idx in range(int(count)):
            u0 = rng()
            v0 = rng()
            ph = rng()
            u = (u0 + drift * math.sin(math.tau * (p + ph))) % 1.0
            v = (v0 + drift * 0.7 * math.cos(math.tau * (p + ph * 1.3))) % 1.0
            col = alt_color if (alt_color is not None and idx % 2 == 1) else color
            pane.put_uv(u, v, col)


def rising_steam(
    target: Canvas,
    x: int | float,
    y: int | float,
    *,
    color: int,
    alt_color: int | None = None,
    height: int = 12,
    spread: int = 3,
    count: int = 6,
    phase: float = 0.0,
    seed: int = 0,
) -> None:
    """Render deterministic looping rising vapor wisps for mugs, vents, or faulty hardware."""
    if count <= 0 or height <= 0:
        return
    rng = mulberry32(int(seed) ^ 0x57EA0001)
    p = wrap_phase(phase)
    ox = float(x)
    oy = float(y)

    for _ in range(int(count)):
        t0 = rng()
        sway_phase = rng()
        base_off = (rng() - 0.5) * 2.0
        t = (t0 + p) % 1.0
        py = round(oy - t * float(height))
        sway = math.sin(math.tau * (t + sway_phase)) * float(spread) * (0.35 + 0.65 * t)
        px = round(ox + base_off + sway)
        col = alt_color if (alt_color is not None and t > 0.62) else color
        target.surface.put(px, py, col)
        if t < 0.45:
            target.surface.put(px + 1, py, col)
