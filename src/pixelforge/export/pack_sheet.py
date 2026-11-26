"""Comparative 1x + 2x batch pack `.contact.png` generator and cross-asset consistency metrics."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.palette import hex_to_rgb
from pixelforge.core.surface import IndexedSurface, orphan_pixel_mask
from pixelforge.core.types import TRANSPARENT_INDEX, AssetSpec, StylePack
from pixelforge.export._canvas import Rgb, composite_rgba, draw_checkerboard
from pixelforge.export._font import draw_bitmap_text, fill_rgba_rect, measure_text
from pixelforge.export.png import rgba_to_png, surface_to_rgba

_BG_MAIN: Final[Rgb] = (18, 22, 29)
_BG_HEADER: Final[Rgb] = (28, 34, 45)
_BG_CELL: Final[Rgb] = (22, 27, 36)
_BORDER_SUBTLE: Final[Rgb] = (48, 56, 70)
_TEXT_LIGHT: Final[Rgb] = (230, 237, 243)
_TEXT_MUTED: Final[Rgb] = (139, 148, 158)
_TEXT_OK: Final[Rgb] = (86, 211, 100)
_TEXT_WARN: Final[Rgb] = (248, 189, 73)
_CHECK_DARK_A: Final[Rgb] = (13, 17, 23)
_CHECK_DARK_B: Final[Rgb] = (24, 30, 40)

_MAX_LUMINANCE_SPREAD: Final[float] = 0.35
_MAX_OUTLINE_SPREAD_PCT: Final[float] = 45.0
_MAX_SIZE_RATIO: Final[float] = 4.0


@dataclass(frozen=True)
class PackSheetEntry:
    """Single rendered asset entry included in a batch pack contact sheet."""

    spec: AssetSpec
    style: StylePack
    surface: IndexedSurface
    source_path: Path | None = None


@dataclass(frozen=True)
class PackSheetOptions:
    """Configuration options for `generate_pack_sheet`."""

    variant: str | None = None
    title: str | None = None
    columns: int | None = None


@dataclass(frozen=True)
class PackAssetMetrics:
    """Per-asset scale, lighting, and outline metrics for pack comparison."""

    id: str
    style_id: str
    perspective: str
    lighting_angle: str
    width: int
    height: int
    bbox: tuple[int, int, int, int] | None
    opaque_pixels: int
    coverage_pct: float
    orphan_pixels: int
    mean_luminance: float
    light_bias_tl: float
    outline_coverage_pct: float


@dataclass(frozen=True)
class PackConsistencyMetrics:
    """Cross-asset scale, lighting, and outline consistency metrics."""

    asset_count: int
    style_ids: tuple[str, ...]
    perspectives: tuple[str, ...]
    lighting_angles: tuple[str, ...]
    min_size: tuple[int, int]
    max_size: tuple[int, int]
    bbox_height_range: tuple[int, int]
    luminance_range: tuple[float, float]
    luminance_spread: float
    light_bias_range: tuple[float, float]
    outline_coverage_range: tuple[float, float]
    outline_spread_pct: float
    orphan_total: int
    scale_consistent: bool
    lighting_consistent: bool
    outline_consistent: bool
    warnings: tuple[str, ...]
    assets: tuple[PackAssetMetrics, ...]


@dataclass(frozen=True)
class PackSheetResult:
    """Generated batch pack contact sheet RGBA buffer, PNG bytes, and metrics."""

    width: int
    height: int
    rgba: NDArray[np.uint8]
    png: bytes
    metrics: PackConsistencyMetrics


def _style_luminance_lut(style: StylePack, variant: str | None) -> NDArray[np.float32]:
    lut = np.zeros(256, dtype=np.float32)
    overrides = style.variants.get(variant, {}) if variant else {}
    for color in style.palette:
        hex_val = overrides.get(color.name, color.hex)
        r, g, b = hex_to_rgb(hex_val)
        lut[color.index] = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    return lut


def _compute_light_bias_tl(
    lum_map: NDArray[np.float32],
    opaque: NDArray[np.bool_],
    bbox: tuple[int, int, int, int],
) -> float:
    bx, by, bw, bh = bbox
    if bw <= 1 and bh <= 1:
        return 0.0
    sub_opaque = opaque[by : by + bh, bx : bx + bw]
    sub_lum = lum_map[by : by + bh, bx : bx + bw]
    yy, xx = np.mgrid[0:bh, 0:bw]
    nx = xx / max(1, bw - 1)
    ny = yy / max(1, bh - 1)
    diag = nx + ny
    tl_mask = sub_opaque & (diag < 1.0)
    br_mask = sub_opaque & (diag > 1.0)
    if not np.any(tl_mask) or not np.any(br_mask):
        return 0.0
    return round(float(sub_lum[tl_mask].mean() - sub_lum[br_mask].mean()), 3)


def _compute_outline_coverage(surface: IndexedSurface, style: StylePack) -> float:
    opaque = surface.data != TRANSPARENT_INDEX
    if not np.any(opaque):
        return 0.0
    outline_indices: set[int] = {style.outline_index}
    for color in style.palette:
        if "outline" in color.flags:
            outline_indices.add(color.index)
    if not outline_indices:
        return 0.0

    padded = np.pad(opaque, 1, mode="constant", constant_values=False)
    has_transparent_neighbor = (
        ~padded[:-2, 1:-1] | ~padded[2:, 1:-1] | ~padded[1:-1, :-2] | ~padded[1:-1, 2:]
    )
    boundary = opaque & has_transparent_neighbor
    boundary_count = int(np.count_nonzero(boundary))
    if boundary_count == 0:
        return 0.0

    outline_mask = np.isin(surface.data, sorted(outline_indices))
    outline_boundary = int(np.count_nonzero(boundary & outline_mask))
    return round((outline_boundary / boundary_count) * 100.0, 1)


def compute_pack_asset_metrics(
    entry: PackSheetEntry,
    *,
    variant: str | None = None,
) -> PackAssetMetrics:
    """Compute per-asset scale, luminance, and outline metrics for a pack entry."""
    surf = entry.surface
    opaque = surf.data != TRANSPARENT_INDEX
    opaque_count = int(np.count_nonzero(opaque))
    total_pixels = surf.width * surf.height
    coverage = round((opaque_count / total_pixels) * 100.0, 1) if total_pixels > 0 else 0.0
    orphans = int(np.count_nonzero(orphan_pixel_mask(surf)))
    outline_pct = _compute_outline_coverage(surf, entry.style)

    if opaque_count == 0:
        return PackAssetMetrics(
            id=entry.spec.id,
            style_id=entry.style.id,
            perspective=entry.spec.perspective,
            lighting_angle=entry.style.lighting_angle,
            width=surf.width,
            height=surf.height,
            bbox=None,
            opaque_pixels=0,
            coverage_pct=0.0,
            orphan_pixels=0,
            mean_luminance=0.0,
            light_bias_tl=0.0,
            outline_coverage_pct=0.0,
        )

    ys, xs = np.nonzero(opaque)
    min_x, max_x = int(xs.min()), int(xs.max())
    min_y, max_y = int(ys.min()), int(ys.max())
    bbox = (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)

    lum_lut = _style_luminance_lut(entry.style, variant)
    lum_map = lum_lut[surf.data]
    mean_lum = round(float(lum_map[opaque].mean()), 3)
    light_bias = _compute_light_bias_tl(lum_map, opaque, bbox)

    return PackAssetMetrics(
        id=entry.spec.id,
        style_id=entry.style.id,
        perspective=entry.spec.perspective,
        lighting_angle=entry.style.lighting_angle,
        width=surf.width,
        height=surf.height,
        bbox=bbox,
        opaque_pixels=opaque_count,
        coverage_pct=coverage,
        orphan_pixels=orphans,
        mean_luminance=mean_lum,
        light_bias_tl=light_bias,
        outline_coverage_pct=outline_pct,
    )


def _collect_consistency_warnings(
    asset_metrics: tuple[PackAssetMetrics, ...],
    perspectives: tuple[str, ...],
    lighting_angles: tuple[str, ...],
    min_size: tuple[int, int],
    max_size: tuple[int, int],
    lum_spread: float,
    bias_range: tuple[float, float],
    outline_spread: float,
    orphan_total: int,
) -> tuple[bool, bool, bool, tuple[str, ...]]:
    warnings: list[str] = []
    scale_ok = len(perspectives) <= 1
    if not scale_ok:
        warnings.append(f"mixed perspectives: {', '.join(perspectives)}")
    if len(asset_metrics) > 1:
        w_ratio = max_size[0] / max(1, min_size[0])
        h_ratio = max_size[1] / max(1, min_size[1])
        if w_ratio > _MAX_SIZE_RATIO or h_ratio > _MAX_SIZE_RATIO:
            scale_ok = False
            warnings.append(
                f"wide scale ratio ({min_size[0]}x{min_size[1]}..{max_size[0]}x{max_size[1]})"
            )

    lighting_ok = len(lighting_angles) <= 1 and lum_spread <= _MAX_LUMINANCE_SPREAD
    if len(lighting_angles) > 1:
        warnings.append(f"mixed lighting angles: {', '.join(lighting_angles)}")
    if lum_spread > _MAX_LUMINANCE_SPREAD:
        warnings.append(f"wide luminance spread ({lum_spread:.2f})")
    if bias_range[0] < -0.08 and bias_range[1] > 0.08:
        lighting_ok = False
        warnings.append(f"conflicting light bias ({bias_range[0]:+.2f}..{bias_range[1]:+.2f})")

    outline_ok = outline_spread <= _MAX_OUTLINE_SPREAD_PCT
    if not outline_ok:
        warnings.append(f"outline coverage spread {outline_spread:.1f}%")
    if orphan_total > 0:
        warnings.append(f"{orphan_total} orphan pixel(s)")

    return (scale_ok, lighting_ok, outline_ok, tuple(warnings))


def compute_pack_consistency_metrics(
    entries: Sequence[PackSheetEntry],
    *,
    variant: str | None = None,
) -> PackConsistencyMetrics:
    """Compute cross-asset scale, lighting, and outline consistency metrics."""
    if not entries:
        raise ValueError("Cannot compute pack metrics from zero entries")

    asset_metrics = tuple(compute_pack_asset_metrics(e, variant=variant) for e in entries)
    style_ids = tuple(sorted({m.style_id for m in asset_metrics}))
    perspectives = tuple(sorted({m.perspective for m in asset_metrics}))
    lighting_angles = tuple(sorted({m.lighting_angle for m in asset_metrics}))

    min_w = min(m.width for m in asset_metrics)
    min_h = min(m.height for m in asset_metrics)
    max_w = max(m.width for m in asset_metrics)
    max_h = max(m.height for m in asset_metrics)
    bbox_heights = [m.bbox[3] if m.bbox is not None else 0 for m in asset_metrics]
    lums = [m.mean_luminance for m in asset_metrics]
    biases = [m.light_bias_tl for m in asset_metrics]
    outlines = [m.outline_coverage_pct for m in asset_metrics]
    orphan_total = sum(m.orphan_pixels for m in asset_metrics)

    lum_range = (min(lums), max(lums))
    lum_spread = round(lum_range[1] - lum_range[0], 3)
    bias_range = (min(biases), max(biases))
    outline_range = (min(outlines), max(outlines))
    outline_spread = round(outline_range[1] - outline_range[0], 1)

    scale_ok, lighting_ok, outline_ok, warnings = _collect_consistency_warnings(
        asset_metrics,
        perspectives,
        lighting_angles,
        (min_w, min_h),
        (max_w, max_h),
        lum_spread,
        bias_range,
        outline_spread,
        orphan_total,
    )

    return PackConsistencyMetrics(
        asset_count=len(asset_metrics),
        style_ids=style_ids,
        perspectives=perspectives,
        lighting_angles=lighting_angles,
        min_size=(min_w, min_h),
        max_size=(max_w, max_h),
        bbox_height_range=(min(bbox_heights), max(bbox_heights)),
        luminance_range=lum_range,
        luminance_spread=lum_spread,
        light_bias_range=bias_range,
        outline_coverage_range=outline_range,
        outline_spread_pct=outline_spread,
        orphan_total=orphan_total,
        scale_consistent=scale_ok,
        lighting_consistent=lighting_ok,
        outline_consistent=outline_ok,
        warnings=warnings,
        assets=asset_metrics,
    )


def _choose_grid_columns(count: int, override: int | None) -> int:
    if override is not None:
        return max(1, min(count, override))
    if count <= 1:
        return 1
    if count <= 4:
        return 2
    if count <= 9:
        return 3
    if count <= 16:
        return 4
    return min(6, math.ceil(math.sqrt(count)))


@dataclass(frozen=True)
class _PackLayout:
    pad: int
    cell_pad: int
    cell_gap: int
    slot_gap: int
    header_h: int
    cols: int
    rows: int
    slot_1x_w: int
    slot_2x_w: int
    slot_h: int
    cell_w: int
    cell_h: int
    canvas_w: int
    canvas_h: int
    title_line: str
    scale_line: str
    light_line: str
    outline_line: str
    warn_line: str | None


def _compute_pack_layout(
    entries: Sequence[PackSheetEntry],
    metrics: PackConsistencyMetrics,
    opts: PackSheetOptions,
) -> _PackLayout:
    pad = 14
    cell_pad = 10
    cell_gap = 10
    slot_gap = 8
    cols = _choose_grid_columns(len(entries), opts.columns)
    rows = math.ceil(len(entries) / cols)

    slot_1x_w = max(24, metrics.max_size[0])
    slot_2x_w = max(48, metrics.max_size[0] * 2)
    slot_h = max(32, metrics.max_size[1] * 2)

    min_text_w = max(slot_1x_w + slot_gap + slot_2x_w, 160)
    cell_w = min_text_w + cell_pad * 2
    # Top title (14) + scale label row (10) + sprite area (slot_h) + bottom metrics (14)
    cell_h = cell_pad * 2 + 14 + 10 + slot_h + 14

    title = opts.title or "PACK CONTACT SHEET"
    styles_csv = ",".join(metrics.style_ids)
    title_line = f"{title} | {metrics.asset_count} ASSETS | STYLES: {styles_csv}"
    persp_csv = ",".join(metrics.perspectives)
    scale_status = "OK" if metrics.scale_consistent else "WARN"
    scale_line = (
        f"SCALE[{scale_status}]: {metrics.min_size[0]}x{metrics.min_size[1]}.."
        f"{metrics.max_size[0]}x{metrics.max_size[1]} "
        f"BBOX_H:{metrics.bbox_height_range[0]}..{metrics.bbox_height_range[1]} "
        f"PERSP:{persp_csv}"
    )
    light_status = "OK" if metrics.lighting_consistent else "WARN"
    light_csv = ",".join(metrics.lighting_angles)
    light_line = (
        f"LIGHT[{light_status}]: {light_csv} "
        f"LUM:{metrics.luminance_range[0]:.2f}..{metrics.luminance_range[1]:.2f} "
        f"(SPREAD {metrics.luminance_spread:.2f}) "
        f"BIAS:{metrics.light_bias_range[0]:+.2f}..{metrics.light_bias_range[1]:+.2f}"
    )
    out_status = "OK" if metrics.outline_consistent else "WARN"
    outline_line = (
        f"OUTLINE[{out_status}]: {metrics.outline_coverage_range[0]:.1f}%.."
        f"{metrics.outline_coverage_range[1]:.1f}% "
        f"(SPREAD {metrics.outline_spread_pct:.1f}%) "
        f"ORPHANS:{metrics.orphan_total}"
    )
    warn_line = f"WARNINGS: {'; '.join(metrics.warnings)}" if metrics.warnings else None

    header_lines = [title_line, scale_line, light_line, outline_line]
    if warn_line is not None:
        header_lines.append(warn_line)
    max_header_tw = max(measure_text(line)[0] for line in header_lines)
    header_h = 12 + len(header_lines) * 11 + 8

    grid_w = cols * cell_w + (cols - 1) * cell_gap
    grid_h = rows * cell_h + (rows - 1) * cell_gap
    canvas_w = max(grid_w, max_header_tw) + pad * 2
    canvas_h = header_h + pad + grid_h + pad

    return _PackLayout(
        pad=pad,
        cell_pad=cell_pad,
        cell_gap=cell_gap,
        slot_gap=slot_gap,
        header_h=header_h,
        cols=cols,
        rows=rows,
        slot_1x_w=slot_1x_w,
        slot_2x_w=slot_2x_w,
        slot_h=slot_h,
        cell_w=cell_w,
        cell_h=cell_h,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        title_line=title_line,
        scale_line=scale_line,
        light_line=light_line,
        outline_line=outline_line,
        warn_line=warn_line,
    )


def _render_pack_cell(
    canvas: NDArray[np.uint8],
    entry: PackSheetEntry,
    asset_metrics: PackAssetMetrics,
    cx: int,
    cy: int,
    layout: _PackLayout,
    variant: str | None,
) -> None:
    fill_rgba_rect(canvas, cx, cy, layout.cell_w, layout.cell_h, _BORDER_SUBTLE)
    fill_rgba_rect(canvas, cx + 1, cy + 1, layout.cell_w - 2, layout.cell_h - 2, _BG_CELL)

    ix = cx + layout.cell_pad
    iy = cy + layout.cell_pad
    header_txt = f"{entry.spec.id} ({entry.spec.width}x{entry.spec.height})"
    draw_bitmap_text(canvas, header_txt, ix, iy, _TEXT_LIGHT)

    label_y = iy + 13
    slot_y = label_y + 10
    s1x_x = ix
    s2x_x = ix + layout.slot_1x_w + layout.slot_gap

    draw_bitmap_text(canvas, "1X", s1x_x, label_y, _TEXT_MUTED)
    draw_bitmap_text(canvas, "2X", s2x_x, label_y, _TEXT_MUTED)

    draw_checkerboard(
        canvas, s1x_x, slot_y, layout.slot_1x_w, layout.slot_h, _CHECK_DARK_A, _CHECK_DARK_B, tile=4
    )
    draw_checkerboard(
        canvas, s2x_x, slot_y, layout.slot_2x_w, layout.slot_h, _CHECK_DARK_A, _CHECK_DARK_B, tile=4
    )

    rgba_1x = surface_to_rgba(entry.surface, entry.style, variant=variant)
    rgba_2x = np.repeat(np.repeat(rgba_1x, 2, axis=0), 2, axis=1)

    # INVARIANT: Bottom-aligning sprites inside uniform max-dimension slots preserves
    # direct visual scale comparison across props of different heights.
    off_1x_x = s1x_x + (layout.slot_1x_w - entry.spec.width) // 2
    off_1x_y = slot_y + (layout.slot_h - entry.spec.height)
    composite_rgba(canvas, rgba_1x, off_1x_x, off_1x_y)

    off_2x_x = s2x_x + (layout.slot_2x_w - entry.spec.width * 2) // 2
    off_2x_y = slot_y + (layout.slot_h - entry.spec.height * 2)
    composite_rgba(canvas, rgba_2x, off_2x_x, off_2x_y)

    foot_y = slot_y + layout.slot_h + 5
    foot_txt = (
        f"C:{asset_metrics.coverage_pct:.0f}% "
        f"L:{asset_metrics.mean_luminance:.2f} "
        f"O:{asset_metrics.outline_coverage_pct:.0f}%"
    )
    draw_bitmap_text(canvas, foot_txt, ix, foot_y, _TEXT_MUTED)


def generate_pack_sheet(
    entries: Sequence[PackSheetEntry],
    options: PackSheetOptions | None = None,
) -> PackSheetResult:
    """Compile a comparative 1x + 2x grid `.contact.png` across multiple assets."""
    if not entries:
        raise ValueError("Cannot generate pack contact sheet from zero assets")

    opts = options or PackSheetOptions()
    ordered = sorted(entries, key=lambda item: (item.style.id, item.spec.id))
    metrics = compute_pack_consistency_metrics(ordered, variant=opts.variant)
    layout = _compute_pack_layout(ordered, metrics, opts)

    canvas = np.empty((layout.canvas_h, layout.canvas_w, 4), dtype=np.uint8)
    canvas[:, :] = (*_BG_MAIN, 255)

    fill_rgba_rect(canvas, 0, 0, layout.canvas_w, layout.header_h, _BG_HEADER)
    fill_rgba_rect(canvas, 0, layout.header_h - 1, layout.canvas_w, 1, _BORDER_SUBTLE)

    hy = 10
    draw_bitmap_text(canvas, layout.title_line, layout.pad, hy, _TEXT_LIGHT)
    hy += 11
    draw_bitmap_text(
        canvas,
        layout.scale_line,
        layout.pad,
        hy,
        _TEXT_OK if metrics.scale_consistent else _TEXT_WARN,
    )
    hy += 11
    draw_bitmap_text(
        canvas,
        layout.light_line,
        layout.pad,
        hy,
        _TEXT_OK if metrics.lighting_consistent else _TEXT_WARN,
    )
    hy += 11
    draw_bitmap_text(
        canvas,
        layout.outline_line,
        layout.pad,
        hy,
        _TEXT_OK if metrics.outline_consistent else _TEXT_WARN,
    )
    if layout.warn_line is not None:
        hy += 11
        draw_bitmap_text(canvas, layout.warn_line, layout.pad, hy, _TEXT_WARN)

    grid_y = layout.header_h + layout.pad
    for idx, (entry, asset_m) in enumerate(zip(ordered, metrics.assets, strict=True)):
        row = idx // layout.cols
        col = idx % layout.cols
        cx = layout.pad + col * (layout.cell_w + layout.cell_gap)
        cy = grid_y + row * (layout.cell_h + layout.cell_gap)
        _render_pack_cell(canvas, entry, asset_m, cx, cy, layout, opts.variant)

    return PackSheetResult(
        width=layout.canvas_w,
        height=layout.canvas_h,
        rgba=canvas,
        png=rgba_to_png(canvas),
        metrics=metrics,
    )
