"""Deterministic scene-composition helper, anchor/bounds validation, and preview sheets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from pixelforge.core.builder import Asset
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import TRANSPARENT_INDEX, AnchorPoint, StylePack
from pixelforge.export._canvas import Rgb, composite_rgba, draw_checkerboard
from pixelforge.export._font import draw_bitmap_text, fill_rgba_rect, measure_text
from pixelforge.export.bundle import AssetModule, RenderedFrame
from pixelforge.export.contact_sheet import choose_zoom
from pixelforge.export.png import rgba_to_png, surface_to_rgba

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


class SceneCompositionError(ValueError):
    """Raised when scene composition fails style, anchor, state, or strict bounds checks."""


class SceneMountSpec(BaseModel):
    """Single child prop mount directive targeting a parent scene anchor."""

    model_config = ConfigDict(frozen=True)

    prop_id: str = Field(min_length=1)
    anchor: str = Field(min_length=1)
    prop_anchor: str | None = None
    state: str | None = None
    frame: int = Field(default=0, ge=0)
    offset_x: int = 0
    offset_y: int = 0
    z_index: int = 0


class SceneCompositionSpec(BaseModel):
    """Complete deterministic scene composition specification."""

    model_config = ConfigDict(frozen=True)

    parent_id: str = Field(min_length=1)
    parent_state: str | None = None
    parent_frame: int = Field(default=0, ge=0)
    mounts: tuple[SceneMountSpec, ...] = ()
    variant: str | None = None


class MountedPropPlacement(BaseModel):
    """Resolved placement, bounds, and occlusion diagnostics for one mounted prop."""

    model_config = ConfigDict(frozen=True)

    prop_id: str
    anchor: str
    prop_anchor: str | None
    state: str
    frame: int
    z_index: int
    dest_x: int
    dest_y: int
    width: int
    height: int
    opaque_bbox: tuple[int, int, int, int] | None
    in_bounds: bool
    clipped_pixels: int
    occluded_by: tuple[str, ...]
    occluded_pixels: int


@dataclass(frozen=True)
class SceneCompositionResult:
    """Compiled composite surface alongside anchor, bounds, and occlusion diagnostics."""

    parent_id: str
    style_id: str
    parent_state: str
    parent_frame: int
    surface: IndexedSurface
    parent_anchors: tuple[AnchorPoint, ...]
    placements: tuple[MountedPropPlacement, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SceneSheetResult:
    """Generated composite scene contact sheet RGBA buffer and PNG bytes."""

    width: int
    height: int
    rgba: NDArray[np.uint8]
    png: bytes


def _render_single_frame(
    asset: AssetModule,
    style: StylePack,
    *,
    state: str,
    frame: int,
    variant: str | None,
) -> RenderedFrame:
    spec = asset.SPEC
    if state not in spec.states:
        available = ", ".join(spec.states)
        msg = f"Asset {spec.id!r} has no state {state!r} (available: {available})"
        raise SceneCompositionError(msg)
    if frame < 0 or frame >= spec.frames:
        msg = f"Asset {spec.id!r} frame {frame} out of range [0..{spec.frames - 1}]"
        raise SceneCompositionError(msg)

    builder = Asset(spec, style, state=state, frame=frame, variant=variant)
    asset.render(builder)
    return RenderedFrame(
        state=state,
        frame=frame,
        surface=builder.root_surface,
        anchors=builder.anchors,
        hitboxes=builder.hitboxes,
    )


def _resolve_prop_state(prop: AssetModule, requested: str | None, parent_state: str) -> str:
    if requested is not None:
        return requested
    if parent_state in prop.SPEC.states:
        return parent_state
    return prop.SPEC.states[0]


def _resolve_anchor_point(
    anchors: tuple[AnchorPoint, ...],
    name: str,
    *,
    owner_id: str,
) -> AnchorPoint:
    for anchor in anchors:
        if anchor.name == name:
            return anchor
    available = ", ".join(a.name for a in anchors) or "(none)"
    msg = f"Anchor {name!r} not found on asset {owner_id!r} (available: {available})"
    raise SceneCompositionError(msg)


def _compute_placed_bounds(
    prop_surface: IndexedSurface,
    dest_x: int,
    dest_y: int,
    canvas_w: int,
    canvas_h: int,
) -> tuple[tuple[int, int, int, int] | None, bool, int, NDArray[np.bool_]]:
    opaque_local = prop_surface.data != TRANSPARENT_INDEX
    ys, xs = np.nonzero(opaque_local)
    canvas_mask = np.zeros((canvas_h, canvas_w), dtype=bool)

    if len(xs) == 0:
        in_bounds = (
            dest_x >= 0
            and dest_y >= 0
            and dest_x + prop_surface.width <= canvas_w
            and dest_y + prop_surface.height <= canvas_h
        )
        return None, in_bounds, 0, canvas_mask

    world_xs = xs + dest_x
    world_ys = ys + dest_y
    bbox = (
        int(world_xs.min()),
        int(world_ys.min()),
        int(world_xs.max() - world_xs.min() + 1),
        int(world_ys.max() - world_ys.min() + 1),
    )

    inside = (world_xs >= 0) & (world_xs < canvas_w) & (world_ys >= 0) & (world_ys < canvas_h)
    clipped_pixels = int(len(xs) - int(np.count_nonzero(inside)))
    if np.any(inside):
        canvas_mask[world_ys[inside], world_xs[inside]] = True

    return bbox, clipped_pixels == 0, clipped_pixels, canvas_mask


def compose_scene(
    parent: AssetModule,
    props_by_id: Mapping[str, AssetModule],
    style: StylePack,
    spec: SceneCompositionSpec,
    *,
    strict_bounds: bool = False,
) -> SceneCompositionResult:
    """Deterministically compose child prop assets onto a parent scene's declared anchors."""
    if parent.SPEC.id != spec.parent_id:
        msg = f"Expected parent asset {spec.parent_id!r}, got {parent.SPEC.id!r}"
        raise SceneCompositionError(msg)
    if parent.SPEC.style_id != style.id:
        msg = (
            f"Parent asset {parent.SPEC.id!r} uses style {parent.SPEC.style_id!r}, "
            f"expected {style.id!r}"
        )
        raise SceneCompositionError(msg)

    parent_state = spec.parent_state or parent.SPEC.states[0]
    parent_rendered = _render_single_frame(
        parent,
        style,
        state=parent_state,
        frame=spec.parent_frame,
        variant=spec.variant,
    )
    composite = parent_rendered.surface.clone()

    # INVARIANT: Sort mounts deterministically by (z_index, declaration_index) so
    # painter's-algorithm compositing and occlusion checks never depend on dict order.
    ordered_mounts = sorted(enumerate(spec.mounts), key=lambda item: (item[1].z_index, item[0]))

    staged: list[
        tuple[
            SceneMountSpec,
            str,
            int,
            int,
            int,
            int,
            tuple[int, int, int, int] | None,
            bool,
            int,
            NDArray[np.bool_],
        ]
    ] = []
    warnings: list[str] = []

    for _, mount in ordered_mounts:
        prop = props_by_id.get(mount.prop_id)
        if prop is None:
            msg = f"Mounted prop asset {mount.prop_id!r} not found"
            raise SceneCompositionError(msg)
        if prop.SPEC.style_id != style.id:
            msg = (
                f"Prop asset {prop.SPEC.id!r} uses style {prop.SPEC.style_id!r}, "
                f"cannot compose onto {style.id!r}"
            )
            raise SceneCompositionError(msg)

        parent_anchor = _resolve_anchor_point(
            parent_rendered.anchors,
            mount.anchor,
            owner_id=parent.SPEC.id,
        )
        prop_state = _resolve_prop_state(prop, mount.state, parent_state)
        prop_rendered = _render_single_frame(
            prop,
            style,
            state=prop_state,
            frame=mount.frame,
            variant=spec.variant,
        )

        if mount.prop_anchor is not None:
            child_anchor = _resolve_anchor_point(
                prop_rendered.anchors,
                mount.prop_anchor,
                owner_id=prop.SPEC.id,
            )
            align_x, align_y = child_anchor.x, child_anchor.y
        else:
            align_x = prop_rendered.surface.width // 2
            align_y = prop_rendered.surface.height - 1

        dest_x = parent_anchor.x - align_x + mount.offset_x
        dest_y = parent_anchor.y - align_y + mount.offset_y

        bbox, in_bounds, clipped_pixels, canvas_mask = _compute_placed_bounds(
            prop_rendered.surface,
            dest_x,
            dest_y,
            composite.width,
            composite.height,
        )
        if not in_bounds:
            detail = (
                f"Prop {prop.SPEC.id!r} at anchor {mount.anchor!r} exceeds canvas "
                f"{composite.width}x{composite.height} ({clipped_pixels} clipped pixel(s))"
            )
            if strict_bounds:
                raise SceneCompositionError(detail)
            warnings.append(detail)

        composite.blit_layer(prop_rendered.surface, dest_x, dest_y)
        staged.append(
            (
                mount,
                prop_state,
                dest_x,
                dest_y,
                prop_rendered.surface.width,
                prop_rendered.surface.height,
                bbox,
                in_bounds,
                clipped_pixels,
                canvas_mask,
            )
        )

    placements: list[MountedPropPlacement] = []
    for idx, entry in enumerate(staged):
        (
            mount,
            prop_state,
            dest_x,
            dest_y,
            prop_w,
            prop_h,
            bbox,
            in_bounds,
            clipped_pixels,
            mask,
        ) = entry
        occluded_mask = np.zeros_like(mask)
        occluded_by: list[str] = []
        for later_mount, *_, later_mask in staged[idx + 1 :]:
            overlap = mask & later_mask
            if np.any(overlap):
                occluded_mask |= overlap
                occluded_by.append(f"{later_mount.prop_id}@{later_mount.anchor}")

        occluded_pixels = int(np.count_nonzero(occluded_mask))
        if occluded_pixels > 0:
            warnings.append(
                f"Prop {mount.prop_id!r} at {mount.anchor!r} has {occluded_pixels} "
                f"pixel(s) occluded by {', '.join(occluded_by)}"
            )

        placements.append(
            MountedPropPlacement(
                prop_id=mount.prop_id,
                anchor=mount.anchor,
                prop_anchor=mount.prop_anchor,
                state=prop_state,
                frame=mount.frame,
                z_index=mount.z_index,
                dest_x=dest_x,
                dest_y=dest_y,
                width=prop_w,
                height=prop_h,
                opaque_bbox=bbox,
                in_bounds=in_bounds,
                clipped_pixels=clipped_pixels,
                occluded_by=tuple(occluded_by),
                occluded_pixels=occluded_pixels,
            )
        )

    return SceneCompositionResult(
        parent_id=parent.SPEC.id,
        style_id=style.id,
        parent_state=parent_state,
        parent_frame=spec.parent_frame,
        surface=composite,
        parent_anchors=parent_rendered.anchors,
        placements=tuple(placements),
        warnings=tuple(warnings),
    )


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
    occ = f" occ={p.occluded_pixels}px({','.join(p.occluded_by)})" if p.occluded_pixels > 0 else ""
    pa = f":{p.prop_anchor}" if p.prop_anchor else ""
    return (
        f"{p.prop_id}{pa}@{p.anchor} -> ({p.dest_x},{p.dest_y}) "
        f"{p.width}x{p.height} z={p.z_index} [{status}]{occ}"
    )


def generate_scene_sheet(
    result: SceneCompositionResult,
    style: StylePack,
    *,
    variant: str | None = None,
    zoom: int | None = None,
) -> SceneSheetResult:
    """Render a diagnostic composite scene contact sheet with anchor/bounds overlays."""
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
    summary_line = (
        f"canvas={surf.width}x{surf.height}  zoom={zoom_val}x  "
        f"props={len(result.placements)}  oob={oob_count}  occluded={occ_count}"
    )

    right_col_w = max(surf.width + 24, 180)
    table_y = max(zoom_y + zoomed_h + 18, right_y + surf.height * 2 + 46)
    table_h = 18 + len(placement_lines) * 12

    canvas_w = max(
        right_x + right_col_w + pad,
        pad + max_line_w + pad,
        pad + max(measure_text(title_line)[0], measure_text(summary_line)[0]) + pad,
    )
    canvas_h = table_y + table_h + pad

    canvas = np.empty((canvas_h, canvas_w, 4), dtype=np.uint8)
    canvas[:, :] = (*_BG_MAIN, 255)
    fill_rgba_rect(canvas, 0, 0, canvas_w, header_h, _BG_HEADER)
    fill_rgba_rect(canvas, 0, header_h, canvas_w, 1, _BORDER_SUBTLE)

    draw_bitmap_text(canvas, title_line, pad, 8, _TEXT_LIGHT)
    summary_color = _TEXT_ERR if oob_count > 0 else (_TEXT_WARN if occ_count > 0 else _TEXT_MUTED)
    draw_bitmap_text(canvas, summary_line, pad, 22, summary_color)

    rgba_1x = surface_to_rgba(surf, style, variant=variant)
    zoomed_rgba = np.repeat(np.repeat(rgba_1x, zoom_val, axis=0), zoom_val, axis=1)
    draw_checkerboard(canvas, zoom_x, zoom_y, zoomed_w, zoomed_h, _CHECK_DARK_A, _CHECK_DARK_B, 8)
    composite_rgba(canvas, zoomed_rgba, zoom_x, zoom_y)
    _draw_rect_outline(canvas, zoom_x - 1, zoom_y - 1, zoomed_w + 2, zoomed_h + 2, _BORDER_SUBTLE)

    tick_step = 16 if max(surf.width, surf.height) > 96 else 4
    for x in range(0, surf.width + 1, tick_step):
        px = zoom_x + x * zoom_val
        fill_rgba_rect(canvas, px, zoom_y - 3, 1, 3, _RULER_COLOR)
        if x < surf.width:
            draw_bitmap_text(canvas, str(x), px, zoom_y - 11, _RULER_COLOR)
    for y in range(0, surf.height + 1, tick_step):
        py = zoom_y + y * zoom_val
        fill_rgba_rect(canvas, zoom_x - 3, py, 3, 1, _RULER_COLOR)
        if y < surf.height:
            label = str(y)
            tw, _ = measure_text(label)
            draw_bitmap_text(canvas, label, max(4, zoom_x - 5 - tw), py, _RULER_COLOR)

    for anchor in result.parent_anchors:
        ax = zoom_x + anchor.x * zoom_val + (zoom_val // 2)
        ay = zoom_y + anchor.y * zoom_val + (zoom_val // 2)
        fill_rgba_rect(canvas, ax - 3, ay, 7, 1, _ANCHOR_COLOR)
        fill_rgba_rect(canvas, ax, ay - 3, 1, 7, _ANCHOR_COLOR)

    for p in result.placements:
        bx, by, bw, bh = (
            p.opaque_bbox
            if p.opaque_bbox is not None
            else (
                p.dest_x,
                p.dest_y,
                p.width,
                p.height,
            )
        )
        color = (
            _TEXT_ERR if not p.in_bounds else (_TEXT_WARN if p.occluded_pixels > 0 else _TEXT_OK)
        )
        rx = zoom_x + bx * zoom_val
        ry = zoom_y + by * zoom_val
        _draw_rect_outline(canvas, rx, ry, bw * zoom_val, bh * zoom_val, color)
        draw_bitmap_text(canvas, f"{p.prop_id}@{p.anchor}", rx + 2, max(zoom_y, ry - 8), color)

    draw_bitmap_text(canvas, "1X DARK", right_x, right_y, _TEXT_MUTED)
    draw_checkerboard(
        canvas, right_x, right_y + 10, surf.width, surf.height, _CHECK_DARK_A, _CHECK_DARK_B, 4
    )
    composite_rgba(canvas, rgba_1x, right_x, right_y + 10)

    light_y = right_y + surf.height + 24
    draw_bitmap_text(canvas, "1X LIGHT", right_x, light_y, _TEXT_MUTED)
    draw_checkerboard(
        canvas, right_x, light_y + 10, surf.width, surf.height, _CHECK_LIGHT_A, _CHECK_LIGHT_B, 4
    )
    composite_rgba(canvas, rgba_1x, right_x, light_y + 10)

    draw_bitmap_text(canvas, "MOUNT PLACEMENTS", pad, table_y, _TEXT_LIGHT)
    for idx, line in enumerate(placement_lines):
        if idx < len(result.placements):
            pl = result.placements[idx]
            row_col = (
                _TEXT_ERR
                if not pl.in_bounds
                else (_TEXT_WARN if pl.occluded_pixels > 0 else _TEXT_MUTED)
            )
        else:
            row_col = _TEXT_MUTED
        draw_bitmap_text(canvas, line, pad, table_y + 14 + idx * 12, row_col)

    return SceneSheetResult(
        width=canvas_w,
        height=canvas_h,
        rgba=canvas,
        png=rgba_to_png(canvas),
    )
