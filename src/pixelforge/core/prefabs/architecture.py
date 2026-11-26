"""Architectural 2:1 isometric prefab helpers (rooms, floors, windows, vents)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.plane import Point2D
from pixelforge.core.prefabs.atmosphere import (
    ClippedPane,
    PlaneRegion,
    RectRegion,
    clipped_pane,
)
from pixelforge.core.surface import (
    DitherPattern,
    IndexedSurface,
    compute_dither_thresholds,
)
from pixelforge.core.types import LightingAngle

Canvas = Asset | Layer
FloorPatternMode = Literal["planks", "tiles", "grid"]
FloorZoneMode = Literal["planks", "tiles", "grid", "carpet", "solid"]
WallMoldingStyle = Literal["crown", "chair_rail", "wainscot", "baseboard"]
DoorwayStyle = Literal["rect", "arch"]
WallSide = Literal["left", "right"]


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class IsoRoomGeometry:
    """Spatial coordinates and projection helpers derived from `iso_room_shell` bounds."""

    cx: int
    cy: int
    hw: int
    hh: int
    wall_h: int
    lighting_angle: LightingAngle = "top-left"
    u_scale: float = 1.0
    v_scale: float = 1.0

    @property
    def apex_y(self) -> int:
        """Y coordinate of the back-center floor corner."""
        return self.cy - self.hh

    @property
    def left_x(self) -> int:
        """X coordinate of the leftmost floor corner."""
        return self.cx - self.hw

    @property
    def right_x(self) -> int:
        """X coordinate of the rightmost floor corner."""
        return self.cx + self.hw

    def _floor_point_f(self, u: float, v: float) -> tuple[float, float]:
        du = (float(u) - 0.5) * self.u_scale
        dv = (float(v) - 0.5) * self.v_scale
        px = self.cx + (du - dv) * self.hw
        py = self.cy + (du + dv) * self.hh
        return (px, py)

    def floor_point(self, u: float, v: float) -> tuple[int, int]:
        """Project normalized `(u, v)` floor coords (`(0,0)`=apex, `(1,0)`=right, `(0,1)`=left)."""
        px, py = self._floor_point_f(u, v)
        return (round(px), round(py))

    def floor_plane(
        self,
        u0: float = 0.0,
        v0: float = 0.0,
        u1: float = 1.0,
        v1: float = 1.0,
    ) -> PlaneRegion:
        """Return `(p0, p1, p2)` for a clamped `(u0..u1, v0..v1)` floor sub-region."""
        cu0 = _clamp_unit(u0)
        cv0 = _clamp_unit(v0)
        cu1 = _clamp_unit(u1)
        cv1 = _clamp_unit(v1)
        if cu1 <= cu0 or cv1 <= cv0:
            msg = (
                f"Invalid floor sub-region ({u0}, {v0}, {u1}, {v1}): "
                "requires 0 <= u0 < u1 <= 1 and 0 <= v0 < v1 <= 1"
            )
            raise ValueError(msg)
        return (
            self._floor_point_f(cu0, cv0),
            self._floor_point_f(cu1, cv0),
            self._floor_point_f(cu0, cv1),
        )

    def _wall_point(
        self,
        wall: WallSide,
        u: float,
        v: float,
        *,
        at: float = 0.0,
        height: int | None = None,
    ) -> tuple[float, float]:
        cu = _clamp_unit(u)
        cv = _clamp_unit(v)
        cat = _clamp_unit(at)
        eff_h = self.wall_h if height is None else max(1, int(height))
        if wall == "left":
            p_start = self._floor_point_f(cat, 1.0)
            p_end = self._floor_point_f(cat, 0.0)
        else:
            p_start = self._floor_point_f(0.0, cat)
            p_end = self._floor_point_f(1.0, cat)
        bx = p_start[0] + cu * (p_end[0] - p_start[0])
        by = p_start[1] + cu * (p_end[1] - p_start[1])
        return (bx, (by - eff_h) + cv * eff_h)

    def _wall_plane(
        self,
        wall: WallSide,
        u0: float,
        v0: float,
        u1: float,
        v1: float,
        *,
        at: float = 0.0,
        height: int | None = None,
    ) -> PlaneRegion:
        cu0 = _clamp_unit(u0)
        cv0 = _clamp_unit(v0)
        cu1 = _clamp_unit(u1)
        cv1 = _clamp_unit(v1)
        if cu1 <= cu0 or cv1 <= cv0:
            msg = (
                f"Invalid {wall} wall sub-region ({u0}, {v0}, {u1}, {v1}): "
                "requires 0 <= u0 < u1 <= 1 and 0 <= v0 < v1 <= 1"
            )
            raise ValueError(msg)
        return (
            self._wall_point(wall, cu0, cv0, at=at, height=height),
            self._wall_point(wall, cu1, cv0, at=at, height=height),
            self._wall_point(wall, cu0, cv1, at=at, height=height),
        )

    def left_wall_plane(
        self,
        u0: float = 0.0,
        v0: float = 0.0,
        u1: float = 1.0,
        v1: float = 1.0,
    ) -> PlaneRegion:
        """Return `(p0, p1, p2)` for a clamped `(u0..u1, v0..v1)` region on the left back wall."""
        return self._wall_plane("left", u0, v0, u1, v1)

    def right_wall_plane(
        self,
        u0: float = 0.0,
        v0: float = 0.0,
        u1: float = 1.0,
        v1: float = 1.0,
    ) -> PlaneRegion:
        """Return `(p0, p1, p2)` for a clamped `(u0..u1, v0..v1)` region on the right back wall."""
        return self._wall_plane("right", u0, v0, u1, v1)

    def partition_plane(
        self,
        wall: WallSide,
        at: float,
        u0: float = 0.0,
        v0: float = 0.0,
        u1: float = 1.0,
        v1: float = 1.0,
        *,
        height: int | None = None,
    ) -> PlaneRegion:
        """Return `(p0, p1, p2)` for an interior dividing wall parallel to `wall` at `at`."""
        if wall not in ("left", "right"):
            msg = f"Unsupported wall side: {wall!r}"
            raise ValueError(msg)
        return self._wall_plane(wall, u0, v0, u1, v1, at=at, height=height)

    def subroom(
        self,
        u0: float,
        v0: float,
        u1: float,
        v1: float,
        *,
        wall_h: int | None = None,
    ) -> IsoRoomGeometry:
        """Return a derived `IsoRoomGeometry` for the `(u0..u1, v0..v1)` floor sub-region."""
        cu0 = _clamp_unit(u0)
        cv0 = _clamp_unit(v0)
        cu1 = _clamp_unit(u1)
        cv1 = _clamp_unit(v1)
        if cu1 <= cu0 or cv1 <= cv0:
            msg = (
                f"Invalid subroom bounds ({u0}, {v0}, {u1}, {v1}): "
                "requires 0 <= u0 < u1 <= 1 and 0 <= v0 < v1 <= 1"
            )
            raise ValueError(msg)

        u_span = (cu1 - cu0) * self.u_scale
        v_span = (cv1 - cv0) * self.v_scale
        avg_span = 0.5 * (u_span + v_span)
        sub_hw = max(1, round(self.hw * avg_span))
        sub_hh = max(1, round(self.hh * avg_span))
        sub_cx, sub_cy = self.floor_point(0.5 * (cu0 + cu1), 0.5 * (cv0 + cv1))
        # INVARIANT: Scale (u_scale, v_scale) against sub_hw so rectangular subrooms
        # (e.g. a 0.5x1.0 two-room split) preserve exact parent floor/wall coordinates.
        next_u_scale = (self.hw * u_span) / float(sub_hw)
        next_v_scale = (self.hw * v_span) / float(sub_hw)
        return IsoRoomGeometry(
            cx=sub_cx,
            cy=sub_cy,
            hw=sub_hw,
            hh=sub_hh,
            wall_h=self.wall_h if wall_h is None else max(1, int(wall_h)),
            lighting_angle=self.lighting_angle,
            u_scale=next_u_scale,
            v_scale=next_v_scale,
        )

    def window_spill_quad(
        self,
        u0: float,
        u1: float,
        *,
        wall: WallSide = "left",
        depth: float = 0.35,
        inset: float = 0.025,
    ) -> tuple[Point2D, Point2D, Point2D, Point2D]:
        """Return a 4-vertex floor light-spill quad aligned to `wall` and `lighting_angle`."""
        cu0 = _clamp_unit(u0)
        cu1 = _clamp_unit(u1)
        if cu1 <= cu0:
            msg = f"window_spill_quad requires u0 < u1, got ({u0}, {u1})"
            raise ValueError(msg)
        pad = min(max(0.0, float(inset)), (cu1 - cu0) * 0.4)
        span_a = cu0 + pad
        span_b = cu1 - pad
        d = max(0.05, min(0.95, float(depth)))

        if wall == "left":
            va = 1.0 - span_a
            vb = 1.0 - span_b
            skew = 0.0
            if self.lighting_angle == "top-right":
                skew = 0.18 * d
            elif self.lighting_angle == "top":
                skew = 0.08 * d
            near_u = 0.025
            far_u = min(0.98, near_u + d)
            return (
                self.floor_point(near_u, va),
                self.floor_point(near_u, vb),
                self.floor_point(far_u, _clamp_unit(vb + skew)),
                self.floor_point(far_u, _clamp_unit(va + skew)),
            )

        skew = 0.0
        if self.lighting_angle == "top-left":
            skew = 0.18 * d
        elif self.lighting_angle == "top":
            skew = 0.08 * d
        near_v = 0.025
        far_v = min(0.98, near_v + d)
        return (
            self.floor_point(span_a, near_v),
            self.floor_point(span_b, near_v),
            self.floor_point(_clamp_unit(span_b + skew), far_v),
            self.floor_point(_clamp_unit(span_a + skew), far_v),
        )

    def wall_box_center(
        self,
        wall: WallSide,
        w: int,
        d: int,
        h: int = 0,
        *,
        along: float = 0.5,
        margin: int = 2,
        corner_margin: int = 2,
    ) -> tuple[int, int]:
        """Return top-center `(x, y)` to place an `iso_box`/`iso_desk` flush against `wall`.

        Args:
            wall: Target back wall (`"left"` or `"right"`).
            w: Isometric span along `+u` (parallel to the right back wall).
            d: Isometric span along `+v` (parallel to the left back wall).
            h: Vertical elevation above the floor (`leg_h + top_h` for `iso_desk`,
                `h` for `iso_rack`/`iso_shelf`/`iso_drawer_unit`, or `0` for floor center).
            along: Clamped `[0.0, 1.0]` position along the wall from the back-center corner
                (`0.0`) toward the outer room corner (`1.0`).
            margin: Clearance in iso-depth pixels from the wall baseboard (`>= 0`).
            corner_margin: Clearance in pixels along the wall from room corners (`>= 0`).
        """
        if wall not in ("left", "right"):
            msg = f"Unsupported wall side: {wall!r}"
            raise ValueError(msg)

        iw = max(1, int(w))
        id_ = max(1, int(d))
        ih = max(0, int(h))
        m = max(0, int(margin))
        cm = max(0, int(corner_margin))
        hw_u = max(1.0, self.hw * self.u_scale)
        hw_v = max(1.0, self.hw * self.v_scale)
        t = _clamp_unit(along)

        # INVARIANT: In 2:1 iso, `u` moves (+1, +0.5) along the right wall and `v` moves
        # (-1, +0.5) along the left wall, so offsetting `margin` along the perpendicular floor
        # axis yields a `margin` px vertical gap from the baseboard line without trim overlap.
        if wall == "right":
            cm_eff = min(cm, max(0, (round(hw_u) - iw) // 2))
            travel = max(0.0, hw_u - iw - 2 * cm_eff)
            u_start = cm_eff + t * travel
            u_center = u_start + iw * 0.5
            v_center = m + id_ * 0.5
        else:
            cm_eff = min(cm, max(0, (round(hw_v) - id_) // 2))
            travel = max(0.0, hw_v - id_ - 2 * cm_eff)
            v_start = cm_eff + t * travel
            u_center = m + iw * 0.5
            v_center = v_start + id_ * 0.5

        fx, fy = self.floor_point(u_center / hw_u, v_center / hw_v)
        return (fx, fy - ih)


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
    lighting_angle: LightingAngle | None = None,
) -> IsoRoomGeometry:
    """Draw a 2:1 isometric room shell and return its `IsoRoomGeometry` spatial context."""
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

    resolved_lighting: LightingAngle = (
        lighting_angle
        if lighting_angle is not None
        else (target.style.lighting_angle if isinstance(target, Asset) else "top-left")
    )
    return IsoRoomGeometry(
        cx=icx,
        cy=icy,
        hw=ihw,
        hh=ihh,
        wall_h=iwall_h,
        lighting_angle=resolved_lighting,
    )


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


def iso_door(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    frame: int,
    panel: int,
    recess: int | None = None,
    handle: int | None = None,
    outline: int | None = None,
    window: int | None = None,
    threshold: int | None = None,
) -> None:
    """Draw a skewed isometric door onto a `(p0, p1, p2)` wall plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as door:
        door.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        door.rect(0.10, 0.06, 0.80, 0.94, fill=panel)
        if window is not None:
            door.rect(0.24, 0.14, 0.52, 0.26, fill=window, outline=recess)
        elif recess is not None:
            door.rect(0.22, 0.14, 0.56, 0.30, fill=recess)
        if recess is not None:
            door.rect(0.22, 0.54, 0.56, 0.34, fill=recess)
        if handle is not None:
            door.dot(0.78, 0.52, handle)
        if threshold is not None:
            door.rect(-0.04, 0.96, 1.08, 0.06, fill=threshold)


def front_door(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int | float,
    h: int | float,
    *,
    frame: int,
    panel: int,
    recess: int | None = None,
    handle: int | None = None,
    outline: int | None = None,
    window: int | None = None,
    threshold: int | None = None,
    frame_thickness: int = 2,
) -> None:
    """Draw a `front-2.5d` rectangular door with frame, optional vision glass, and handle."""
    ix = round(x)
    iy = round(y)
    iw = max(5, int(w))
    ih = max(8, int(h))
    t = max(1, min(int(frame_thickness), (iw - 2) // 2, (ih - 2) // 2))

    target.rect(ix, iy, iw, ih, frame, fill=True)
    if outline is not None:
        target.rect(ix, iy, iw, ih, outline, fill=False)

    px, py = ix + t, iy + t
    pw, ph = max(2, iw - 2 * t), max(4, ih - t)
    target.rect(px, py, pw, ph, panel, fill=True)

    inset_x = max(1, pw // 5)
    inner_w = max(1, pw - 2 * inset_x)
    if window is not None:
        win_h = max(2, ph // 4)
        target.rect(px + inset_x, py + max(2, ph // 8), inner_w, win_h, window, fill=True)
        if recess is not None:
            target.rect(px + inset_x, py + max(2, ph // 8), inner_w, win_h, recess, fill=False)
    elif recess is not None:
        target.rect(px + inset_x, py + max(2, ph // 8), inner_w, max(2, ph // 4), recess, fill=True)

    if recess is not None:
        target.rect(
            px + inset_x,
            py + max(4, (ph * 55) // 100),
            inner_w,
            max(2, ph // 3),
            recess,
            fill=True,
        )
    if handle is not None:
        hx = px + max(1, pw - max(2, pw // 5))
        hy = py + ph // 2
        target.rect(hx, hy, 1, 2, handle, fill=True)
    if threshold is not None:
        target.rect(ix - 1, iy + ih - 1, iw + 2, 2, threshold, fill=True)


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


def window_blinds(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    slat: int,
    shadow: int | None = None,
    cord: int | None = None,
    slats: int = 5,
    open_ratio: float = 0.7,
) -> None:
    """Draw horizontal venetian blinds across a `(p0, p1, p2)` window glass plane."""
    ratio = _clamp_unit(open_ratio)
    if ratio <= 0.0:
        return
    count = max(1, int(slats))
    with target.plane(p0=p0, p1=p1, p2=p2) as blinds:
        step_v = ratio / count
        slat_h = max(0.03, step_v * 0.55)
        for idx in range(count):
            v = idx * step_v
            blinds.rect(0.0, v, 1.0, slat_h, fill=slat)
            if shadow is not None:
                blinds.line(0.0, min(1.0, v + slat_h), 1.0, min(1.0, v + slat_h), shadow)
        if cord is not None:
            blinds.line(0.84, 0.0, 0.84, min(1.0, ratio + 0.08), cord)


def window_curtains(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    fabric: int,
    fold: int | None = None,
    rod: int | None = None,
    outline: int | None = None,
    open_ratio: float = 0.35,
) -> None:
    """Draw parted left and right curtains onto a `(p0, p1, p2)` window plane."""
    ratio = _clamp_unit(open_ratio)
    panel_w = max(0.12, 0.48 * (1.0 - ratio * 0.72))
    with target.plane(p0=p0, p1=p1, p2=p2) as curtains:
        curtains.rect(0.0, 0.04, panel_w, 0.96, fill=fabric, outline=outline)
        curtains.rect(1.0 - panel_w, 0.04, panel_w, 0.96, fill=fabric, outline=outline)
        if fold is not None:
            curtains.line(panel_w * 0.45, 0.06, panel_w * 0.45, 0.98, fold)
            curtains.line(1.0 - panel_w * 0.45, 0.06, 1.0 - panel_w * 0.45, 0.98, fold)
        if rod is not None:
            curtains.rect(-0.04, 0.0, 1.08, 0.05, fill=rod)


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
    cu0 = _clamp_unit(u0)
    cv0 = _clamp_unit(v0)
    cu1 = _clamp_unit(u1)
    cv1 = _clamp_unit(v1)
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
    s0 = _clamp_unit(span[0])
    s1 = _clamp_unit(span[1])
    if s1 <= s0:
        msg = f"Invalid threshold span {span!r}: requires 0 <= s0 < s1 <= 1"
        raise ValueError(msg)

    half_w = max(0.005, min(0.25, float(width) * 0.5))
    if wall == "left":
        u0, u1 = _clamp_unit(at - half_w), _clamp_unit(at + half_w)
        v0, v1 = s0, s1
    else:
        u0, u1 = s0, s1
        v0, v1 = _clamp_unit(at - half_w), _clamp_unit(at + half_w)

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
    cu0 = _clamp_unit(u0)
    cu1 = _clamp_unit(u1)
    if cu1 <= cu0:
        msg = f"Invalid partition span ({u0}, {u1}): requires 0 <= u0 < u1 <= 1"
        raise ValueError(msg)

    eff_h = geom.wall_h if height is None else max(2, int(height))
    t = max(1, int(thickness))
    dx_b = -t if wall == "left" else t
    dy_b = -max(1, t // 2)
    side_col = side if side is not None else cap
    front_plane = geom.partition_plane(wall, at, cu0, 0.0, cu1, 1.0, height=eff_h)

    with target.plane(p0=front_plane[0], p1=front_plane[1], p2=front_plane[2]) as wp:
        c00 = wp.project(0.0, 0.0)
        c10 = wp.project(1.0, 0.0)
        c11 = wp.project(1.0, 1.0)
        c01 = wp.project(0.0, 1.0)

        if doorway is None:
            wp.rect(0.0, 0.0, 1.0, 1.0, fill=face)
        else:
            du0 = max(0.04, min(0.92, float(doorway[0])))
            du1 = max(du0 + 0.04, min(0.96, float(doorway[1])))
            dh = max(0.25, min(0.92, float(door_height)))
            lintel_v = 1.0 - dh
            wp.rect(0.0, 0.0, du0, 1.0, fill=face)
            wp.rect(du1, 0.0, 1.0 - du1, 1.0, fill=face)
            wp.rect(du0, 0.0, du1 - du0, lintel_v, fill=face)

    if doorway is not None and doorway_style == "arch":
        du0 = max(0.04, min(0.92, float(doorway[0])))
        du1 = max(du0 + 0.04, min(0.96, float(doorway[1])))
        dh = max(0.25, min(0.92, float(door_height)))
        lintel_v = 1.0 - dh
        _draw_arch_spandrels(target, front_plane, du0, du1, lintel_v, min(0.18, dh * 0.3), face)

    # Top cap and visible end-face thickness extruded backward along the perpendicular iso axis.
    b00 = _offset_pt(c00, dx_b, dy_b)
    b10 = _offset_pt(c10, dx_b, dy_b)
    target.polygon((c00, c10, b10, b00), cap)
    if wall == "left":
        b01 = _offset_pt(c01, dx_b, dy_b)
        target.polygon((c00, b00, b01, c01), side_col)
    else:
        b11 = _offset_pt(c11, dx_b, dy_b)
        target.polygon((c10, b10, b11, c11), side_col)

    if doorway is not None:
        du0 = max(0.04, min(0.92, float(doorway[0])))
        du1 = max(du0 + 0.04, min(0.96, float(doorway[1])))
        dh = max(0.25, min(0.92, float(door_height)))
        lintel_v = 1.0 - dh
        jamb_u = du1 if wall == "left" else du0
        with target.plane(p0=front_plane[0], p1=front_plane[1], p2=front_plane[2]) as wp:
            jt = wp.project(jamb_u, lintel_v)
            jb = wp.project(jamb_u, 1.0)
        target.polygon((jt, _offset_pt(jt, dx_b, dy_b), _offset_pt(jb, dx_b, dy_b), jb), side_col)

    if baseboard is not None:
        bb_top, bb_bot = baseboard
        with target.plane(p0=front_plane[0], p1=front_plane[1], p2=front_plane[2]) as wp:
            if doorway is None:
                wp.line(0.0, 0.96, 1.0, 0.96, bb_top)
                wp.line(0.0, 1.0, 1.0, 1.0, bb_bot)
            else:
                du0 = max(0.04, min(0.92, float(doorway[0])))
                du1 = max(du0 + 0.04, min(0.96, float(doorway[1])))
                wp.line(0.0, 0.96, du0, 0.96, bb_top)
                wp.line(0.0, 1.0, du0, 1.0, bb_bot)
                wp.line(du1, 0.96, 1.0, 0.96, bb_top)
                wp.line(du1, 1.0, 1.0, 1.0, bb_bot)

    if outline is not None:
        target.line(b00[0], b00[1], b10[0], b10[1], outline)
        target.line(c00[0], c00[1], c10[0], c10[1], outline)
        target.line(c00[0], c00[1], b00[0], b00[1], outline)
        target.line(c10[0], c10[1], b10[0], b10[1], outline)
        target.line(c00[0], c00[1], c01[0], c01[1], outline)
        target.line(c10[0], c10[1], c11[0], c11[1], outline)

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
    cu0 = _clamp_unit(u0)
    cu1 = _clamp_unit(u1)
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
