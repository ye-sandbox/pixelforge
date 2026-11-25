"""Runtime invariant checks and orphan-pixel diagnostics for rendered assets."""

from __future__ import annotations

import hashlib

import numpy as np

from pixelforge.core.surface import orphan_pixel_mask
from pixelforge.core.types import TRANSPARENT_INDEX, AssetSpec, StylePack
from pixelforge.export.bundle import AssetModule, RenderedFrame, render_asset_frames
from pixelforge.export.png import surface_to_rgba
from pixelforge.guard.types import GuardSeverity, GuardViolation


def find_orphan_pixel_coords(frame: RenderedFrame) -> list[tuple[int, int]]:
    """Return `(x, y)` coordinates of opaque pixels with zero 8-connected opaque neighbors."""
    ys, xs = np.nonzero(orphan_pixel_mask(frame.surface))
    return [(int(x), int(y)) for y, x in zip(ys.tolist(), xs.tolist(), strict=True)]


def _check_anchors_and_hitboxes(
    frame: RenderedFrame,
    width: int,
    height: int,
    file_path: str,
) -> list[GuardViolation]:
    violations: list[GuardViolation] = []
    seen_anchors: set[str] = set()
    for anchor in frame.anchors:
        if anchor.name in seen_anchors:
            violations.append(
                GuardViolation(
                    file=file_path,
                    line=1,
                    col=0,
                    rule="valid-anchors",
                    detail=(
                        f"Duplicate anchor {anchor.name!r} in ({frame.state!r}, {frame.frame})"
                    ),
                )
            )
        seen_anchors.add(anchor.name)
        if not (0 <= anchor.x <= width and 0 <= anchor.y <= height):
            violations.append(
                GuardViolation(
                    file=file_path,
                    line=1,
                    col=0,
                    rule="valid-anchors",
                    detail=(
                        f"Anchor {anchor.name!r} ({anchor.x}, {anchor.y}) out of bounds "
                        f"[0..{width}]x[0..{height}] in ({frame.state!r}, {frame.frame})"
                    ),
                )
            )

    seen_hitboxes: set[str] = set()
    for hb in frame.hitboxes:
        if hb.name in seen_hitboxes:
            violations.append(
                GuardViolation(
                    file=file_path,
                    line=1,
                    col=0,
                    rule="valid-anchors",
                    detail=(f"Duplicate hitbox {hb.name!r} in ({frame.state!r}, {frame.frame})"),
                )
            )
        seen_hitboxes.add(hb.name)
        in_bounds = (
            hb.w > 0
            and hb.h > 0
            and hb.x >= 0
            and hb.y >= 0
            and hb.x + hb.w <= width
            and hb.y + hb.h <= height
        )
        if not in_bounds:
            violations.append(
                GuardViolation(
                    file=file_path,
                    line=1,
                    col=0,
                    rule="valid-anchors",
                    detail=(
                        f"Hitbox {hb.name!r} ({hb.x}, {hb.y}, {hb.w}x{hb.h}) out of bounds "
                        f"[0..{width}]x[0..{height}] in ({frame.state!r}, {frame.frame})"
                    ),
                )
            )
    return violations


def _check_surface_invariants(
    frame: RenderedFrame,
    spec: AssetSpec,
    style: StylePack,
    valid_indices: set[int],
    file_path: str,
    label: str,
) -> list[GuardViolation]:
    violations: list[GuardViolation] = []
    surf = frame.surface
    if surf.data.shape != (spec.height, spec.width):
        violations.append(
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="exact-dimensions",
                detail=(
                    f"Surface shape {surf.data.shape} != expected "
                    f"({spec.height}, {spec.width}) in {label}"
                ),
            )
        )

    unique_vals = {int(v) for v in np.unique(surf.data).tolist()}
    bad_vals = sorted(unique_vals - valid_indices)
    if bad_vals:
        violations.append(
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="closed-palette",
                detail=f"Undeclared palette indices {bad_vals} in {label}",
            )
        )
        return violations

    rgba = surface_to_rgba(surf, style)
    alpha = rgba[:, :, 3]
    if not bool(np.all((alpha == 0) | (alpha == 255))):
        violations.append(
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="binary-alpha",
                detail=f"Non-binary alpha detected in {label}",
            )
        )
    return violations


def _check_frame_invariants(
    frame_a: RenderedFrame,
    frame_b: RenderedFrame,
    spec: AssetSpec,
    style: StylePack,
    valid_indices: set[int],
    *,
    file_path: str,
    strict_orphans: bool,
) -> list[GuardViolation]:
    label = f"({frame_a.state!r}, frame={frame_a.frame})"
    violations = _check_surface_invariants(frame_a, spec, style, valid_indices, file_path, label)

    digest_a = hashlib.sha256(frame_a.surface.data.tobytes()).hexdigest()
    digest_b = hashlib.sha256(frame_b.surface.data.tobytes()).hexdigest()
    if (
        digest_a != digest_b
        or frame_a.anchors != frame_b.anchors
        or frame_a.hitboxes != frame_b.hitboxes
    ):
        violations.append(
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="bit-determinism",
                detail=f"Non-deterministic output across repeated renders in {label}",
            )
        )

    violations.extend(_check_anchors_and_hitboxes(frame_a, spec.width, spec.height, file_path))

    orphans = find_orphan_pixel_coords(frame_a)
    if orphans:
        sample = ", ".join(f"({x},{y})" for x, y in orphans[:6])
        suffix = "..." if len(orphans) > 6 else ""
        severity: GuardSeverity = "error" if strict_orphans else "warning"
        violations.append(
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="orphan-pixels",
                detail=f"{len(orphans)} isolated 1x1 pixel(s) at {sample}{suffix} in {label}",
                severity=severity,
            )
        )
    return violations


def check_asset_runtime(
    asset: AssetModule,
    style: StylePack,
    *,
    file_path: str = "<asset>",
    strict_orphans: bool = False,
) -> list[GuardViolation]:
    """Validate runtime invariants and orphan-pixel diagnostics on an asset."""
    spec = asset.SPEC
    valid_indices = {entry.index for entry in style.palette} | {TRANSPARENT_INDEX}

    first_pass = render_asset_frames(asset, style)
    second_pass = render_asset_frames(asset, style)

    if len(first_pass) != len(second_pass):
        return [
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="bit-determinism",
                detail="Frame count differed across repeated renders",
            )
        ]

    violations: list[GuardViolation] = []
    for frame_a, frame_b in zip(first_pass, second_pass, strict=True):
        violations.extend(
            _check_frame_invariants(
                frame_a,
                frame_b,
                spec,
                style,
                valid_indices,
                file_path=file_path,
                strict_orphans=strict_orphans,
            )
        )
    return violations
