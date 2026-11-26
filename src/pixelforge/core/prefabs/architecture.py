"""Architectural 2:1 isometric prefab helpers (rooms, floors, windows, vents)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.plane import Point2D
from pixelforge.core.prefabs.atmosphere import (
    ClippedPane,
    PlaneRegion,
    RectRegion,
    clipped_pane,
)
from pixelforge.core.surface import IndexedSurface

Canvas = Asset | Layer
FloorPatternMode = Literal["planks", "tiles", "grid"]


def iso_room_shell(
    target: Canvas,
    cx: int | float,
    cy: int | float,
    hw: int,
    hh: int,
    wall_h: int,
    *,
    floor: int,
    left_wall: int,
    right_wall: int,
    floor_alt: int | None = None,
    floor_dither_ratio: float = 0.12,
    baseboard: tuple[int, int] | None = None,
    wall_seam: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a 2:1 isometric room shell with floor diamond, two back walls, and trim."""
    icx = round(cx)
    icy = round(cy)
    ihw = max(1, int(hw))
    ihh = max(1, int(hh))
    iwall_h = max(1, int(wall_h))

    target.iso_tile(icx, icy, ihw * 2, floor, height=ihh * 2)
    if floor_alt is not None:
        target.dither(
            icx - ihw,
            icy - ihh,
            ihw * 2,
            ihh * 2,
            None,
            floor_alt,
            pattern="bayer4",
            ratio=floor_dither_ratio,
            mask="opaque",
        )

    apex_y = icy - ihh
    left_x = icx - ihw
    right_x = icx + ihw

    target.polygon(
        (
            (left_x, icy),
            (icx, apex_y),
            (icx, apex_y - iwall_h),
            (left_x, icy - iwall_h),
        ),
        left_wall,
    )
    target.polygon(
        (
            (icx, apex_y),
            (right_x, icy),
            (right_x, icy - iwall_h),
            (icx, apex_y - iwall_h),
        ),
        right_wall,
    )

    if baseboard is not None:
        bb_top, bb_bot = baseboard
        target.line(left_x, icy - 1, icx, apex_y - 1, bb_top)
        target.line(left_x, icy, icx, apex_y, bb_bot)
        target.line(icx, apex_y - 1, right_x, icy - 1, bb_top)
        target.line(icx, apex_y, right_x, icy, bb_bot)

    if wall_seam is not None:
        target.line(icx, apex_y, icx, apex_y - iwall_h, wall_seam)

    if outline is not None:
        target.line(left_x, icy - iwall_h, icx, apex_y - iwall_h, outline)
        target.line(icx, apex_y - iwall_h, right_x, icy - iwall_h, outline)
        target.line(left_x, icy, left_x, icy - iwall_h, outline)
        target.line(right_x, icy, right_x, icy - iwall_h, outline)
        target.line(left_x, icy, icx, icy + ihh, outline)
        target.line(icx, icy + ihh, right_x, icy, outline)


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


def iso_window_glass_region(p0: Point2D, p1: Point2D, p2: Point2D) -> PlaneRegion:
    """Return the `(gp0, gp1, gp2)` plane region corresponding to `iso_window` inner glass."""
    u_vec = (float(p1[0]) - float(p0[0]), float(p1[1]) - float(p0[1]))
    v_vec = (float(p2[0]) - float(p0[0]), float(p2[1]) - float(p0[1]))

    def _proj(u: float, v: float) -> Point2D:
        return (
            float(p0[0]) + u * u_vec[0] + v * v_vec[0],
            float(p0[1]) + u * u_vec[1] + v * v_vec[1],
        )

    return (_proj(0.07, 0.08), _proj(0.93, 0.08), _proj(0.07, 0.92))


def front_window_glass_region(
    x: int | float,
    y: int | float,
    w: int | float,
    h: int | float,
    *,
    frame_thickness: int = 2,
) -> RectRegion:
    """Return the `(gx, gy, gw, gh)` rectangle corresponding to `front_window` inner glass."""
    ix = round(x)
    iy = round(y)
    iw = max(3, int(w))
    ih = max(3, int(h))
    t = max(1, min(int(frame_thickness), (iw - 1) // 2, (ih - 1) // 2))
    return (ix + t, iy + t, max(1, iw - 2 * t), max(1, ih - 2 * t))


def iso_window(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    frame: int,
    sky: int,
    outline: int | None = None,
    sky_alt: int | None = None,
    mullion: int | None = None,
    sill: int | None = None,
    cols: int = 1,
    rows: int = 2,
    glint: int | None = None,
    scene: Callable[[ClippedPane], None] | None = None,
) -> None:
    """Draw a skewed isometric window onto `(p0, p1, p2)` with optional clipped vista scene."""
    glass_region = iso_window_glass_region(p0, p1, p2)
    with target.plane(p0=p0, p1=p1, p2=p2) as win:
        win.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        if scene is None:
            win.rect(0.07, 0.08, 0.86, 0.84, fill=sky)
            if sky_alt is not None:
                win.dither(0.07, 0.08, 0.86, 0.45, sky_alt, sky, pattern="bayer4", ratio=0.4)

    if scene is not None or glint is not None:
        with clipped_pane(target, glass_region) as glass_pane:
            if scene is not None:
                scene(glass_pane)
            if glint is not None:
                gx0, gy0 = glass_pane.project(0.14, 0.14)
                gx1, gy1 = glass_pane.project(0.26, 0.28)
                glass_pane.surface.line(gx0, gy0, gx1, gy1, glint)
                sx0, sy0 = glass_pane.project(0.22, 0.13)
                sx1, sy1 = glass_pane.project(0.30, 0.22)
                glass_pane.surface.line(sx0, sy0, sx1, sy1, glint)

    with target.plane(p0=p0, p1=p1, p2=p2) as win:
        if mullion is not None:
            icols = max(1, int(cols))
            irows = max(1, int(rows))
            if icols == 1 and irows == 2:
                # INVARIANT: Preserve exact legacy mullion placement for default 1x2 callers.
                win.rect(0.05, 0.48, 0.90, 0.06, fill=mullion)
            else:
                for r in range(1, irows):
                    vr = 0.08 + (r / float(irows)) * 0.84 - 0.03
                    win.rect(0.05, vr, 0.90, 0.06, fill=mullion)
                for c in range(1, icols):
                    uc = 0.07 + (c / float(icols)) * 0.86 - 0.025
                    win.rect(uc, 0.06, 0.05, 0.88, fill=mullion)
        if sill is not None:
            win.rect(-0.04, 0.94, 1.08, 0.08, fill=sill)


def _draw_front_glint(surface: IndexedSurface, gw: int, gh: int, glint: int) -> None:
    g_len = max(2, min(5, min(gw, gh) // 5))
    surface.line(2, 2, 2 + g_len, 2 + g_len, glint)
    surface.line(5, 2, 5 + max(1, g_len // 2), 2 + max(1, g_len // 2), glint)


def front_window(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int | float,
    h: int | float,
    *,
    frame: int,
    sky: int,
    outline: int | None = None,
    sky_alt: int | None = None,
    mullion: int | None = None,
    sill: int | None = None,
    cols: int = 1,
    rows: int = 2,
    glint: int | None = None,
    frame_thickness: int = 2,
    scene: Callable[[ClippedPane], None] | None = None,
) -> None:
    """Draw a `front-2.5d` rectangular window with clipped glass vista, mullions, and sill."""
    ix = round(x)
    iy = round(y)
    iw = max(3, int(w))
    ih = max(3, int(h))

    target.rect(ix, iy, iw, ih, frame, fill=True)
    if outline is not None:
        target.rect(ix, iy, iw, ih, outline, fill=False)

    glass_region = front_window_glass_region(ix, iy, iw, ih, frame_thickness=frame_thickness)
    gx, gy, gw, gh = (
        round(glass_region[0]),
        round(glass_region[1]),
        int(glass_region[2]),
        int(glass_region[3]),
    )
    if scene is not None:
        with clipped_pane(target, glass_region) as glass_pane:
            scene(glass_pane)
            if glint is not None:
                _draw_front_glint(glass_pane.surface, gw, gh, glint)
    else:
        target.rect(gx, gy, gw, gh, sky, fill=True)
        if sky_alt is not None:
            target.dither(gx, gy, gw, max(1, gh // 2), sky_alt, sky, pattern="bayer4", ratio=0.4)
        if glint is not None:
            with clipped_pane(target, glass_region) as glint_pane:
                _draw_front_glint(glint_pane.surface, gw, gh, glint)

    if mullion is not None:
        icols = max(1, int(cols))
        irows = max(1, int(rows))
        bar_h = 1 if gh < 18 else 2
        bar_w = 1 if gw < 18 else 2
        for r in range(1, irows):
            my = gy + round((r / float(irows)) * gh) - (bar_h // 2)
            target.rect(gx, my, gw, bar_h, mullion, fill=True)
        for c in range(1, icols):
            mx = gx + round((c / float(icols)) * gw) - (bar_w // 2)
            target.rect(mx, gy, bar_w, gh, mullion, fill=True)

    if sill is not None:
        target.rect(ix - 1, iy + ih - 1, iw + 2, 2, sill, fill=True)


def wall_vent(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    frame: int,
    slat: int,
    outline: int | None = None,
    slats: int = 3,
) -> None:
    """Draw a louvered wall vent onto a `(p0, p1, p2)` wall plane."""
    count = max(1, int(slats))
    with target.plane(p0=p0, p1=p1, p2=p2) as vent:
        vent.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        vent.grid(0.15, 0.20, 0.70, 0.60, cols=1, rows=count, color=slat, cell_fill=0.55)
