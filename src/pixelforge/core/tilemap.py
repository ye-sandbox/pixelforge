"""Vectorized 16-tile cardinal and 47-tile blob autotile generators."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import TRANSPARENT_INDEX, AutotileMode, TilemapSpec

AutotileTarget = Asset[object] | Layer | IndexedSurface
AutotileKind = Literal["wall", "floor", "cable", "terrain"]

CARDINAL_N: Final[int] = 1
CARDINAL_E: Final[int] = 2
CARDINAL_S: Final[int] = 4
CARDINAL_W: Final[int] = 8

BLOB_N: Final[int] = 1
BLOB_NE: Final[int] = 2
BLOB_E: Final[int] = 4
BLOB_SE: Final[int] = 8
BLOB_S: Final[int] = 16
BLOB_SW: Final[int] = 32
BLOB_W: Final[int] = 64
BLOB_NW: Final[int] = 128

CARDINAL16_MASKS: Final[tuple[int, ...]] = tuple(range(16))


def reduce_blob_mask(mask: int) -> int:
    """Strip diagonal bits unless both adjacent cardinal neighbors are present."""
    # INVARIANT: Standard 47-tile blob autotiling ignores diagonal bits when either
    # adjacent cardinal bit is 0, collapsing 256 raw 8-neighbor states into 47 tiles.
    reduced = mask & (BLOB_N | BLOB_E | BLOB_S | BLOB_W)
    if (reduced & (BLOB_N | BLOB_E)) == (BLOB_N | BLOB_E):
        reduced |= mask & BLOB_NE
    if (reduced & (BLOB_S | BLOB_E)) == (BLOB_S | BLOB_E):
        reduced |= mask & BLOB_SE
    if (reduced & (BLOB_S | BLOB_W)) == (BLOB_S | BLOB_W):
        reduced |= mask & BLOB_SW
    if (reduced & (BLOB_N | BLOB_W)) == (BLOB_N | BLOB_W):
        reduced |= mask & BLOB_NW
    return reduced


def canonical_blob47_masks() -> tuple[int, ...]:
    """Return the 47 canonical 8-bit blob autotile bitmasks in ascending order."""
    return tuple(sorted({reduce_blob_mask(raw) for raw in range(256)}))


BLOB47_MASKS: Final[tuple[int, ...]] = canonical_blob47_masks()


@dataclass(frozen=True)
class AutotileStyle:
    """Semantic palette indices for StylePack-agnostic autotile rendering."""

    fill: int
    edge: int
    highlight: int
    shadow: int
    detail: int | None = None
    inner_corner: int | None = None


@dataclass(frozen=True)
class _NeighborFlags:
    n: bool
    ne: bool
    e: bool
    se: bool
    s: bool
    sw: bool
    w: bool
    nw: bool


def _decode_neighbors(mask: int, mode: AutotileMode) -> _NeighborFlags:
    if mode == "cardinal16":
        n = bool(mask & CARDINAL_N)
        e = bool(mask & CARDINAL_E)
        s = bool(mask & CARDINAL_S)
        w = bool(mask & CARDINAL_W)
        return _NeighborFlags(
            n=n,
            ne=n and e,
            e=e,
            se=s and e,
            s=s,
            sw=s and w,
            w=w,
            nw=n and w,
        )
    reduced = reduce_blob_mask(mask)
    return _NeighborFlags(
        n=bool(reduced & BLOB_N),
        ne=bool(reduced & BLOB_NE),
        e=bool(reduced & BLOB_E),
        se=bool(reduced & BLOB_SE),
        s=bool(reduced & BLOB_S),
        sw=bool(reduced & BLOB_SW),
        w=bool(reduced & BLOB_W),
        nw=bool(reduced & BLOB_NW),
    )


def compute_grid_bitmasks(
    grid: NDArray[np.bool_] | Sequence[Sequence[bool]],
    *,
    mode: AutotileMode = "blob47",
    wrap: bool = False,
) -> NDArray[np.int16]:
    """Compute vectorized autotile bitmasks (`-1` for empty cells) for a 2D boolean grid."""
    occ = np.asarray(grid, dtype=bool)
    if occ.ndim != 2:
        msg = f"grid must be 2D, got shape {occ.shape}"
        raise ValueError(msg)
    h, w = occ.shape
    out = np.full((h, w), -1, dtype=np.int16)
    if h == 0 or w == 0:
        return out

    pad_mode = "wrap" if wrap else "constant"
    padded = np.pad(occ, 1, mode=pad_mode)
    n = padded[0:h, 1 : w + 1]
    e = padded[1 : h + 1, 2 : w + 2]
    s = padded[2 : h + 2, 1 : w + 1]
    w_nbr = padded[1 : h + 1, 0:w]

    if mode == "cardinal16":
        masks = (
            n.astype(np.int16) * CARDINAL_N
            + e.astype(np.int16) * CARDINAL_E
            + s.astype(np.int16) * CARDINAL_S
            + w_nbr.astype(np.int16) * CARDINAL_W
        )
    else:
        ne = padded[0:h, 2 : w + 2] & n & e
        se = padded[2 : h + 2, 2 : w + 2] & s & e
        sw = padded[2 : h + 2, 0:w] & s & w_nbr
        nw = padded[0:h, 0:w] & n & w_nbr
        masks = (
            n.astype(np.int16) * BLOB_N
            + ne.astype(np.int16) * BLOB_NE
            + e.astype(np.int16) * BLOB_E
            + se.astype(np.int16) * BLOB_SE
            + s.astype(np.int16) * BLOB_S
            + sw.astype(np.int16) * BLOB_SW
            + w_nbr.astype(np.int16) * BLOB_W
            + nw.astype(np.int16) * BLOB_NW
        )
    out[occ] = masks[occ]
    return out


def _apply_inner_corners(
    buf: NDArray[np.uint8],
    nbr: _NeighborFlags,
    color: int,
    size: int,
) -> None:
    if size <= 0:
        return
    if nbr.n and nbr.e and not nbr.ne:
        buf[:size, -size:] = color
    if nbr.s and nbr.e and not nbr.se:
        buf[-size:, -size:] = color
    if nbr.s and nbr.w and not nbr.sw:
        buf[-size:, :size] = color
    if nbr.n and nbr.w and not nbr.nw:
        buf[:size, :size] = color


def _render_wall_cell(
    tile_w: int,
    tile_h: int,
    nbr: _NeighborFlags,
    style: AutotileStyle,
    seed: int,
) -> NDArray[np.uint8]:
    buf = np.full((tile_h, tile_w), style.fill, dtype=np.uint8)
    bevel = 2 if tile_h >= 12 and tile_w >= 12 else 1

    if not nbr.n:
        buf[: bevel + 1, :] = style.highlight
        buf[0, :] = style.edge
    if not nbr.s:
        buf[-bevel - 1 :, :] = style.shadow
        buf[-1, :] = style.edge
    if not nbr.w:
        buf[:, :bevel] = style.highlight if nbr.n else style.edge
        buf[:, 0] = style.edge
    if not nbr.e:
        buf[:, -bevel:] = style.shadow
        buf[:, -1] = style.edge

    if style.detail is not None and tile_w >= 8 and tile_h >= 8:
        yy, xx = np.ogrid[:tile_h, :tile_w]
        brick_row = (yy % max(4, tile_h // 3)) == (max(4, tile_h // 3) - 1)
        interior = (yy > 1) & (yy < tile_h - 2) & (xx > 1) & (xx < tile_w - 2)
        buf[brick_row & interior & (((xx + seed) % 4) != 0)] = style.detail

    corner_col = style.inner_corner if style.inner_corner is not None else style.edge
    _apply_inner_corners(buf, nbr, corner_col, size=2 if tile_w >= 10 else 1)
    return buf


def _render_floor_cell(
    tile_w: int,
    tile_h: int,
    nbr: _NeighborFlags,
    style: AutotileStyle,
    seed: int,
) -> NDArray[np.uint8]:
    buf = np.full((tile_h, tile_w), style.fill, dtype=np.uint8)
    if style.detail is not None and tile_w >= 6 and tile_h >= 6:
        yy, xx = np.ogrid[:tile_h, :tile_w]
        checker = ((xx + yy + seed) & 1) == 0
        seam = (xx == tile_w // 2) | (yy == tile_h // 2)
        buf[seam & checker] = style.detail

    if not nbr.n:
        buf[1, :] = style.highlight
        buf[0, :] = style.edge
    if not nbr.w:
        buf[:, 1] = style.highlight
        buf[:, 0] = style.edge
    if not nbr.s:
        buf[-2, :] = style.shadow
        buf[-1, :] = style.edge
    if not nbr.e:
        buf[:, -2] = style.shadow
        buf[:, -1] = style.edge

    corner_col = style.inner_corner if style.inner_corner is not None else style.edge
    _apply_inner_corners(buf, nbr, corner_col, size=1)
    return buf


def _render_terrain_cell(
    tile_w: int,
    tile_h: int,
    nbr: _NeighborFlags,
    style: AutotileStyle,
    seed: int,
) -> NDArray[np.uint8]:
    buf = np.full((tile_h, tile_w), style.fill, dtype=np.uint8)
    yy, xx = np.ogrid[:tile_h, :tile_w]
    dither_mask = ((xx * 3 + yy * 5 + seed) % 7) == 0

    if not nbr.n:
        buf[1, :] = style.highlight
        buf[0, :] = style.edge
    if not nbr.w:
        buf[:, 1] = style.highlight
        buf[:, 0] = style.edge
    if not nbr.s:
        buf[-2, :] = style.shadow
        buf[-1, :] = style.edge
    if not nbr.e:
        buf[:, -2] = style.shadow
        buf[:, -1] = style.edge

    if style.detail is not None:
        interior = (xx >= 2) & (xx < tile_w - 2) & (yy >= 2) & (yy < tile_h - 2)
        buf[interior & dither_mask] = style.detail

    if not nbr.n and not nbr.w:
        buf[0, 0] = TRANSPARENT_INDEX
        buf[1, 1] = style.edge
    if not nbr.n and not nbr.e:
        buf[0, -1] = TRANSPARENT_INDEX
        buf[1, -2] = style.edge
    if not nbr.s and not nbr.w:
        buf[-1, 0] = TRANSPARENT_INDEX
        buf[-2, 1] = style.edge
    if not nbr.s and not nbr.e:
        buf[-1, -1] = TRANSPARENT_INDEX
        buf[-2, -2] = style.edge

    corner_col = style.inner_corner if style.inner_corner is not None else style.edge
    _apply_inner_corners(buf, nbr, corner_col, size=2 if tile_w >= 12 else 1)
    return buf


def _render_cable_cell(
    tile_w: int,
    tile_h: int,
    nbr: _NeighborFlags,
    style: AutotileStyle,
) -> NDArray[np.uint8]:
    buf = np.full((tile_h, tile_w), TRANSPARENT_INDEX, dtype=np.uint8)
    cx = tile_w // 2
    cy = tile_h // 2
    half = max(1, min(tile_w, tile_h) // 6)
    y0, y1 = max(0, cy - half), min(tile_h, cy + half + 1)
    x0, x1 = max(0, cx - half), min(tile_w, cx + half + 1)

    def _paint_arm(ax0: int, ax1: int, ay0: int, ay1: int) -> None:
        ey0, ey1 = max(0, ay0 - 1), min(tile_h, ay1 + 1)
        ex0, ex1 = max(0, ax0 - 1), min(tile_w, ax1 + 1)
        region = buf[ey0:ey1, ex0:ex1]
        region[region == TRANSPARENT_INDEX] = style.edge
        buf[ay0:ay1, ax0:ax1] = style.fill
        buf[ay0, ax0:ax1] = style.highlight
        if ay1 - ay0 >= 3:
            buf[ay1 - 1, ax0:ax1] = style.shadow

    _paint_arm(x0, x1, y0, y1)
    if nbr.n:
        _paint_arm(x0, x1, 0, y1)
    if nbr.s:
        _paint_arm(x0, x1, y0, tile_h)
    if nbr.w:
        _paint_arm(0, x1, y0, y1)
    if nbr.e:
        _paint_arm(x0, tile_w, y0, y1)

    if style.detail is not None:
        degree = int(nbr.n) + int(nbr.e) + int(nbr.s) + int(nbr.w)
        if degree <= 1 or degree >= 3:
            buf[cy, cx] = style.detail
    return buf


def render_autotile_cell(
    mask: int,
    tile_w: int,
    tile_h: int,
    *,
    kind: AutotileKind,
    style: AutotileStyle,
    mode: AutotileMode = "blob47",
    seed: int = 0,
) -> IndexedSurface:
    """Render a single deterministic autotile cell for `mask` into an `IndexedSurface`."""
    if tile_w <= 0 or tile_h <= 0:
        msg = f"tile dimensions must be positive, got {tile_w}x{tile_h}"
        raise ValueError(msg)
    nbr = _decode_neighbors(mask, mode)
    if kind == "wall":
        arr = _render_wall_cell(tile_w, tile_h, nbr, style, seed)
    elif kind == "floor":
        arr = _render_floor_cell(tile_w, tile_h, nbr, style, seed)
    elif kind == "cable":
        arr = _render_cable_cell(tile_w, tile_h, nbr, style)
    else:
        arr = _render_terrain_cell(tile_w, tile_h, nbr, style, seed)
    return IndexedSurface(tile_w, tile_h, initial_data=arr)


def _resolve_surface(target: AutotileTarget) -> IndexedSurface:
    if isinstance(target, IndexedSurface):
        return target
    return target.surface


def autotile_sheet(
    target: AutotileTarget,
    *,
    kind: AutotileKind,
    style: AutotileStyle,
    tile_w: int = 16,
    tile_h: int = 16,
    mode: AutotileMode = "blob47",
    columns: int | None = None,
    margin: int = 0,
    spacing: int = 0,
    ox: int = 0,
    oy: int = 0,
    terrain_name: str | None = None,
    seed: int = 0,
) -> TilemapSpec:
    """Render a full 16-tile or 47-tile autotile sheet onto `target` and return `TilemapSpec`."""
    bitmasks = CARDINAL16_MASKS if mode == "cardinal16" else BLOB47_MASKS
    cols = columns if columns is not None else (4 if mode == "cardinal16" else 8)
    if cols <= 0:
        msg = f"columns must be >= 1, got {cols}"
        raise ValueError(msg)
    rows = (len(bitmasks) + cols - 1) // cols

    surface = _resolve_surface(target)
    for idx, mask in enumerate(bitmasks):
        col = idx % cols
        row = idx // cols
        px = ox + margin + col * (tile_w + spacing)
        py = oy + margin + row * (tile_h + spacing)
        cell = render_autotile_cell(
            mask,
            tile_w,
            tile_h,
            kind=kind,
            style=style,
            mode=mode,
            seed=seed + mask,
        )
        surface.blit_layer(cell, px, py)

    return TilemapSpec(
        mode=mode,
        tile_width=tile_w,
        tile_height=tile_h,
        columns=cols,
        rows=rows,
        bitmasks=bitmasks,
        terrain_name=terrain_name or kind,
        margin=margin,
        spacing=spacing,
    )


def autotile_walls(
    target: AutotileTarget,
    style: AutotileStyle,
    *,
    tile_w: int = 16,
    tile_h: int = 16,
    mode: AutotileMode = "blob47",
    columns: int | None = None,
    margin: int = 0,
    spacing: int = 0,
    ox: int = 0,
    oy: int = 0,
    terrain_name: str = "wall",
    seed: int = 0,
) -> TilemapSpec:
    """Render a deterministic wall autotile sheet onto `target`."""
    return autotile_sheet(
        target,
        kind="wall",
        style=style,
        tile_w=tile_w,
        tile_h=tile_h,
        mode=mode,
        columns=columns,
        margin=margin,
        spacing=spacing,
        ox=ox,
        oy=oy,
        terrain_name=terrain_name,
        seed=seed,
    )


def autotile_floors(
    target: AutotileTarget,
    style: AutotileStyle,
    *,
    tile_w: int = 16,
    tile_h: int = 16,
    mode: AutotileMode = "blob47",
    columns: int | None = None,
    margin: int = 0,
    spacing: int = 0,
    ox: int = 0,
    oy: int = 0,
    terrain_name: str = "floor",
    seed: int = 0,
) -> TilemapSpec:
    """Render a deterministic floor autotile sheet onto `target`."""
    return autotile_sheet(
        target,
        kind="floor",
        style=style,
        tile_w=tile_w,
        tile_h=tile_h,
        mode=mode,
        columns=columns,
        margin=margin,
        spacing=spacing,
        ox=ox,
        oy=oy,
        terrain_name=terrain_name,
        seed=seed,
    )


def autotile_cables(
    target: AutotileTarget,
    style: AutotileStyle,
    *,
    tile_w: int = 16,
    tile_h: int = 16,
    mode: AutotileMode = "cardinal16",
    columns: int | None = None,
    margin: int = 0,
    spacing: int = 0,
    ox: int = 0,
    oy: int = 0,
    terrain_name: str = "cable",
    seed: int = 0,
) -> TilemapSpec:
    """Render a deterministic cable/conduit autotile sheet onto `target`."""
    return autotile_sheet(
        target,
        kind="cable",
        style=style,
        tile_w=tile_w,
        tile_h=tile_h,
        mode=mode,
        columns=columns,
        margin=margin,
        spacing=spacing,
        ox=ox,
        oy=oy,
        terrain_name=terrain_name,
        seed=seed,
    )


def autotile_terrain(
    target: AutotileTarget,
    style: AutotileStyle,
    *,
    tile_w: int = 16,
    tile_h: int = 16,
    mode: AutotileMode = "blob47",
    columns: int | None = None,
    margin: int = 0,
    spacing: int = 0,
    ox: int = 0,
    oy: int = 0,
    terrain_name: str = "terrain",
    seed: int = 0,
) -> TilemapSpec:
    """Render a deterministic terrain autotile sheet onto `target`."""
    return autotile_sheet(
        target,
        kind="terrain",
        style=style,
        tile_w=tile_w,
        tile_h=tile_h,
        mode=mode,
        columns=columns,
        margin=margin,
        spacing=spacing,
        ox=ox,
        oy=oy,
        terrain_name=terrain_name,
        seed=seed,
    )
