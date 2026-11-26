"""Spatial room geometry and 2:1 isometric room shell prefabs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.plane import Point2D
from pixelforge.core.prefabs.atmosphere import PlaneRegion
from pixelforge.core.types import LightingAngle

Canvas = Asset | Layer
FloorPatternMode = Literal["planks", "tiles", "grid"]
FloorZoneMode = Literal["planks", "tiles", "grid", "carpet", "solid"]
WallMoldingStyle = Literal["crown", "chair_rail", "wainscot", "baseboard"]
DoorwayStyle = Literal["rect", "arch"]
WallSide = Literal["left", "right"]


def clamp_unit(value: float) -> float:
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
        cu0 = clamp_unit(u0)
        cv0 = clamp_unit(v0)
        cu1 = clamp_unit(u1)
        cv1 = clamp_unit(v1)
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
        cu = clamp_unit(u)
        cv = clamp_unit(v)
        cat = clamp_unit(at)
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
        cu0 = clamp_unit(u0)
        cv0 = clamp_unit(v0)
        cu1 = clamp_unit(u1)
        cv1 = clamp_unit(v1)
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
        cu0 = clamp_unit(u0)
        cv0 = clamp_unit(v0)
        cu1 = clamp_unit(u1)
        cv1 = clamp_unit(v1)
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
        cu0 = clamp_unit(u0)
        cu1 = clamp_unit(u1)
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
                self.floor_point(far_u, clamp_unit(vb + skew)),
                self.floor_point(far_u, clamp_unit(va + skew)),
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
            self.floor_point(clamp_unit(span_b + skew), far_v),
            self.floor_point(clamp_unit(span_a + skew), far_v),
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
        """Return top-center `(x, y)` to place an `iso_box`/`iso_desk` flush against `wall`."""
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
        t = clamp_unit(along)

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
