"""Deterministic pitched roof and exterior building facade prefabs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pixelforge.core.iso import IsoAnchor
from pixelforge.core.plane import Point2D
from pixelforge.core.prefabs.architecture.openings import (
    front_door,
    front_window,
    iso_door,
    iso_window,
)
from pixelforge.core.prefabs.architecture.partitions import wall_molding
from pixelforge.core.prefabs.architecture.room import Canvas
from pixelforge.core.surface import IndexedSurface

RoofOrientation = Literal["iso-left", "iso-right", "front"]
FacadePerspective = Literal["iso-2:1", "front-2.5d"]
DoorSide = Literal["left", "right", "center"]


@dataclass(frozen=True)
class BuildingFacadeAnchors:
    """Semantic anchors emitted or computed for `building_facade`."""

    foot: tuple[int, int]
    door: tuple[int, int]
    roof_peak: tuple[int, int]


def _iso_top_origin(
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    anchor: IsoAnchor,
) -> tuple[int, int]:
    ix = round(x)
    iy = round(y)
    if anchor == "top":
        return (ix, iy)
    if anchor == "bottom":
        return (ix - w + d, iy - (w // 2) - (d // 2))
    if anchor == "center":
        return (ix - (w - d) // 2, iy - (w // 2 + d // 2) // 2)
    msg = f"Unsupported pitched_roof anchor: {anchor!r}"
    raise ValueError(msg)


def _draw_iso_roof(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    pitch_h: int,
    *,
    lit_slope: int,
    shade_slope: int,
    ridge: int | None,
    gable: int | None,
    trim: int | None,
    outline: int | None,
    overhang: int,
    shingle_step: int,
    orientation: Literal["iso-left", "iso-right"],
    anchor: IsoAnchor,
) -> tuple[int, int]:
    tx, ty = _iso_top_origin(x, y, w, d, anchor)
    ov = max(0, int(overhang))
    ew = max(4, int(w) + ov * 2)
    ed = max(4, int(d) + ov * 2)
    etx = tx
    ety = ty - ov

    dy_r = ew // 2
    dy_l = ed // 2
    p_top = (etx, ety)
    p_right = (etx + ew, ety + dy_r)
    p_left = (etx - ed, ety + dy_l)
    p_front = (etx + ew - ed, ety + dy_r + dy_l)

    if orientation == "iso-left":
        r0 = ((p_top[0] + p_left[0]) // 2, (p_top[1] + p_left[1]) // 2 - pitch_h)
        r1 = ((p_right[0] + p_front[0]) // 2, (p_right[1] + p_front[1]) // 2 - pitch_h)
        front_quad = (p_left, p_front, r1, r0)
        back_quad = (p_top, p_right, r1, r0)
        gable_tri = (p_front, p_right, r1)
        eave_a, eave_b = p_left, p_front
    else:
        r0 = ((p_top[0] + p_right[0]) // 2, (p_top[1] + p_right[1]) // 2 - pitch_h)
        r1 = ((p_left[0] + p_front[0]) // 2, (p_left[1] + p_front[1]) // 2 - pitch_h)
        front_quad = (p_front, p_right, r0, r1)
        back_quad = (p_top, p_left, r1, r0)
        gable_tri = (p_left, p_front, r1)
        eave_a, eave_b = p_front, p_right

    pts = (p_top, p_right, p_left, p_front, r0, r1)
    min_x = min(pt[0] for pt in pts) - 2
    max_x = max(pt[0] for pt in pts) + 2
    min_y = min(pt[1] for pt in pts) - 2
    max_y = max(pt[1] for pt in pts) + 2
    surf = IndexedSurface(max_x - min_x + 1, max_y - min_y + 1, track_maps=target.surface.has_maps)

    def _s(pt: tuple[int, int]) -> tuple[int, int]:
        return (pt[0] - min_x, pt[1] - min_y)

    surf.quad(_s(back_quad[0]), _s(back_quad[1]), _s(back_quad[2]), _s(back_quad[3]), shade_slope)
    surf.polygon((_s(gable_tri[0]), _s(gable_tri[1]), _s(gable_tri[2])), gable or shade_slope)
    surf.quad(_s(front_quad[0]), _s(front_quad[1]), _s(front_quad[2]), _s(front_quad[3]), lit_slope)

    if shingle_step > 0:
        step = max(2, int(shingle_step))
        for sy in range(step, pitch_h, step):
            t = sy / float(max(1, pitch_h))
            lx0 = round(front_quad[0][0] + t * (front_quad[3][0] - front_quad[0][0]))
            ly0 = round(front_quad[0][1] + t * (front_quad[3][1] - front_quad[0][1]))
            lx1 = round(front_quad[1][0] + t * (front_quad[2][0] - front_quad[1][0]))
            ly1 = round(front_quad[1][1] + t * (front_quad[2][1] - front_quad[1][1]))
            surf.line(lx0 - min_x, ly0 - min_y, lx1 - min_x, ly1 - min_y, shade_slope)

    if trim is not None:
        surf.line(eave_a[0] - min_x, eave_a[1] - min_y, eave_b[0] - min_x, eave_b[1] - min_y, trim)
    if ridge is not None:
        surf.line(r0[0] - min_x, r0[1] - min_y, r1[0] - min_x, r1[1] - min_y, ridge)
    if outline is not None:
        surf.auto_outline(outline)
    target.surface.blit_layer(surf, min_x, min_y)
    return ((r0[0] + r1[0]) // 2, min(r0[1], r1[1]))


def _draw_front_roof(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int,
    pitch_h: int,
    *,
    lit_slope: int,
    shade_slope: int,
    ridge: int | None,
    trim: int | None,
    outline: int | None,
    overhang: int,
    shingle_step: int,
) -> tuple[int, int]:
    ix = round(x)
    iy = round(y)
    ov = max(0, int(overhang))
    left_x = ix - ov
    right_x = ix + max(4, int(w)) + ov
    peak_x = (left_x + right_x) // 2
    peak_y = iy - max(3, int(pitch_h))

    min_x = left_x - 2
    min_y = peak_y - 2
    surf_w = (right_x - left_x) + 5
    surf_h = (iy - peak_y) + 5
    surf = IndexedSurface(surf_w, surf_h, track_maps=target.surface.has_maps)

    def _s(px: int, py: int) -> tuple[int, int]:
        return (px - min_x, py - min_y)

    surf.polygon((_s(left_x, iy), _s(peak_x, iy), _s(peak_x, peak_y)), lit_slope)
    surf.polygon((_s(peak_x, iy), _s(right_x, iy), _s(peak_x, peak_y)), shade_slope)

    if shingle_step > 0:
        step = max(2, int(shingle_step))
        for sy in range(peak_y + step, iy, step):
            t = (sy - peak_y) / float(max(1, iy - peak_y))
            lx = round(peak_x + t * (left_x - peak_x))
            surf.line(lx - min_x, sy - min_y, peak_x - min_x, sy - min_y, shade_slope)

    if trim is not None:
        surf.line(left_x - min_x, iy - min_y, right_x - min_x, iy - min_y, trim)
    if ridge is not None:
        surf.line(peak_x - min_x, peak_y - min_y, peak_x - min_x, iy - min_y, ridge)
    if outline is not None:
        surf.auto_outline(outline)
    target.surface.blit_layer(surf, min_x, min_y)
    return (peak_x, peak_y)


def pitched_roof(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    pitch_h: int,
    *,
    lit_slope: int,
    shade_slope: int,
    ridge: int | None = None,
    gable: int | None = None,
    trim: int | None = None,
    outline: int | None = None,
    overhang: int = 2,
    shingle_step: int = 0,
    orientation: RoofOrientation = "iso-left",
    anchor: IsoAnchor = "top",
) -> tuple[int, int]:
    """Draw a pitched roof (`iso-left`, `iso-right`, or `front`) with optional eave overhang."""
    ph = max(3, int(pitch_h))
    if orientation == "front":
        return _draw_front_roof(
            target,
            x,
            y,
            w,
            ph,
            lit_slope=lit_slope,
            shade_slope=shade_slope,
            ridge=ridge,
            trim=trim,
            outline=outline,
            overhang=overhang,
            shingle_step=shingle_step,
        )
    return _draw_iso_roof(
        target,
        x,
        y,
        w,
        d,
        ph,
        lit_slope=lit_slope,
        shade_slope=shade_slope,
        ridge=ridge,
        gable=gable,
        trim=trim,
        outline=outline,
        overhang=overhang,
        shingle_step=shingle_step,
        orientation=orientation,
        anchor=anchor,
    )


def _lerp_pt(a: Point2D, b: Point2D, t: float) -> Point2D:
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def _wall_subplane(
    p_start: Point2D,
    p_end: Point2D,
    wall_h: int,
    u0: float,
    v0: float,
    u1: float,
    v1: float,
) -> tuple[Point2D, Point2D, Point2D]:
    b0 = _lerp_pt(p_start, p_end, u0)
    b1 = _lerp_pt(p_start, p_end, u1)
    return (
        (b0[0], b0[1] + v0 * wall_h),
        (b1[0], b1[1] + v0 * wall_h),
        (b0[0], b0[1] + v1 * wall_h),
    )


def _draw_iso_facade(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    h: int,
    *,
    wall: int,
    wall_shade: int,
    roof_lit: int,
    roof_shade: int,
    door_frame: int,
    door_fill: int,
    window_frame: int,
    window_sky: int,
    trim: int | None,
    outline: int | None,
    roof_h: int,
    overhang: int,
    windows: int,
    door_side: DoorSide,
    roof_orientation: RoofOrientation,
) -> BuildingFacadeAnchors:
    tx = round(x)
    ty = round(y)
    target.iso_box(tx, ty, w, d, h, top=wall, left=wall, right=wall_shade, outline=outline)

    dy_r = w // 2
    dy_l = d // 2
    p_left = (tx - d, ty + dy_l)
    p_front = (tx + w - d, ty + dy_r + dy_l)
    p_right = (tx + w, ty + dy_r)

    door_on_right = door_side == "right"
    door_wall = (p_front, p_right) if door_on_right else (p_left, p_front)
    win_wall = (p_left, p_front) if door_on_right else (p_front, p_right)

    du0, du1 = (0.34, 0.66) if door_side == "center" else (0.18, 0.50)
    dp0, dp1, dp2 = _wall_subplane(door_wall[0], door_wall[1], h, du0, 0.28, du1, 1.0)
    iso_door(
        target,
        dp0,
        dp1,
        dp2,
        frame=door_frame,
        panel=door_fill,
        outline=outline,
        handle=trim,
    )

    win_count = max(0, min(3, int(windows)))
    if win_count > 0:
        span = 0.72 / float(win_count)
        for idx in range(win_count):
            wu0 = 0.14 + idx * span
            wu1 = wu0 + span * 0.72
            wp0, wp1, wp2 = _wall_subplane(win_wall[0], win_wall[1], h, wu0, 0.26, wu1, 0.68)
            iso_window(
                target,
                wp0,
                wp1,
                wp2,
                frame=window_frame,
                sky=window_sky,
                outline=outline,
                sill=trim,
            )

    eff_orient: Literal["iso-left", "iso-right"] = (
        "iso-right" if roof_orientation == "iso-right" else "iso-left"
    )
    peak = pitched_roof(
        target,
        tx,
        ty,
        w,
        d,
        roof_h,
        lit_slope=roof_lit,
        shade_slope=roof_shade,
        ridge=trim,
        gable=wall_shade,
        trim=trim,
        outline=outline,
        overhang=overhang,
        orientation=eff_orient,
    )
    foot = (p_front[0], p_front[1] + h)
    door_pt = (round((dp0[0] + dp1[0]) * 0.5), round(dp2[1]))
    return BuildingFacadeAnchors(foot=foot, door=door_pt, roof_peak=peak)


def _draw_front_facade(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int,
    h: int,
    *,
    wall: int,
    roof_lit: int,
    roof_shade: int,
    door_frame: int,
    door_fill: int,
    window_frame: int,
    window_sky: int,
    trim: int | None,
    outline: int | None,
    roof_h: int,
    overhang: int,
    windows: int,
    door_side: DoorSide,
) -> BuildingFacadeAnchors:
    ix = round(x)
    iy = round(y)
    iw = max(12, int(w))
    ih = max(12, int(h))

    target.rect(ix, iy, iw, ih, wall, fill=True)
    if outline is not None:
        target.rect(ix, iy, iw, ih, outline, fill=False)
    if trim is not None:
        wall_molding(
            target,
            (ix + 1, iy + ih - 3),
            (ix + iw - 1, iy + ih - 3),
            (ix + 1, iy + ih - 1),
            primary=trim,
            style="baseboard",
        )

    door_w = max(6, min(12, iw // 4))
    door_h = max(8, min(ih - 4, round(ih * 0.62)))
    if door_side == "center":
        door_x = ix + (iw - door_w) // 2
    elif door_side == "right":
        door_x = ix + iw - door_w - max(3, iw // 10)
    else:
        door_x = ix + max(3, iw // 10)
    door_y = iy + ih - door_h
    front_door(
        target,
        door_x,
        door_y,
        door_w,
        door_h,
        frame=door_frame,
        panel=door_fill,
        outline=outline,
        handle=trim,
    )

    win_count = max(0, min(3, int(windows)))
    if win_count > 0:
        win_w = max(5, min(10, iw // 5))
        win_h = max(5, min(10, ih // 3))
        win_y = iy + max(3, ih // 5)
        placed = 0
        slot_x = ix + max(3, iw // 10)
        step_x = max(win_w + 3, (iw - 6) // max(1, win_count + 1))
        while placed < win_count and slot_x + win_w <= ix + iw - 2:
            overlaps_door = not (slot_x + win_w <= door_x - 1 or slot_x >= door_x + door_w + 1)
            if not overlaps_door or win_y + win_h <= door_y - 1:
                front_window(
                    target,
                    slot_x,
                    win_y,
                    win_w,
                    win_h,
                    frame=window_frame,
                    sky=window_sky,
                    outline=outline,
                    sill=trim,
                )
                placed += 1
            slot_x += step_x

    peak = pitched_roof(
        target,
        ix,
        iy,
        iw,
        iw,
        roof_h,
        lit_slope=roof_lit,
        shade_slope=roof_shade,
        ridge=trim,
        trim=trim,
        outline=outline,
        overhang=overhang,
        orientation="front",
    )
    return BuildingFacadeAnchors(
        foot=(ix + iw // 2, iy + ih),
        door=(door_x + door_w // 2, iy + ih),
        roof_peak=peak,
    )


def building_facade(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int,
    h: int,
    *,
    wall: int,
    roof_lit: int,
    roof_shade: int,
    door_frame: int,
    door_fill: int,
    window_frame: int,
    window_sky: int,
    wall_shade: int | None = None,
    trim: int | None = None,
    outline: int | None = None,
    d: int | None = None,
    roof_h: int | None = None,
    overhang: int = 2,
    perspective: FacadePerspective = "iso-2:1",
    windows: int = 2,
    door_side: DoorSide = "left",
    roof_orientation: RoofOrientation = "iso-left",
    emit_anchor: bool = True,
) -> BuildingFacadeAnchors:
    """Draw a complete `iso-2:1` or `front-2.5d` building facade with pitched roof and openings."""
    iw = max(12, int(w))
    ih = max(12, int(h))
    id_ = max(12, int(d)) if d is not None else iw
    r_h = max(4, int(roof_h)) if roof_h is not None else max(6, min(iw, id_) // 2)
    shade = wall_shade if wall_shade is not None else wall

    if perspective == "front-2.5d":
        anchors = _draw_front_facade(
            target,
            x,
            y,
            iw,
            ih,
            wall=wall,
            roof_lit=roof_lit,
            roof_shade=roof_shade,
            door_frame=door_frame,
            door_fill=door_fill,
            window_frame=window_frame,
            window_sky=window_sky,
            trim=trim,
            outline=outline,
            roof_h=r_h,
            overhang=overhang,
            windows=windows,
            door_side=door_side,
        )
    else:
        anchors = _draw_iso_facade(
            target,
            x,
            y,
            iw,
            id_,
            ih,
            wall=wall,
            wall_shade=shade,
            roof_lit=roof_lit,
            roof_shade=roof_shade,
            door_frame=door_frame,
            door_fill=door_fill,
            window_frame=window_frame,
            window_sky=window_sky,
            trim=trim,
            outline=outline,
            roof_h=r_h,
            overhang=overhang,
            windows=windows,
            door_side=door_side,
            roof_orientation=roof_orientation,
        )

    if emit_anchor:
        target.anchor("foot", anchors.foot[0], anchors.foot[1], kind="ground")
    return anchors
