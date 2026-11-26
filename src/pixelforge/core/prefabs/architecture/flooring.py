"""Isometric flooring, raised platforms, rugs, cable trays, and zone thresholds."""

from __future__ import annotations

import numpy as np

from pixelforge.core.plane import Point2D
from pixelforge.core.prefabs.architecture.room import (
    Canvas,
    FloorPatternMode,
    FloorZoneMode,
    IsoRoomGeometry,
    WallSide,
    clamp_unit,
)
from pixelforge.core.prefabs.atmosphere import PlaneRegion, clipped_pane
from pixelforge.core.surface import DitherPattern, compute_dither_thresholds


def iso_floor_pattern(
    target: Canvas,
    cx: int | float,
    cy: int | float,
    hw: int,
    hh: int,
    *,
    color: int,
    step: int = 16,
    mode: FloorPatternMode = "planks",
) -> None:
    """Draw deterministic plank or tile seams bounded to an isometric floor diamond."""
    icx = round(cx)
    icy = round(cy)
    ihw = max(1, int(hw))
    ihh = max(1, int(hh))
    istep = max(2, int(step))
    divisions = max(2, (ihw + ihh) // istep)

    # INVARIANT: Parameterizing the diamond via apex->right (u) and apex->left (v) keeps
    # all seam lines strictly inside the isometric floor bounds without OOB clipping drift.
    with target.plane(
        p0=(icx, icy - ihh),
        p1=(icx + ihw, icy),
        p2=(icx - ihw, icy),
    ) as floor_plane:
        if mode == "planks":
            for idx in range(1, divisions):
                u = idx / divisions
                floor_plane.line(u, 0.0, u, 1.0, color)
        elif mode in ("tiles", "grid"):
            floor_plane.grid(
                0.0,
                0.0,
                1.0,
                1.0,
                cols=divisions,
                rows=divisions,
                color=color,
                mode="lines",
            )
        else:
            msg = f"Unsupported floor pattern mode: {mode!r}"
            raise ValueError(msg)


def iso_raised_floor(
    target: Canvas,
    cx: int | float,
    cy: int | float,
    hw: int,
    hh: int,
    *,
    step_h: int = 4,
    top: int,
    left: int,
    right: int,
    grid_color: int | None = None,
    step: int = 12,
    outline: int | None = None,
) -> None:
    """Draw a 2:1 isometric raised floor platform with extruded front skirts and optional grid."""
    icx = round(cx)
    icy = round(cy)
    ihw = max(2, int(hw))
    ihh = max(1, int(hh))
    istep_h = max(1, int(step_h))

    p_top = (icx, icy - ihh)
    p_right = (icx + ihw, icy)
    p_bot = (icx, icy + ihh)
    p_left = (icx - ihw, icy)

    target.polygon((p_top, p_right, p_bot, p_left), top)
    if grid_color is not None:
        iso_floor_pattern(target, icx, icy, ihw, ihh, color=grid_color, step=step, mode="grid")

    target.polygon(
        (p_left, p_bot, (p_bot[0], p_bot[1] + istep_h), (p_left[0], p_left[1] + istep_h)),
        left,
    )
    target.polygon(
        (p_bot, p_right, (p_right[0], p_right[1] + istep_h), (p_bot[0], p_bot[1] + istep_h)),
        right,
    )

    if outline is not None:
        target.line(p_top[0], p_top[1], p_right[0], p_right[1], outline)
        target.line(p_top[0], p_top[1], p_left[0], p_left[1], outline)
        target.line(p_left[0], p_left[1], p_left[0], p_left[1] + istep_h, outline)
        target.line(p_right[0], p_right[1], p_right[0], p_right[1] + istep_h, outline)
        target.line(p_left[0], p_left[1] + istep_h, p_bot[0], p_bot[1] + istep_h, outline)
        target.line(p_bot[0], p_bot[1] + istep_h, p_right[0], p_right[1] + istep_h, outline)


def iso_rug(
    target: Canvas,
    cx: int | float,
    cy: int | float,
    hw: int,
    hh: int,
    *,
    fill: int,
    border: int | None = None,
    pattern: int | None = None,
    fringe: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a flat 2:1 isometric area rug with optional border, inner motif, and end fringe."""
    icx = round(cx)
    icy = round(cy)
    ihw = max(2, int(hw))
    ihh = max(1, int(hh))

    target.iso_tile(icx, icy, ihw * 2, fill, height=ihh * 2, outline=outline)
    with target.plane(
        p0=(icx, icy - ihh),
        p1=(icx + ihw, icy),
        p2=(icx - ihw, icy),
    ) as rug:
        if border is not None:
            rug.rect(0.10, 0.10, 0.80, 0.80, outline=border)
        if pattern is not None:
            rug.rect(0.28, 0.28, 0.44, 0.44, fill=pattern)
        if fringe is not None:
            for idx in range(4):
                u = 0.18 + idx * 0.21
                rug.dot(u, 0.02, fringe)
                rug.dot(u, 0.98, fringe)


def iso_cable_tray(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    *,
    rail: int,
    rung: int,
    width: int = 4,
    rungs: int = 5,
    outline: int | None = None,
) -> None:
    """Draw a ladder-style cable tray between `p0` and `p1` with side rails and rungs."""
    x0, y0 = round(p0[0]), round(p0[1])
    x1, y1 = round(p1[0]), round(p1[1])
    iw = max(2, int(width))
    count = max(1, int(rungs))

    for idx in range(count):
        t = (idx + 0.5) / count
        rx = round(x0 + t * (x1 - x0))
        ry = round(y0 + t * (y1 - y0))
        target.line(rx, ry, rx, ry + iw, rung)

    target.line(x0, y0, x1, y1, rail)
    target.line(x0, y0 + iw, x1, y1 + iw, rail)
    if outline is not None:
        target.line(x0, y0 - 1, x1, y1 - 1, outline)
        target.line(x0, y0 + iw + 1, x1, y1 + iw + 1, outline)


def iso_floor_zone(
    target: Canvas,
    geom: IsoRoomGeometry,
    u0: float,
    v0: float,
    u1: float,
    v1: float,
    *,
    fill: int,
    alt: int | None = None,
    pattern_color: int | None = None,
    mode: FloorZoneMode = "tiles",
    step: int = 12,
    dither_pattern: DitherPattern = "bayer4",
    dither_ratio: float = 0.14,
    border: int | None = None,
) -> PlaneRegion:
    """Draw a clipped `(u0..u1, v0..v1)` floor sub-zone with pattern and ordered dithering."""
    cu0 = clamp_unit(u0)
    cv0 = clamp_unit(v0)
    cu1 = clamp_unit(u1)
    cv1 = clamp_unit(v1)
    if cu1 <= cu0 or cv1 <= cv0:
        msg = (
            f"Invalid floor zone ({u0}, {v0}, {u1}, {v1}): "
            "requires 0 <= u0 < u1 <= 1 and 0 <= v0 < v1 <= 1"
        )
        raise ValueError(msg)

    zone_region = geom.floor_plane(cu0, cv0, cu1, cv1)

    with clipped_pane(target, zone_region) as pane:
        if not np.any(pane.mask):
            return zone_region
        pane.surface.data[pane.mask] = int(fill)
        if alt is not None and dither_ratio > 0.0:
            thresholds = compute_dither_thresholds(
                pane.ox,
                pane.oy,
                pane.ox + pane.width,
                pane.oy + pane.height,
                pattern=dither_pattern,
            )
            pane.surface.data[pane.mask & (thresholds < float(dither_ratio))] = int(alt)

        seam_col = pattern_color if pattern_color is not None else alt
        u_px = max(1.0, (cu1 - cu0) * geom.hw * geom.u_scale)
        v_px = max(1.0, (cv1 - cv0) * geom.hw * geom.v_scale)
        istep = max(2, int(step))
        cols = max(2, round(u_px / istep))
        rows = max(2, round(v_px / istep))

        if mode == "planks" and seam_col is not None:
            for idx in range(1, cols):
                u = idx / cols
                a0 = pane.project(u, 0.0)
                a1 = pane.project(u, 1.0)
                pane.surface.line(a0[0], a0[1], a1[0], a1[1], seam_col)
        elif mode in ("tiles", "grid") and seam_col is not None:
            for idx in range(1, cols):
                u = idx / cols
                a0 = pane.project(u, 0.0)
                a1 = pane.project(u, 1.0)
                pane.surface.line(a0[0], a0[1], a1[0], a1[1], seam_col)
            for idx in range(1, rows):
                v = idx / rows
                b0 = pane.project(0.0, v)
                b1 = pane.project(1.0, v)
                pane.surface.line(b0[0], b0[1], b1[0], b1[1], seam_col)
        elif mode == "carpet" and pattern_color is not None:
            c00 = pane.project(0.14, 0.14)
            c10 = pane.project(0.86, 0.14)
            c11 = pane.project(0.86, 0.86)
            c01 = pane.project(0.14, 0.86)
            for sa, sb in ((c00, c10), (c10, c11), (c11, c01), (c01, c00)):
                pane.surface.line(sa[0], sa[1], sb[0], sb[1], pattern_color)
        elif mode not in ("solid", "planks", "tiles", "grid", "carpet"):
            msg = f"Unsupported floor zone mode: {mode!r}"
            raise ValueError(msg)

        if border is not None:
            e00 = pane.project(0.0, 0.0)
            e10 = pane.project(1.0, 0.0)
            e11 = pane.project(1.0, 1.0)
            e01 = pane.project(0.0, 1.0)
            for sa, sb in ((e00, e10), (e10, e11), (e11, e01), (e01, e00)):
                pane.surface.line(sa[0], sa[1], sb[0], sb[1], border)

    return zone_region


def iso_floor_threshold(
    target: Canvas,
    geom: IsoRoomGeometry,
    wall: WallSide,
    at: float,
    span: tuple[float, float] = (0.0, 1.0),
    *,
    fill: int,
    highlight: int | None = None,
    outline: int | None = None,
    width: float = 0.04,
) -> PlaneRegion:
    """Draw a transition threshold strip between floor zones along `wall` at `at`."""
    if wall not in ("left", "right"):
        msg = f"Unsupported wall side: {wall!r}"
        raise ValueError(msg)
    s0 = clamp_unit(span[0])
    s1 = clamp_unit(span[1])
    if s1 <= s0:
        msg = f"Invalid threshold span {span!r}: requires 0 <= s0 < s1 <= 1"
        raise ValueError(msg)

    half_w = max(0.005, min(0.25, float(width) * 0.5))
    if wall == "left":
        u0, u1 = clamp_unit(at - half_w), clamp_unit(at + half_w)
        v0, v1 = s0, s1
    else:
        u0, u1 = s0, s1
        v0, v1 = clamp_unit(at - half_w), clamp_unit(at + half_w)

    strip_region = geom.floor_plane(u0, v0, u1, v1)

    with clipped_pane(target, strip_region) as pane:
        if not np.any(pane.mask):
            return strip_region
        pane.surface.data[pane.mask] = int(fill)
        if highlight is not None:
            if wall == "left":
                h0, h1 = pane.project(0.5, 0.0), pane.project(0.5, 1.0)
            else:
                h0, h1 = pane.project(0.0, 0.5), pane.project(1.0, 0.5)
            pane.surface.line(h0[0], h0[1], h1[0], h1[1], highlight)
        if outline is not None:
            if wall == "left":
                edges = (
                    (pane.project(0.0, 0.0), pane.project(0.0, 1.0)),
                    (pane.project(1.0, 0.0), pane.project(1.0, 1.0)),
                )
            else:
                edges = (
                    (pane.project(0.0, 0.0), pane.project(1.0, 0.0)),
                    (pane.project(0.0, 1.0), pane.project(1.0, 1.0)),
                )
            for ea, eb in edges:
                pane.surface.line(ea[0], ea[1], eb[0], eb[1], outline)

    return strip_region
