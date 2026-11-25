"""Upgraded diagnostic `.contact.png` generator for Multimodal Visual Critic loops."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.palette import hex_to_rgb
from pixelforge.core.surface import IndexedSurface, orphan_pixel_mask
from pixelforge.core.types import TRANSPARENT_INDEX, AnchorPoint, AssetSpec, HitboxRect, StylePack
from pixelforge.export._canvas import Rgb, composite_rgba, draw_checkerboard
from pixelforge.export._font import draw_bitmap_text, fill_rgba_rect, measure_text
from pixelforge.export.bundle import AssetModule, RenderedFrame, render_asset_frames
from pixelforge.export.png import rgba_to_png, surface_to_rgba

_BG_MAIN: Final[Rgb] = (18, 22, 29)
_BG_HEADER: Final[Rgb] = (28, 34, 45)
_BORDER_SUBTLE: Final[Rgb] = (48, 56, 70)
_TEXT_LIGHT: Final[Rgb] = (230, 237, 243)
_TEXT_MUTED: Final[Rgb] = (139, 148, 158)
_TEXT_WARN: Final[Rgb] = (248, 189, 73)
_GRID_LINE: Final[Rgb] = (55, 65, 81)
_RULER_COLOR: Final[Rgb] = (121, 192, 255)
_ANCHOR_COLOR: Final[Rgb] = (255, 123, 114)
_HITBOX_COLOR: Final[Rgb] = (86, 211, 100)
_CHECK_DARK_A: Final[Rgb] = (13, 17, 23)
_CHECK_DARK_B: Final[Rgb] = (24, 30, 40)
_CHECK_LIGHT_A: Final[Rgb] = (230, 237, 243)
_CHECK_LIGHT_B: Final[Rgb] = (208, 215, 222)


@dataclass(frozen=True)
class ContactSheetMetrics:
    """Diagnostic geometry and orphan-pixel summary for a rendered asset."""

    opaque_pixels: int
    total_pixels: int
    coverage_pct: float
    bbox: tuple[int, int, int, int] | None
    orphan_pixels: int


@dataclass(frozen=True)
class ContactSheetOptions:
    """Configuration options for `generate_contact_sheet`."""

    zoom: int | None = None
    variant: str | None = None
    include_variants: bool = True


@dataclass(frozen=True)
class ContactSheetResult:
    """Generated diagnostic contact sheet RGBA buffer, PNG bytes, and metrics."""

    width: int
    height: int
    rgba: NDArray[np.uint8]
    png: bytes
    metrics: ContactSheetMetrics


def choose_zoom(width: int, height: int) -> int:
    """Select an automatic integer zoom factor so small sprites remain crisp."""
    max_dim = max(width, height)
    if max_dim <= 32:
        return 8
    if max_dim <= 96:
        return 4
    if max_dim <= 200:
        return 2
    return 1


def compute_surface_metrics(surface: IndexedSurface) -> ContactSheetMetrics:
    """Compute opaque pixel count, tight `(x, y, w, h)` bbox, and 8-connected orphan count."""
    opaque = surface.data != TRANSPARENT_INDEX
    opaque_count = int(np.count_nonzero(opaque))
    total_pixels = surface.width * surface.height
    coverage = (opaque_count / total_pixels) * 100.0 if total_pixels > 0 else 0.0

    if opaque_count == 0:
        return ContactSheetMetrics(
            opaque_pixels=0,
            total_pixels=total_pixels,
            coverage_pct=0.0,
            bbox=None,
            orphan_pixels=0,
        )

    ys, xs = np.nonzero(opaque)
    min_x, max_x = int(xs.min()), int(xs.max())
    min_y, max_y = int(ys.min()), int(ys.max())
    bbox = (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)

    orphan_count = int(np.count_nonzero(orphan_pixel_mask(surface)))
    return ContactSheetMetrics(
        opaque_pixels=opaque_count,
        total_pixels=total_pixels,
        coverage_pct=round(coverage, 1),
        bbox=bbox,
        orphan_pixels=orphan_count,
    )


def _draw_dashed_rect(
    canvas: NDArray[np.uint8],
    x: int,
    y: int,
    w: int,
    h: int,
    rgb: Rgb,
    dash: int = 3,
) -> None:
    if w <= 0 or h <= 0:
        return
    ch, cw, _ = canvas.shape
    for px in range(x, x + w):
        if ((px - x) // dash) % 2 == 0 and 0 <= px < cw:
            if 0 <= y < ch:
                canvas[y, px] = (*rgb, 255)
            if 0 <= y + h - 1 < ch:
                canvas[y + h - 1, px] = (*rgb, 255)
    for py in range(y, y + h):
        if ((py - y) // dash) % 2 == 0 and 0 <= py < ch:
            if 0 <= x < cw:
                canvas[py, x] = (*rgb, 255)
            if 0 <= x + w - 1 < cw:
                canvas[py, x + w - 1] = (*rgb, 255)


def _draw_zoom_overlays(
    canvas: NDArray[np.uint8],
    panel_x: int,
    panel_y: int,
    asset_w: int,
    asset_h: int,
    zoom: int,
    anchors: tuple[AnchorPoint, ...],
    hitboxes: tuple[HitboxRect, ...],
) -> None:
    zoomed_w = asset_w * zoom
    zoomed_h = asset_h * zoom

    if zoom >= 4:
        for gx in range(1, asset_w):
            px = panel_x + gx * zoom
            canvas[panel_y : panel_y + zoomed_h, px] = (*_GRID_LINE, 255)
        for gy in range(1, asset_h):
            py = panel_y + gy * zoom
            canvas[py, panel_x : panel_x + zoomed_w] = (*_GRID_LINE, 255)

    tick_step = 16 if max(asset_w, asset_h) > 96 else 4
    for x in range(0, asset_w + 1, tick_step):
        px = panel_x + x * zoom
        fill_rgba_rect(canvas, px, panel_y - 3, 1, 3, _RULER_COLOR)
        if x < asset_w:
            draw_bitmap_text(canvas, str(x), px, panel_y - 11, _RULER_COLOR)

    for y in range(0, asset_h + 1, tick_step):
        py = panel_y + y * zoom
        fill_rgba_rect(canvas, panel_x - 3, py, 3, 1, _RULER_COLOR)
        if y < asset_h:
            label = str(y)
            tw, _ = measure_text(label)
            draw_bitmap_text(canvas, label, max(4, panel_x - 5 - tw), py, _RULER_COLOR)

    for hb in hitboxes:
        hx = panel_x + hb.x * zoom
        hy = panel_y + hb.y * zoom
        hw = hb.w * zoom
        hh = hb.h * zoom
        _draw_dashed_rect(canvas, hx, hy, hw, hh, _HITBOX_COLOR)
        draw_bitmap_text(canvas, hb.name, hx + 2, max(panel_y, hy - 7), _HITBOX_COLOR)

    for anchor in anchors:
        ax = panel_x + anchor.x * zoom + (zoom // 2)
        ay = panel_y + anchor.y * zoom + (zoom // 2)
        fill_rgba_rect(canvas, ax - 3, ay, 7, 1, _ANCHOR_COLOR)
        fill_rgba_rect(canvas, ax, ay - 3, 1, 7, _ANCHOR_COLOR)
        draw_bitmap_text(canvas, anchor.name, ax + 5, ay - 3, _ANCHOR_COLOR)


def _collect_used_indices(frames: tuple[RenderedFrame, ...]) -> set[int]:
    used: set[int] = set()
    for item in frames:
        unique_vals = np.unique(item.surface.data)
        for val in unique_vals.tolist():
            if val != TRANSPARENT_INDEX:
                used.add(int(val))
    return used


def _format_swatch_label(idx: int, name: str, flags: tuple[str, ...]) -> str:
    tag_chars: list[str] = []
    if "emissive" in flags:
        tag_chars.append("E")
    if "bright" in flags:
        tag_chars.append("B")
    tag = f"[{''.join(tag_chars)}]" if tag_chars else ""
    return f"{idx:02d}:{name}{tag}" if not tag else f"{idx:02d}:{name} {tag}"


@dataclass(frozen=True)
class _ContactSheetLayout:
    pad: int
    header_h: int
    zoom: int
    zoom_x: int
    zoom_y: int
    zoomed_w: int
    zoomed_h: int
    right_x: int
    right_y: int
    has_emissive: bool
    cell_scale: int
    cell_w: int
    cell_h: int
    cell_gap: int
    state_label_w: int
    matrix_title: str
    matrix_row_offset: int
    matrix_y: int
    matrix_h: int
    variant_names: tuple[str, ...]
    variant_scale: int
    variant_cell_w: int
    variant_cell_h: int
    swatch_labels: list[tuple[str, Rgb]]
    swatch_col_w: int
    swatch_cols: int
    swatches_y: int
    title_line: str
    metrics_line: str
    canvas_w: int
    canvas_h: int


def _compute_contact_sheet_layout(
    spec: AssetSpec,
    style: StylePack,
    primary: RenderedFrame,
    frames: tuple[RenderedFrame, ...],
    metrics: ContactSheetMetrics,
    opts: ContactSheetOptions,
) -> _ContactSheetLayout:
    zoom = opts.zoom if opts.zoom is not None else choose_zoom(spec.width, spec.height)
    pad = 16
    ruler_left = 28
    ruler_top = 14
    header_h = 44
    zoomed_w = spec.width * zoom
    zoomed_h = spec.height * zoom
    preview_1x_w = max(spec.width * 2 + 12, 120)

    has_emissive = any("emissive" in entry.flags for entry in style.palette)
    cell_scale = 2 if max(spec.width, spec.height) <= 32 else 1
    cell_w, cell_h, cell_gap = spec.width * cell_scale, spec.height * cell_scale, 6
    state_label_w = max((measure_text(s)[0] for s in spec.states), default=24) + 10
    matrix_title = "states x frames (+emissive)" if has_emissive else "states x frames"
    emissive_col_w = max(cell_w, measure_text("emissive")[0]) if has_emissive else 0
    matrix_row_offset = 20 if has_emissive else 12
    matrix_cells_w = (
        state_label_w
        + spec.frames * (cell_w + cell_gap)
        + (emissive_col_w + cell_gap if has_emissive else 0)
    )
    matrix_w = max(matrix_cells_w, measure_text(matrix_title)[0])
    matrix_h = len(spec.states) * (cell_h + cell_gap) + matrix_row_offset + 4

    variant_names = tuple(style.variants.keys()) if opts.include_variants else ()
    variant_scale = 2 if max(spec.width, spec.height) <= 32 else 1
    variant_cell_w, variant_cell_h = spec.width * variant_scale, spec.height * variant_scale
    variant_strip_w = len(variant_names) * (max(variant_cell_w, 64) + 8) if variant_names else 0
    variant_strip_h = (variant_cell_h + 22) if variant_names else 0

    used_indices = _collect_used_indices(frames)
    swatch_entries = [entry for entry in style.palette if entry.index in used_indices]
    if not swatch_entries:
        swatch_entries = list(style.palette[: min(16, len(style.palette))])
    swatch_labels = [
        (_format_swatch_label(e.index, e.name, e.flags), hex_to_rgb(e.hex)) for e in swatch_entries
    ]
    max_label_w = max((measure_text(lbl)[0] for lbl, _ in swatch_labels), default=60)
    swatch_col_w = 18 + max_label_w + 14

    left_col_w = ruler_left + zoomed_w
    right_col_w = max(preview_1x_w, matrix_w, variant_strip_w)
    body_w = left_col_w + 24 + right_col_w

    bbox_str = (
        f"({metrics.bbox[0]},{metrics.bbox[1]},{metrics.bbox[2]}x{metrics.bbox[3]})"
        if metrics.bbox is not None
        else "empty"
    )
    title_line = (
        f"{spec.id}  {spec.width}x{spec.height}  style:{style.id}"
        f"  states:{len(spec.states)}  frames:{spec.frames}  zoom:{zoom}x"
    )
    metrics_line = (
        f"opaque:{metrics.opaque_pixels}/{metrics.total_pixels} ({metrics.coverage_pct}%)"
        f"  bbox:{bbox_str}  orphans:{metrics.orphan_pixels}"
        f"  anchors:{len(primary.anchors)}  hitboxes:{len(primary.hitboxes)}"
    )
    header_min_w = max(measure_text(title_line)[0], measure_text(metrics_line)[0]) + pad * 2

    canvas_w = max(body_w + pad * 2, header_min_w, 460)
    swatch_cols = max(1, (canvas_w - pad * 2) // swatch_col_w)
    swatch_rows = (len(swatch_labels) + swatch_cols - 1) // swatch_cols
    swatch_h = swatch_rows * 16 + 18

    left_h = ruler_top + zoomed_h + 10
    right_h = (spec.height + 16) + 12 + matrix_h + (variant_strip_h + 12 if variant_names else 0)
    canvas_h = header_h + pad + max(left_h, right_h) + 16 + swatch_h + pad

    return _ContactSheetLayout(
        pad=pad,
        header_h=header_h,
        zoom=zoom,
        zoom_x=pad + ruler_left,
        zoom_y=header_h + pad + ruler_top,
        zoomed_w=zoomed_w,
        zoomed_h=zoomed_h,
        right_x=pad + left_col_w + 24,
        right_y=header_h + pad,
        has_emissive=has_emissive,
        cell_scale=cell_scale,
        cell_w=cell_w,
        cell_h=cell_h,
        cell_gap=cell_gap,
        state_label_w=state_label_w,
        matrix_title=matrix_title,
        matrix_row_offset=matrix_row_offset,
        matrix_y=header_h + pad + spec.height + 24,
        matrix_h=matrix_h,
        variant_names=variant_names,
        variant_scale=variant_scale,
        variant_cell_w=variant_cell_w,
        variant_cell_h=variant_cell_h,
        swatch_labels=swatch_labels,
        swatch_col_w=swatch_col_w,
        swatch_cols=swatch_cols,
        swatches_y=header_h + pad + max(left_h, right_h) + 14,
        title_line=title_line,
        metrics_line=metrics_line,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
    )


def _render_header(
    canvas: NDArray[np.uint8],
    layout: _ContactSheetLayout,
    metrics: ContactSheetMetrics,
) -> None:
    fill_rgba_rect(canvas, 0, 0, layout.canvas_w, layout.header_h, _BG_HEADER)
    fill_rgba_rect(canvas, 0, layout.header_h - 1, layout.canvas_w, 1, _BORDER_SUBTLE)
    draw_bitmap_text(canvas, layout.title_line, layout.pad, 10, _TEXT_LIGHT)
    metrics_color = _TEXT_WARN if metrics.orphan_pixels > 0 else _TEXT_MUTED
    draw_bitmap_text(canvas, layout.metrics_line, layout.pad, 24, metrics_color)


def _render_zoom_panel(
    canvas: NDArray[np.uint8],
    layout: _ContactSheetLayout,
    spec: AssetSpec,
    primary: RenderedFrame,
    style: StylePack,
    opts: ContactSheetOptions,
) -> None:
    draw_checkerboard(
        canvas,
        layout.zoom_x,
        layout.zoom_y,
        layout.zoomed_w,
        layout.zoomed_h,
        _CHECK_DARK_A,
        _CHECK_DARK_B,
        8,
    )
    zoomed_rgba = surface_to_rgba(primary.surface, style, variant=opts.variant, scale=layout.zoom)
    composite_rgba(canvas, zoomed_rgba, layout.zoom_x, layout.zoom_y)
    _draw_zoom_overlays(
        canvas,
        layout.zoom_x,
        layout.zoom_y,
        spec.width,
        spec.height,
        layout.zoom,
        primary.anchors,
        primary.hitboxes,
    )


def _render_1x_previews(
    canvas: NDArray[np.uint8],
    layout: _ContactSheetLayout,
    spec: AssetSpec,
    primary: RenderedFrame,
    style: StylePack,
    opts: ContactSheetOptions,
) -> None:
    primary_1x = surface_to_rgba(primary.surface, style, variant=opts.variant, scale=1)
    draw_bitmap_text(canvas, "1x dark", layout.right_x, layout.right_y, _TEXT_MUTED)
    draw_checkerboard(
        canvas,
        layout.right_x,
        layout.right_y + 10,
        spec.width,
        spec.height,
        _CHECK_DARK_A,
        _CHECK_DARK_B,
        4,
    )
    composite_rgba(canvas, primary_1x, layout.right_x, layout.right_y + 10)

    light_x = layout.right_x + max(spec.width + 16, 60)
    draw_bitmap_text(canvas, "1x light", light_x, layout.right_y, _TEXT_MUTED)
    draw_checkerboard(
        canvas,
        light_x,
        layout.right_y + 10,
        spec.width,
        spec.height,
        _CHECK_LIGHT_A,
        _CHECK_LIGHT_B,
        4,
    )
    composite_rgba(canvas, primary_1x, light_x, layout.right_y + 10)


def _render_state_matrix(
    canvas: NDArray[np.uint8],
    layout: _ContactSheetLayout,
    spec: AssetSpec,
    frames: tuple[RenderedFrame, ...],
    style: StylePack,
    opts: ContactSheetOptions,
) -> None:
    draw_bitmap_text(canvas, layout.matrix_title, layout.right_x, layout.matrix_y, _TEXT_MUTED)
    grid_x0 = layout.right_x + layout.state_label_w
    cell_step = layout.cell_w + layout.cell_gap
    row_step = layout.cell_h + layout.cell_gap
    emit_x = grid_x0 + spec.frames * cell_step

    if layout.has_emissive:
        col_hdr_y = layout.matrix_y + 10
        for frame_idx in range(spec.frames):
            draw_bitmap_text(
                canvas, f"f{frame_idx}", grid_x0 + frame_idx * cell_step, col_hdr_y, _TEXT_MUTED
            )
        draw_bitmap_text(canvas, "emissive", emit_x, col_hdr_y, _TEXT_MUTED)

    by_key = {(f.state, f.frame): f for f in frames}
    for s_idx, state in enumerate(spec.states):
        row_y = layout.matrix_y + layout.matrix_row_offset + s_idx * row_step
        draw_bitmap_text(
            canvas, state, layout.right_x, row_y + max(0, (layout.cell_h - 6) // 2), _TEXT_LIGHT
        )
        for frame_idx in range(spec.frames):
            cell_x = grid_x0 + frame_idx * cell_step
            draw_checkerboard(
                canvas, cell_x, row_y, layout.cell_w, layout.cell_h, _CHECK_DARK_A, _CHECK_DARK_B, 4
            )
            cell_rgba = surface_to_rgba(
                by_key[(state, frame_idx)].surface,
                style,
                variant=opts.variant,
                scale=layout.cell_scale,
            )
            composite_rgba(canvas, cell_rgba, cell_x, row_y)
        if layout.has_emissive:
            draw_checkerboard(
                canvas, emit_x, row_y, layout.cell_w, layout.cell_h, _CHECK_DARK_A, _CHECK_DARK_B, 4
            )
            for frame_idx in range(spec.frames):
                emit_rgba = surface_to_rgba(
                    by_key[(state, frame_idx)].surface,
                    style,
                    variant=opts.variant,
                    scale=layout.cell_scale,
                    emissive_only=True,
                )
                composite_rgba(canvas, emit_rgba, emit_x, row_y)


def _render_variant_strip(
    canvas: NDArray[np.uint8],
    layout: _ContactSheetLayout,
    primary: RenderedFrame,
    style: StylePack,
) -> None:
    if not layout.variant_names:
        return
    var_y = layout.matrix_y + layout.matrix_h + 6
    draw_bitmap_text(canvas, "variants", layout.right_x, var_y, _TEXT_MUTED)
    vx = layout.right_x
    for v_name in layout.variant_names:
        draw_bitmap_text(canvas, v_name, vx, var_y + 10, _TEXT_LIGHT)
        draw_checkerboard(
            canvas,
            vx,
            var_y + 20,
            layout.variant_cell_w,
            layout.variant_cell_h,
            _CHECK_DARK_A,
            _CHECK_DARK_B,
            4,
        )
        v_rgba = surface_to_rgba(primary.surface, style, variant=v_name, scale=layout.variant_scale)
        composite_rgba(canvas, v_rgba, vx, var_y + 20)
        vx += max(layout.variant_cell_w, 64) + 8


def _render_swatches(canvas: NDArray[np.uint8], layout: _ContactSheetLayout) -> None:
    draw_bitmap_text(canvas, "palette (used tokens)", layout.pad, layout.swatches_y, _TEXT_MUTED)
    for idx, (label, rgb) in enumerate(layout.swatch_labels):
        col = idx % layout.swatch_cols
        row = idx // layout.swatch_cols
        sx = layout.pad + col * layout.swatch_col_w
        sy = layout.swatches_y + 14 + row * 16
        fill_rgba_rect(canvas, sx, sy, 12, 12, rgb)
        draw_bitmap_text(canvas, label, sx + 16, sy + 3, _TEXT_LIGHT)


def generate_contact_sheet(
    asset: AssetModule,
    style: StylePack,
    options: ContactSheetOptions | None = None,
) -> ContactSheetResult:
    """Render an informative `.contact.png` with rulers, hitboxes, anchors, matrix, and swatches."""
    opts = options or ContactSheetOptions()
    spec = asset.SPEC
    frames = render_asset_frames(asset, style, variant=opts.variant)
    primary = frames[0]
    metrics = compute_surface_metrics(primary.surface)
    layout = _compute_contact_sheet_layout(spec, style, primary, frames, metrics, opts)

    canvas = np.empty((layout.canvas_h, layout.canvas_w, 4), dtype=np.uint8)
    canvas[:, :] = (*_BG_MAIN, 255)
    _render_header(canvas, layout, metrics)
    _render_zoom_panel(canvas, layout, spec, primary, style, opts)
    _render_1x_previews(canvas, layout, spec, primary, style, opts)
    _render_state_matrix(canvas, layout, spec, frames, style, opts)
    _render_variant_strip(canvas, layout, primary, style)
    _render_swatches(canvas, layout)

    return ContactSheetResult(
        width=layout.canvas_w,
        height=layout.canvas_h,
        rgba=canvas,
        png=rgba_to_png(canvas),
        metrics=metrics,
    )
