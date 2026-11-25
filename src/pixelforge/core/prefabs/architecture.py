"""Architectural 2:1 isometric prefab helpers (rooms, floors, windows, vents)."""

from __future__ import annotations

from typing import Literal

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.plane import Point2D

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
) -> None:
    """Draw a skewed isometric window onto a `(p0, p1, p2)` wall plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as win:
        win.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        win.rect(0.07, 0.08, 0.86, 0.84, fill=sky)
        if sky_alt is not None:
            win.dither(0.07, 0.08, 0.86, 0.45, sky_alt, sky, pattern="bayer4", ratio=0.4)
        if mullion is not None:
            win.rect(0.05, 0.48, 0.90, 0.06, fill=mullion)
        if sill is not None:
            win.rect(-0.04, 0.94, 1.08, 0.08, fill=sill)


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
