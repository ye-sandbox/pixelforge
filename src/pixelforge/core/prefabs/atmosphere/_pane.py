"""Clipped pane buffer, region types, and shared atmospheric constants."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from types import TracebackType
from typing import Literal, Self

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.plane import Point2D
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import TRANSPARENT_INDEX

Canvas = Asset | Layer
RectRegion = tuple[int | float, int | float, int | float, int | float]
PlaneRegion = tuple[Point2D, Point2D, Point2D]
PaneRegion = RectRegion | PlaneRegion
SkyPreset = Literal["day", "dusk", "cycle", "starry_night", "full_moon", "rain", "snow"]
HorizonMode = Literal["city", "hills", "trees", "rooftops", "industrial", "mountains"]
TelemetryMode = Literal["waveform", "bars", "sparkline", "grid_scan"]


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
def open_pane(
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


def wrap_phase(phase: float) -> float:
    return float(phase) % 1.0
