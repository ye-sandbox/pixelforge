"""Side-by-side + magenta pixel-diff PNG generator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import StylePack
from pixelforge.export.png import rgba_to_png, surface_to_rgba

_GAP: Final[int] = 4
_PADDING: Final[int] = 8
_MAGENTA: Final[tuple[int, int, int, int]] = (255, 42, 133, 255)
_FRAME_BG: Final[tuple[int, int, int, int]] = (13, 17, 23, 255)


@dataclass(frozen=True)
class DiffResult:
    """Pixel-diff summary and 3-panel PNG output (`baseline | current | diff`)."""

    changed_pixels: int
    total_pixels: int
    width: int
    height: int
    png: bytes


def _fill_checker(canvas: NDArray[np.uint8], x0: int, y0: int, w: int, h: int) -> None:
    yy, xx = np.mgrid[0:h, 0:w]
    dark = (((xx >> 2) + (yy >> 2)) & 1) == 0
    patch = np.empty((h, w, 4), dtype=np.uint8)
    patch[dark] = (22, 24, 28, 255)
    patch[~dark] = (30, 32, 36, 255)
    canvas[y0 : y0 + h, x0 : x0 + w] = patch


def _blit_opaque(
    canvas: NDArray[np.uint8],
    src: NDArray[np.uint8],
    dx: int,
    dy: int,
) -> None:
    sh, sw, _ = src.shape
    patch = canvas[dy : dy + sh, dx : dx + sw]
    mask = src[:, :, 3] > 0
    patch[mask] = src[mask]


def generate_pixel_diff(
    baseline: NDArray[np.uint8],
    current: NDArray[np.uint8],
) -> DiffResult:
    """Compare two RGBA arrays into a `(baseline | current | magenta diff)` PNG."""
    if baseline.ndim != 3 or baseline.shape[2] != 4:
        msg = f"Expected (H, W, 4) baseline RGBA array, got shape {baseline.shape}"
        raise ValueError(msg)
    if current.ndim != 3 or current.shape[2] != 4:
        msg = f"Expected (H, W, 4) current RGBA array, got shape {current.shape}"
        raise ValueError(msg)

    bh, bw, _ = baseline.shape
    ch, cw, _ = current.shape
    panel_w = max(bw, cw)
    panel_h = max(bh, ch)

    total_w = _PADDING * 2 + panel_w * 3 + _GAP * 2
    total_h = _PADDING * 2 + panel_h
    canvas = np.empty((total_h, total_w, 4), dtype=np.uint8)
    canvas[:, :] = _FRAME_BG

    base_x = _PADDING
    curr_x = _PADDING + panel_w + _GAP
    diff_x = _PADDING + (panel_w + _GAP) * 2

    _fill_checker(canvas, base_x, _PADDING, panel_w, panel_h)
    _fill_checker(canvas, curr_x, _PADDING, panel_w, panel_h)
    _fill_checker(canvas, diff_x, _PADDING, panel_w, panel_h)

    _blit_opaque(canvas, baseline, base_x, _PADDING)
    _blit_opaque(canvas, current, curr_x, _PADDING)

    padded_base = np.zeros((panel_h, panel_w, 4), dtype=np.uint8)
    padded_curr = np.zeros((panel_h, panel_w, 4), dtype=np.uint8)
    padded_base[:bh, :bw] = baseline
    padded_curr[:ch, :cw] = current

    diff_mask = np.any(padded_base != padded_curr, axis=2)
    changed_pixels = int(np.count_nonzero(diff_mask))

    diff_panel = canvas[_PADDING : _PADDING + panel_h, diff_x : diff_x + panel_w]
    unchanged_opaque = (~diff_mask) & (padded_curr[:, :, 3] > 0)
    diff_panel[unchanged_opaque, :3] = padded_curr[unchanged_opaque, :3] >> 2
    diff_panel[unchanged_opaque, 3] = 255
    diff_panel[diff_mask] = _MAGENTA

    return DiffResult(
        changed_pixels=changed_pixels,
        total_pixels=panel_w * panel_h,
        width=total_w,
        height=total_h,
        png=rgba_to_png(canvas),
    )


def generate_surface_diff(
    baseline: IndexedSurface,
    current: IndexedSurface,
    style: StylePack,
    *,
    variant: str | None = None,
    scale: int = 1,
) -> DiffResult:
    """Render and diff two `IndexedSurface` buffers under a common `StylePack`."""
    base_rgba = surface_to_rgba(baseline, style, variant=variant, scale=scale)
    curr_rgba = surface_to_rgba(current, style, variant=variant, scale=scale)
    return generate_pixel_diff(base_rgba, curr_rgba)
