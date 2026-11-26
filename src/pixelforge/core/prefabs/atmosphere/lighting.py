"""Window/point light spill and animated screen telemetry prefabs."""

from __future__ import annotations

import math

import numpy as np

from pixelforge.core.plane import Plane, Point2D
from pixelforge.core.prefabs.atmosphere._pane import (
    Canvas,
    ClippedPane,
    PaneRegion,
    TargetCanvas,
    TelemetryMode,
    open_pane,
    wrap_phase,
)
from pixelforge.core.prng import mulberry32
from pixelforge.core.surface import (
    DitherMask,
    DitherPattern,
    IndexedSurface,
    compute_dither_thresholds,
)
from pixelforge.core.types import TRANSPARENT_INDEX


def window_light_spill(
    target: Canvas,
    *,
    points: tuple[Point2D, Point2D, Point2D, Point2D],
    color: int,
    secondary_color: int | None = None,
    pattern: DitherPattern = "bayer4",
    near_ratio: float = 0.70,
    far_ratio: float = 0.18,
    mask: DitherMask = "opaque",
) -> None:
    """Project a crisp ordered-dither light spill onto a 4-vertex interior quad.

    INVARIANT: Light spill targets floor/wall surfaces using strictly non-emissive palette
    tokens so WebGL2 bloom masks remain confined to true emitters.
    """
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

    region = target.surface.data[min_y : max_y + 1, min_x : max_x + 1]
    active = in_quad & (region != TRANSPARENT_INDEX) if mask == "opaque" else in_quad
    if not np.any(active):
        return

    near_mid = (0.5 * (points[0][0] + points[1][0]), 0.5 * (points[0][1] + points[1][1]))
    far_mid = (0.5 * (points[2][0] + points[3][0]), 0.5 * (points[2][1] + points[3][1]))
    ax = float(far_mid[0] - near_mid[0])
    ay = float(far_mid[1] - near_mid[1])
    norm2 = max(1.0, ax * ax + ay * ay)

    ly, lx = np.mgrid[0:h, 0:w]
    gx = min_x + lx
    gy = min_y + ly
    t = np.clip(((gx - near_mid[0]) * ax + (gy - near_mid[1]) * ay) / norm2, 0.0, 1.0)
    ratio_grid = float(near_ratio) + t * (float(far_ratio) - float(near_ratio))
    thresholds = compute_dither_thresholds(
        min_x,
        min_y,
        max_x + 1,
        max_y + 1,
        pattern=pattern,
    )
    select_primary = active & (
        (ratio_grid >= 1.0) | ((ratio_grid > 0.0) & (thresholds < ratio_grid))
    )
    if secondary_color is not None:
        sec_ratio = ratio_grid * 0.55
        select_secondary = (
            active & (~select_primary) & ((sec_ratio > 0.0) & (thresholds < sec_ratio))
        )
        region[select_secondary] = int(secondary_color)
    region[select_primary] = int(color)


def light_beam(
    target: Canvas,
    region: PaneRegion,
    *,
    color: int,
    secondary_color: int | None = None,
    dx: int = 24,
    dy: int = 16,
    spread: int = 6,
    pattern: DitherPattern = "bayer4",
    near_ratio: float = 0.70,
    far_ratio: float = 0.18,
    mask: DitherMask = "opaque",
) -> None:
    """Compute a window-anchored floor/wall light spill quad and render `window_light_spill`."""
    if len(region) == 4:
        rx, ry, rw, rh = region
        b0: Point2D = (rx, ry + rh)
        b1: Point2D = (rx + rw, ry + rh)
    elif len(region) == 3:
        p0, p1, p2 = region
        b0 = p2
        b1 = (
            float(p1[0]) + float(p2[0]) - float(p0[0]),
            float(p1[1]) + float(p2[1]) - float(p0[1]),
        )
    else:
        msg = f"Expected 4-tuple rect or 3-point plane region, got {len(region)} elements"
        raise ValueError(msg)

    f0: Point2D = (b0[0] + dx - spread, b0[1] + dy)
    f1: Point2D = (b1[0] + dx + spread, b1[1] + dy)
    window_light_spill(
        target,
        points=(b0, b1, f1, f0),
        color=color,
        secondary_color=secondary_color,
        pattern=pattern,
        near_ratio=near_ratio,
        far_ratio=far_ratio,
        mask=mask,
    )


def point_light_spill(
    target: Canvas,
    cx: int | float,
    cy: int | float,
    rx: int | float,
    ry: int | float,
    *,
    color: int,
    secondary_color: int | None = None,
    direction: tuple[float, float] | None = None,
    cone_cos: float = 0.0,
    pattern: DitherPattern = "bayer4",
    near_ratio: float = 0.75,
    far_ratio: float = 0.05,
    mask: DitherMask = "opaque",
) -> None:
    """Project a non-emissive radial or conical dithered light pool for lamps/monitors.

    INVARIANT: Light spill targets floor/wall surfaces using strictly non-emissive palette
    tokens so WebGL2 bloom masks remain confined to true emitters.
    """
    frx = max(1.0, float(rx))
    fry = max(1.0, float(ry))
    min_x = max(0, round(cx - frx))
    min_y = max(0, round(cy - fry))
    max_x = min(target.surface.width - 1, round(cx + frx))
    max_y = min(target.surface.height - 1, round(cy + fry))
    if min_x > max_x or min_y > max_y:
        return

    w = max_x - min_x + 1
    h = max_y - min_y + 1
    ly, lx = np.mgrid[0:h, 0:w]
    gx = min_x + lx
    gy = min_y + ly
    dx = gx - float(cx)
    dy = gy - float(cy)
    dist = np.sqrt((dx / frx) ** 2 + (dy / fry) ** 2)
    in_pool = dist <= 1.0

    if direction is not None:
        d_len = math.hypot(direction[0], direction[1])
        if d_len > 1e-6:
            ux = direction[0] / d_len
            uy = direction[1] / d_len
            pix_len = np.sqrt(dx * dx + dy * dy)
            dot = np.where(pix_len > 1e-6, (dx * ux + dy * uy) / np.maximum(1e-6, pix_len), 1.0)
            in_pool &= dot >= float(cone_cos)

    region = target.surface.data[min_y : max_y + 1, min_x : max_x + 1]
    active = in_pool & (region != TRANSPARENT_INDEX) if mask == "opaque" else in_pool
    if not np.any(active):
        return

    t = np.clip(dist, 0.0, 1.0)
    ratio_grid = float(near_ratio) + t * (float(far_ratio) - float(near_ratio))
    thresholds = compute_dither_thresholds(
        min_x,
        min_y,
        max_x + 1,
        max_y + 1,
        pattern=pattern,
    )
    select_primary = active & (
        (ratio_grid >= 1.0) | ((ratio_grid > 0.0) & (thresholds < ratio_grid))
    )
    if secondary_color is not None:
        sec_ratio = ratio_grid * 0.55
        select_secondary = (
            active & (~select_primary) & ((sec_ratio > 0.0) & (thresholds < sec_ratio))
        )
        region[select_secondary] = int(secondary_color)
    region[select_primary] = int(color)


def _telemetry_project(
    target: Plane | ClippedPane,
    u: float,
    v: float,
    color: int,
) -> None:
    if isinstance(target, Plane):
        target.dot(u, v, color)
    else:
        target.put_uv(u, v, color)


def _telemetry_line(
    target: Plane | ClippedPane,
    u0: float,
    v0: float,
    u1: float,
    v1: float,
    color: int,
) -> None:
    if isinstance(target, Plane):
        target.line(u0, v0, u1, v1, color)
    else:
        x0, y0 = target.project(u0, v0)
        x1, y1 = target.project(u1, v1)
        target.surface.line(x0, y0, x1, y1, color)


def _telemetry_rect(
    target: Plane | ClippedPane,
    u: float,
    v: float,
    w: float,
    h: float,
    fill: int,
) -> None:
    if isinstance(target, Plane):
        target.rect(u, v, w, h, fill=fill)
    else:
        c00 = target.project(u, v)
        c10 = target.project(u + w, v)
        c11 = target.project(u + w, v + h)
        c01 = target.project(u, v + h)
        target.surface.quad(c00, c10, c11, c01, fill, fill=True)


def _draw_telemetry_body(
    target: Plane | ClippedPane,
    *,
    color: int,
    bg_color: int | None,
    accent: int | None,
    mode: TelemetryMode,
    phase: float,
    samples: int,
    seed: int,
) -> None:
    if bg_color is not None:
        _telemetry_rect(target, 0.0, 0.0, 1.0, 1.0, bg_color)

    rng = mulberry32(int(seed) ^ 0x7E1E0001)
    p = wrap_phase(phase)
    n = max(3, int(samples))

    if mode == "waveform":
        if accent is not None:
            _telemetry_line(target, 0.06, 0.50, 0.94, 0.50, accent)
        prev_u = 0.08
        prev_v = 0.50 + 0.28 * math.sin(math.tau * p)
        for idx in range(1, n):
            t = idx / float(n - 1)
            u = 0.08 + t * 0.84
            amp = 0.16 + 0.16 * rng()
            v = 0.50 + amp * math.sin(math.tau * (t * 2.0 + p))
            _telemetry_line(target, prev_u, prev_v, u, v, color)
            prev_u, prev_v = u, v
        return

    if mode == "bars":
        bar_span = 0.84 / float(n)
        bar_w = bar_span * 0.65
        for idx in range(n):
            base_h = 0.20 + 0.50 * rng()
            pulse = 0.14 * math.sin(math.tau * (p + idx / float(n)))
            bh = max(0.10, min(0.76, base_h + pulse))
            bu = 0.08 + idx * bar_span
            bv = 0.88 - bh
            _telemetry_rect(target, bu, bv, bar_w, bh, color)
            if accent is not None and bh > 0.52:
                _telemetry_project(target, bu + bar_w * 0.5, bv, accent)
        return

    if mode == "sparkline":
        pts: list[tuple[float, float]] = []
        for idx in range(n):
            t = idx / float(n - 1)
            u = 0.08 + t * 0.84
            jitter = 0.24 * math.sin(math.tau * (p + t * 1.5 + rng()))
            v = max(0.14, min(0.86, 0.50 + jitter))
            pts.append((u, v))
        for idx in range(len(pts) - 1):
            _telemetry_line(
                target, pts[idx][0], pts[idx][1], pts[idx + 1][0], pts[idx + 1][1], color
            )
        if accent is not None:
            for u, v in pts[::2]:
                _telemetry_project(target, u, v, accent)
        return

    if mode == "grid_scan":
        grid_col = accent if accent is not None else color
        _telemetry_line(target, 0.08, 0.50, 0.92, 0.50, grid_col)
        _telemetry_line(target, 0.50, 0.10, 0.50, 0.90, grid_col)
        scan_u = 0.10 + p * 0.80
        _telemetry_line(target, scan_u, 0.12, scan_u, 0.88, color)
        blip_v = 0.25 + 0.50 * rng()
        _telemetry_project(target, scan_u, blip_v, accent if accent is not None else color)
        return

    msg = f"Unsupported telemetry mode: {mode!r}"
    raise ValueError(msg)


def screen_telemetry(
    target: Plane | TargetCanvas,
    *,
    color: int,
    bg_color: int | None = None,
    accent: int | None = None,
    mode: TelemetryMode = "waveform",
    phase: float = 0.0,
    samples: int = 8,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render animated charts, waveforms, or scanlines inside a `Plane` or `ClippedPane`."""
    if isinstance(target, (Plane, ClippedPane)):
        _draw_telemetry_body(
            target,
            color=color,
            bg_color=bg_color,
            accent=accent,
            mode=mode,
            phase=phase,
            samples=samples,
            seed=seed,
        )
        return

    with open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        _draw_telemetry_body(
            pane,
            color=color,
            bg_color=bg_color,
            accent=accent,
            mode=mode,
            phase=phase,
            samples=samples,
            seed=seed,
        )
