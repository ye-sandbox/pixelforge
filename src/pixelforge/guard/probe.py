"""Exact pixel, layer, token histogram, and orphan-pixel diagnostics (`pixelforge probe`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.builder import Asset, LayerDiagnostic
from pixelforge.core.surface import orphan_pixel_mask
from pixelforge.core.types import (
    TRANSPARENT_INDEX,
    AnchorPoint,
    HitboxRect,
    PaletteColor,
    StylePack,
)
from pixelforge.export.bundle import LoadedAsset

# INVARIANT: '.' is reserved exclusively for TRANSPARENT_INDEX (255) in ASCII slices.
_ASCII_SYMBOLS: Final[str] = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*+=?~"
)
_DEFAULT_FULL_CANVAS_MAX_DIM: Final[int] = 64


@dataclass(frozen=True)
class TokenUsageEntry:
    """Actual pixel count and percentage for a single palette token in a rendered frame."""

    index: int
    name: str
    hex: str
    flags: tuple[str, ...]
    emissive: bool
    count: int
    pct: float


@dataclass(frozen=True)
class AsciiLegendEntry:
    """Mapping between an ASCII slice character and its StylePack palette token."""

    symbol: str
    index: int
    name: str
    hex: str
    flags: tuple[str, ...]
    emissive: bool


@dataclass(frozen=True)
class RegionSlice:
    """Token-mapped ASCII pixel grid for a rectangular `(x, y, w, h)` canvas slice."""

    x: int
    y: int
    w: int
    h: int
    rows: tuple[str, ...]
    legend: tuple[AsciiLegendEntry, ...]


@dataclass(frozen=True)
class AssetProbeReport:
    """Complete deterministic pixel, layer, histogram, and orphan report for one asset frame."""

    asset_id: str
    style_id: str
    state: str
    frame: int
    width: int
    height: int
    opaque_pixels: int
    total_pixels: int
    coverage_pct: float
    opaque_bbox: tuple[int, int, int, int] | None
    region: RegionSlice
    histogram: tuple[TokenUsageEntry, ...]
    orphan_pixels: tuple[tuple[int, int], ...]
    layers: tuple[LayerDiagnostic, ...]
    anchors: tuple[AnchorPoint, ...]
    hitboxes: tuple[HitboxRect, ...]


def parse_region(region_str: str, width: int, height: int) -> tuple[int, int, int, int]:
    """Parse and bounds-check an `x,y,w,h` region specification against `(width, height)`."""
    parts = [part.strip() for part in region_str.split(",")]
    if len(parts) != 4:
        msg = f"Invalid --region {region_str!r}; expected 'x,y,w,h' (4 integers)"
        raise ValueError(msg)
    try:
        rx, ry, rw, rh = (int(part) for part in parts)
    except ValueError as exc:
        msg = f"Invalid --region {region_str!r}; coordinates must be integers"
        raise ValueError(msg) from exc

    if rw <= 0 or rh <= 0:
        msg = f"Invalid --region {region_str!r}; width and height must be positive"
        raise ValueError(msg)
    if rx < 0 or ry < 0 or rx + rw > width or ry + rh > height:
        msg = (
            f"Region ({rx}, {ry}, {rw}, {rh}) out of bounds for "
            f"{width}x{height} canvas [0..{width})x[0..{height})"
        )
        raise ValueError(msg)
    return (rx, ry, rw, rh)


def _compute_opaque_bbox(data: NDArray[np.uint8]) -> tuple[tuple[int, int, int, int] | None, int]:
    ys, xs = np.nonzero(data != TRANSPARENT_INDEX)
    count = len(xs)
    if count == 0:
        return (None, 0)
    min_x = int(xs.min())
    max_x = int(xs.max())
    min_y = int(ys.min())
    max_y = int(ys.max())
    return ((min_x, min_y, max_x - min_x + 1, max_y - min_y + 1), count)


def _resolve_palette_entry(style_by_index: dict[int, PaletteColor], index: int) -> PaletteColor:
    entry = style_by_index.get(index)
    if entry is not None:
        return entry
    return PaletteColor(index=index, name=f"UNDECLARED_{index}", hex="#000000", flags=())


def _build_histogram(
    data: NDArray[np.uint8],
    style_by_index: dict[int, PaletteColor],
    opaque_pixels: int,
) -> tuple[TokenUsageEntry, ...]:
    unique_vals, counts = np.unique(data, return_counts=True)
    entries: list[TokenUsageEntry] = []
    for raw_idx, raw_count in zip(unique_vals.tolist(), counts.tolist(), strict=True):
        idx = int(raw_idx)
        if idx == TRANSPARENT_INDEX:
            continue
        count = int(raw_count)
        entry = _resolve_palette_entry(style_by_index, idx)
        pct = round((count / opaque_pixels) * 100.0, 2) if opaque_pixels > 0 else 0.0
        entries.append(
            TokenUsageEntry(
                index=idx,
                name=entry.name,
                hex=entry.hex,
                flags=entry.flags,
                emissive="emissive" in entry.flags,
                count=count,
                pct=pct,
            )
        )
    entries.sort(key=lambda item: (-item.count, item.index))
    return tuple(entries)


def _build_region_slice(
    data: NDArray[np.uint8],
    region: tuple[int, int, int, int],
    style_by_index: dict[int, PaletteColor],
) -> RegionSlice:
    rx, ry, rw, rh = region
    patch = data[ry : ry + rh, rx : rx + rw]
    used_indices = sorted(int(v) for v in np.unique(patch).tolist() if int(v) != TRANSPARENT_INDEX)

    symbol_map: dict[int, str] = {}
    legend: list[AsciiLegendEntry] = []
    for pos, idx in enumerate(used_indices):
        symbol = _ASCII_SYMBOLS[pos] if pos < len(_ASCII_SYMBOLS) else "?"
        symbol_map[idx] = symbol
        entry = _resolve_palette_entry(style_by_index, idx)
        legend.append(
            AsciiLegendEntry(
                symbol=symbol,
                index=idx,
                name=entry.name,
                hex=entry.hex,
                flags=entry.flags,
                emissive="emissive" in entry.flags,
            )
        )

    rows: list[str] = []
    for row_vals in patch.tolist():
        chars = ["." if int(val) == TRANSPARENT_INDEX else symbol_map[int(val)] for val in row_vals]
        rows.append("".join(chars))

    return RegionSlice(
        x=rx,
        y=ry,
        w=rw,
        h=rh,
        rows=tuple(rows),
        legend=tuple(legend),
    )


def _default_region(
    width: int,
    height: int,
    opaque_bbox: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int]:
    if width <= _DEFAULT_FULL_CANVAS_MAX_DIM and height <= _DEFAULT_FULL_CANVAS_MAX_DIM:
        return (0, 0, width, height)
    if opaque_bbox is not None:
        return opaque_bbox
    return (
        0,
        0,
        min(width, _DEFAULT_FULL_CANVAS_MAX_DIM),
        min(height, _DEFAULT_FULL_CANVAS_MAX_DIM),
    )


def probe_asset(
    loaded: LoadedAsset,
    style: StylePack,
    *,
    state: str | None = None,
    frame: int = 0,
    region: tuple[int, int, int, int] | None = None,
) -> AssetProbeReport:
    """Render one `(state, frame)` with layer tracking and return exact pixel diagnostics."""
    asset = Asset(loaded.SPEC, style, state=state, frame=frame, track_layers=True)
    loaded.render(asset)

    surf = asset.root_surface
    opaque_bbox, opaque_pixels = _compute_opaque_bbox(surf.data)
    total_pixels = loaded.SPEC.width * loaded.SPEC.height
    coverage_pct = round((opaque_pixels / total_pixels) * 100.0, 2) if total_pixels > 0 else 0.0

    resolved_region = (
        region
        if region is not None
        else _default_region(loaded.SPEC.width, loaded.SPEC.height, opaque_bbox)
    )
    style_by_index = {entry.index: entry for entry in style.palette}
    region_slice = _build_region_slice(surf.data, resolved_region, style_by_index)
    histogram = _build_histogram(surf.data, style_by_index, opaque_pixels)

    ys, xs = np.nonzero(orphan_pixel_mask(surf))
    orphans = tuple((int(x), int(y)) for y, x in zip(ys.tolist(), xs.tolist(), strict=True))

    return AssetProbeReport(
        asset_id=loaded.SPEC.id,
        style_id=style.id,
        state=asset.state,
        frame=asset.frame,
        width=loaded.SPEC.width,
        height=loaded.SPEC.height,
        opaque_pixels=opaque_pixels,
        total_pixels=total_pixels,
        coverage_pct=coverage_pct,
        opaque_bbox=opaque_bbox,
        region=region_slice,
        histogram=histogram,
        orphan_pixels=orphans,
        layers=asset.layer_diagnostics,
        anchors=asset.anchors,
        hitboxes=asset.hitboxes,
    )
