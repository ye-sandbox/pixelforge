"""Deterministic runtime ergonomics guards for declarative `*.scene.py` modules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

import numpy as np

from pixelforge.core.types import TRANSPARENT_INDEX, AnchorPoint, StylePack
from pixelforge.export.bundle import AssetModule, RenderedFrame, render_asset_frames
from pixelforge.export.scene import (
    MountedPropPlacement,
    SceneCompositionError,
    SceneCompositionResult,
    SceneSpec,
    compose_scene_results,
)
from pixelforge.guard.types import GuardSeverity, GuardViolation

SCENE_OCCLUSION_WARN_RATIO: Final[float] = 0.25
SCENE_OCCLUSION_ERROR_RATIO: Final[float] = 0.50


def _violation(
    file_path: str,
    rule: str,
    detail: str,
    *,
    severity: GuardSeverity = "error",
) -> GuardViolation:
    return GuardViolation(
        file=file_path,
        line=1,
        col=0,
        rule=rule,
        detail=detail,
        severity=severity,
    )


def _check_duplicate_mounts(scene_spec: SceneSpec, file_path: str) -> list[GuardViolation]:
    violations: list[GuardViolation] = []
    seen_anchors: set[str] = set()
    reported: set[str] = set()
    for mount in scene_spec.mounts:
        if mount.anchor in seen_anchors and mount.anchor not in reported:
            reported.add(mount.anchor)
            violations.append(
                _violation(
                    file_path,
                    "duplicate-mount",
                    f"Duplicate mount on parent anchor {mount.anchor!r} in scene {scene_spec.id!r}",
                )
            )
        seen_anchors.add(mount.anchor)
    return violations


def _opaque_bbox(frame: RenderedFrame) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(frame.surface.data != TRANSPARENT_INDEX)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _check_parent_anchor_bounds(
    scene_spec: SceneSpec,
    parent: AssetModule,
    parent_frames_by_key: Mapping[tuple[str, int], RenderedFrame],
    res: SceneCompositionResult,
    file_path: str,
    seen_keys: set[tuple[str, str]],
) -> list[GuardViolation]:
    if not scene_spec.mounts:
        return []
    parent_frame = parent_frames_by_key.get((res.parent_state, res.parent_frame))
    if parent_frame is None:
        return []

    label = f"({res.parent_state!r}, frame={res.parent_frame})"
    bbox = _opaque_bbox(parent_frame)
    if bbox is None:
        key = ("scene-anchor-bounds", f"__empty__:{res.parent_state}:{res.parent_frame}")
        if key in seen_keys:
            return []
        seen_keys.add(key)
        return [
            _violation(
                file_path,
                "scene-anchor-bounds",
                f"Parent asset {parent.SPEC.id!r} has no opaque pixels in {label}",
            )
        ]

    x0, y0, x1, y1 = bbox
    anchors_by_name: dict[str, AnchorPoint] = {a.name: a for a in res.parent_anchors}
    violations: list[GuardViolation] = []
    for mount in scene_spec.mounts:
        anchor = anchors_by_name.get(mount.anchor)
        if anchor is None:
            continue
        if not (x0 <= anchor.x <= x1 and y0 <= anchor.y <= y1):
            key = ("scene-anchor-bounds", mount.anchor)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            violations.append(
                _violation(
                    file_path,
                    "scene-anchor-bounds",
                    (
                        f"Mount anchor {mount.anchor!r} ({anchor.x}, {anchor.y}) lies outside "
                        f"parent {parent.SPEC.id!r} opaque bbox "
                        f"[{x0}..{x1}]x[{y0}..{y1}] in {label}"
                    ),
                )
            )
    return violations


def _check_placement_ergonomics(
    scene_spec: SceneSpec,
    parent: AssetModule,
    placement: MountedPropPlacement,
    label: str,
    file_path: str,
    seen_keys: set[tuple[str, str]],
) -> list[GuardViolation]:
    violations: list[GuardViolation] = []
    target_id = f"{placement.prop_id}@{placement.anchor}"

    if not placement.in_bounds:
        key = ("scene-bounds", target_id)
        if key not in seen_keys:
            seen_keys.add(key)
            severity: GuardSeverity = "error" if scene_spec.strict_bounds else "warning"
            violations.append(
                _violation(
                    file_path,
                    "scene-bounds",
                    (
                        f"Prop {placement.prop_id!r} at anchor {placement.anchor!r} exceeds canvas "
                        f"({placement.clipped_pixels} clipped pixel(s)) in {label}"
                    ),
                    severity=severity,
                )
            )

    if not placement.perspective_match:
        key = ("scene-perspective", target_id)
        if key not in seen_keys:
            seen_keys.add(key)
            severity = "error" if scene_spec.strict_perspective else "warning"
            violations.append(
                _violation(
                    file_path,
                    "scene-perspective",
                    (
                        f"Prop {placement.prop_id!r} uses perspective {placement.perspective!r}, "
                        f"expected {parent.SPEC.perspective!r} in {label}"
                    ),
                    severity=severity,
                )
            )

    if placement.opaque_pixels > 0 and placement.occluded_pixels > 0:
        ratio = placement.occluded_pixels / placement.opaque_pixels
        occ_severity: GuardSeverity | None = None
        if ratio >= SCENE_OCCLUSION_ERROR_RATIO:
            occ_severity = "error"
        elif ratio >= SCENE_OCCLUSION_WARN_RATIO:
            occ_severity = "warning"

        if occ_severity is not None:
            key = ("scene-occlusion", f"{target_id}:{occ_severity}")
            if key not in seen_keys:
                seen_keys.add(key)
                violations.append(
                    _violation(
                        file_path,
                        "scene-occlusion",
                        (
                            f"Prop {placement.prop_id!r} at anchor {placement.anchor!r} is "
                            f"{ratio * 100:.1f}% occluded "
                            f"({placement.occluded_pixels}/{placement.opaque_pixels} px) by "
                            f"{', '.join(placement.occluded_by)} in {label}"
                        ),
                        severity=occ_severity,
                    )
                )

    return violations


def check_scene_runtime(
    scene_spec: SceneSpec,
    parent: AssetModule,
    props_by_id: Mapping[str, AssetModule],
    style: StylePack,
    *,
    file_path: str = "<scene>",
) -> list[GuardViolation]:
    """Validate deterministic ergonomics invariants on a `SceneSpec`."""
    violations = _check_duplicate_mounts(scene_spec, file_path)

    try:
        _, results, _ = compose_scene_results(
            scene_spec,
            parent,
            props_by_id,
            style,
            strict_bounds=False,
            strict_perspective=False,
        )
    except SceneCompositionError as exc:
        violations.append(_violation(file_path, "scene-error", str(exc)))
        return violations

    parent_frames = render_asset_frames(parent, style, variant=scene_spec.variant)
    parent_frames_by_key = {(f.state, f.frame): f for f in parent_frames}
    seen_keys: set[tuple[str, str]] = set()

    for res in results:
        violations.extend(
            _check_parent_anchor_bounds(
                scene_spec,
                parent,
                parent_frames_by_key,
                res,
                file_path,
                seen_keys,
            )
        )
        label = f"({res.parent_state!r}, frame={res.parent_frame})"
        for placement in res.placements:
            violations.extend(
                _check_placement_ergonomics(
                    scene_spec,
                    parent,
                    placement,
                    label,
                    file_path,
                    seen_keys,
                )
            )

    return violations
