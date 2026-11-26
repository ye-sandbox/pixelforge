"""Diagnostic contact sheet rendering for composed scenes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import StylePack
from pixelforge.export._canvas import Rgb, composite_rgba, draw_checkerboard
from pixelforge.export._font import draw_bitmap_text, fill_rgba_rect, measure_text
from pixelforge.export.contact_sheet import choose_zoom
from pixelforge.export.png import rgba_to_png, surface_to_rgba
from pixelforge.export.scene_models import (
    MountedPropPlacement,
    SceneCompositionResult,
    SceneSheetResult,
)

_BG_MAIN: Final[Rgb] = (18, 22, 29)
_BG_HEADER: Final[Rgb] = (28, 34, 45)
_BORDER_SUBTLE: Final[Rgb] = (48, 56, 70)
_TEXT_LIGHT: Final[Rgb] = (230, 237, 243)
_TEXT_MUTED: Final[Rgb] = (139, 148, 158)
_TEXT_WARN: Final[Rgb] = (248, 189, 73)
_TEXT_ERR: Final[Rgb] = (255, 123, 114)
_TEXT_OK: Final[Rgb] = (86, 211, 100)
_RULER_COLOR: Final[Rgb] = (121, 192, 255)
_ANCHOR_COLOR: Final[Rgb] = (255, 123, 114)
_CHECK_DARK_A: Final[Rgb] = (13, 17, 23)
_CHECK_DARK_B: Final[Rgb] = (24, 30, 40)
_CHECK_LIGHT_A: Final[Rgb] = (230, 237, 243)
_CHECK_LIGHT_B: Final[Rgb] = (208, 215, 222)


def _draw_rect_outline(
    canvas: NDArray[np.uint8],
    x: int,
    y: int,
    w: int,
    h: int,
    rgb: Rgb,
) -> None:
    if w <= 0 or h <= 0:
        return
    ch, cw, _ = canvas.shape
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(cw - 1, x + w - 1)
    y1 = min(ch - 1, y + h - 1)
    if x0 > x1 or y0 > y1:
        return
    if 0 <= y < ch:
        canvas[y, x0 : x1 + 1] = (*rgb, 255)
    if 0 <= y + h - 1 < ch:
        canvas[y + h - 1, x0 : x1 + 1] = (*rgb, 255)
    if 0 <= x < cw:
        canvas[y0 : y1 + 1, x] = (*rgb, 255)
    if 0 <= x + w - 1 < cw:
        canvas[y0 : y1 + 1, x + w - 1] = (*rgb, 255)


def _format_placement_line(p: MountedPropPlacement) -> str:
    status = "OK" if p.in_bounds else f"CLIP({p.clipped_pixels}px)"
    persp = "" if p.perspective_match else f" [PERSP:{p.perspective}]"
    occ = f" occ={p.occluded_pixels}px({','.join(p.occluded_by)})" if p.occluded_pixels > 0 else ""
    pa = f":{p.prop_anchor}" if p.prop_anchor else ""
    return (
        f"{p.prop_id}{pa}@{p.anchor} -> ({p.dest_x},{p.dest_y}) "
        f"{p.width}x{p.height} z={p.z_index} [{status}]{persp}{occ}"
    )


@dataclass(frozen=True)
class _SceneSheetLayout:
    pad: int
    header_h: int
    zoom_val: int
    zoom_x: int
    zoom_y: int
    zoomed_w: int
    zoomed_h: int
    right_x: int
    right_y: int
    table_y: int
    canvas_w: int
    canvas_h: int
    title_line: str
    summary_line: str
    summary_color: Rgb
    placement_lines: list[str]


def _compute_sheet_layout(
    result: SceneCompositionResult,
    zoom: int | None,
) -> _SceneSheetLayout:
    pad = 16
    header_h = 38
    surf = result.surface
    zoom_val = zoom if zoom is not None and zoom > 0 else choose_zoom(surf.width, surf.height)
    zoomed_w = surf.width * zoom_val
    zoomed_h = surf.height * zoom_val

    zoom_x = pad + 26
    zoom_y = header_h + pad + 14
    right_x = zoom_x + zoomed_w + 20
    right_y = header_h + pad

    placement_lines = [_format_placement_line(p) for p in result.placements] or [
        "(no mounted props)"
    ]
    max_line_w = max(measure_text(line)[0] for line in placement_lines)
    title_line = (
        f"COMPOSE: {result.parent_id} [{result.parent_state} f{result.parent_frame}]  "
        f"style={result.style_id}"
    )
    oob_count = sum(1 for p in result.placements if not p.in_bounds)
    occ_count = sum(1 for p in result.placements if p.occluded_pixels > 0)
    persp_mismatch_count = sum(1 for p in result.placements if not p.perspective_match)
    summary_line = (
        f"canvas={surf.width}x{surf.height}  zoom={zoom_val}x  "
        f"props={len(result.placements)}  oob={oob_count}  "
        f"occluded={occ_count}  persp_mismatch={persp_mismatch_count}"
    )
    has_warn = occ_count > 0 or persp_mismatch_count > 0
    summary_color = _TEXT_ERR if oob_count > 0 else (_TEXT_WARN if has_warn else _TEXT_MUTED)

    right_col_w = max(surf.width + 24, 180)
    table_y = max(zoom_y + zoomed_h + 18, right_y + surf.height * 2 + 46)
    table_h = 18 + len(placement_lines) * 12

    canvas_w = max(
        right_x + right_col_w + pad,
        pad + max_line_w + pad,
        pad + max(measure_text(title_line)[0], measure_text(summary_line)[0]) + pad,
    )
    canvas_h = table_y + table_h + pad
    return _SceneSheetLayout(
        pad=pad,
        header_h=header_h,
        zoom_val=zoom_val,
        zoom_x=zoom_x,
        zoom_y=zoom_y,
        zoomed_w=zoomed_w,
        zoomed_h=zoomed_h,
        right_x=right_x,
        right_y=right_y,
        table_y=table_y,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        title_line=title_line,
        summary_line=summary_line,
        summary_color=summary_color,
        placement_lines=placement_lines,
    )


def _draw_zoomed_preview(
    canvas: NDArray[np.uint8],
    rgba_1x: NDArray[np.uint8],
    surf: IndexedSurface,
    layout: _SceneSheetLayout,
) -> None:
    zoom_val = layout.zoom_val
    zoomed_rgba = np.repeat(np.repeat(rgba_1x, zoom_val, axis=0), zoom_val, axis=1)
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
    composite_rgba(canvas, zoomed_rgba, layout.zoom_x, layout.zoom_y)
    _draw_rect_outline(
        canvas,
        layout.zoom_x - 1,
        layout.zoom_y - 1,
        layout.zoomed_w + 2,
        layout.zoomed_h + 2,
        _BORDER_SUBTLE,
    )

    tick_step = 16 if max(surf.width, surf.height) > 96 else 4
    for x in range(0, surf.width + 1, tick_step):
        px = layout.zoom_x + x * zoom_val
        fill_rgba_rect(canvas, px, layout.zoom_y - 3, 1, 3, _RULER_COLOR)
        if x < surf.width:
            draw_bitmap_text(canvas, str(x), px, layout.zoom_y - 11, _RULER_COLOR)
    for y in range(0, surf.height + 1, tick_step):
        py = layout.zoom_y + y * zoom_val
        fill_rgba_rect(canvas, layout.zoom_x - 3, py, 3, 1, _RULER_COLOR)
        if y < surf.height:
            label = str(y)
            tw, _ = measure_text(label)
            draw_bitmap_text(canvas, label, max(4, layout.zoom_x - 5 - tw), py, _RULER_COLOR)


def _draw_sheet_overlays(
    canvas: NDArray[np.uint8],
    result: SceneCompositionResult,
    layout: _SceneSheetLayout,
) -> None:
    zoom_val = layout.zoom_val
    for anchor in result.parent_anchors:
        ax = layout.zoom_x + anchor.x * zoom_val + (zoom_val // 2)
        ay = layout.zoom_y + anchor.y * zoom_val + (zoom_val // 2)
        fill_rgba_rect(canvas, ax - 3, ay, 7, 1, _ANCHOR_COLOR)
        fill_rgba_rect(canvas, ax, ay - 3, 1, 7, _ANCHOR_COLOR)

    for p in result.placements:
        bx, by, bw, bh = (
            p.opaque_bbox if p.opaque_bbox is not None else (p.dest_x, p.dest_y, p.width, p.height)
        )
        has_prop_warn = p.occluded_pixels > 0 or not p.perspective_match
        color = _TEXT_ERR if not p.in_bounds else (_TEXT_WARN if has_prop_warn else _TEXT_OK)
        rx = layout.zoom_x + bx * zoom_val
        ry = layout.zoom_y + by * zoom_val
        _draw_rect_outline(canvas, rx, ry, bw * zoom_val, bh * zoom_val, color)
        draw_bitmap_text(
            canvas, f"{p.prop_id}@{p.anchor}", rx + 2, max(layout.zoom_y, ry - 8), color
        )


def _draw_1x_previews(
    canvas: NDArray[np.uint8],
    rgba_1x: NDArray[np.uint8],
    surf: IndexedSurface,
    layout: _SceneSheetLayout,
) -> None:
    draw_bitmap_text(canvas, "1X DARK", layout.right_x, layout.right_y, _TEXT_MUTED)
    draw_checkerboard(
        canvas,
        layout.right_x,
        layout.right_y + 10,
        surf.width,
        surf.height,
        _CHECK_DARK_A,
        _CHECK_DARK_B,
        4,
    )
    composite_rgba(canvas, rgba_1x, layout.right_x, layout.right_y + 10)

    light_y = layout.right_y + surf.height + 24
    draw_bitmap_text(canvas, "1X LIGHT", layout.right_x, light_y, _TEXT_MUTED)
    draw_checkerboard(
        canvas,
        layout.right_x,
        light_y + 10,
        surf.width,
        surf.height,
        _CHECK_LIGHT_A,
        _CHECK_LIGHT_B,
        4,
    )
    composite_rgba(canvas, rgba_1x, layout.right_x, light_y + 10)


def _draw_placement_table(
    canvas: NDArray[np.uint8],
    result: SceneCompositionResult,
    layout: _SceneSheetLayout,
) -> None:
    draw_bitmap_text(canvas, "MOUNT PLACEMENTS", layout.pad, layout.table_y, _TEXT_LIGHT)
    for idx, line in enumerate(layout.placement_lines):
        if idx < len(result.placements):
            pl = result.placements[idx]
            has_row_warn = pl.occluded_pixels > 0 or not pl.perspective_match
            row_col = (
                _TEXT_ERR if not pl.in_bounds else (_TEXT_WARN if has_row_warn else _TEXT_MUTED)
            )
        else:
            row_col = _TEXT_MUTED
        draw_bitmap_text(canvas, line, layout.pad, layout.table_y + 14 + idx * 12, row_col)


def generate_scene_sheet(
    result: SceneCompositionResult,
    style: StylePack,
    *,
    variant: str | None = None,
    zoom: int | None = None,
) -> SceneSheetResult:
    """Render a diagnostic composite scene contact sheet with anchor/bounds overlays."""
    layout = _compute_sheet_layout(result, zoom)
    canvas = np.empty((layout.canvas_h, layout.canvas_w, 4), dtype=np.uint8)
    canvas[:, :] = (*_BG_MAIN, 255)
    fill_rgba_rect(canvas, 0, 0, layout.canvas_w, layout.header_h, _BG_HEADER)
    fill_rgba_rect(canvas, 0, layout.header_h, layout.canvas_w, 1, _BORDER_SUBTLE)

    draw_bitmap_text(canvas, layout.title_line, layout.pad, 8, _TEXT_LIGHT)
    draw_bitmap_text(canvas, layout.summary_line, layout.pad, 22, layout.summary_color)

    rgba_1x = surface_to_rgba(result.surface, style, variant=variant)
    _draw_zoomed_preview(canvas, rgba_1x, result.surface, layout)
    _draw_sheet_overlays(canvas, result, layout)
    _draw_1x_previews(canvas, rgba_1x, result.surface, layout)
    _draw_placement_table(canvas, result, layout)

    return SceneSheetResult(
        width=layout.canvas_w,
        height=layout.canvas_h,
        rgba=canvas,
        png=rgba_to_png(canvas),
    )


__all__ = ["generate_scene_sheet"]
