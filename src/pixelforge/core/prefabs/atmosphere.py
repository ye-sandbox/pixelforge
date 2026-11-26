"""Deterministic atmospheric, celestial, weather, and window-light prefabs."""

from __future__ import annotations

import math
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Self

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.plane import Plane, Point2D
from pixelforge.core.prng import mulberry32
from pixelforge.core.surface import (
    DitherMask,
    DitherPattern,
    IndexedSurface,
    compute_dither_thresholds,
)
from pixelforge.core.types import TRANSPARENT_INDEX

Canvas = Asset | Layer
RectRegion = tuple[int | float, int | float, int | float, int | float]
PlaneRegion = tuple[Point2D, Point2D, Point2D]
PaneRegion = RectRegion | PlaneRegion
SkyPreset = Literal["day", "dusk", "cycle", "starry_night", "full_moon", "rain", "snow"]
HorizonMode = Literal["city", "hills", "trees", "rooftops", "industrial", "mountains"]
TelemetryMode = Literal["waveform", "bars", "sparkline", "grid_scan"]


@dataclass(frozen=True)
class CycleStep:
    """Resolved atmospheric parameters for one frame of a day-night cycle."""

    phase: float
    sky_bands: tuple[int, ...]
    celestial_kind: Literal["sun", "moon"]
    celestial_u: float
    celestial_v: float
    star_visibility: float
    spill_intensity: float


class ClippedPane:
    """Auxiliary clipped glass-pane buffer for `front-2.5d` rects and `iso-2:1` planes."""

    target: Canvas
    ox: int
    oy: int
    width: int
    height: int
    surface: IndexedSurface
    mask: NDArray[np.bool_]
    u_grid: NDArray[np.float64]
    v_grid: NDArray[np.float64]
    xx: NDArray[np.int64]
    yy: NDArray[np.int64]
    is_iso: bool
    _p0: tuple[float, float]
    _u_vec: tuple[float, float]
    _v_vec: tuple[float, float]

    def __init__(self, target: Canvas, region: PaneRegion) -> None:
        self.target = target
        if len(region) == 4:
            self._init_rect(region)
        elif len(region) == 3:
            self._init_plane(region)
        else:
            msg = f"Expected 4-tuple rect or 3-point plane region, got {len(region)} elements"
            raise ValueError(msg)

    def _init_empty(self) -> None:
        self.ox = 0
        self.oy = 0
        self.width = 1
        self.height = 1
        self.surface = IndexedSurface(1, 1)
        self.mask = np.zeros((1, 1), dtype=bool)
        self.u_grid = np.zeros((1, 1), dtype=np.float64)
        self.v_grid = np.zeros((1, 1), dtype=np.float64)
        self.xx = np.zeros((1, 1), dtype=np.int64)
        self.yy = np.zeros((1, 1), dtype=np.int64)
        self._p0 = (0.0, 0.0)
        self._u_vec = (1.0, 0.0)
        self._v_vec = (0.0, 1.0)

    def _init_rect(self, region: RectRegion) -> None:
        self.is_iso = False
        rx, ry, rw, rh = region
        ix = round(rx)
        iy = round(ry)
        iw = int(rw)
        ih = int(rh)
        if iw <= 0 or ih <= 0:
            self._init_empty()
            return

        self.ox = ix
        self.oy = iy
        self.width = iw
        self.height = ih
        self.surface = IndexedSurface(iw, ih)
        self.mask = np.ones((ih, iw), dtype=bool)
        ly, lx = np.mgrid[0:ih, 0:iw]
        self.u_grid = (lx + 0.5) / float(iw)
        self.v_grid = (ly + 0.5) / float(ih)
        self.xx = np.asarray(ix + lx, dtype=np.int64)
        self.yy = np.asarray(iy + ly, dtype=np.int64)
        self._p0 = (0.0, 0.0)
        self._u_vec = (float(max(1, iw - 1)), 0.0)
        self._v_vec = (0.0, float(max(1, ih - 1)))

    def _init_plane(self, region: PlaneRegion) -> None:
        self.is_iso = True
        p0, p1, p2 = region
        u_vec = (float(p1[0]) - float(p0[0]), float(p1[1]) - float(p0[1]))
        v_vec = (float(p2[0]) - float(p0[0]), float(p2[1]) - float(p0[1]))
        det = (u_vec[0] * v_vec[1]) - (u_vec[1] * v_vec[0])
        if abs(det) < 1e-6:
            self._init_empty()
            return

        c00 = (round(p0[0]), round(p0[1]))
        c10 = (round(p1[0]), round(p1[1]))
        c01 = (round(p2[0]), round(p2[1]))
        c11 = (
            round(float(p1[0]) + float(p2[0]) - float(p0[0])),
            round(float(p1[1]) + float(p2[1]) - float(p0[1])),
        )
        min_x = min(c00[0], c10[0], c11[0], c01[0])
        max_x = max(c00[0], c10[0], c11[0], c01[0])
        min_y = min(c00[1], c10[1], c11[1], c01[1])
        max_y = max(c00[1], c10[1], c11[1], c01[1])

        w = max(1, max_x - min_x + 1)
        h = max(1, max_y - min_y + 1)

        self.ox = min_x
        self.oy = min_y
        self.width = w
        self.height = h
        self.surface = IndexedSurface(w, h)

        ly, lx = np.mgrid[0:h, 0:w]
        gx = min_x + lx
        gy = min_y + ly
        dx = gx - float(p0[0])
        dy = gy - float(p0[1])
        u_raw = ((dx * v_vec[1]) - (dy * v_vec[0])) / det
        v_raw = ((u_vec[0] * dy) - (u_vec[1] * dx)) / det
        eps = 1e-6
        self.mask = np.asarray(
            (u_raw >= -eps) & (u_raw <= 1.0 + eps) & (v_raw >= -eps) & (v_raw <= 1.0 + eps),
            dtype=bool,
        )
        self.u_grid = np.clip(u_raw, 0.0, 1.0)
        self.v_grid = np.clip(v_raw, 0.0, 1.0)
        self.xx = np.asarray(gx, dtype=np.int64)
        self.yy = np.asarray(gy, dtype=np.int64)
        self._p0 = (float(p0[0]) - min_x, float(p0[1]) - min_y)
        self._u_vec = u_vec
        self._v_vec = v_vec

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.commit()

    def project(self, u: float, v: float) -> tuple[int, int]:
        """Project normalized `(u, v)` coordinates to local `surface` pixel `(lx, ly)`."""
        lx = self._p0[0] + u * self._u_vec[0] + v * self._v_vec[0]
        ly = self._p0[1] + u * self._u_vec[1] + v * self._v_vec[1]
        return (round(lx), round(ly))

    def put_uv(self, u: float, v: float, color: int) -> None:
        """Write a pixel at `(u, v)` only when inside the clipped glass mask."""
        lx, ly = self.project(u, v)
        if 0 <= lx < self.width and 0 <= ly < self.height and bool(self.mask[ly, lx]):
            self.surface.put(lx, ly, color)

    def commit(self) -> None:
        """Clip the auxiliary buffer strictly to `mask` and composite onto the parent canvas."""
        # INVARIANT: Clearing all pixels outside `mask` guarantees zero bleed past the glass
        # boundary onto surrounding window frames or mullions regardless of primitive geometry.
        self.surface.data[~self.mask] = TRANSPARENT_INDEX
        self.target.surface.blit_layer(self.surface, self.ox, self.oy)


TargetCanvas = Canvas | ClippedPane


def clipped_pane(target: Canvas, region: PaneRegion) -> ClippedPane:
    """Create a clipped glass-pane context manager for `(x, y, w, h)` or `(p0, p1, p2)`."""
    return ClippedPane(target, region)


@contextmanager
def _open_pane(
    target: TargetCanvas,
    region: PaneRegion | None,
) -> Generator[ClippedPane]:
    if isinstance(target, ClippedPane):
        yield target
        return
    if region is None:
        msg = "region is required when calling atmospheric prefabs directly on an Asset or Layer"
        raise ValueError(msg)
    with ClippedPane(target, region) as pane:
        yield pane


def _wrap_phase(phase: float) -> float:
    return float(phase) % 1.0


def sky_backdrop(
    target: TargetCanvas,
    *,
    bands: Sequence[int],
    region: PaneRegion | None = None,
    pattern: DitherPattern = "bayer4",
    dither_width: float = 0.65,
) -> None:
    """Render a multi-band ordered-dither sky gradient inside a clipped window pane."""
    if not bands:
        msg = "sky_backdrop requires at least one palette index in bands"
        raise ValueError(msg)

    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        if len(bands) == 1:
            pane.surface.data[pane.mask] = int(bands[0])
            return

        n_seg = len(bands) - 1
        pos = np.clip(pane.v_grid * n_seg, 0.0, float(n_seg))
        seg = np.minimum(pos.astype(np.int64), n_seg - 1)
        frac = pos - seg

        width = max(0.05, min(1.0, float(dither_width)))
        half_w = 0.5 * width
        ratio = np.clip((frac - (0.5 - half_w)) / width, 0.0, 1.0)

        thresholds = compute_dither_thresholds(
            pane.ox,
            pane.oy,
            pane.ox + pane.width,
            pane.oy + pane.height,
            pattern=pattern,
        )
        choose_next = (ratio >= 1.0) | ((ratio > 0.0) & (thresholds < ratio))
        band_arr = np.asarray([int(c) for c in bands], dtype=np.uint8)
        idx_map = np.where(choose_next, seg + 1, seg)
        rendered = band_arr[idx_map]
        pane.surface.data[pane.mask] = rendered[pane.mask]


def _draw_checker_halo(
    pane: ClippedPane,
    cx: int,
    cy: int,
    outer_r: int,
    inner_r: int,
    halo_color: int,
) -> None:
    ly, lx = np.mgrid[0 : pane.height, 0 : pane.width]
    dist2 = (lx - cx) * (lx - cx) + (ly - cy) * (ly - cy)
    ring = pane.mask & (dist2 <= outer_r * outer_r) & (dist2 > inner_r * inner_r)
    checker = ((pane.xx + pane.yy) & 1) == 0
    pane.surface.data[ring & checker] = int(halo_color)


def sun(
    target: TargetCanvas,
    u: float = 0.28,
    v: float = 0.28,
    *,
    radius: int = 3,
    color: int,
    halo: int | None = None,
    rays: bool = False,
    ray_color: int | None = None,
    region: PaneRegion | None = None,
) -> None:
    """Render a crisp pixel-art sun with optional checker halo and cardinal/diagonal rays."""
    ir = max(0, int(radius))
    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        cx, cy = pane.project(u, v)
        if halo is not None:
            _draw_checker_halo(pane, cx, cy, ir + 2, ir, halo)
        if rays:
            rc = int(ray_color if ray_color is not None else (halo if halo is not None else color))
            ray_start = ir + 1
            ray_end = ir + 3
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                pane.surface.line(
                    cx + dx * ray_start,
                    cy + dy * ray_start,
                    cx + dx * ray_end,
                    cy + dy * ray_end,
                    rc,
                )
            diag = ir + 2
            for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                pane.surface.put(cx + dx * diag, cy + dy * diag, rc)
        pane.surface.circle(cx, cy, ir, color, fill=True)


def moon(
    target: TargetCanvas,
    u: float = 0.72,
    v: float = 0.28,
    *,
    radius: int = 3,
    color: int,
    crater_color: int | None = None,
    shadow_color: int | None = None,
    crescent: bool = False,
    halo: int | None = None,
    region: PaneRegion | None = None,
) -> None:
    """Render a full moon (with pixel craters) or crescent moon clipped inside a pane."""
    ir = max(1, int(radius))
    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        cx, cy = pane.project(u, v)
        if halo is not None:
            _draw_checker_halo(pane, cx, cy, ir + 1, ir, halo)

        if crescent:
            moon_buf = IndexedSurface(pane.width, pane.height)
            moon_buf.circle(cx, cy, ir, color, fill=True)
            cut_x = cx + max(1, (ir + 1) // 2)
            cut_y = cy - max(0, ir // 3)
            cut_r = max(1, ir - 1) if ir >= 2 else 1
            carve_color = TRANSPARENT_INDEX if shadow_color is None else int(shadow_color)
            if shadow_color is None:
                moon_buf.circle(cut_x, cut_y, cut_r, carve_color, fill=True)
            else:
                carve_mask = IndexedSurface(pane.width, pane.height)
                carve_mask.circle(cut_x, cut_y, cut_r, 0, fill=True)
                overlap = (moon_buf.data != TRANSPARENT_INDEX) & (
                    carve_mask.data != TRANSPARENT_INDEX
                )
                moon_buf.data[overlap] = carve_color
            pane.surface.blit_layer(moon_buf, 0, 0)
            return

        pane.surface.circle(cx, cy, ir, color, fill=True)
        if crater_color is not None and ir >= 2:
            craters = (
                (-max(1, ir // 2), -max(1, ir // 3)),
                (max(1, ir // 3), max(0, ir // 4)),
                (-max(0, ir // 4), max(1, ir // 2)),
            )
            limit2 = max(1, (ir - 1) * (ir - 1))
            for ox, oy in craters:
                if ox * ox + oy * oy <= limit2:
                    pane.surface.put(cx + ox, cy + oy, crater_color)


def starfield(
    target: TargetCanvas,
    *,
    count: int = 12,
    color: int,
    twinkle_color: int | None = None,
    frame: int = 0,
    frames: int = 1,
    seed: int = 0,
    max_v: float = 0.78,
    region: PaneRegion | None = None,
) -> None:
    """Render deterministic fixed-position stars with smooth periodic frame twinkling."""
    if count <= 0:
        return
    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0x51A7F1E1)
        phase_base = (int(frame) % max(1, int(frames))) / float(max(1, int(frames)))
        v_cap = max(0.15, min(0.95, float(max_v)))

        for idx in range(int(count)):
            su = 0.06 + rng() * 0.88
            sv = 0.06 + rng() * (v_cap - 0.06)
            star_phase = rng()
            t = (phase_base + star_phase) % 1.0

            star_col = color
            if twinkle_color is not None and int(frames) > 1:
                if t < 0.22:
                    star_col = twinkle_color
                elif t > 0.86 and idx % 3 == 0:
                    continue
            pane.put_uv(su, sv, star_col)


def clouds(
    target: TargetCanvas,
    *,
    color: int,
    shade_color: int | None = None,
    count: int = 2,
    phase: float = 0.0,
    min_v: float = 0.14,
    max_v: float = 0.48,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render seamlessly looping drifting clouds in `(u, v)` pane space."""
    if count <= 0:
        return
    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0xC10D5EED)
        p = _wrap_phase(phase)
        v_lo = max(0.05, min(0.85, float(min_v)))
        v_hi = max(v_lo + 0.05, min(0.92, float(max_v)))

        cloud_mask = np.zeros_like(pane.mask, dtype=bool)
        shade_mask = np.zeros_like(pane.mask, dtype=bool)

        # INVARIANT: Stratify vertical bands across `count` and permute deterministically
        # so multi-cloud vistas never collapse onto the same height or identical silhouette.
        n_clouds = int(count)
        band_h = (v_hi - v_lo) / float(n_clouds)
        slots = list(range(n_clouds))
        for idx in range(n_clouds - 1, 0, -1):
            swap_idx = int(rng() * (idx + 1))
            slots[idx], slots[swap_idx] = slots[swap_idx], slots[idx]

        for idx in range(n_clouds):
            u0 = rng()
            slot = slots[idx]
            v0 = v_lo + (slot + 0.15 + 0.70 * rng()) * band_h
            size_t = (idx + 0.20 + 0.65 * rng()) / float(max(1, n_clouds))
            rx = 0.09 + size_t * 0.16
            ry = 0.05 + size_t * 0.09
            left_scale = 0.58 + rng() * 0.22
            right_scale = 0.60 + rng() * 0.24
            uc = ((u0 + p) % 1.0) * 1.56 - 0.28

            puff_a = (((pane.u_grid - uc) / rx) ** 2 + ((pane.v_grid - v0) / ry) ** 2) <= 1.0
            puff_b = (
                ((pane.u_grid - (uc - 0.55 * rx)) / (left_scale * rx)) ** 2
                + ((pane.v_grid - (v0 + 0.14 * ry)) / (0.76 * ry)) ** 2
            ) <= 1.0
            puff_c = (
                ((pane.u_grid - (uc + 0.58 * rx)) / (right_scale * rx)) ** 2
                + ((pane.v_grid - (v0 + 0.10 * ry)) / (0.80 * ry)) ** 2
            ) <= 1.0
            flat_base = pane.v_grid <= (v0 + 0.58 * ry)
            body = (puff_a | puff_b | puff_c) & flat_base
            cloud_mask |= body
            if shade_color is not None:
                shade_mask |= body & (pane.v_grid >= (v0 + 0.22 * ry))

        pane.surface.data[pane.mask & cloud_mask] = int(color)
        if shade_color is not None:
            pane.surface.data[pane.mask & shade_mask] = int(shade_color)


def horizon_silhouette(
    target: TargetCanvas,
    *,
    color: int,
    accent: int | None = None,
    mode: HorizonMode = "city",
    base_v: float = 0.74,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render a city, rooftop, hill, or pine-tree horizon silhouette clipped to a window pane."""
    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0x40A1204E)
        bv = max(0.35, min(0.95, float(base_v)))
        u = pane.u_grid
        v = pane.v_grid

        if mode in ("city", "rooftops"):
            cols = 7 if mode == "city" else 5
            ridge = np.full_like(v, bv)
            for idx in range(cols):
                u0 = idx / float(cols)
                u1 = (idx + 1) / float(cols)
                h_off = (rng() - 0.45) * (0.20 if mode == "city" else 0.14)
                top_v = max(0.42, min(0.92, bv - abs(h_off)))
                in_col = (u >= u0) & (u <= u1)
                if mode == "rooftops":
                    center = 0.5 * (u0 + u1)
                    span = 0.5 * (u1 - u0)
                    slope = np.abs(u - center) / max(1e-6, span)
                    col_v = top_v + slope * 0.08
                    ridge = np.where(in_col, np.minimum(ridge, col_v), ridge)
                else:
                    ridge = np.where(in_col, np.minimum(ridge, top_v), ridge)
            sil_mask = pane.mask & (v >= ridge)
            pane.surface.data[sil_mask] = int(color)
            if accent is not None:
                for _ in range(cols):
                    wu = 0.08 + rng() * 0.84
                    wv = min(0.94, bv + 0.04 + rng() * 0.14)
                    pane.put_uv(wu, wv, accent)
            return

        if mode == "hills":
            phase_a = rng() * math.tau
            phase_b = rng() * math.tau
            ridge_a = bv + 0.07 * np.sin(u * math.tau * 1.3 + phase_a)
            sil_a = pane.mask & (v >= ridge_a)
            if accent is not None:
                ridge_b = (bv - 0.06) + 0.05 * np.sin(u * math.tau * 1.9 + phase_b)
                pane.surface.data[pane.mask & (v >= ridge_b)] = int(accent)
            pane.surface.data[sil_a] = int(color)
            return

        if mode == "trees":
            peaks = 9
            saw = np.abs(((u * peaks) % 1.0) - 0.5) * 2.0
            jitter = 0.03 * np.sin(u * math.tau * 3.0 + rng() * math.tau)
            ridge = (bv - 0.08) + saw * 0.13 + jitter
            if accent is not None:
                pane.surface.data[pane.mask & (v >= (ridge - 0.04))] = int(accent)
            pane.surface.data[pane.mask & (v >= ridge)] = int(color)
            return

        if mode == "mountains":
            p_a = rng() * math.tau
            p_b = rng() * math.tau
            tri_a = np.abs(((u * 2.5 + p_a / math.tau) % 1.0) - 0.5) * 2.0
            tri_b = np.abs(((u * 4.5 + p_b / math.tau) % 1.0) - 0.5) * 2.0
            ridge = (bv - 0.20) + tri_a * 0.22 + tri_b * 0.07
            sil = pane.mask & (v >= ridge)
            pane.surface.data[sil] = int(color)
            if accent is not None:
                # Snowcap / sunlit upper slope on peaks above threshold
                cap = sil & (v <= (bv - 0.09))
                pane.surface.data[cap] = int(accent)
            return

        if mode == "industrial":
            ridge = np.full_like(v, bv)
            bays = 4
            for idx in range(bays):
                u0 = idx / float(bays)
                u1 = (idx + 1) / float(bays)
                in_bay = (u >= u0) & (u <= u1)
                # Sawtooth factory roof slope
                local_u = (u - u0) / max(1e-6, u1 - u0)
                roof_v = (bv - 0.10) + local_u * 0.08
                ridge = np.where(in_bay, np.minimum(ridge, roof_v), ridge)
            # Add deterministic smokestacks
            for stack_idx in range(2):
                su = 0.18 + stack_idx * 0.48 + (rng() - 0.5) * 0.08
                sw = 0.05
                in_stack = (u >= su) & (u <= su + sw)
                stack_top = max(0.28, bv - 0.24 - rng() * 0.08)
                ridge = np.where(in_stack, np.minimum(ridge, stack_top), ridge)
                if accent is not None:
                    pane.put_uv(su + sw * 0.5, stack_top + 0.02, accent)
            pane.surface.data[pane.mask & (v >= ridge)] = int(color)
            if accent is not None:
                for _ in range(3):
                    pane.put_uv(0.12 + rng() * 0.76, min(0.92, bv + 0.03 + rng() * 0.08), accent)
            return

        msg = f"Unsupported horizon mode: {mode!r}"
        raise ValueError(msg)


def weather_rain(
    target: TargetCanvas,
    *,
    color: int,
    splash_color: int | None = None,
    count: int = 16,
    phase: float = 0.0,
    slant: float = -0.14,
    length: float = 0.14,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render deterministic looping rain streaks (`phase = frame / frames`)."""
    if count <= 0:
        return
    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0xFA110001)
        p = _wrap_phase(phase)
        streak_len = max(0.04, min(0.45, float(length)))

        for _ in range(int(count)):
            u0 = rng()
            v0 = rng()
            speed = 1 if rng() < 0.55 else 2
            t = (v0 + p * speed) % 1.0
            v_head = -0.08 + t * 1.18
            u_head = (u0 + slant * (v_head - 0.5)) % 1.0
            v_tail = v_head - streak_len
            u_tail = u_head - slant * streak_len

            x0, y0 = pane.project(u_tail, v_tail)
            x1, y1 = pane.project(u_head, v_head)
            pane.surface.line(x0, y0, x1, y1, color)
            if splash_color is not None and v_head >= 0.90:
                pane.put_uv(u_head, 0.95, splash_color)


def weather_snow(
    target: TargetCanvas,
    *,
    color: int,
    alt_color: int | None = None,
    count: int = 18,
    phase: float = 0.0,
    drift: float = 0.08,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render deterministic looping swaying snowflakes (`phase = frame / frames`)."""
    if count <= 0:
        return
    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0x590BF1A3)
        p = _wrap_phase(phase)

        for _ in range(int(count)):
            u0 = rng()
            v0 = rng()
            sway_phase = rng()
            is_bg = rng() < 0.45
            speed = 1 if is_bg else 2
            t = (v0 + p * speed) % 1.0
            v_pos = -0.04 + t * 1.08
            u_pos = (u0 + drift * math.sin(math.tau * (p + sway_phase))) % 1.0
            flake_col = alt_color if (is_bg and alt_color is not None) else color
            pane.put_uv(u_pos, v_pos, flake_col)


def eval_day_night_cycle(
    phase: float,
    *,
    day_bands: Sequence[int],
    dusk_bands: Sequence[int],
    night_bands: Sequence[int],
    dawn_bands: Sequence[int] | None = None,
) -> CycleStep:
    """Compute interpolated sky bands, sun/moon arc, star visibility, and spill intensity."""
    if not day_bands or not dusk_bands or not night_bands:
        msg = "day_bands, dusk_bands, and night_bands must each contain at least one color"
        raise ValueError(msg)

    p = _wrap_phase(phase)
    dawn = tuple(dawn_bands if dawn_bands is not None else dusk_bands)
    day = tuple(day_bands)
    dusk = tuple(dusk_bands)
    night = tuple(night_bands)

    if p < 0.35:
        local = p / 0.35
        u = 0.22 + 0.56 * local
        v = 0.42 - 0.20 * math.sin(local * math.pi)
        return CycleStep(
            phase=p,
            sky_bands=day,
            celestial_kind="sun",
            celestial_u=u,
            celestial_v=v,
            star_visibility=0.0,
            spill_intensity=0.85,
        )
    if p < 0.55:
        local = (p - 0.35) / 0.20
        u = 0.78 + 0.08 * local
        v = 0.42 + 0.22 * local
        return CycleStep(
            phase=p,
            sky_bands=dusk,
            celestial_kind="sun",
            celestial_u=u,
            celestial_v=v,
            star_visibility=0.35 * local,
            spill_intensity=0.45 * (1.0 - 0.5 * local),
        )
    if p < 0.80:
        local = (p - 0.55) / 0.25
        u = 0.24 + 0.52 * local
        v = 0.38 - 0.14 * math.sin(local * math.pi)
        return CycleStep(
            phase=p,
            sky_bands=night,
            celestial_kind="moon",
            celestial_u=u,
            celestial_v=v,
            star_visibility=1.0,
            spill_intensity=0.22,
        )

    local = (p - 0.80) / 0.20
    u = 0.16 + 0.08 * local
    v = 0.60 - 0.18 * local
    return CycleStep(
        phase=p,
        sky_bands=dawn,
        celestial_kind="sun",
        celestial_u=u,
        celestial_v=v,
        star_visibility=0.45 * (1.0 - local),
        spill_intensity=0.45 + 0.35 * local,
    )


def day_night_cycle(
    target: TargetCanvas,
    *,
    phase: float,
    day_bands: Sequence[int],
    dusk_bands: Sequence[int],
    night_bands: Sequence[int],
    sun_color: int,
    moon_color: int,
    star_color: int,
    dawn_bands: Sequence[int] | None = None,
    sun_halo: int | None = None,
    moon_crater: int | None = None,
    cloud_color: int | None = None,
    cloud_shade: int | None = None,
    horizon_color: int | None = None,
    horizon_accent: int | None = None,
    horizon_mode: HorizonMode = "city",
    star_count: int = 12,
    frame: int = 0,
    frames: int = 1,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> CycleStep:
    """Render an animated day-dusk-night-dawn vista inside a clipped pane and return `CycleStep`."""
    step = eval_day_night_cycle(
        phase,
        day_bands=day_bands,
        dusk_bands=dusk_bands,
        night_bands=night_bands,
        dawn_bands=dawn_bands,
    )
    with _open_pane(target, region) as pane:
        sky_backdrop(pane, bands=step.sky_bands)
        if step.star_visibility > 0.05:
            visible_stars = max(1, round(star_count * step.star_visibility))
            starfield(
                pane,
                count=visible_stars,
                color=star_color,
                twinkle_color=moon_color,
                frame=frame,
                frames=frames,
                seed=seed,
            )
        if step.celestial_kind == "sun":
            sun(
                pane,
                step.celestial_u,
                step.celestial_v,
                radius=3,
                color=sun_color,
                halo=sun_halo,
                rays=step.spill_intensity > 0.6,
            )
        else:
            moon(
                pane,
                step.celestial_u,
                step.celestial_v,
                radius=3,
                color=moon_color,
                crater_color=moon_crater,
                halo=sun_halo if step.star_visibility < 0.5 else None,
            )
        if cloud_color is not None:
            clouds(
                pane,
                color=cloud_color,
                shade_color=cloud_shade,
                count=2,
                phase=step.phase,
                seed=seed + 17,
            )
        if horizon_color is not None:
            horizon_silhouette(
                pane,
                color=horizon_color,
                accent=horizon_accent if step.celestial_kind == "moon" else None,
                mode=horizon_mode,
                seed=seed + 31,
            )
    return step


def window_light_spill(
    target: Canvas,
    *,
    points: tuple[Point2D, Point2D, Point2D, Point2D],
    color: int,
    secondary_color: int | None = None,
    pattern: DitherPattern = "bayer4",
    near_ratio: float = 0.70,
    far_ratio: float = 0.18,
    mask: DitherMask = "opaque",
) -> None:
    """Project a crisp ordered-dither light spill onto a 4-vertex interior quad.

    INVARIANT: Light spill targets floor/wall surfaces using strictly non-emissive palette
    tokens so WebGL2 bloom masks remain confined to true emitters.
    """
    verts = [(round(pt[0]), round(pt[1])) for pt in points]
    min_x = max(0, min(px for px, _ in verts))
    min_y = max(0, min(py for _, py in verts))
    max_x = min(target.surface.width - 1, max(px for px, _ in verts))
    max_y = min(target.surface.height - 1, max(py for _, py in verts))
    if min_x > max_x or min_y > max_y:
        return

    w = max_x - min_x + 1
    h = max_y - min_y + 1
    quad_surf = IndexedSurface(w, h)
    shifted = tuple((px - min_x, py - min_y) for px, py in verts)
    quad_surf.quad(shifted[0], shifted[1], shifted[2], shifted[3], 0, fill=True)
    in_quad = quad_surf.data != TRANSPARENT_INDEX

    region = target.surface.data[min_y : max_y + 1, min_x : max_x + 1]
    active = in_quad & (region != TRANSPARENT_INDEX) if mask == "opaque" else in_quad
    if not np.any(active):
        return

    near_mid = (0.5 * (points[0][0] + points[1][0]), 0.5 * (points[0][1] + points[1][1]))
    far_mid = (0.5 * (points[2][0] + points[3][0]), 0.5 * (points[2][1] + points[3][1]))
    ax = float(far_mid[0] - near_mid[0])
    ay = float(far_mid[1] - near_mid[1])
    norm2 = max(1.0, ax * ax + ay * ay)

    ly, lx = np.mgrid[0:h, 0:w]
    gx = min_x + lx
    gy = min_y + ly
    t = np.clip(((gx - near_mid[0]) * ax + (gy - near_mid[1]) * ay) / norm2, 0.0, 1.0)
    ratio_grid = float(near_ratio) + t * (float(far_ratio) - float(near_ratio))
    thresholds = compute_dither_thresholds(
        min_x,
        min_y,
        max_x + 1,
        max_y + 1,
        pattern=pattern,
    )
    select_primary = active & (
        (ratio_grid >= 1.0) | ((ratio_grid > 0.0) & (thresholds < ratio_grid))
    )
    if secondary_color is not None:
        sec_ratio = ratio_grid * 0.55
        select_secondary = (
            active & (~select_primary) & ((sec_ratio > 0.0) & (thresholds < sec_ratio))
        )
        region[select_secondary] = int(secondary_color)
    region[select_primary] = int(color)


def light_beam(
    target: Canvas,
    region: PaneRegion,
    *,
    color: int,
    secondary_color: int | None = None,
    dx: int = 24,
    dy: int = 16,
    spread: int = 6,
    pattern: DitherPattern = "bayer4",
    near_ratio: float = 0.70,
    far_ratio: float = 0.18,
    mask: DitherMask = "opaque",
) -> None:
    """Compute a window-anchored floor/wall light spill quad and render `window_light_spill`."""
    if len(region) == 4:
        rx, ry, rw, rh = region
        b0: Point2D = (rx, ry + rh)
        b1: Point2D = (rx + rw, ry + rh)
    elif len(region) == 3:
        p0, p1, p2 = region
        b0 = p2
        b1 = (
            float(p1[0]) + float(p2[0]) - float(p0[0]),
            float(p1[1]) + float(p2[1]) - float(p0[1]),
        )
    else:
        msg = f"Expected 4-tuple rect or 3-point plane region, got {len(region)} elements"
        raise ValueError(msg)

    f0: Point2D = (b0[0] + dx - spread, b0[1] + dy)
    f1: Point2D = (b1[0] + dx + spread, b1[1] + dy)
    window_light_spill(
        target,
        points=(b0, b1, f1, f0),
        color=color,
        secondary_color=secondary_color,
        pattern=pattern,
        near_ratio=near_ratio,
        far_ratio=far_ratio,
        mask=mask,
    )


def point_light_spill(
    target: Canvas,
    cx: int | float,
    cy: int | float,
    rx: int | float,
    ry: int | float,
    *,
    color: int,
    secondary_color: int | None = None,
    direction: tuple[float, float] | None = None,
    cone_cos: float = 0.0,
    pattern: DitherPattern = "bayer4",
    near_ratio: float = 0.75,
    far_ratio: float = 0.05,
    mask: DitherMask = "opaque",
) -> None:
    """Project a non-emissive radial or conical dithered light pool for lamps/monitors.

    INVARIANT: Light spill targets floor/wall surfaces using strictly non-emissive palette
    tokens so WebGL2 bloom masks remain confined to true emitters.
    """
    frx = max(1.0, float(rx))
    fry = max(1.0, float(ry))
    min_x = max(0, round(cx - frx))
    min_y = max(0, round(cy - fry))
    max_x = min(target.surface.width - 1, round(cx + frx))
    max_y = min(target.surface.height - 1, round(cy + fry))
    if min_x > max_x or min_y > max_y:
        return

    w = max_x - min_x + 1
    h = max_y - min_y + 1
    ly, lx = np.mgrid[0:h, 0:w]
    gx = min_x + lx
    gy = min_y + ly
    dx = gx - float(cx)
    dy = gy - float(cy)
    dist = np.sqrt((dx / frx) ** 2 + (dy / fry) ** 2)
    in_pool = dist <= 1.0

    if direction is not None:
        d_len = math.hypot(direction[0], direction[1])
        if d_len > 1e-6:
            ux = direction[0] / d_len
            uy = direction[1] / d_len
            pix_len = np.sqrt(dx * dx + dy * dy)
            dot = np.where(pix_len > 1e-6, (dx * ux + dy * uy) / np.maximum(1e-6, pix_len), 1.0)
            in_pool &= dot >= float(cone_cos)

    region = target.surface.data[min_y : max_y + 1, min_x : max_x + 1]
    active = in_pool & (region != TRANSPARENT_INDEX) if mask == "opaque" else in_pool
    if not np.any(active):
        return

    t = np.clip(dist, 0.0, 1.0)
    ratio_grid = float(near_ratio) + t * (float(far_ratio) - float(near_ratio))
    thresholds = compute_dither_thresholds(
        min_x,
        min_y,
        max_x + 1,
        max_y + 1,
        pattern=pattern,
    )
    select_primary = active & (
        (ratio_grid >= 1.0) | ((ratio_grid > 0.0) & (thresholds < ratio_grid))
    )
    if secondary_color is not None:
        sec_ratio = ratio_grid * 0.55
        select_secondary = (
            active & (~select_primary) & ((sec_ratio > 0.0) & (thresholds < sec_ratio))
        )
        region[select_secondary] = int(secondary_color)
    region[select_primary] = int(color)


def dust_motes(
    target: TargetCanvas,
    *,
    color: int,
    alt_color: int | None = None,
    count: int = 12,
    phase: float = 0.0,
    drift: float = 0.06,
    seed: int = 0,
    region: PaneRegion | None = None,
    points: tuple[Point2D, Point2D, Point2D, Point2D] | None = None,
) -> None:
    """Render deterministic looping dust motes clipped to a light beam, spill quad, or pane."""
    if count <= 0:
        return
    rng = mulberry32(int(seed) ^ 0xD0570001)
    p = _wrap_phase(phase)

    if points is not None:
        if isinstance(target, ClippedPane):
            msg = "points cannot be combined with a ClippedPane target"
            raise ValueError(msg)
        verts = [(round(pt[0]), round(pt[1])) for pt in points]
        min_x = max(0, min(px for px, _ in verts))
        min_y = max(0, min(py for _, py in verts))
        max_x = min(target.surface.width - 1, max(px for px, _ in verts))
        max_y = min(target.surface.height - 1, max(py for _, py in verts))
        if min_x > max_x or min_y > max_y:
            return
        w = max_x - min_x + 1
        h = max_y - min_y + 1
        quad_surf = IndexedSurface(w, h)
        shifted = tuple((px - min_x, py - min_y) for px, py in verts)
        quad_surf.quad(shifted[0], shifted[1], shifted[2], shifted[3], 0, fill=True)
        in_quad = quad_surf.data != TRANSPARENT_INDEX
        for idx in range(int(count)):
            u0 = rng()
            v0 = rng()
            ph = rng()
            u = (u0 + drift * math.sin(math.tau * (p + ph))) % 1.0
            v = (v0 + drift * 0.7 * math.cos(math.tau * (p + ph * 1.3))) % 1.0
            lx = min(w - 1, max(0, round(u * (w - 1))))
            ly = min(h - 1, max(0, round(v * (h - 1))))
            if bool(in_quad[ly, lx]):
                col = alt_color if (alt_color is not None and idx % 2 == 1) else color
                target.surface.put(min_x + lx, min_y + ly, col)
        return

    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        for idx in range(int(count)):
            u0 = rng()
            v0 = rng()
            ph = rng()
            u = (u0 + drift * math.sin(math.tau * (p + ph))) % 1.0
            v = (v0 + drift * 0.7 * math.cos(math.tau * (p + ph * 1.3))) % 1.0
            col = alt_color if (alt_color is not None and idx % 2 == 1) else color
            pane.put_uv(u, v, col)


def rising_steam(
    target: Canvas,
    x: int | float,
    y: int | float,
    *,
    color: int,
    alt_color: int | None = None,
    height: int = 12,
    spread: int = 3,
    count: int = 6,
    phase: float = 0.0,
    seed: int = 0,
) -> None:
    """Render deterministic looping rising vapor wisps for mugs, vents, or faulty hardware."""
    if count <= 0 or height <= 0:
        return
    rng = mulberry32(int(seed) ^ 0x57EA0001)
    p = _wrap_phase(phase)
    ox = float(x)
    oy = float(y)

    for _ in range(int(count)):
        t0 = rng()
        sway_phase = rng()
        base_off = (rng() - 0.5) * 2.0
        t = (t0 + p) % 1.0
        py = round(oy - t * float(height))
        sway = math.sin(math.tau * (t + sway_phase)) * float(spread) * (0.35 + 0.65 * t)
        px = round(ox + base_off + sway)
        col = alt_color if (alt_color is not None and t > 0.62) else color
        target.surface.put(px, py, col)
        if t < 0.45:
            target.surface.put(px + 1, py, col)


def weather_lightning(
    target: TargetCanvas,
    *,
    color: int,
    glow_color: int | None = None,
    phase: float = 0.0,
    active_window: tuple[float, float] = (0.0, 0.25),
    branches: int = 2,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render a clip-safe jagged lightning bolt inside a window pane during `active_window`."""
    p = _wrap_phase(phase)
    start, end = active_window
    is_active = start <= p < end if start <= end else p >= start or p < end
    if not is_active:
        return

    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        rng = mulberry32(int(seed) ^ 0x11647001)
        u_cur = 0.30 + rng() * 0.40
        v_cur = 0.02
        segments = 6
        pts: list[tuple[float, float]] = [(u_cur, v_cur)]
        for step_idx in range(1, segments + 1):
            v_next = 0.02 + (0.84 * step_idx) / float(segments)
            u_next = max(0.08, min(0.92, u_cur + (rng() - 0.5) * 0.24))
            pts.append((u_next, v_next))
            u_cur, v_cur = u_next, v_next

        branch_segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for _ in range(max(0, int(branches))):
            anchor_idx = 1 + int(rng() * max(1, len(pts) - 2))
            bu0, bv0 = pts[anchor_idx]
            bu1 = max(0.05, min(0.95, bu0 + (-0.18 if rng() < 0.5 else 0.18)))
            bv1 = min(0.95, bv0 + 0.16)
            branch_segs.append(((bu0, bv0), (bu1, bv1)))

        if glow_color is not None:
            for idx in range(len(pts) - 1):
                x0, y0 = pane.project(pts[idx][0], pts[idx][1])
                x1, y1 = pane.project(pts[idx + 1][0], pts[idx + 1][1])
                pane.surface.line(x0 + 1, y0, x1 + 1, y1, glow_color)

        for idx in range(len(pts) - 1):
            x0, y0 = pane.project(pts[idx][0], pts[idx][1])
            x1, y1 = pane.project(pts[idx + 1][0], pts[idx + 1][1])
            pane.surface.line(x0, y0, x1, y1, color)

        for (bu0, bv0), (bu1, bv1) in branch_segs:
            bx0, by0 = pane.project(bu0, bv0)
            bx1, by1 = pane.project(bu1, bv1)
            pane.surface.line(bx0, by0, bx1, by1, color)


def window_condensation(
    target: TargetCanvas,
    *,
    color: int,
    droplet_color: int | None = None,
    edge_thickness: float = 0.18,
    density: float = 0.45,
    droplets: int = 4,
    phase: float = 0.0,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render frosted edge condensation and slow-creeping droplets inside a window pane."""
    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        u = pane.u_grid
        v = pane.v_grid
        edge_dist = np.minimum(np.minimum(u, 1.0 - u), np.minimum(v, 1.0 - v))
        thick = max(1e-4, float(edge_thickness))
        ratio = np.clip(1.0 - edge_dist / thick, 0.0, 1.0) * float(density)
        thresholds = compute_dither_thresholds(
            pane.ox,
            pane.oy,
            pane.ox + pane.width,
            pane.oy + pane.height,
            pattern="bayer4",
        )
        frost_mask = pane.mask & (ratio > 0.0) & (thresholds < ratio)
        pane.surface.data[frost_mask] = int(color)

        if droplets > 0:
            rng = mulberry32(int(seed) ^ 0xC0AD0001)
            p = _wrap_phase(phase)
            drop_col = droplet_color if droplet_color is not None else color
            for _ in range(int(droplets)):
                du = 0.12 + rng() * 0.76
                dv0 = rng()
                dv = 0.10 + ((dv0 + p) % 1.0) * 0.78
                pane.put_uv(du, dv, drop_col)
                pane.put_uv(du, min(0.96, dv + 0.04), drop_col)


def _telemetry_project(
    target: Plane | ClippedPane,
    u: float,
    v: float,
    color: int,
) -> None:
    if isinstance(target, Plane):
        target.dot(u, v, color)
    else:
        target.put_uv(u, v, color)


def _telemetry_line(
    target: Plane | ClippedPane,
    u0: float,
    v0: float,
    u1: float,
    v1: float,
    color: int,
) -> None:
    if isinstance(target, Plane):
        target.line(u0, v0, u1, v1, color)
    else:
        x0, y0 = target.project(u0, v0)
        x1, y1 = target.project(u1, v1)
        target.surface.line(x0, y0, x1, y1, color)


def _telemetry_rect(
    target: Plane | ClippedPane,
    u: float,
    v: float,
    w: float,
    h: float,
    fill: int,
) -> None:
    if isinstance(target, Plane):
        target.rect(u, v, w, h, fill=fill)
    else:
        c00 = target.project(u, v)
        c10 = target.project(u + w, v)
        c11 = target.project(u + w, v + h)
        c01 = target.project(u, v + h)
        target.surface.quad(c00, c10, c11, c01, fill, fill=True)


def _draw_telemetry_body(
    target: Plane | ClippedPane,
    *,
    color: int,
    bg_color: int | None,
    accent: int | None,
    mode: TelemetryMode,
    phase: float,
    samples: int,
    seed: int,
) -> None:
    if bg_color is not None:
        _telemetry_rect(target, 0.0, 0.0, 1.0, 1.0, bg_color)

    rng = mulberry32(int(seed) ^ 0x7E1E0001)
    p = _wrap_phase(phase)
    n = max(3, int(samples))

    if mode == "waveform":
        if accent is not None:
            _telemetry_line(target, 0.06, 0.50, 0.94, 0.50, accent)
        prev_u = 0.08
        prev_v = 0.50 + 0.28 * math.sin(math.tau * p)
        for idx in range(1, n):
            t = idx / float(n - 1)
            u = 0.08 + t * 0.84
            amp = 0.16 + 0.16 * rng()
            v = 0.50 + amp * math.sin(math.tau * (t * 2.0 + p))
            _telemetry_line(target, prev_u, prev_v, u, v, color)
            prev_u, prev_v = u, v
        return

    if mode == "bars":
        bar_span = 0.84 / float(n)
        bar_w = bar_span * 0.65
        for idx in range(n):
            base_h = 0.20 + 0.50 * rng()
            pulse = 0.14 * math.sin(math.tau * (p + idx / float(n)))
            bh = max(0.10, min(0.76, base_h + pulse))
            bu = 0.08 + idx * bar_span
            bv = 0.88 - bh
            _telemetry_rect(target, bu, bv, bar_w, bh, color)
            if accent is not None and bh > 0.52:
                _telemetry_project(target, bu + bar_w * 0.5, bv, accent)
        return

    if mode == "sparkline":
        pts: list[tuple[float, float]] = []
        for idx in range(n):
            t = idx / float(n - 1)
            u = 0.08 + t * 0.84
            jitter = 0.24 * math.sin(math.tau * (p + t * 1.5 + rng()))
            v = max(0.14, min(0.86, 0.50 + jitter))
            pts.append((u, v))
        for idx in range(len(pts) - 1):
            _telemetry_line(
                target, pts[idx][0], pts[idx][1], pts[idx + 1][0], pts[idx + 1][1], color
            )
        if accent is not None:
            for u, v in pts[::2]:
                _telemetry_project(target, u, v, accent)
        return

    if mode == "grid_scan":
        grid_col = accent if accent is not None else color
        _telemetry_line(target, 0.08, 0.50, 0.92, 0.50, grid_col)
        _telemetry_line(target, 0.50, 0.10, 0.50, 0.90, grid_col)
        scan_u = 0.10 + p * 0.80
        _telemetry_line(target, scan_u, 0.12, scan_u, 0.88, color)
        blip_v = 0.25 + 0.50 * rng()
        _telemetry_project(target, scan_u, blip_v, accent if accent is not None else color)
        return

    msg = f"Unsupported telemetry mode: {mode!r}"
    raise ValueError(msg)


def screen_telemetry(
    target: Plane | TargetCanvas,
    *,
    color: int,
    bg_color: int | None = None,
    accent: int | None = None,
    mode: TelemetryMode = "waveform",
    phase: float = 0.0,
    samples: int = 8,
    seed: int = 0,
    region: PaneRegion | None = None,
) -> None:
    """Render animated charts, waveforms, or scanlines inside a `Plane` or `ClippedPane`."""
    if isinstance(target, (Plane, ClippedPane)):
        _draw_telemetry_body(
            target,
            color=color,
            bg_color=bg_color,
            accent=accent,
            mode=mode,
            phase=phase,
            samples=samples,
            seed=seed,
        )
        return

    with _open_pane(target, region) as pane:
        if not np.any(pane.mask):
            return
        _draw_telemetry_body(
            pane,
            color=color,
            bg_color=bg_color,
            accent=accent,
            mode=mode,
            phase=phase,
            samples=samples,
            seed=seed,
        )


__all__ = [
    "ClippedPane",
    "CycleStep",
    "HorizonMode",
    "PaneRegion",
    "PlaneRegion",
    "RectRegion",
    "SkyPreset",
    "TargetCanvas",
    "TelemetryMode",
    "clipped_pane",
    "clouds",
    "day_night_cycle",
    "dust_motes",
    "eval_day_night_cycle",
    "horizon_silhouette",
    "light_beam",
    "moon",
    "point_light_spill",
    "rising_steam",
    "screen_telemetry",
    "sky_backdrop",
    "starfield",
    "sun",
    "weather_lightning",
    "weather_rain",
    "weather_snow",
    "window_condensation",
    "window_light_spill",
]
