"""Interior partition walls, glass dividers, pillars, and wall molding prefabs."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from pixelforge.core.plane import Point2D
from pixelforge.core.prefabs.architecture.room import (
    Canvas,
    DoorwayStyle,
    IsoRoomGeometry,
    WallMoldingStyle,
    WallSide,
    clamp_unit,
)
from pixelforge.core.prefabs.atmosphere import ClippedPane, PlaneRegion, clipped_pane


def _offset_pt(pt: tuple[int, int], dx: int, dy: int) -> tuple[int, int]:
    return (pt[0] + dx, pt[1] + dy)


def _draw_arch_spandrels(
    target: Canvas,
    front_plane: PlaneRegion,
    du0: float,
    du1: float,
    lintel_v: float,
    arch_drop: float,
    face: int,
) -> None:
    steps = 4
    span = du1 - du0
    with target.plane(p0=front_plane[0], p1=front_plane[1], p2=front_plane[2]) as wall_p:
        for i in range(steps):
            t0 = i / steps
            t1 = (i + 1) / steps
            w_frac = 0.22 * (1.0 - t0)
            h_frac = arch_drop * (t1 - t0)
            v_top = lintel_v + arch_drop * t0
            if w_frac > 0.0:
                wall_p.rect(du0, v_top, span * w_frac, h_frac, fill=face)
                wall_p.rect(du1 - span * w_frac, v_top, span * w_frac, h_frac, fill=face)


def _draw_partition_extrusion(
    target: Canvas,
    front_plane: PlaneRegion,
    corners: tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]],
    wall: WallSide,
    thickness: int,
    cap: int,
    side_col: int,
    door_bounds: tuple[float, float, float] | None,
    baseboard: tuple[int, int] | None,
    outline: int | None,
) -> None:
    c00, c10, c11, c01 = corners
    dx_b = -thickness if wall == "left" else thickness
    dy_b = -max(1, thickness // 2)

    b00 = _offset_pt(c00, dx_b, dy_b)
    b10 = _offset_pt(c10, dx_b, dy_b)
    target.polygon((c00, c10, b10, b00), cap)
    if wall == "left":
        b01 = _offset_pt(c01, dx_b, dy_b)
        target.polygon((c00, b00, b01, c01), side_col)
    else:
        b11 = _offset_pt(c11, dx_b, dy_b)
        target.polygon((c10, b10, b11, c11), side_col)

    if door_bounds is not None:
        du0, du1, lintel_v = door_bounds
        jamb_u = du1 if wall == "left" else du0
        with target.plane(p0=front_plane[0], p1=front_plane[1], p2=front_plane[2]) as wp:
            jt = wp.project(jamb_u, lintel_v)
            jb = wp.project(jamb_u, 1.0)
        target.polygon((jt, _offset_pt(jt, dx_b, dy_b), _offset_pt(jb, dx_b, dy_b), jb), side_col)

    if baseboard is not None:
        bb_top, bb_bot = baseboard
        with target.plane(p0=front_plane[0], p1=front_plane[1], p2=front_plane[2]) as wp:
            if door_bounds is None:
                wp.line(0.0, 0.96, 1.0, 0.96, bb_top)
                wp.line(0.0, 1.0, 1.0, 1.0, bb_bot)
            else:
                du0, du1, _ = door_bounds
                wp.line(0.0, 0.96, du0, 0.96, bb_top)
                wp.line(0.0, 1.0, du0, 1.0, bb_bot)
                wp.line(du1, 0.96, 1.0, 0.96, bb_top)
                wp.line(du1, 1.0, 1.0, 1.0, bb_bot)

    if outline is not None:
        for pa, pb in (
            (b00, b10),
            (c00, c10),
            (c00, b00),
            (c10, b10),
            (c00, c01),
            (c10, c11),
        ):
            target.line(pa[0], pa[1], pb[0], pb[1], outline)


def iso_partition_wall(
    target: Canvas,
    geom: IsoRoomGeometry,
    wall: WallSide,
    at: float,
    u0: float = 0.0,
    u1: float = 1.0,
    *,
    face: int,
    cap: int,
    side: int | None = None,
    height: int | None = None,
    thickness: int = 3,
    doorway: tuple[float, float] | None = None,
    door_height: float = 0.72,
    doorway_style: DoorwayStyle = "rect",
    baseboard: tuple[int, int] | None = None,
    outline: int | None = None,
) -> PlaneRegion:
    """Draw a 2:1 isometric interior partition wall with cap, thickness, and optional cutout."""
    if wall not in ("left", "right"):
        msg = f"Unsupported wall side: {wall!r}"
        raise ValueError(msg)
    cu0 = clamp_unit(u0)
    cu1 = clamp_unit(u1)
    if cu1 <= cu0:
        msg = f"Invalid partition span ({u0}, {u1}): requires 0 <= u0 < u1 <= 1"
        raise ValueError(msg)

    eff_h = geom.wall_h if height is None else max(2, int(height))
    t = max(1, int(thickness))
    side_col = side if side is not None else cap
    front_plane = geom.partition_plane(wall, at, cu0, 0.0, cu1, 1.0, height=eff_h)

    door_bounds: tuple[float, float, float] | None = None
    if doorway is not None:
        du0 = max(0.04, min(0.92, float(doorway[0])))
        du1 = max(du0 + 0.04, min(0.96, float(doorway[1])))
        dh = max(0.25, min(0.92, float(door_height)))
        door_bounds = (du0, du1, 1.0 - dh)

    with target.plane(p0=front_plane[0], p1=front_plane[1], p2=front_plane[2]) as wp:
        corners = (
            wp.project(0.0, 0.0),
            wp.project(1.0, 0.0),
            wp.project(1.0, 1.0),
            wp.project(0.0, 1.0),
        )
        if door_bounds is None:
            wp.rect(0.0, 0.0, 1.0, 1.0, fill=face)
        else:
            du0, du1, lintel_v = door_bounds
            wp.rect(0.0, 0.0, du0, 1.0, fill=face)
            wp.rect(du1, 0.0, 1.0 - du1, 1.0, fill=face)
            wp.rect(du0, 0.0, du1 - du0, lintel_v, fill=face)

    if door_bounds is not None and doorway_style == "arch":
        du0, du1, lintel_v = door_bounds
        _draw_arch_spandrels(
            target, front_plane, du0, du1, lintel_v, min(0.18, (1.0 - lintel_v) * 0.3), face
        )

    _draw_partition_extrusion(
        target,
        front_plane,
        corners,
        wall,
        t,
        cap,
        side_col,
        door_bounds,
        baseboard,
        outline,
    )
    return front_plane


def iso_glass_partition(
    target: Canvas,
    geom: IsoRoomGeometry,
    wall: WallSide,
    at: float,
    u0: float = 0.0,
    u1: float = 1.0,
    *,
    frame: int,
    glass: int,
    height: int | None = None,
    glint: int | None = None,
    mullion: int | None = None,
    cols: int = 2,
    rows: int = 1,
    kickplate: int | None = None,
    kickplate_ratio: float = 0.18,
    outline: int | None = None,
    scene: Callable[[ClippedPane], None] | None = None,
) -> PlaneRegion:
    """Draw a framed isometric glass partition divider using `clipped_pane`."""
    if wall not in ("left", "right"):
        msg = f"Unsupported wall side: {wall!r}"
        raise ValueError(msg)
    cu0 = clamp_unit(u0)
    cu1 = clamp_unit(u1)
    if cu1 <= cu0:
        msg = f"Invalid glass partition span ({u0}, {u1}): requires 0 <= u0 < u1 <= 1"
        raise ValueError(msg)

    eff_h = geom.wall_h if height is None else max(4, int(height))
    plane = geom.partition_plane(wall, at, cu0, 0.0, cu1, 1.0, height=eff_h)
    kp = max(0.0, min(0.45, float(kickplate_ratio))) if kickplate is not None else 0.0
    v_glass_bot = 0.94 - kp

    with target.plane(p0=plane[0], p1=plane[1], p2=plane[2]) as fp:
        fp.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        if kickplate is not None and kp > 0.0:
            fp.rect(0.04, 0.96 - kp, 0.92, kp, fill=kickplate)
        gp0 = fp.project(0.06, 0.06)
        gp1 = fp.project(0.94, 0.06)
        gp2 = fp.project(0.06, v_glass_bot)

    glass_region: PlaneRegion = (gp0, gp1, gp2)
    with clipped_pane(target, glass_region) as gp:
        if np.any(gp.mask):
            gp.surface.data[gp.mask] = int(glass)
            if scene is not None:
                scene(gp)
            if glint is not None:
                a0, a1 = gp.project(0.14, 0.14), gp.project(0.28, 0.30)
                b0, b1 = gp.project(0.24, 0.13), gp.project(0.34, 0.24)
                gp.surface.line(a0[0], a0[1], a1[0], a1[1], glint)
                gp.surface.line(b0[0], b0[1], b1[0], b1[1], glint)

    if mullion is not None:
        icols = max(1, int(cols))
        irows = max(1, int(rows))
        with target.plane(p0=plane[0], p1=plane[1], p2=plane[2]) as fp:
            for c in range(1, icols):
                uc = 0.06 + (c / float(icols)) * 0.88 - 0.02
                fp.rect(uc, 0.06, 0.04, v_glass_bot - 0.06, fill=mullion)
            for r in range(1, irows):
                vr = 0.06 + (r / float(irows)) * (v_glass_bot - 0.06) - 0.02
                fp.rect(0.06, vr, 0.88, 0.04, fill=mullion)

    return plane


def iso_pillar(
    target: Canvas,
    cx: int | float,
    cy: int | float,
    w: int = 8,
    d: int = 8,
    h: int = 38,
    *,
    top: int,
    left: int,
    right: int,
    cap_color: int | None = None,
    base_color: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a 2:1 isometric architectural pillar with optional plinth base and top capital."""
    icx = round(cx)
    icy = round(cy)
    iw = max(4, int(w))
    id_ = max(4, int(d))
    ih = max(6, int(h))

    target.iso_box(icx, icy, iw, id_, ih, top=top, left=left, right=right, outline=outline)
    if base_color is not None:
        base_h = max(2, min(4, ih // 6))
        target.iso_box(
            icx,
            icy + ih - base_h,
            iw + 2,
            id_ + 2,
            base_h,
            top=base_color,
            left=base_color,
            right=base_color,
            outline=outline,
        )
    if cap_color is not None:
        cap_h = max(2, min(4, ih // 6))
        target.iso_box(
            icx,
            icy,
            iw + 2,
            id_ + 2,
            cap_h,
            top=cap_color,
            left=cap_color,
            right=cap_color,
            outline=outline,
        )


def wall_molding(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    primary: int,
    highlight: int | None = None,
    shadow: int | None = None,
    style: WallMoldingStyle = "chair_rail",
    v_pos: float | None = None,
    thickness: float = 0.06,
) -> None:
    """Draw architectural molding (crown, chair rail, wainscot, or baseboard) on a wall plane."""
    t = max(0.02, min(0.25, float(thickness)))
    if v_pos is not None:
        vp = max(0.0, min(1.0 - t, float(v_pos)))
    elif style == "crown":
        vp = 0.0
    elif style in ("chair_rail", "wainscot"):
        vp = 0.62
    elif style == "baseboard":
        vp = 1.0 - t
    else:
        msg = f"Unsupported wall molding style: {style!r}"
        raise ValueError(msg)

    with target.plane(p0=p0, p1=p1, p2=p2) as mold:
        mold.rect(0.0, vp, 1.0, t, fill=primary)
        if highlight is not None:
            mold.line(0.0, vp, 1.0, vp, highlight)
        if shadow is not None:
            mold.line(0.0, min(1.0, vp + t), 1.0, min(1.0, vp + t), shadow)
        if style == "wainscot":
            panel_top = min(0.90, vp + t + 0.04)
            panel_h = max(0.04, 0.94 - panel_top)
            for idx in range(3):
                u_start = 0.06 + idx * 0.31
                mold.rect(u_start, panel_top, 0.25, panel_h, outline=primary)
                if shadow is not None:
                    mold.rect(
                        u_start + 0.02, panel_top + 0.02, 0.21, panel_h - 0.04, outline=shadow
                    )
