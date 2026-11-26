"""Derived 2D normal and height map tracking for compositional pixel surfaces."""

from __future__ import annotations

import math
from collections.abc import Generator
from contextlib import contextmanager
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray

MirrorSource = Literal["left", "right"]

Normal3D = tuple[float, float, float]

# INVARIANT: Camera-space right-handed normals (+X right, +Y up, +Z toward camera).
# The three canonical 2:1 isometric face normals are mutually orthogonal unit vectors.
NORMAL_FLAT: Final[Normal3D] = (0.0, 0.0, 1.0)
NORMAL_ISO_TOP: Final[Normal3D] = (0.0, math.sqrt(2.0 / 3.0), math.sqrt(1.0 / 3.0))
NORMAL_ISO_LEFT: Final[Normal3D] = (
    -math.sqrt(0.5),
    -math.sqrt(1.0 / 6.0),
    math.sqrt(1.0 / 3.0),
)
NORMAL_ISO_RIGHT: Final[Normal3D] = (
    math.sqrt(0.5),
    -math.sqrt(1.0 / 6.0),
    math.sqrt(1.0 / 3.0),
)
NORMAL_FRONT_DOWN: Final[Normal3D] = (0.0, -math.sqrt(2.0 / 3.0), math.sqrt(1.0 / 3.0))


def normalize_normal(nx: float, ny: float, nz: float) -> Normal3D:
    """Return a unit 3D normal vector, falling back to `(0, 0, 1)` for degenerate inputs."""
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-8:
        return NORMAL_FLAT
    return (nx / length, ny / length, nz / length)


def infer_plane_normal(
    u_vec: tuple[float, float],
    v_vec: tuple[float, float],
) -> Normal3D:
    """Infer a plausible camera-space 3D normal from a `Plane`'s screen `(u, v)` basis."""
    ux, uy = float(u_vec[0]), float(u_vec[1])
    vx, vy = float(v_vec[0]), float(v_vec[1])
    u_len = math.hypot(ux, uy)
    v_len = math.hypot(vx, vy)
    if u_len < 1e-6 or v_len < 1e-6:
        return NORMAL_FLAT

    # Axis-aligned orthographic plane -> flat camera-facing normal.
    if (abs(uy) < 1e-6 and abs(vx) < 1e-6) or (abs(ux) < 1e-6 and abs(vy) < 1e-6):
        return NORMAL_FLAT

    # Vertical wall plane (one basis axis is vertical on screen).
    if abs(vx) < 1e-6 or abs(ux) < 1e-6:
        hx, hy = (ux, uy) if abs(vx) < 1e-6 else (vx, vy)
        if hx < 0:
            hx, hy = -hx, -hy
        slope = hy / max(abs(hx), 1e-6)
        if abs(slope) < 1e-6:
            return NORMAL_FLAT
        tilt = min(1.0, abs(slope) / 0.5)
        nx = (-1.0 if slope > 0 else 1.0) * math.sqrt(0.5) * tilt
        ny = -math.sqrt(1.0 / 6.0) * tilt
        nz = math.sqrt(max(0.0, 1.0 - nx * nx - ny * ny))
        return normalize_normal(nx, ny, nz)

    # Isometric diamond / horizontal top plane: basis vectors diverge in X and share Y sign.
    if ux * vx < 0 and uy * vy > 0:
        return NORMAL_ISO_TOP

    # General angled/tilted plane (e.g., tilted laptop lid or angled roof).
    ny = max(
        -0.85,
        min(
            0.85,
            0.5 * (abs(uy) / u_len + abs(vx) / v_len) * NORMAL_ISO_TOP[1],
        ),
    )
    nx = max(-0.5, min(0.5, -0.5 * (uy / max(abs(ux), 1.0))))
    nz = math.sqrt(max(0.05, 1.0 - nx * nx - ny * ny))
    return normalize_normal(nx, ny, nz)


class SurfaceMaps:
    """Companion `(H, W, 3)` normal and `(H, W)` height buffers for `IndexedSurface`."""

    width: int
    height: int
    normals: NDArray[np.float32]
    height_data: NDArray[np.float32]
    active_normal: Normal3D
    active_height: float
    height_plane: tuple[float, float, float, float, float] | None

    def __init__(
        self,
        width: int,
        height: int,
        *,
        normals: NDArray[np.float32] | None = None,
        height_data: NDArray[np.float32] | None = None,
    ) -> None:
        self.width = int(width)
        self.height = int(height)
        if normals is not None:
            self.normals = np.array(normals, dtype=np.float32, copy=True)
        else:
            self.normals = np.zeros((self.height, self.width, 3), dtype=np.float32)
            self.normals[..., 2] = 1.0

        if height_data is not None:
            self.height_data = np.array(height_data, dtype=np.float32, copy=True)
        else:
            self.height_data = np.zeros((self.height, self.width), dtype=np.float32)

        self.active_normal = NORMAL_FLAT
        self.active_height = 0.0
        self.height_plane = None

    def clone(self) -> SurfaceMaps:
        """Return an independent deep copy of these surface maps."""
        return SurfaceMaps(
            self.width,
            self.height,
            normals=self.normals,
            height_data=self.height_data,
        )

    @contextmanager
    def normal_scope(self, normal: Normal3D) -> Generator[None]:
        """Temporarily set the active 3D surface normal for subsequent draws."""
        prev = self.active_normal
        self.active_normal = normalize_normal(*normal)
        try:
            yield
        finally:
            self.active_normal = prev

    @contextmanager
    def height_scope(self, height: float) -> Generator[None]:
        """Temporarily set a constant surface height for subsequent draws."""
        prev_h = self.active_height
        prev_plane = self.height_plane
        self.active_height = float(height)
        self.height_plane = None
        try:
            yield
        finally:
            self.active_height = prev_h
            self.height_plane = prev_plane

    @contextmanager
    def height_plane_scope(
        self,
        hx: float,
        hy: float,
        c: float,
        min_h: float,
        max_h: float,
    ) -> Generator[None]:
        """Temporarily set a clamped linear height plane `hx*x + hy*y + c`."""
        prev_plane = self.height_plane
        self.height_plane = (float(hx), float(hy), float(c), float(min_h), float(max_h))
        try:
            yield
        finally:
            self.height_plane = prev_plane

    def _eval_height_pixel(self, x: int, y: int) -> float:
        if self.height_plane is None:
            return self.active_height
        hx, hy, c, lo, hi = self.height_plane
        val = hx * x + hy * y + c
        return max(lo, min(hi, val))

    def _eval_height_grid(self, x0: int, y0: int, x1: int, y1: int) -> NDArray[np.float32] | float:
        if self.height_plane is None:
            return self.active_height
        hx, hy, c, lo, hi = self.height_plane
        yy, xx = np.mgrid[y0:y1, x0:x1]
        vals = hx * xx.astype(np.float32) + hy * yy.astype(np.float32) + c
        return np.clip(vals, lo, hi).astype(np.float32)

    def clear(self, *, erase: bool) -> None:
        """Reset normal and height buffers on full-surface clear."""
        if erase:
            self.normals[..., 0] = 0.0
            self.normals[..., 1] = 0.0
            self.normals[..., 2] = 1.0
            self.height_data.fill(0.0)
        else:
            self.normals[...] = self.active_normal
            self.height_data[...] = self._eval_height_grid(0, 0, self.width, self.height)

    def write_pixel(self, x: int, y: int, *, erase: bool = False) -> None:
        """Update normal and height for a single in-bounds pixel."""
        if erase:
            self.normals[y, x] = NORMAL_FLAT
            self.height_data[y, x] = 0.0
        else:
            self.normals[y, x] = self.active_normal
            self.height_data[y, x] = self._eval_height_pixel(x, y)

    def write_span(self, start: int, end: int, y: int, *, erase: bool = False) -> None:
        """Update normal and height across an inclusive horizontal span `[start, end]`."""
        if erase:
            self.normals[y, start : end + 1] = NORMAL_FLAT
            self.height_data[y, start : end + 1] = 0.0
            return
        self.normals[y, start : end + 1] = self.active_normal
        if self.height_plane is None:
            self.height_data[y, start : end + 1] = self.active_height
        else:
            hx, hy, c, lo, hi = self.height_plane
            xs = np.arange(start, end + 1, dtype=np.float32)
            self.height_data[y, start : end + 1] = np.clip(hx * xs + hy * y + c, lo, hi)

    def write_rect(self, x0: int, y0: int, x1: int, y1: int, *, erase: bool = False) -> None:
        """Update normal and height over `[x0, x1) x [y0, y1)`."""
        if erase:
            self.normals[y0:y1, x0:x1] = NORMAL_FLAT
            self.height_data[y0:y1, x0:x1] = 0.0
            return
        self.normals[y0:y1, x0:x1] = self.active_normal
        self.height_data[y0:y1, x0:x1] = self._eval_height_grid(x0, y0, x1, y1)

    def write_region_mask(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        mask: NDArray[np.bool_],
        *,
        erase: bool = False,
    ) -> None:
        """Update normal and height where `mask` is True inside `[x0, x1) x [y0, y1)`."""
        if not np.any(mask):
            return
        n_region = self.normals[y0:y1, x0:x1]
        h_region = self.height_data[y0:y1, x0:x1]
        if erase:
            n_region[mask] = NORMAL_FLAT
            h_region[mask] = 0.0
            return
        n_region[mask] = self.active_normal
        grid = self._eval_height_grid(x0, y0, x1, y1)
        if isinstance(grid, np.ndarray):
            h_region[mask] = grid[mask]
        else:
            h_region[mask] = grid

    def write_global_mask(self, mask: NDArray[np.bool_], *, erase: bool = False) -> None:
        """Update normal and height across the full surface where `mask` is True."""
        self.write_region_mask(0, 0, self.width, self.height, mask, erase=erase)

    def blit(
        self,
        src: SurfaceMaps,
        opaque: NDArray[np.bool_],
        sx0: int,
        sy0: int,
        tx0: int,
        ty0: int,
        copy_w: int,
        copy_h: int,
        *,
        z_offset: float = 0.0,
    ) -> None:
        """Composite `src` normal and height maps onto `self` over opaque pixels."""
        src_n = src.normals[sy0 : sy0 + copy_h, sx0 : sx0 + copy_w]
        dst_n = self.normals[ty0 : ty0 + copy_h, tx0 : tx0 + copy_w]
        dst_n[opaque] = src_n[opaque]

        src_h = src.height_data[sy0 : sy0 + copy_h, sx0 : sx0 + copy_w]
        dst_h = self.height_data[ty0 : ty0 + copy_h, tx0 : tx0 + copy_w]
        dst_h[opaque] = src_h[opaque] + float(z_offset)

    def mirror_x(self, source: MirrorSource) -> None:
        """Mirror normals (negating `nx`) and height horizontally."""
        half = self.width // 2
        if half <= 0:
            return
        if source == "left":
            mirrored_n = self.normals[:, half - 1 :: -1, :].copy()
            mirrored_n[..., 0] = -mirrored_n[..., 0]
            self.normals[:, self.width - half :, :] = mirrored_n
            self.height_data[:, self.width - half :] = self.height_data[:, half - 1 :: -1]
        else:
            mirrored_n = self.normals[:, self.width - 1 : self.width - half - 1 : -1, :].copy()
            mirrored_n[..., 0] = -mirrored_n[..., 0]
            self.normals[:, :half, :] = mirrored_n
            self.height_data[:, :half] = self.height_data[
                :, self.width - 1 : self.width - half - 1 : -1
            ]

    def flip_x(self) -> None:
        """Flip normals (negating `nx`) and height horizontally in-place."""
        self.normals[:] = self.normals[:, ::-1, :]
        self.normals[..., 0] = -self.normals[..., 0]
        self.height_data[:] = self.height_data[:, ::-1]

    def flip_y(self) -> None:
        """Flip normals (negating `ny`) and height vertically in-place."""
        self.normals[:] = self.normals[::-1, :, :]
        self.normals[..., 1] = -self.normals[..., 1]
        self.height_data[:] = self.height_data[::-1, :]
