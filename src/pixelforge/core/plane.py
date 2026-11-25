"""Affine normalized `(u, v)` plane context manager for angled and isometric geometry."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Literal, Self

from pixelforge.core.surface import (
    DitherMask,
    DitherPattern,
    IndexedSurface,
    compute_dither_selection,
)
from pixelforge.core.types import TRANSPARENT_INDEX, AnchorPoint

Point2D = tuple[int | float, int | float]
GridMode = Literal["cells", "lines"]


class Plane:
    """Affine `(u, v)` coordinate plane bound to an `IndexedSurface` and anchor emitter."""

    _surface: IndexedSurface
    _p0: tuple[float, float]
    _u_vec: tuple[float, float]
    _v_vec: tuple[float, float]
    _emit_anchor: Callable[[str, int, int], AnchorPoint]

    def __init__(
        self,
        surface: IndexedSurface,
        p0: Point2D,
        p1: Point2D,
        p2: Point2D,
        emit_anchor: Callable[[str, int, int], AnchorPoint],
    ) -> None:
        self._surface = surface
        self._p0 = (float(p0[0]), float(p0[1]))
        self._u_vec = (float(p1[0]) - self._p0[0], float(p1[1]) - self._p0[1])
        self._v_vec = (float(p2[0]) - self._p0[0], float(p2[1]) - self._p0[1])
        self._emit_anchor = emit_anchor

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return None

    def project(self, u: float, v: float) -> tuple[int, int]:
        """Project normalized `(u, v)` coordinates onto integer surface `(x, y)`."""
        px = self._p0[0] + u * self._u_vec[0] + v * self._v_vec[0]
        py = self._p0[1] + u * self._u_vec[1] + v * self._v_vec[1]
        return (round(px), round(py))

    def _rect_corners(
        self,
        u: float,
        v: float,
        w: float,
        h: float,
    ) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]]:
        c00 = self.project(u, v)
        c10 = self.project(u + w, v)
        c11 = self.project(u + w, v + h)
        c01 = self.project(u, v + h)
        return (c00, c10, c11, c01)

    def extrude_y(
        self,
        u: float,
        v: float,
        w: float,
        h: float,
        depth: int,
        color: int,
        *,
        side_left: int | None = None,
        side_right: int | None = None,
    ) -> None:
        """Extrude the downward-facing edges of a `(u, v, w, h)` quad by `depth` pixels."""
        d = int(depth)
        if d <= 0:
            return
        corners = self._rect_corners(u, v, w, h)
        # Compute signed area so outward normals work regardless of plane handedness.
        area2 = 0
        for i in range(4):
            ax, ay = corners[i]
            bx, by = corners[(i + 1) % 4]
            area2 += (ax * by) - (bx * ay)
        cw_sign = 1 if area2 >= 0 else -1

        for i in range(4):
            ax, ay = corners[i]
            bx, by = corners[(i + 1) % 4]
            # INVARIANT: In screen coords (+X right, +Y down), CW winding has interior to
            # the right of edge (dx, dy), so the outward normal is (dy, -dx) * cw_sign.
            nx = (by - ay) * cw_sign
            ny = -(bx - ax) * cw_sign
            if ny <= 0:
                continue
            edge_color = color
            if nx < 0 and side_left is not None:
                edge_color = side_left
            elif nx > 0 and side_right is not None:
                edge_color = side_right
            self._surface.quad(
                (ax, ay),
                (bx, by),
                (bx, by + d),
                (ax, ay + d),
                edge_color,
            )

    def rect(
        self,
        u: float,
        v: float,
        w: float,
        h: float,
        fill: int | None = None,
        *,
        outline: int | None = None,
        bevel: tuple[int, int] | None = None,
        extrude_y: int = 0,
        side: int | None = None,
        side_left: int | None = None,
        side_right: int | None = None,
    ) -> None:
        """Draw a projected `(u, v, w, h)` quad with optional extrusion, bevel, and outline."""
        c00, c10, c11, c01 = self._rect_corners(u, v, w, h)

        if extrude_y > 0:
            base_side = side if side is not None else fill
            if base_side is not None:
                self.extrude_y(
                    u,
                    v,
                    w,
                    h,
                    extrude_y,
                    base_side,
                    side_left=side_left,
                    side_right=side_right,
                )

        if fill is not None:
            self._surface.quad(c00, c10, c11, c01, fill, fill=True)

        if bevel is not None:
            hi_color, lo_color = bevel
            self._surface.line(c01[0], c01[1], c11[0], c11[1], lo_color)
            self._surface.line(c10[0], c10[1], c11[0], c11[1], lo_color)
            self._surface.line(c00[0], c00[1], c10[0], c10[1], hi_color)
            self._surface.line(c00[0], c00[1], c01[0], c01[1], hi_color)

        if outline is not None:
            self._surface.quad(c00, c10, c11, c01, outline, fill=False)

    def grid(
        self,
        u: float,
        v: float,
        w: float,
        h: float,
        *,
        cols: int,
        rows: int,
        color: int,
        cell_fill: float = 0.65,
        mode: GridMode = "cells",
        bg: int | None = None,
    ) -> None:
        """Draw a projected `cols x rows` cell grid (default) or divider line grid."""
        if cols <= 0 or rows <= 0:
            return
        if bg is not None:
            self.rect(u, v, w, h, fill=bg)

        if mode == "lines":
            for c in range(cols + 1):
                uc = u + (c / cols) * w
                self.line(uc, v, uc, v + h, color)
            for r in range(rows + 1):
                vr = v + (r / rows) * h
                self.line(u, vr, u + w, vr, color)
            return

        if mode != "cells":
            msg = f"Unsupported grid mode: {mode!r}"
            raise ValueError(msg)

        ratio = max(0.1, min(1.0, float(cell_fill)))
        du = w / cols
        dv = h / rows
        for r in range(rows):
            v0 = v + r * dv
            v1 = v0 + dv * ratio
            for c in range(cols):
                u0 = u + c * du
                u1 = u0 + du * ratio
                c00, c10, c11, c01 = self._rect_corners(u0, v0, u1 - u0, v1 - v0)
                self._surface.quad(c00, c10, c11, c01, color, fill=True)

    def line(self, u0: float, v0: float, u1: float, v1: float, color: int) -> None:
        """Draw a projected Bresenham line between `(u0, v0)` and `(u1, v1)`."""
        x0, y0 = self.project(u0, v0)
        x1, y1 = self.project(u1, v1)
        self._surface.line(x0, y0, x1, y1, color)

    def dot(
        self,
        u: float,
        v: float,
        color: int,
        *,
        radius: int = 0,
        anchor: str | None = None,
    ) -> None:
        """Draw a projected 1px dot (or filled circle when `radius > 0`) and optional anchor."""
        px, py = self.project(u, v)
        if radius <= 0:
            self._surface.put(px, py, color)
        else:
            self._surface.circle(px, py, radius, color, fill=True)
        if anchor is not None:
            self._emit_anchor(anchor, px, py)

    def quad(
        self,
        uv0: tuple[float, float],
        uv1: tuple[float, float],
        uv2: tuple[float, float],
        uv3: tuple[float, float],
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw an arbitrary projected quadrilateral from four `(u, v)` vertices."""
        self._surface.quad(
            self.project(uv0[0], uv0[1]),
            self.project(uv1[0], uv1[1]),
            self.project(uv2[0], uv2[1]),
            self.project(uv3[0], uv3[1]),
            color,
            fill=fill,
        )

    def put(self, u: float, v: float, color: int) -> None:
        """Write a single pixel at projected `(u, v)`."""
        px, py = self.project(u, v)
        self._surface.put(px, py, color)

    def dither(
        self,
        u: float,
        v: float,
        w: float,
        h: float,
        color_a: int | None,
        color_b: int | None,
        *,
        pattern: DitherPattern = "bayer4",
        ratio: float = 0.5,
        mask: DitherMask = "opaque",
    ) -> None:
        """Apply ordered dithering clipped to the projected `(u, v, w, h)` quadrilateral."""
        corners = self._rect_corners(u, v, w, h)
        x0 = max(0, min(pt[0] for pt in corners))
        y0 = max(0, min(pt[1] for pt in corners))
        x1 = min(self._surface.width, max(pt[0] for pt in corners) + 1)
        y1 = min(self._surface.height, max(pt[1] for pt in corners) + 1)
        if x0 >= x1 or y0 >= y1:
            return

        quad_mask_surf = IndexedSurface(x1 - x0, y1 - y0)
        shifted = tuple((px - x0, py - y0) for px, py in corners)
        quad_mask_surf.polygon(shifted, 0, fill=True)
        in_quad = quad_mask_surf.data != TRANSPARENT_INDEX

        region = self._surface.data[y0:y1, x0:x1]
        active = in_quad & (region != TRANSPARENT_INDEX) if mask == "opaque" else in_quad
        select_b = compute_dither_selection(x0, y0, x1, y1, pattern=pattern, ratio=ratio)
        if color_b is not None:
            region[active & select_b] = color_b
        if color_a is not None:
            region[active & ~select_b] = color_a

    def anchor(self, name: str, u: float, v: float) -> AnchorPoint:
        """Register an `AnchorPoint` projected from normalized `(u, v)` coordinates."""
        px, py = self.project(u, v)
        return self._emit_anchor(name, px, py)
