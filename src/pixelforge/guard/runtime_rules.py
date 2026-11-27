"""Runtime invariant checks and orphan-pixel diagnostics for rendered assets."""

from __future__ import annotations

import hashlib
from typing import Final

import numpy as np

from pixelforge.core.surface import orphan_pixel_mask
from pixelforge.core.types import TRANSPARENT_INDEX, AssetSpec, HitboxRect, StylePack
from pixelforge.export.bundle import AssetModule, RenderedFrame, render_asset_frames
from pixelforge.export.png import surface_to_rgba
from pixelforge.guard.craft_rules import check_asset_craft
from pixelforge.guard.types import GuardSeverity, GuardViolation

ADVISORY_EMISSIVE_BLEED_RATIO: Final[float] = 0.25
ADVISORY_MIN_COVERAGE_RATIO: Final[float] = 0.05
ADVISORY_MAX_COVERAGE_RATIO: Final[float] = 0.95
FURNITURE_OVERLAP_WARN_RATIO: Final[float] = 0.25


def _is_container_hitbox(hb: HitboxRect) -> bool:
    if hb.kind is not None and hb.kind.startswith("ui_"):
        return True
    return hb.name == "room" or hb.name.endswith("_zone") or hb.name.startswith("door_")


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
    violations.extend(_check_spatial_ergonomics(frame_a, file_path))

    if spec.font is None:
        # INVARIANT: Bitmap font atlases inherently contain isolated 1x1 dots (`.`, `i`, `:`, `!`).
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

    violations.extend(_check_advisory_diagnostics(frame_a, style, file_path=file_path, label=label))
    return violations


def _check_spatial_ergonomics(frame: RenderedFrame, file_path: str) -> list[GuardViolation]:
    """Emit advisory warnings for doorway obstructions and abnormal furniture overlap."""
    violations: list[GuardViolation] = []
    label = f"({frame.state!r}, frame={frame.frame})"
    clearances = [hb for hb in frame.hitboxes if hb.name.startswith("door_clearance_")]
    furniture = [hb for hb in frame.hitboxes if not _is_container_hitbox(hb)]

    for clr in clearances:
        for hb in furniture:
            ix0 = max(clr.x, hb.x)
            iy0 = max(clr.y, hb.y)
            ix1 = min(clr.x + clr.w, hb.x + hb.w)
            iy1 = min(clr.y + clr.h, hb.y + hb.h)
            if ix1 > ix0 and iy1 > iy0:
                violations.append(
                    GuardViolation(
                        file=file_path,
                        line=1,
                        col=0,
                        rule="door-obstruction",
                        detail=(
                            f"Furniture hitbox {hb.name!r} overlaps doorway clearance "
                            f"{clr.name!r} in {label}"
                        ),
                        severity="warning",
                    )
                )

    for idx, hb_a in enumerate(furniture):
        for hb_b in furniture[idx + 1 :]:
            ix0 = max(hb_a.x, hb_b.x)
            iy0 = max(hb_a.y, hb_b.y)
            ix1 = min(hb_a.x + hb_a.w, hb_b.x + hb_b.w)
            iy1 = min(hb_a.y + hb_a.h, hb_b.y + hb_b.h)
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            inter_area = (ix1 - ix0) * (iy1 - iy0)
            min_area = min(hb_a.w * hb_a.h, hb_b.w * hb_b.h)
            if min_area > 0 and (inter_area / min_area) >= FURNITURE_OVERLAP_WARN_RATIO:
                violations.append(
                    GuardViolation(
                        file=file_path,
                        line=1,
                        col=0,
                        rule="furniture-overlap",
                        detail=(
                            f"Furniture hitboxes {hb_a.name!r} and {hb_b.name!r} overlap by "
                            f"{(inter_area / min_area) * 100:.1f}% in {label}"
                        ),
                        severity="warning",
                    )
                )

    return violations


def _check_advisory_diagnostics(
    frame: RenderedFrame,
    style: StylePack,
    *,
    file_path: str,
    label: str,
) -> list[GuardViolation]:
    """Emit non-fatal advisory warnings for canvas coverage and emissive bleed."""
    violations: list[GuardViolation] = []
    data = frame.surface.data
    total_pixels = data.size
    if total_pixels == 0:
        return violations

    opaque_pixels = int(np.count_nonzero(data != TRANSPARENT_INDEX))
    if opaque_pixels == 0:
        violations.append(
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="canvas-coverage",
                detail=f"Empty frame (0.0% opaque pixels) in {label}",
                severity="warning",
            )
        )
        return violations

    coverage_ratio = opaque_pixels / total_pixels
    if coverage_ratio < ADVISORY_MIN_COVERAGE_RATIO:
        violations.append(
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="canvas-coverage",
                detail=(
                    f"Sparse canvas coverage ({coverage_ratio * 100:.1f}% < "
                    f"{ADVISORY_MIN_COVERAGE_RATIO * 100:.1f}%) in {label}"
                ),
                severity="warning",
            )
        )
    elif coverage_ratio > ADVISORY_MAX_COVERAGE_RATIO:
        violations.append(
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="canvas-coverage",
                detail=(
                    f"Overfilled canvas coverage ({coverage_ratio * 100:.1f}% > "
                    f"{ADVISORY_MAX_COVERAGE_RATIO * 100:.1f}%) in {label}"
                ),
                severity="warning",
            )
        )

    emissive_indices = [entry.index for entry in style.palette if "emissive" in entry.flags]
    if emissive_indices:
        emissive_pixels = int(np.count_nonzero(np.isin(data, emissive_indices)))
        emissive_ratio = emissive_pixels / opaque_pixels
        if emissive_ratio > ADVISORY_EMISSIVE_BLEED_RATIO:
            violations.append(
                GuardViolation(
                    file=file_path,
                    line=1,
                    col=0,
                    rule="emissive-bleed",
                    detail=(
                        f"High emissive ratio ({emissive_ratio * 100:.1f}% > "
                        f"{ADVISORY_EMISSIVE_BLEED_RATIO * 100:.1f}% of opaque pixels) in {label}"
                    ),
                    severity="warning",
                )
            )
    return violations


def check_asset_runtime(
    asset: AssetModule,
    style: StylePack,
    *,
    file_path: str = "<asset>",
    strict_orphans: bool = False,
    strict_craft: bool = False,
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
    violations.extend(
        check_asset_craft(
            asset,
            first_pass,
            style,
            file_path=file_path,
            strict_craft=strict_craft,
        )
    )
    return violations
