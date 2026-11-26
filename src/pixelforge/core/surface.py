"""Deterministic numpy-backed indexed framebuffer and pixel art primitives."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.surface_maps import SurfaceMaps
from pixelforge.core.types import TRANSPARENT_INDEX

DitherPattern = Literal["bayer2", "bayer4", "checker"]
DitherMask = Literal["all", "opaque"]
MirrorSource = Literal["left", "right"]

_BAYER_2X2: Final[NDArray[np.float64]] = (np.array([[0, 2], [3, 1]], dtype=np.float64) + 0.5) / 4.0
_BAYER_4X4: Final[NDArray[np.float64]] = (
    np.array(
        [
            [0, 8, 2, 10],
            [12, 4, 14, 6],
            [3, 11, 1, 9],
            [15, 7, 13, 5],
        ],
        dtype=np.float64,
    )
    + 0.5
) / 16.0


def compute_dither_thresholds(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    pattern: DitherPattern = "bayer4",
) -> NDArray[np.float64]:
    """Return ordered dither thresholds in `[0, 1)` over `[x0, x1) x [y0, y1)`."""
    yy, xx = np.mgrid[y0:y1, x0:x1]
    if pattern == "bayer2":
        return np.asarray(_BAYER_2X2[yy & 1, xx & 1], dtype=np.float64)
    if pattern == "bayer4":
        return np.asarray(_BAYER_4X4[yy & 3, xx & 3], dtype=np.float64)
    if pattern == "checker":
        return np.where(((xx + yy) & 1) == 0, 0.25, 0.75)
    msg = f"Unsupported dither pattern: {pattern!r}"
    raise ValueError(msg)


def compute_dither_selection(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    pattern: DitherPattern = "bayer4",
    ratio: float = 0.5,
) -> NDArray[np.bool_]:
    """Compute a boolean mask selecting pixels for `color_b` over `[x0, x1) x [y0, y1)`."""
    if pattern == "checker":
        yy, xx = np.mgrid[y0:y1, x0:x1]
        if ratio <= 0.0:
            return np.zeros_like(xx, dtype=bool)
        if ratio >= 1.0:
            return np.ones_like(xx, dtype=bool)
        return np.asarray(((xx + yy) & 1) == 0, dtype=bool)
    thresholds = compute_dither_thresholds(x0, y0, x1, y1, pattern=pattern)
    return np.asarray(thresholds < ratio, dtype=bool)


def _normalize_index(color: int) -> int:
    idx = int(color)
    if idx < 0 or idx > TRANSPARENT_INDEX:
        msg = f"Palette index {color} out of range [0..{TRANSPARENT_INDEX}]"
        raise ValueError(msg)
    return idx


def _round_point(point: tuple[int | float, int | float]) -> tuple[int, int]:
    return (round(point[0]), round(point[1]))


class IndexedSurface:
    """Deterministic integer-grid indexed framebuffer backed by `numpy.ndarray(uint8)`."""

    width: int
    height: int
    data: NDArray[np.uint8]
    _maps: SurfaceMaps | None

    def __init__(
        self,
        width: int,
        height: int,
        initial_data: NDArray[np.uint8] | None = None,
        *,
        track_maps: bool = False,
        initial_maps: SurfaceMaps | None = None,
    ) -> None:
        w = int(width)
        h = int(height)
        if w <= 0 or h <= 0:
            msg = f"Surface dimensions must be positive, got {width}x{height}"
            raise ValueError(msg)

        self.width = w
        self.height = h
        if initial_data is not None:
            if initial_data.shape != (h, w):
                msg = f"Expected shape ({h}, {w}) for {w}x{h} surface, got {initial_data.shape}"
                raise ValueError(msg)
            self.data = np.array(initial_data, dtype=np.uint8, copy=True)
        else:
            self.data = np.full((h, w), TRANSPARENT_INDEX, dtype=np.uint8)

        if initial_maps is not None:
            self._maps = initial_maps.clone()
        elif track_maps:
            self._maps = SurfaceMaps(w, h)
        else:
            self._maps = None

    @property
    def maps(self) -> SurfaceMaps | None:
        """Optional companion normal and height maps when `track_maps=True`."""
        return self._maps

    @property
    def has_maps(self) -> bool:
        """Return True when normal/height map tracking is active on this surface."""
        return self._maps is not None

    def in_bounds(self, x: int | float, y: int | float) -> bool:
        """Return True if integer-truncated `(x, y)` lies inside `[0, width) x [0, height)`."""
        ix = int(x)
        iy = int(y)
        return 0 <= ix < self.width and 0 <= iy < self.height

    def get(self, x: int | float, y: int | float) -> int:
        """Read palette index at `(x, y)` or return `TRANSPARENT_INDEX` when out of bounds."""
        ix = int(x)
        iy = int(y)
        if ix < 0 or ix >= self.width or iy < 0 or iy >= self.height:
            return TRANSPARENT_INDEX
        return int(self.data[iy, ix])

    def put(self, x: int | float, y: int | float, color: int) -> None:
        """Write palette index at integer-truncated `(x, y)`, ignoring out-of-bounds coords."""
        # INVARIANT: Truncate to integer grid and clamp OOB silently to prevent mixels.
        c = _normalize_index(color)
        ix = int(x)
        iy = int(y)
        if ix < 0 or ix >= self.width or iy < 0 or iy >= self.height:
            return
        self.data[iy, ix] = c
        if self._maps is not None:
            self._maps.write_pixel(ix, iy, erase=(c == TRANSPARENT_INDEX))

    def erase(self, x: int | float, y: int | float) -> None:
        """Clear a single pixel to `TRANSPARENT_INDEX`."""
        self.put(x, y, TRANSPARENT_INDEX)

    def clear(self, color: int = TRANSPARENT_INDEX) -> None:
        """Fill the entire surface with `color` (defaults to transparent `255`)."""
        c = _normalize_index(color)
        self.data.fill(c)
        if self._maps is not None:
            self._maps.clear(erase=(c == TRANSPARENT_INDEX))

    def clone(self) -> IndexedSurface:
        """Return an independent deep copy of this surface."""
        return IndexedSurface(
            self.width,
            self.height,
            self.data,
            initial_maps=self._maps,
        )

    def _hspan(self, x0: int, x1: int, y: int, color: int) -> None:
        if y < 0 or y >= self.height:
            return
        start = max(0, x0)
        end = min(self.width - 1, x1)
        if start > end:
            return
        self.data[y, start : end + 1] = color
        if self._maps is not None:
            self._maps.write_span(start, end, y, erase=(color == TRANSPARENT_INDEX))

    def rect(
        self,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw a filled or 1px-stroked axis-aligned rectangle."""
        c = _normalize_index(color)
        ix = int(x)
        iy = int(y)
        iw = int(w)
        ih = int(h)
        if iw <= 0 or ih <= 0:
            return

        if fill:
            x0 = max(0, ix)
            y0 = max(0, iy)
            x1 = min(self.width, ix + iw)
            y1 = min(self.height, iy + ih)
            if x0 < x1 and y0 < y1:
                self.data[y0:y1, x0:x1] = c
                if self._maps is not None:
                    self._maps.write_rect(x0, y0, x1, y1, erase=(c == TRANSPARENT_INDEX))
            return

        x_end = ix + iw - 1
        y_end = iy + ih - 1
        self._hspan(ix, x_end, iy, c)
        if y_end != iy:
            self._hspan(ix, x_end, y_end, c)
        for py in range(iy + 1, y_end):
            self.put(ix, py, c)
            if x_end != ix:
                self.put(x_end, py, c)

    def rounded_rect(
        self,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        radius: int,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw a pixel-crisp rounded rectangle using integer corner radius."""
        c = _normalize_index(color)
        ix = int(x)
        iy = int(y)
        iw = int(w)
        ih = int(h)
        if iw <= 0 or ih <= 0:
            return

        r = max(0, min(int(radius), iw // 2, ih // 2))
        if r == 0:
            self.rect(ix, iy, iw, ih, c, fill=fill)
            return

        if fill:
            self._fill_rounded_rect(ix, iy, iw, ih, r, c)
        else:
            self._stroke_rounded_rect(ix, iy, iw, ih, r, c)

    def _fill_rounded_rect(self, ix: int, iy: int, iw: int, ih: int, r: int, c: int) -> None:
        x_end = ix + iw - 1
        y_end = iy + ih - 1
        for py in range(iy, y_end + 1):
            dy = 0
            if py < iy + r:
                dy = (iy + r) - py
            elif py > y_end - r:
                dy = py - (y_end - r)
            inset = 0
            if dy > 0:
                while inset <= r and (r - inset) * (r - inset) + dy * dy > r * r:
                    inset += 1
            self._hspan(ix + inset, x_end - inset, py, c)

    def _stroke_rounded_rect(self, ix: int, iy: int, iw: int, ih: int, r: int, c: int) -> None:
        x_end = ix + iw - 1
        y_end = iy + ih - 1
        self._hspan(ix + r, x_end - r, iy, c)
        self._hspan(ix + r, x_end - r, y_end, c)
        for py in range(iy + r, y_end - r + 1):
            self.put(ix, py, c)
            self.put(x_end, py, c)

        cx_l = ix + r
        cx_r = x_end - r
        cy_t = iy + r
        cy_b = y_end - r
        px = r
        py = 0
        err = 1 - r
        while px >= py:
            for ox, oy in ((px, py), (py, px)):
                self.put(cx_l - ox, cy_t - oy, c)
                self.put(cx_r + ox, cy_t - oy, c)
                self.put(cx_l - ox, cy_b + oy, c)
                self.put(cx_r + ox, cy_b + oy, c)
            py += 1
            if err < 0:
                err += 2 * py + 1
            else:
                px -= 1
                err += 2 * (py - px) + 1

    def line(
        self,
        x0: int | float,
        y0: int | float,
        x1: int | float,
        y1: int | float,
        color: int,
    ) -> None:
        """Draw an integer Bresenham line between `(x0, y0)` and `(x1, y1)`."""
        c = _normalize_index(color)
        ix0 = int(x0)
        iy0 = int(y0)
        ix1 = int(x1)
        iy1 = int(y1)

        if iy0 == iy1:
            self._hspan(min(ix0, ix1), max(ix0, ix1), iy0, c)
            return

        w = self.width
        h = self.height
        data = self.data
        dx = abs(ix1 - ix0)
        dy = -abs(iy1 - iy0)
        sx = 1 if ix0 < ix1 else -1
        sy = 1 if iy0 < iy1 else -1
        err = dx + dy

        while True:
            if 0 <= ix0 < w and 0 <= iy0 < h:
                data[iy0, ix0] = c
                if self._maps is not None:
                    self._maps.write_pixel(ix0, iy0, erase=(c == TRANSPARENT_INDEX))
            if ix0 == ix1 and iy0 == iy1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                ix0 += sx
            if e2 <= dx:
                err += dx
                iy0 += sy

    def circle(
        self,
        cx: int | float,
        cy: int | float,
        radius: int,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw an integer midpoint circle centered at `(cx, cy)`."""
        c = _normalize_index(color)
        icx = int(cx)
        icy = int(cy)
        r = int(radius)
        if r < 0:
            return
        if r == 0:
            self.put(icx, icy, c)
            return

        x = r
        y = 0
        err = 1 - r
        while x >= y:
            if fill:
                self._hspan(icx - x, icx + x, icy + y, c)
                self._hspan(icx - x, icx + x, icy - y, c)
                self._hspan(icx - y, icx + y, icy + x, c)
                self._hspan(icx - y, icx + y, icy - x, c)
            else:
                self._plot_octants(icx, icy, x, y, c)
            y += 1
            if err < 0:
                err += 2 * y + 1
            else:
                x -= 1
                err += 2 * (y - x) + 1

    def _plot_octants(self, cx: int, cy: int, x: int, y: int, color: int) -> None:
        for px, py in (
            (cx + x, cy + y),
            (cx - x, cy + y),
            (cx + x, cy - y),
            (cx - x, cy - y),
            (cx + y, cy + x),
            (cx - y, cy + x),
            (cx + y, cy - x),
            (cx - y, cy - x),
        ):
            self.put(px, py, color)

    def ellipse(
        self,
        cx: int | float,
        cy: int | float,
        rx: int,
        ry: int,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw an integer midpoint ellipse centered at `(cx, cy)`."""
        c = _normalize_index(color)
        icx = int(cx)
        icy = int(cy)
        irx = int(rx)
        iry = int(ry)
        if irx < 0 or iry < 0:
            return
        if irx == 0:
            self.line(icx, icy - iry, icx, icy + iry, c)
            return
        if iry == 0:
            self.line(icx - irx, icy, icx + irx, icy, c)
            return

        rx2 = irx * irx
        ry2 = iry * iry
        two_rx2 = 2 * rx2
        two_ry2 = 2 * ry2

        x = 0
        y = iry
        px = 0
        py = two_rx2 * y
        d1 = ry2 - (rx2 * iry) + (0.25 * rx2)
        while px < py:
            self._emit_ellipse_points(icx, icy, x, y, c, fill=fill)
            x += 1
            px += two_ry2
            if d1 < 0:
                d1 += ry2 + px
            else:
                y -= 1
                py -= two_rx2
                d1 += ry2 + px - py

        d2 = (ry2 * (x + 0.5) * (x + 0.5)) + (rx2 * (y - 1) * (y - 1)) - (rx2 * ry2)
        while y >= 0:
            self._emit_ellipse_points(icx, icy, x, y, c, fill=fill)
            y -= 1
            py -= two_rx2
            if d2 > 0:
                d2 += rx2 - py
            else:
                x += 1
                px += two_rx2
                d2 += rx2 - py + px

    def _emit_ellipse_points(
        self,
        cx: int,
        cy: int,
        x: int,
        y: int,
        color: int,
        *,
        fill: bool,
    ) -> None:
        if fill:
            self._hspan(cx - x, cx + x, cy + y, color)
            if y != 0:
                self._hspan(cx - x, cx + x, cy - y, color)
            return
        self.put(cx + x, cy + y, color)
        self.put(cx - x, cy + y, color)
        self.put(cx + x, cy - y, color)
        self.put(cx - x, cy - y, color)

    def polygon(
        self,
        points: Sequence[tuple[int | float, int | float]],
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw a filled or stroked polygon from a sequence of `(x, y)` vertices."""
        c = _normalize_index(color)
        if not points:
            return
        verts = [_round_point(pt) for pt in points]
        n = len(verts)
        if n == 1:
            self.put(verts[0][0], verts[0][1], c)
            return
        if n == 2:
            self.line(verts[0][0], verts[0][1], verts[1][0], verts[1][1], c)
            return

        if fill:
            min_y = max(0, min(vy for _, vy in verts))
            max_y = min(self.height - 1, max(vy for _, vy in verts))
            for y in range(min_y, max_y + 1):
                xs: list[float] = []
                for i in range(n):
                    ax, ay = verts[i]
                    bx, by = verts[(i + 1) % n]
                    if (ay <= y < by) or (by <= y < ay):
                        xs.append(ax + ((y - ay) * (bx - ax)) / (by - ay))
                xs.sort()
                for i in range(0, len(xs) - 1, 2):
                    self._hspan(round(xs[i]), round(xs[i + 1]), y, c)

        # INVARIANT: Stroke perimeter edges after scanline fill so horizontal or thin edges
        # are never dropped.
        for i in range(n):
            ax, ay = verts[i]
            bx, by = verts[(i + 1) % n]
            self.line(ax, ay, bx, by, c)

    def quad(
        self,
        p0: tuple[int | float, int | float],
        p1: tuple[int | float, int | float],
        p2: tuple[int | float, int | float],
        p3: tuple[int | float, int | float],
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw a quadrilateral from four `(x, y)` vertices."""
        self.polygon((p0, p1, p2, p3), color, fill=fill)

    def fill(self, x: int | float, y: int | float, color: int) -> None:
        """Scanline 4-connected flood fill starting at `(x, y)`."""
        replacement = _normalize_index(color)
        ix = int(x)
        iy = int(y)
        if not self.in_bounds(ix, iy):
            return

        target = int(self.data[iy, ix])
        if target == replacement:
            return

        stack: list[tuple[int, int]] = [(ix, iy)]
        while stack:
            sx, sy = stack.pop()
            if int(self.data[sy, sx]) != target:
                continue

            lx = sx
            while lx > 0 and int(self.data[sy, lx - 1]) == target:
                lx -= 1
            rx = sx
            while rx < self.width - 1 and int(self.data[sy, rx + 1]) == target:
                rx += 1

            self.data[sy, lx : rx + 1] = replacement
            if self._maps is not None:
                self._maps.write_span(lx, rx, sy, erase=(replacement == TRANSPARENT_INDEX))
            self._scan_neighbor_row(lx, rx, sy - 1, target, stack)
            self._scan_neighbor_row(lx, rx, sy + 1, target, stack)

    def _scan_neighbor_row(
        self,
        lx: int,
        rx: int,
        ny: int,
        target: int,
        stack: list[tuple[int, int]],
    ) -> None:
        if ny < 0 or ny >= self.height:
            return
        row = self.data[ny]
        span_active = False
        for px in range(lx, rx + 1):
            matches = int(row[px]) == target
            if matches and not span_active:
                stack.append((px, ny))
                span_active = True
            elif not matches:
                span_active = False

    def dither(
        self,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        color_a: int | None,
        color_b: int | None,
        *,
        pattern: DitherPattern = "bayer4",
        ratio: float = 0.5,
        mask: DitherMask = "all",
    ) -> None:
        """Apply ordered Bayer 2x2/4x4 or checker dithering over a rectangular region."""
        ca = _normalize_index(color_a) if color_a is not None else None
        cb = _normalize_index(color_b) if color_b is not None else None
        ix, iy, iw, ih = int(x), int(y), int(w), int(h)
        if iw <= 0 or ih <= 0:
            return

        x0 = max(0, ix)
        y0 = max(0, iy)
        x1 = min(self.width, ix + iw)
        y1 = min(self.height, iy + ih)
        if x0 >= x1 or y0 >= y1:
            return

        select_b = compute_dither_selection(x0, y0, x1, y1, pattern=pattern, ratio=ratio)

        region = self.data[y0:y1, x0:x1]
        active = (region != TRANSPARENT_INDEX) if mask == "opaque" else np.ones_like(region, bool)
        if cb is not None:
            mask_b = active & select_b
            region[mask_b] = cb
            if self._maps is not None:
                self._maps.write_region_mask(
                    x0, y0, x1, y1, mask_b, erase=(cb == TRANSPARENT_INDEX)
                )
        if ca is not None:
            mask_a = active & ~select_b
            region[mask_a] = ca
            if self._maps is not None:
                self._maps.write_region_mask(
                    x0, y0, x1, y1, mask_a, erase=(ca == TRANSPARENT_INDEX)
                )

    def spr(
        self,
        grid: Sequence[str],
        x: int | float,
        y: int | float,
        color_map: Mapping[str, int],
    ) -> None:
        """Stamp an ASCII sprite grid onto the surface at `(x, y)`."""
        ox = int(x)
        oy = int(y)
        for row_idx, line in enumerate(grid):
            for col_idx, ch in enumerate(line):
                if ch in (".", " "):
                    continue
                idx = color_map.get(ch)
                if idx is not None and idx != TRANSPARENT_INDEX:
                    self.put(ox + col_idx, oy + row_idx, idx)

    def blit_layer(
        self,
        src: IndexedSurface,
        dx: int | float = 0,
        dy: int | float = 0,
        *,
        z_offset: float = 0.0,
    ) -> None:
        """Composite non-transparent pixels from `src` onto this surface at `(dx, dy)`."""
        ox = int(dx)
        oy = int(dy)
        sx0 = max(0, -ox)
        sy0 = max(0, -oy)
        tx0 = max(0, ox)
        ty0 = max(0, oy)
        copy_w = min(src.width - sx0, self.width - tx0)
        copy_h = min(src.height - sy0, self.height - ty0)
        if copy_w <= 0 or copy_h <= 0:
            return

        src_patch = src.data[sy0 : sy0 + copy_h, sx0 : sx0 + copy_w]
        dst_patch = self.data[ty0 : ty0 + copy_h, tx0 : tx0 + copy_w]
        opaque = src_patch != TRANSPARENT_INDEX
        dst_patch[opaque] = src_patch[opaque]
        if self._maps is not None and src._maps is not None:
            self._maps.blit(
                src._maps,
                opaque,
                sx0,
                sy0,
                tx0,
                ty0,
                copy_w,
                copy_h,
                z_offset=z_offset,
            )

    def mirror_x(self, source: MirrorSource = "left") -> None:
        """Mirror one horizontal half of the surface onto the opposite half."""
        half = self.width // 2
        if half <= 0:
            return
        if source == "left":
            self.data[:, self.width - half :] = self.data[:, half - 1 :: -1]
        elif source == "right":
            self.data[:, :half] = self.data[:, self.width - 1 : self.width - half - 1 : -1]
        else:
            msg = f"Invalid mirror source: {source!r}"
            raise ValueError(msg)
        if self._maps is not None:
            self._maps.mirror_x(source)

    def flip_x(self) -> None:
        """Flip the entire surface horizontally in-place."""
        self.data[:] = self.data[:, ::-1]
        if self._maps is not None:
            self._maps.flip_x()

    def flip_y(self) -> None:
        """Flip the entire surface vertically in-place."""
        self.data[:] = self.data[::-1, :]
        if self._maps is not None:
            self._maps.flip_y()

    def _cardinal_opaque_masks(
        self,
    ) -> tuple[
        NDArray[np.bool_],
        NDArray[np.bool_],
        NDArray[np.bool_],
        NDArray[np.bool_],
        NDArray[np.bool_],
    ]:
        opaque = self.data != TRANSPARENT_INDEX
        padded = np.pad(opaque, 1, mode="constant", constant_values=False)
        above = padded[:-2, 1:-1]
        below = padded[2:, 1:-1]
        left = padded[1:-1, :-2]
        right = padded[1:-1, 2:]
        return opaque, above, below, left, right

    def auto_outline(self, outline_color: int) -> None:
        """Add a 1px 4-connected outline onto transparent pixels bordering opaque pixels."""
        c = _normalize_index(outline_color)
        opaque, above, below, left, right = self._cardinal_opaque_masks()
        border = (~opaque) & (above | below | left | right)
        self.data[border] = c
        if self._maps is not None:
            self._maps.write_global_mask(border, erase=(c == TRANSPARENT_INDEX))

    def sel_out(
        self,
        top_color: int,
        bottom_color: int | None = None,
        *,
        side_color: int | None = None,
    ) -> None:
        """Apply directional selective outlining around opaque pixels."""
        c_top = _normalize_index(top_color)
        c_bot = _normalize_index(bottom_color) if bottom_color is not None else c_top
        c_side = _normalize_index(side_color) if side_color is not None else c_bot

        opaque, above, below, left, right = self._cardinal_opaque_masks()
        transparent = ~opaque
        side_mask = transparent & (left | right) & (~below) & (~above)
        bot_mask = transparent & above & (~below)
        top_mask = transparent & below

        self.data[side_mask] = c_side
        self.data[bot_mask] = c_bot
        self.data[top_mask] = c_top
        if self._maps is not None:
            self._maps.write_global_mask(side_mask, erase=(c_side == TRANSPARENT_INDEX))
            self._maps.write_global_mask(bot_mask, erase=(c_bot == TRANSPARENT_INDEX))
            self._maps.write_global_mask(top_mask, erase=(c_top == TRANSPARENT_INDEX))

    def edge_mask(
        self,
        top_color: int | None = None,
        bottom_color: int | None = None,
    ) -> None:
        """Recolor top and/or bottom exposed opaque edge pixels for bevels and rims."""
        c_top = _normalize_index(top_color) if top_color is not None else None
        c_bot = _normalize_index(bottom_color) if bottom_color is not None else None
        if c_top is None and c_bot is None:
            return

        opaque, above, below, _left, _right = self._cardinal_opaque_masks()
        above_empty = opaque & (~above)
        below_empty = opaque & (~below)

        if c_bot is not None:
            self.data[below_empty] = c_bot
        if c_top is not None:
            self.data[above_empty] = c_top


def orphan_pixel_mask(surface: IndexedSurface) -> NDArray[np.bool_]:
    """Return a boolean mask of opaque pixels with zero 8-connected opaque neighbors."""
    opaque = surface.data != TRANSPARENT_INDEX
    if not np.any(opaque):
        return np.zeros_like(opaque, dtype=bool)

    # INVARIANT: An orphan pixel is an opaque pixel with zero 8-connected opaque neighbors.
    padded = np.pad(opaque.astype(np.uint8), 1, mode="constant", constant_values=0)
    neighbor_sum = (
        padded[:-2, :-2]
        + padded[:-2, 1:-1]
        + padded[:-2, 2:]
        + padded[1:-1, :-2]
        + padded[1:-1, 2:]
        + padded[2:, :-2]
        + padded[2:, 1:-1]
        + padded[2:, 2:]
    )
    return np.asarray(opaque & (neighbor_sum == 0), dtype=bool)
