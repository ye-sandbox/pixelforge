"""2:1 isometric projection, tiles, and extruded isometric box primitives."""

from __future__ import annotations

import math
from contextlib import nullcontext
from typing import Literal

from pixelforge.core.surface import IndexedSurface
from pixelforge.core.surface_maps import (
    NORMAL_FLAT,
    NORMAL_ISO_LEFT,
    NORMAL_ISO_RIGHT,
    NORMAL_ISO_TOP,
    normalize_normal,
)

IsoAnchor = Literal["top", "center", "bottom"]
IsoRampDirection = Literal["right", "left", "front", "back"]


def iso_project(
    x: int | float,
    y: int | float,
    z: int | float = 0.0,
    *,
    origin: tuple[int | float, int | float] = (0, 0),
    tile_w: float = 4.0,
    tile_h: float = 2.0,
    z_scale: float = 1.0,
) -> tuple[int, int]:
    """Project 3D `(x, y, z)` coordinates into 2D integer 2:1 isometric screen coords.

    With the default `tile_w=4.0, tile_h=2.0`, every integer step in `+x` maps to
    `(+2, +1)` and every integer step in `+y` maps to `(-2, +1)` with zero rounding drift.
    """
    ox, oy = origin
    sx = ox + (x - y) * (tile_w * 0.5)
    sy = oy + (x + y) * (tile_h * 0.5) - (z * z_scale)
    return (round(sx), round(sy))


def _tile_vertices(
    cx: int | float,
    cy: int | float,
    width: int,
    height: int,
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]]:
    icx = round(cx)
    icy = round(cy)
    hw = width // 2
    hh = height // 2
    top = (icx, icy - hh)
    right = (icx + hw, icy)
    bottom = (icx, icy + hh)
    left = (icx - hw, icy)
    return (top, right, bottom, left)


def _draw_with_optional_outline(
    surface: IndexedSurface,
    min_x: int,
    min_y: int,
    max_x: int,
    max_y: int,
    outline: int | None,
) -> tuple[IndexedSurface, int, int]:
    """Allocate a tight local surface when `outline` is requested."""
    if outline is None:
        return (surface, 0, 0)
    # INVARIANT: Outline expands the bounding box by 1px on all sides; render into a tight
    # isolated buffer first so auto_outline never touches surrounding canvas pixels.
    pad = 1
    w = max(1, (max_x - min_x + 1) + 2 * pad)
    h = max(1, (max_y - min_y + 1) + 2 * pad)
    return (IndexedSurface(w, h, track_maps=surface.has_maps), min_x - pad, min_y - pad)


def iso_tile(
    surface: IndexedSurface,
    cx: int | float,
    cy: int | float,
    width: int,
    color: int,
    *,
    height: int | None = None,
    fill: bool = True,
    outline: int | None = None,
) -> None:
    """Draw a 2:1 isometric diamond tile centered at `(cx, cy)`."""
    iw = int(width)
    ih = int(height) if height is not None else max(2, round(iw / 2))
    if iw <= 0 or ih <= 0:
        return

    top, right, bottom, left = _tile_vertices(cx, cy, iw, ih)
    min_x = min(top[0], right[0], bottom[0], left[0])
    max_x = max(top[0], right[0], bottom[0], left[0])
    min_y = min(top[1], right[1], bottom[1], left[1])
    max_y = max(top[1], right[1], bottom[1], left[1])

    target, ox, oy = _draw_with_optional_outline(surface, min_x, min_y, max_x, max_y, outline)
    maps = target.maps
    with maps.normal_scope(NORMAL_ISO_TOP) if maps is not None else nullcontext():
        target.quad(
            (top[0] - ox, top[1] - oy),
            (right[0] - ox, right[1] - oy),
            (bottom[0] - ox, bottom[1] - oy),
            (left[0] - ox, left[1] - oy),
            color,
            fill=fill,
        )
    if outline is not None:
        target.auto_outline(outline)
        surface.blit_layer(target, ox, oy)


def _box_top_origin(
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    h: int,
    anchor: IsoAnchor,
) -> tuple[int, int]:
    dx_r = w
    dy_r = w // 2
    dx_l = d
    dy_l = d // 2
    if anchor == "top":
        return (round(x), round(y))
    if anchor == "center":
        tx = x - (dx_r - dx_l) * 0.5
        ty = y - (dy_r + dy_l) * 0.5
        return (round(tx), round(ty))
    if anchor == "bottom":
        tx = x - (dx_r - dx_l)
        ty = y - (dy_r + dy_l + h)
        return (round(tx), round(ty))
    msg = f"Unsupported iso_box anchor: {anchor!r}"
    raise ValueError(msg)


def iso_box(
    surface: IndexedSurface,
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    h: int,
    *,
    top: int,
    left: int,
    right: int,
    outline: int | None = None,
    highlight: int | None = None,
    anchor: IsoAnchor = "top",
) -> None:
    """Draw a 3-face 2:1 isometric prism with screen-space spans `(w, d)` and height `h`."""
    iw = int(w)
    id_ = int(d)
    ih = int(h)
    if iw <= 0 or id_ <= 0 or ih < 0:
        return

    tx, ty = _box_top_origin(x, y, iw, id_, ih, anchor)
    dy_r = iw // 2
    dy_l = id_ // 2

    p_top = (tx, ty)
    p_right = (tx + iw, ty + dy_r)
    p_left = (tx - id_, ty + dy_l)
    p_front = (tx + iw - id_, ty + dy_r + dy_l)

    p_left_bot = (p_left[0], p_left[1] + ih)
    p_front_bot = (p_front[0], p_front[1] + ih)
    p_right_bot = (p_right[0], p_right[1] + ih)

    all_pts = (p_top, p_right, p_left, p_front, p_left_bot, p_front_bot, p_right_bot)
    min_x = min(pt[0] for pt in all_pts)
    max_x = max(pt[0] for pt in all_pts)
    min_y = min(pt[1] for pt in all_pts)
    max_y = max(pt[1] for pt in all_pts)

    target, ox, oy = _draw_with_optional_outline(surface, min_x, min_y, max_x, max_y, outline)

    def _s(pt: tuple[int, int]) -> tuple[int, int]:
        return (pt[0] - ox, pt[1] - oy)

    # INVARIANT: Draw visible side walls before the top face so top edges cleanly occlude
    # upper side-wall strokes without 1px seam artifacts.
    maps = target.maps
    if ih > 0:
        if maps is not None:
            sl_x, sl_y = _s(p_left)
            sr_x, sr_y = _s(p_front)
            slope_l = dy_l / max(1, id_)
            c_l = float(ih) + float(sl_y) - slope_l * float(sl_x)
            with (
                maps.normal_scope(NORMAL_ISO_LEFT),
                maps.height_plane_scope(slope_l, -1.0, c_l, 0.0, float(ih)),
            ):
                target.quad(_s(p_left), _s(p_front), _s(p_front_bot), _s(p_left_bot), left)

            slope_r = -dy_r / max(1, iw)
            c_r = float(ih) + float(sr_y) - slope_r * float(sr_x)
            with (
                maps.normal_scope(NORMAL_ISO_RIGHT),
                maps.height_plane_scope(slope_r, -1.0, c_r, 0.0, float(ih)),
            ):
                target.quad(_s(p_front), _s(p_right), _s(p_right_bot), _s(p_front_bot), right)
        else:
            target.quad(_s(p_left), _s(p_front), _s(p_front_bot), _s(p_left_bot), left)
            target.quad(_s(p_front), _s(p_right), _s(p_right_bot), _s(p_front_bot), right)

    top_n = maps.normal_scope(NORMAL_ISO_TOP) if maps is not None else nullcontext()
    top_h = maps.height_scope(float(ih)) if maps is not None else nullcontext()
    with top_n, top_h:
        target.quad(_s(p_top), _s(p_right), _s(p_front), _s(p_left), top)

        if highlight is not None:
            target.line(_s(p_left)[0], _s(p_left)[1], _s(p_front)[0], _s(p_front)[1], highlight)
            target.line(_s(p_front)[0], _s(p_front)[1], _s(p_right)[0], _s(p_right)[1], highlight)

    if outline is not None:
        out_n = maps.normal_scope(NORMAL_FLAT) if maps is not None else nullcontext()
        out_h = maps.height_scope(0.0) if maps is not None else nullcontext()
        with out_n, out_h:
            target.auto_outline(outline)
        surface.blit_layer(target, ox, oy)


def iso_cylinder(
    surface: IndexedSurface,
    cx: int | float,
    cy: int | float,
    radius: int,
    h: int,
    *,
    top: int,
    side: int,
    shade: int | None = None,
    ry: int | None = None,
    outline: int | None = None,
    highlight: int | None = None,
    anchor: IsoAnchor = "top",
) -> None:
    """Draw a 2:1 isometric vertical cylinder with elliptical top cap and shaded body."""
    irx = int(radius)
    ih = int(h)
    if irx <= 0 or ih < 0:
        return
    iry = max(1, irx // 2) if ry is None else max(1, int(ry))

    if anchor == "top":
        tcx, tcy = round(cx), round(cy)
    elif anchor == "center":
        tcx, tcy = round(cx), round(float(cy) - ih * 0.5)
    elif anchor == "bottom":
        tcx, tcy = round(cx), round(float(cy) - ih)
    else:
        msg = f"Unsupported iso_cylinder anchor: {anchor!r}"
        raise ValueError(msg)

    target, ox, oy = _draw_with_optional_outline(
        surface,
        tcx - irx,
        tcy - iry,
        tcx + irx,
        tcy + iry + ih,
        outline,
    )
    lx = tcx - ox
    ly = tcy - oy
    maps = target.maps

    if ih > 0:
        shade_cutoff = max(1, irx // 3)
        for dx in range(-irx, irx + 1):
            ratio = dx / float(irx)
            col_dy = round(iry * math.sqrt(max(0.0, 1.0 - ratio * ratio)))
            col_color = shade if (shade is not None and dx >= shade_cutoff) else side
            if maps is not None:
                nx = ratio * 0.85
                ny = -0.15
                nz = math.sqrt(max(0.05, 1.0 - nx * nx - ny * ny))
                col_n = normalize_normal(nx, ny, nz)
                with (
                    maps.normal_scope(col_n),
                    maps.height_plane_scope(0.0, -1.0, float(ih + ly), 0.0, float(ih)),
                ):
                    target.line(lx + dx, ly, lx + dx, ly + ih + col_dy, col_color)
            else:
                target.line(lx + dx, ly, lx + dx, ly + ih + col_dy, col_color)

    top_n = maps.normal_scope(NORMAL_ISO_TOP) if maps is not None else nullcontext()
    top_h = maps.height_scope(float(ih)) if maps is not None else nullcontext()
    with top_n, top_h:
        target.ellipse(lx, ly, irx, iry, top, fill=True)
        if highlight is not None:
            target.arc(lx, ly, irx, 0.0, 180.0, highlight, rx=irx, ry=iry)

    if outline is not None:
        out_n = maps.normal_scope(NORMAL_FLAT) if maps is not None else nullcontext()
        out_h = maps.height_scope(0.0) if maps is not None else nullcontext()
        with out_n, out_h:
            target.auto_outline(outline)
        surface.blit_layer(target, ox, oy)


def iso_ramp(
    surface: IndexedSurface,
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    h: int,
    *,
    slope: int,
    left: int,
    right: int,
    direction: IsoRampDirection = "right",
    outline: int | None = None,
    highlight: int | None = None,
    anchor: IsoAnchor = "top",
) -> None:
    """Draw a 2:1 isometric sloped wedge/ramp prism along `direction`."""
    iw = int(w)
    id_ = int(d)
    ih = int(h)
    if iw <= 0 or id_ <= 0 or ih < 0:
        return

    tx, ty = _box_top_origin(x, y, iw, id_, ih, anchor)
    dy_r = iw // 2
    dy_l = id_ // 2

    p_top = (tx, ty)
    p_right = (tx + iw, ty + dy_r)
    p_left = (tx - id_, ty + dy_l)
    p_front = (tx + iw - id_, ty + dy_r + dy_l)

    p_top_bot = (p_top[0], p_top[1] + ih)
    p_right_bot = (p_right[0], p_right[1] + ih)
    p_left_bot = (p_left[0], p_left[1] + ih)
    p_front_bot = (p_front[0], p_front[1] + ih)

    all_pts = (
        p_top,
        p_right,
        p_left,
        p_front,
        p_top_bot,
        p_right_bot,
        p_left_bot,
        p_front_bot,
    )
    min_x = min(pt[0] for pt in all_pts)
    max_x = max(pt[0] for pt in all_pts)
    min_y = min(pt[1] for pt in all_pts)
    max_y = max(pt[1] for pt in all_pts)

    target, ox, oy = _draw_with_optional_outline(surface, min_x, min_y, max_x, max_y, outline)

    def _s(pt: tuple[int, int]) -> tuple[int, int]:
        return (pt[0] - ox, pt[1] - oy)

    maps = target.maps
    if direction == "right":
        # Low at back-left (top_bot..left_bot), high at front-right (top..right/front)
        slope_quad = (_s(p_top_bot), _s(p_right), _s(p_front), _s(p_left_bot))
        high_edge = (_s(p_front), _s(p_right))
        left_tri = (_s(p_left_bot), _s(p_front), _s(p_front_bot))
        right_quad = (_s(p_front), _s(p_right), _s(p_right_bot), _s(p_front_bot))
    elif direction == "left":
        # High at back-left (top..left), low at front-right (right_bot..front_bot)
        slope_quad = (_s(p_top), _s(p_right_bot), _s(p_front_bot), _s(p_left))
        high_edge = (_s(p_top), _s(p_left))
        left_tri = (_s(p_left), _s(p_front_bot), _s(p_left_bot))
        right_quad = None
    elif direction == "front":
        # Low at back-right (top_bot..right_bot), high at front-left (left..front)
        slope_quad = (_s(p_top_bot), _s(p_right_bot), _s(p_front), _s(p_left))
        high_edge = (_s(p_left), _s(p_front))
        left_tri = (_s(p_left), _s(p_front), _s(p_front_bot), _s(p_left_bot))
        right_quad = (_s(p_front), _s(p_right_bot), _s(p_front_bot))
    elif direction == "back":
        # High at back-right (top..right), low at front-left (left_bot..front_bot)
        slope_quad = (_s(p_top), _s(p_right), _s(p_front_bot), _s(p_left_bot))
        high_edge = (_s(p_top), _s(p_right))
        left_tri = None
        right_quad = (_s(p_front_bot), _s(p_right), _s(p_right_bot))
    else:
        msg = f"Unsupported iso_ramp direction: {direction!r}"
        raise ValueError(msg)

    if ih > 0:
        if left_tri is not None:
            with maps.normal_scope(NORMAL_ISO_LEFT) if maps is not None else nullcontext():
                target.polygon(left_tri, left, fill=True)
        if right_quad is not None:
            with maps.normal_scope(NORMAL_ISO_RIGHT) if maps is not None else nullcontext():
                target.polygon(right_quad, right, fill=True)

    slope_n = maps.normal_scope(NORMAL_ISO_TOP) if maps is not None else nullcontext()
    slope_h = maps.height_scope(float(ih) * 0.5) if maps is not None else nullcontext()
    with slope_n, slope_h:
        target.polygon(slope_quad, slope, fill=True)
        if highlight is not None:
            target.line(
                high_edge[0][0],
                high_edge[0][1],
                high_edge[1][0],
                high_edge[1][1],
                highlight,
            )

    if outline is not None:
        out_n = maps.normal_scope(NORMAL_FLAT) if maps is not None else nullcontext()
        out_h = maps.height_scope(0.0) if maps is not None else nullcontext()
        with out_n, out_h:
            target.auto_outline(outline)
        surface.blit_layer(target, ox, oy)
