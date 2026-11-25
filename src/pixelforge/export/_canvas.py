"""Shared RGBA checkerboard and compositing helpers for diagnostic exports."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

Rgb = tuple[int, int, int]


def draw_checkerboard(
    canvas: NDArray[np.uint8],
    x: int,
    y: int,
    w: int,
    h: int,
    color_a: Rgb,
    color_b: Rgb,
    tile: int = 4,
) -> None:
    """Fill a rectangular region on an RGBA canvas with a 2-tone checkerboard."""
    if w <= 0 or h <= 0:
        return
    yy, xx = np.mgrid[0:h, 0:w]
    even = (((xx // tile) + (yy // tile)) & 1) == 0
    patch = np.empty((h, w, 4), dtype=np.uint8)
    patch[even] = (*color_a, 255)
    patch[~even] = (*color_b, 255)
    canvas[y : y + h, x : x + w] = patch


def composite_rgba(
    canvas: NDArray[np.uint8],
    src: NDArray[np.uint8],
    dx: int,
    dy: int,
) -> None:
    """Composite non-transparent pixels of `src` onto `canvas` at `(dx, dy)` with clipping."""
    sh, sw, _ = src.shape
    ch, cw, _ = canvas.shape
    sx0 = max(0, -dx)
    sy0 = max(0, -dy)
    tx0 = max(0, dx)
    ty0 = max(0, dy)
    copy_w = min(sw - sx0, cw - tx0)
    copy_h = min(sh - sy0, ch - ty0)
    if copy_w <= 0 or copy_h <= 0:
        return
    src_patch = src[sy0 : sy0 + copy_h, sx0 : sx0 + copy_w]
    dst_patch = canvas[ty0 : ty0 + copy_h, tx0 : tx0 + copy_w]
    mask = src_patch[:, :, 3] > 0
    dst_patch[mask] = src_patch[mask]
