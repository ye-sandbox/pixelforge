"""Deterministic scene-composition helper, anchor/bounds validation, and preview sheets."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from pixelforge.core.builder import Asset
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import TRANSPARENT_INDEX, AnchorPoint, AssetSpec, HitboxRect, StylePack
from pixelforge.export._canvas import Rgb, composite_rgba, draw_checkerboard
from pixelforge.export._font import draw_bitmap_text, fill_rgba_rect, measure_text
from pixelforge.export.bundle import (
    AssetModule,
    ExportBundleOptions,
    ExportBundleResult,
    RenderedFrame,
    export_rendered_frames_bundle,
)
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


DepthSortMode = Literal["z_index", "iso_y"]


class SceneCompositionError(ValueError):
    """Raised when scene composition fails style, anchor, state, or strict bounds checks."""


class SceneMountSpec(BaseModel):
    """Single child prop mount directive targeting a parent scene anchor."""

    model_config = ConfigDict(frozen=True)

    prop_id: str = Field(min_length=1)
    anchor: str = Field(min_length=1)
    prop_anchor: str | None = None
    state: str | None = None
    state_map: dict[str, str] | None = None
    frame: int | None = Field(default=None, ge=0)
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
    depth_sort: DepthSortMode = "z_index"


class SceneSpec(BaseModel):
    """Declarative `.scene.py` module specification compiled alongside `.asset.py`."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    parent_id: str = Field(min_length=1)
    style_id: str | None = None
    states: tuple[str, ...] | None = None
    frames: int | None = Field(default=None, ge=1)
    fps: int | None = Field(default=None, ge=1, le=60)
    mounts: tuple[SceneMountSpec, ...] = ()
    depth_sort: DepthSortMode = "iso_y"
    variant: str | None = None
    strict_bounds: bool = False
    strict_perspective: bool = False


@runtime_checkable
class SceneModule(Protocol):
    """Protocol satisfied by any `.scene.py` module or wrapper object."""

    @property
    def SCENE(self) -> SceneSpec: ...


@dataclass(frozen=True)
class LoadedScene:
    """In-memory `SceneModule` container holding `SCENE`."""

    SCENE: SceneSpec


class MountedPropPlacement(BaseModel):
    """Resolved placement, bounds, and occlusion diagnostics for one mounted prop."""

    model_config = ConfigDict(frozen=True)

    prop_id: str
    anchor: str
    prop_anchor: str | None
    perspective: str
    perspective_match: bool
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
    parent_hitboxes: tuple[HitboxRect, ...] = ()


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


def _resolve_prop_state(prop: AssetModule, mount: SceneMountSpec, parent_state: str) -> str:
    if mount.state_map is not None and parent_state in mount.state_map:
        return mount.state_map[parent_state]
    if mount.state is not None:
        return mount.state
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


@dataclass(frozen=True)
class _StagedPlacement:
    mount: SceneMountSpec
    perspective: str
    perspective_match: bool
    state: str
    frame: int
    dest_x: int
    dest_y: int
    width: int
    height: int
    opaque_bbox: tuple[int, int, int, int] | None
    in_bounds: bool
    clipped_pixels: int
    canvas_mask: NDArray[np.bool_]


def _order_mounts(
    mounts: tuple[SceneMountSpec, ...],
    parent_anchors: tuple[AnchorPoint, ...],
    parent_id: str,
    depth_sort: DepthSortMode,
) -> list[tuple[SceneMountSpec, AnchorPoint]]:
    # INVARIANT: Sort mounts deterministically before blitting so painter's-algorithm
    # compositing and occlusion checks never depend on dict order. `iso_y` sorts by
    # (z_index, anchor_y + offset_y, decl_index) for back-to-front isometric layering.
    resolved_anchors = [
        _resolve_anchor_point(parent_anchors, m.anchor, owner_id=parent_id) for m in mounts
    ]
    if depth_sort == "iso_y":
        ordered = sorted(
            enumerate(zip(mounts, resolved_anchors, strict=True)),
            key=lambda item: (item[1][0].z_index, item[1][1].y + item[1][0].offset_y, item[0]),
        )
    else:
        ordered = sorted(
            enumerate(zip(mounts, resolved_anchors, strict=True)),
            key=lambda item: (item[1][0].z_index, item[0]),
        )
    return [pair for _, pair in ordered]


def _validate_mounted_prop(
    mount: SceneMountSpec,
    parent_spec: AssetSpec,
    props_by_id: Mapping[str, AssetModule],
    style_id: str,
    *,
    strict_perspective: bool,
) -> tuple[AssetModule, bool, list[str]]:
    prop = props_by_id.get(mount.prop_id)
    if prop is None:
        msg = f"Mounted prop asset {mount.prop_id!r} not found"
        raise SceneCompositionError(msg)
    if prop.SPEC.style_id != style_id:
        msg = (
            f"Prop asset {prop.SPEC.id!r} uses style {prop.SPEC.style_id!r}, "
            f"cannot compose onto {style_id!r}"
        )
        raise SceneCompositionError(msg)

    warnings: list[str] = []
    perspective_match = prop.SPEC.perspective == parent_spec.perspective
    if not perspective_match:
        persp_detail = (
            f"Prop {prop.SPEC.id!r} has perspective {prop.SPEC.perspective!r}, "
            f"which differs from parent {parent_spec.id!r} ({parent_spec.perspective!r})"
        )
        if strict_perspective:
            raise SceneCompositionError(persp_detail)
        warnings.append(persp_detail)
    return prop, perspective_match, warnings


def _blit_mounted_prop(
    composite: IndexedSurface,
    parent_spec: AssetSpec,
    parent_state: str,
    mount: SceneMountSpec,
    parent_anchor: AnchorPoint,
    props_by_id: Mapping[str, AssetModule],
    style: StylePack,
    variant: str | None,
    *,
    strict_bounds: bool,
    strict_perspective: bool,
) -> tuple[_StagedPlacement, list[str]]:
    prop, perspective_match, warnings = _validate_mounted_prop(
        mount,
        parent_spec,
        props_by_id,
        style.id,
        strict_perspective=strict_perspective,
    )
    prop_state = _resolve_prop_state(prop, mount, parent_state)
    prop_frame = mount.frame if mount.frame is not None else 0
    prop_rendered = _render_single_frame(
        prop,
        style,
        state=prop_state,
        frame=prop_frame,
        variant=variant,
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
    staged = _StagedPlacement(
        mount=mount,
        perspective=prop.SPEC.perspective,
        perspective_match=perspective_match,
        state=prop_state,
        frame=prop_frame,
        dest_x=dest_x,
        dest_y=dest_y,
        width=prop_rendered.surface.width,
        height=prop_rendered.surface.height,
        opaque_bbox=bbox,
        in_bounds=in_bounds,
        clipped_pixels=clipped_pixels,
        canvas_mask=canvas_mask,
    )
    return staged, warnings


def _finalize_placements(
    staged: list[_StagedPlacement],
) -> tuple[list[MountedPropPlacement], list[str]]:
    placements: list[MountedPropPlacement] = []
    warnings: list[str] = []

    for idx, entry in enumerate(staged):
        occluded_mask = np.zeros_like(entry.canvas_mask)
        occluded_by: list[str] = []
        for later in staged[idx + 1 :]:
            overlap = entry.canvas_mask & later.canvas_mask
            if np.any(overlap):
                occluded_mask |= overlap
                occluded_by.append(f"{later.mount.prop_id}@{later.mount.anchor}")

        occluded_pixels = int(np.count_nonzero(occluded_mask))
        if occluded_pixels > 0:
            warnings.append(
                f"Prop {entry.mount.prop_id!r} at {entry.mount.anchor!r} has {occluded_pixels} "
                f"pixel(s) occluded by {', '.join(occluded_by)}"
            )

        placements.append(
            MountedPropPlacement(
                prop_id=entry.mount.prop_id,
                anchor=entry.mount.anchor,
                prop_anchor=entry.mount.prop_anchor,
                perspective=entry.perspective,
                perspective_match=entry.perspective_match,
                state=entry.state,
                frame=entry.frame,
                z_index=entry.mount.z_index,
                dest_x=entry.dest_x,
                dest_y=entry.dest_y,
                width=entry.width,
                height=entry.height,
                opaque_bbox=entry.opaque_bbox,
                in_bounds=entry.in_bounds,
                clipped_pixels=entry.clipped_pixels,
                occluded_by=tuple(occluded_by),
                occluded_pixels=occluded_pixels,
            )
        )

    return placements, warnings


def compose_scene(
    parent: AssetModule,
    props_by_id: Mapping[str, AssetModule],
    style: StylePack,
    spec: SceneCompositionSpec,
    *,
    strict_bounds: bool = False,
    strict_perspective: bool = False,
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
    ordered_mounts = _order_mounts(
        spec.mounts, parent_rendered.anchors, parent.SPEC.id, spec.depth_sort
    )

    staged: list[_StagedPlacement] = []
    warnings: list[str] = []
    for mount, parent_anchor in ordered_mounts:
        entry, prop_warnings = _blit_mounted_prop(
            composite,
            parent.SPEC,
            parent_state,
            mount,
            parent_anchor,
            props_by_id,
            style,
            spec.variant,
            strict_bounds=strict_bounds,
            strict_perspective=strict_perspective,
        )
        staged.append(entry)
        warnings.extend(prop_warnings)

    placements, occlusion_warnings = _finalize_placements(staged)
    warnings.extend(occlusion_warnings)

    return SceneCompositionResult(
        parent_id=parent.SPEC.id,
        style_id=style.id,
        parent_state=parent_state,
        parent_frame=spec.parent_frame,
        surface=composite,
        parent_anchors=parent_rendered.anchors,
        placements=tuple(placements),
        warnings=tuple(warnings),
        parent_hitboxes=parent_rendered.hitboxes,
    )


def resolve_scene_asset_spec(
    scene_spec: SceneSpec,
    parent: AssetModule,
    props_by_id: Mapping[str, AssetModule],
) -> AssetSpec:
    """Resolve the effective `AssetSpec` (states, looping frame cycle, fps) for a `SceneSpec`."""
    if parent.SPEC.id != scene_spec.parent_id:
        msg = f"Expected parent asset {scene_spec.parent_id!r}, got {parent.SPEC.id!r}"
        raise SceneCompositionError(msg)
    if scene_spec.style_id is not None and scene_spec.style_id != parent.SPEC.style_id:
        msg = (
            f"Scene {scene_spec.id!r} specifies style {scene_spec.style_id!r}, "
            f"but parent {parent.SPEC.id!r} uses {parent.SPEC.style_id!r}"
        )
        raise SceneCompositionError(msg)

    frame_counts = [parent.SPEC.frames]
    for mount in scene_spec.mounts:
        prop = props_by_id.get(mount.prop_id)
        if prop is None:
            msg = f"Mounted prop asset {mount.prop_id!r} not found"
            raise SceneCompositionError(msg)
        if mount.frame is None:
            frame_counts.append(prop.SPEC.frames)

    frames = scene_spec.frames if scene_spec.frames is not None else math.lcm(*frame_counts)
    states = scene_spec.states if scene_spec.states is not None else parent.SPEC.states
    fps = scene_spec.fps if scene_spec.fps is not None else parent.SPEC.fps
    return AssetSpec(
        id=scene_spec.id,
        style_id=parent.SPEC.style_id,
        perspective=parent.SPEC.perspective,
        width=parent.SPEC.width,
        height=parent.SPEC.height,
        states=states,
        frames=frames,
        fps=fps,
    )


def compose_scene_frames(
    scene_spec: SceneSpec,
    parent: AssetModule,
    props_by_id: Mapping[str, AssetModule],
    style: StylePack,
    *,
    variant: str | None = None,
) -> tuple[AssetSpec, tuple[RenderedFrame, ...], tuple[str, ...]]:
    """Synchronously compose all `(state, frame)` pairs for a declarative `SceneSpec`."""
    asset_spec = resolve_scene_asset_spec(scene_spec, parent, props_by_id)
    effective_variant = variant if variant is not None else scene_spec.variant
    rendered_frames: list[RenderedFrame] = []
    seen_warnings: dict[str, None] = {}

    for state in asset_spec.states:
        for frame_idx in range(asset_spec.frames):
            # INVARIANT: Unpinned mounts cycle via `frame_idx % prop.SPEC.frames` so
            # multi-frame scenes stay synchronized across parent and child animations.
            sync_mounts = tuple(
                mount.model_copy(
                    update={
                        "frame": (
                            mount.frame
                            if mount.frame is not None
                            else frame_idx % props_by_id[mount.prop_id].SPEC.frames
                        ),
                    }
                )
                for mount in scene_spec.mounts
            )
            comp_spec = SceneCompositionSpec(
                parent_id=scene_spec.parent_id,
                parent_state=state,
                parent_frame=frame_idx % parent.SPEC.frames,
                mounts=sync_mounts,
                variant=effective_variant,
                depth_sort=scene_spec.depth_sort,
            )
            res = compose_scene(
                parent,
                props_by_id,
                style,
                comp_spec,
                strict_bounds=scene_spec.strict_bounds,
                strict_perspective=scene_spec.strict_perspective,
            )
            for warning in res.warnings:
                seen_warnings.setdefault(warning, None)
            rendered_frames.append(
                RenderedFrame(
                    state=state,
                    frame=frame_idx,
                    surface=res.surface,
                    anchors=res.parent_anchors,
                    hitboxes=res.parent_hitboxes,
                )
            )

    return asset_spec, tuple(rendered_frames), tuple(seen_warnings.keys())


def export_scene_bundle(
    scene_spec: SceneSpec,
    parent: AssetModule,
    props_by_id: Mapping[str, AssetModule],
    style: StylePack,
    options: ExportBundleOptions | None = None,
) -> ExportBundleResult:
    """Compile a declarative `SceneSpec` into a full `ExportBundleResult`."""
    opts = options or ExportBundleOptions()
    asset_spec, rendered_frames, _ = compose_scene_frames(
        scene_spec,
        parent,
        props_by_id,
        style,
        variant=opts.variant,
    )
    return export_rendered_frames_bundle(asset_spec, rendered_frames, style, opts)


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
