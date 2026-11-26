"""Deterministic scene composition engine and bundle exporter."""

from __future__ import annotations

import difflib
import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.builder import Asset, LayerSemanticSpan
from pixelforge.core.semantics import derive_gameplay_semantics
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import TRANSPARENT_INDEX, AnchorPoint, AssetSpec, HitboxRect, StylePack
from pixelforge.export.bundle import (
    AssetModule,
    ExportBundleOptions,
    ExportBundleResult,
    RenderedFrame,
    export_rendered_frames_bundle,
)
from pixelforge.export.scene_models import (
    DepthSortMode,
    MountedPropPlacement,
    SceneCompositionError,
    SceneCompositionResult,
    SceneCompositionSpec,
    SceneMountSpec,
    SceneSpec,
)


def _render_single_frame(
    asset: AssetModule,
    style: StylePack,
    *,
    state: str,
    frame: int,
    variant: str | None,
    track_maps: bool = False,
) -> RenderedFrame:
    spec = asset.SPEC
    if state not in spec.states:
        available = ", ".join(spec.states)
        msg = f"Asset {spec.id!r} has no state {state!r} (available: {available})"
        raise SceneCompositionError(msg)
    if frame < 0 or frame >= spec.frames:
        msg = f"Asset {spec.id!r} frame {frame} out of range [0..{spec.frames - 1}]"
        raise SceneCompositionError(msg)

    builder = Asset(spec, style, state=state, frame=frame, variant=variant, track_maps=track_maps)
    asset.render(builder)
    return RenderedFrame(
        state=state,
        frame=frame,
        surface=builder.root_surface,
        anchors=builder.anchors,
        hitboxes=builder.hitboxes,
        layer_spans=builder.layer_spans,
        normal_map=builder.normal_map,
        height_map=builder.height_map,
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
    anchor_names = [a.name for a in anchors]
    available = ", ".join(anchor_names) or "(none)"
    matches = difflib.get_close_matches(name, anchor_names, n=3, cutoff=0.6)
    suggestion = f"; did you mean {', '.join(repr(m) for m in matches)}" if matches else ""
    msg = f"Anchor {name!r} not found on asset {owner_id!r} (available: {available}{suggestion})"
    raise SceneCompositionError(msg)


def _compute_placed_bounds(
    prop_surface: IndexedSurface,
    dest_x: int,
    dest_y: int,
    canvas_w: int,
    canvas_h: int,
) -> tuple[tuple[int, int, int, int] | None, bool, int, int, NDArray[np.bool_]]:
    opaque_local = prop_surface.data != TRANSPARENT_INDEX
    ys, xs = np.nonzero(opaque_local)
    canvas_mask = np.zeros((canvas_h, canvas_w), dtype=bool)
    opaque_pixels = len(xs)

    if opaque_pixels == 0:
        in_bounds = (
            dest_x >= 0
            and dest_y >= 0
            and dest_x + prop_surface.width <= canvas_w
            and dest_y + prop_surface.height <= canvas_h
        )
        return None, in_bounds, 0, 0, canvas_mask

    world_xs = xs + dest_x
    world_ys = ys + dest_y
    bbox = (
        int(world_xs.min()),
        int(world_ys.min()),
        int(world_xs.max() - world_xs.min() + 1),
        int(world_ys.max() - world_ys.min() + 1),
    )

    inside = (world_xs >= 0) & (world_xs < canvas_w) & (world_ys >= 0) & (world_ys < canvas_h)
    clipped_pixels = int(opaque_pixels - int(np.count_nonzero(inside)))
    if np.any(inside):
        canvas_mask[world_ys[inside], world_xs[inside]] = True

    return bbox, clipped_pixels == 0, clipped_pixels, opaque_pixels, canvas_mask


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
    opaque_pixels: int
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
    track_maps: bool = False,
) -> tuple[
    _StagedPlacement,
    list[str],
    tuple[AnchorPoint, ...],
    tuple[HitboxRect, ...],
    tuple[LayerSemanticSpan, ...],
]:
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
        track_maps=track_maps,
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

    bbox, in_bounds, clipped_pixels, opaque_pixels, canvas_mask = _compute_placed_bounds(
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

    z_offset = 0.0
    if (
        composite.maps is not None
        and prop_rendered.surface.maps is not None
        and 0 <= parent_anchor.x < composite.width
        and 0 <= parent_anchor.y < composite.height
    ):
        z_offset = float(composite.maps.height_data[parent_anchor.y, parent_anchor.x])
    composite.blit_layer(prop_rendered.surface, dest_x, dest_y, z_offset=z_offset)
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
        opaque_pixels=opaque_pixels,
        in_bounds=in_bounds,
        clipped_pixels=clipped_pixels,
        canvas_mask=canvas_mask,
    )
    shifted_anchors = tuple(
        AnchorPoint(
            name=f"{mount.prop_id}.{a.name}",
            x=a.x + dest_x,
            y=a.y + dest_y,
            kind=a.kind,
            dir=a.dir,
        )
        for a in prop_rendered.anchors
    )
    shifted_hitboxes = tuple(
        HitboxRect(
            name=f"{mount.prop_id}.{h.name}",
            x=h.x + dest_x,
            y=h.y + dest_y,
            w=h.w,
            h=h.h,
            kind=h.kind,
        )
        for h in prop_rendered.hitboxes
    )
    shifted_spans = tuple(
        LayerSemanticSpan(
            name=f"{mount.prop_id}.{s.name}",
            role=s.role,
            x=s.x + dest_x,
            y=s.y + dest_y,
            w=s.w,
            h=s.h,
            mask=s.mask,
        )
        for s in prop_rendered.layer_spans
    )
    return staged, warnings, shifted_anchors, shifted_hitboxes, shifted_spans


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
                opaque_pixels=entry.opaque_pixels,
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
    track_maps: bool = False,
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
        track_maps=track_maps,
    )
    composite = parent_rendered.surface.clone()
    ordered_mounts = _order_mounts(
        spec.mounts, parent_rendered.anchors, parent.SPEC.id, spec.depth_sort
    )

    staged: list[_StagedPlacement] = []
    warnings: list[str] = []
    semantic_anchors: list[AnchorPoint] = list(parent_rendered.anchors)
    semantic_hitboxes: list[HitboxRect] = list(parent_rendered.hitboxes)
    layer_spans: list[LayerSemanticSpan] = list(parent_rendered.layer_spans)
    for mount, parent_anchor in ordered_mounts:
        entry, prop_warnings, prop_anchors, prop_hitboxes, prop_spans = _blit_mounted_prop(
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
            track_maps=track_maps,
        )
        staged.append(entry)
        warnings.extend(prop_warnings)
        semantic_anchors.extend(prop_anchors)
        semantic_hitboxes.extend(prop_hitboxes)
        layer_spans.extend(prop_spans)

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
        semantic_anchors=tuple(semantic_anchors),
        semantic_hitboxes=tuple(semantic_hitboxes),
        layer_spans=tuple(layer_spans),
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


def compose_scene_results(
    scene_spec: SceneSpec,
    parent: AssetModule,
    props_by_id: Mapping[str, AssetModule],
    style: StylePack,
    *,
    variant: str | None = None,
    strict_bounds: bool | None = None,
    strict_perspective: bool | None = None,
    track_maps: bool = False,
) -> tuple[AssetSpec, tuple[SceneCompositionResult, ...], tuple[str, ...]]:
    """Synchronously compose all `(state, frame)` pairs and return scene results."""
    asset_spec = resolve_scene_asset_spec(scene_spec, parent, props_by_id)
    effective_variant = variant if variant is not None else scene_spec.variant
    eff_strict_bounds = scene_spec.strict_bounds if strict_bounds is None else strict_bounds
    eff_strict_perspective = (
        scene_spec.strict_perspective if strict_perspective is None else strict_perspective
    )
    results: list[SceneCompositionResult] = []
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
                strict_bounds=eff_strict_bounds,
                strict_perspective=eff_strict_perspective,
                track_maps=track_maps,
            )
            for warning in res.warnings:
                seen_warnings.setdefault(warning, None)
            results.append(res)

    return asset_spec, tuple(results), tuple(seen_warnings.keys())


def compose_scene_frames(
    scene_spec: SceneSpec,
    parent: AssetModule,
    props_by_id: Mapping[str, AssetModule],
    style: StylePack,
    *,
    variant: str | None = None,
) -> tuple[AssetSpec, tuple[RenderedFrame, ...], tuple[str, ...]]:
    """Synchronously compose all `(state, frame)` pairs for a declarative `SceneSpec`."""
    asset_spec, results, warnings = compose_scene_results(
        scene_spec,
        parent,
        props_by_id,
        style,
        variant=variant,
    )
    rendered_frames = tuple(
        RenderedFrame(
            state=res.parent_state,
            frame=idx % asset_spec.frames,
            surface=res.surface,
            anchors=res.parent_anchors,
            hitboxes=res.parent_hitboxes,
        )
        for idx, res in enumerate(results)
    )
    return asset_spec, rendered_frames, warnings


def export_scene_bundle(
    scene_spec: SceneSpec,
    parent: AssetModule,
    props_by_id: Mapping[str, AssetModule],
    style: StylePack,
    options: ExportBundleOptions | None = None,
) -> ExportBundleResult:
    """Compile a declarative `SceneSpec` into a full `ExportBundleResult`."""
    opts = options or ExportBundleOptions()
    asset_spec, results, _ = compose_scene_results(
        scene_spec,
        parent,
        props_by_id,
        style,
        variant=opts.variant,
        track_maps=(opts.normals or opts.height),
    )
    rendered_frames = tuple(
        RenderedFrame(
            state=res.parent_state,
            frame=idx % asset_spec.frames,
            surface=res.surface,
            anchors=res.parent_anchors,
            hitboxes=res.parent_hitboxes,
            layer_spans=res.layer_spans,
            normal_map=res.surface.maps.normals if res.surface.maps is not None else None,
            height_map=res.surface.maps.height_data if res.surface.maps is not None else None,
        )
        for idx, res in enumerate(results)
    )
    baseline = results[0]
    scene_semantics = derive_gameplay_semantics(
        asset_spec,
        baseline.surface,
        anchors=baseline.semantic_anchors,
        hitboxes=baseline.semantic_hitboxes,
        layer_spans=baseline.layer_spans,
    )
    return export_rendered_frames_bundle(
        asset_spec,
        rendered_frames,
        style,
        opts,
        semantics=scene_semantics,
    )


__all__ = [
    "compose_scene",
    "compose_scene_frames",
    "compose_scene_results",
    "export_scene_bundle",
    "resolve_scene_asset_spec",
]
