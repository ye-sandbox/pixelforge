"""Deterministic numpy pixel-art craft diagnostics for `pixelforge check`."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Final

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.types import TRANSPARENT_INDEX, AssetSpec, LightingAngle, StylePack
from pixelforge.export.bundle import AssetModule, RenderedFrame
from pixelforge.guard.types import GuardSeverity, GuardViolation

CRAFT_RULE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "craft-jaggies",
        "craft-pillow-shading",
        "craft-lighting",
        "craft-contrast",
        "craft-noop-delta",
        "craft-anchor-fidelity",
    }
)

_DARK_BG_RGB: Final[NDArray[np.float32]] = np.array([13.0, 17.0, 23.0], dtype=np.float32)
_LIGHT_BG_RGB: Final[NDArray[np.float32]] = np.array([230.0, 237.0, 243.0], dtype=np.float32)
_CONTRAST_RGB_THRESHOLD: Final[float] = 32.0
_CONTRAST_MIN_READABLE_RATIO: Final[float] = 0.15
_JAGGY_MIN_COUNT: Final[int] = 10
_JAGGY_MIN_RATIO: Final[float] = 0.12
_SHADING_MIN_PIXELS: Final[int] = 24
_ANCHOR_BBOX_MARGIN: Final[int] = 2
_HITBOX_MIN_FILL_RATIO: Final[float] = 0.10


def _is_container_hitbox(name: str) -> bool:
    return name == "room" or name.endswith("_zone") or name.startswith("door_")


def _build_style_luts(
    style: StylePack,
) -> tuple[NDArray[np.float32], NDArray[np.float32], NDArray[np.bool_]]:
    rgb_lut = np.zeros((256, 3), dtype=np.float32)
    lum_lut = np.zeros(256, dtype=np.float32)
    emissive_lut = np.zeros(256, dtype=np.bool_)
    for entry in style.palette:
        r = float(int(entry.hex[1:3], 16))
        g = float(int(entry.hex[3:5], 16))
        b = float(int(entry.hex[5:7], 16))
        rgb_lut[entry.index] = (r, g, b)
        lum_lut[entry.index] = 0.2126 * r + 0.7152 * g + 0.0722 * b
        if "emissive" in entry.flags:
            emissive_lut[entry.index] = True
    return rgb_lut, lum_lut, emissive_lut


def _pearson_corr(x: NDArray[np.float32], y: NDArray[np.float32]) -> float:
    x_std = float(np.std(x))
    y_std = float(np.std(y))
    if x_std <= 1e-6 or y_std <= 1e-6:
        return 0.0
    x_centered = x - np.mean(x)
    y_centered = y - np.mean(y)
    return float(np.mean(x_centered * y_centered) / (x_std * y_std))


def _light_projection(
    mask: NDArray[np.bool_],
    lighting_angle: LightingAngle,
) -> NDArray[np.float32]:
    ys, xs = np.nonzero(mask)
    min_x, max_x = float(xs.min()), float(xs.max())
    min_y, max_y = float(ys.min()), float(ys.max())
    half_w = max(1.0, (max_x - min_x) * 0.5)
    half_h = max(1.0, (max_y - min_y) * 0.5)
    cx = (min_x + max_x) * 0.5
    cy = (min_y + max_y) * 0.5
    nx = (xs.astype(np.float32) - cx) / half_w
    ny = (ys.astype(np.float32) - cy) / half_h

    if lighting_angle == "top-left":
        lx, ly = -0.70710677, -0.70710677
    elif lighting_angle == "top-right":
        lx, ly = 0.70710677, -0.70710677
    else:
        lx, ly = 0.0, -1.0
    return (nx * np.float32(lx) + ny * np.float32(ly)).astype(np.float32)


def _check_jaggies(
    data: NDArray[np.uint8],
    style: StylePack,
    *,
    file_path: str,
    label: str,
    severity: GuardSeverity,
) -> list[GuardViolation]:
    outline = data == style.outline_index
    outline_count = int(np.count_nonzero(outline))
    if outline_count < 8:
        return []

    h, w = outline.shape
    padded = np.pad(outline, 2, mode="constant", constant_values=False)
    center = padded[2 : h + 2, 2 : w + 2]
    jaggy_mask = np.zeros((h, w), dtype=np.bool_)

    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        h1 = padded[2 : h + 2, 2 + dx : w + 2 + dx]
        v1 = padded[2 + dy : h + 2 + dy, 2 : w + 2]
        diag = padded[2 + dy : h + 2 + dy, 2 + dx : w + 2 + dx]
        h_opp = padded[2 : h + 2, 2 - dx : w + 2 - dx]
        v_opp = padded[2 - dy : h + 2 - dy, 2 : w + 2]
        h2 = padded[2 : h + 2, 2 + 2 * dx : w + 2 + 2 * dx]
        v2 = padded[2 + 2 * dy : h + 2 + 2 * dy, 2 : w + 2]

        # INVARIANT: Exclude 90-degree straight box corners (h2 & v2) and T-junctions
        # so only diagonal/curve staircase L-corners are flagged as jaggies.
        l_corner = center & h1 & v1 & (~diag) & (~h_opp) & (~v_opp) & (~(h2 & v2))
        jaggy_mask |= l_corner

    jaggy_count = int(np.count_nonzero(jaggy_mask))
    if jaggy_count >= _JAGGY_MIN_COUNT and (jaggy_count / outline_count) >= _JAGGY_MIN_RATIO:
        ys, xs = np.nonzero(jaggy_mask)
        sample = ", ".join(f"({int(x)},{int(y)})" for y, x in zip(ys[:6], xs[:6], strict=True))
        suffix = "..." if jaggy_count > 6 else ""
        return [
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="craft-jaggies",
                detail=(
                    f"{jaggy_count} double-pixel L-corner jaggy pixel(s) on outline at "
                    f"{sample}{suffix} in {label}"
                ),
                severity=severity,
            )
        ]
    return []


def _check_shading_and_lighting(
    data: NDArray[np.uint8],
    lum_lut: NDArray[np.float32],
    emissive_lut: NDArray[np.bool_],
    style: StylePack,
    *,
    file_path: str,
    label: str,
    severity: GuardSeverity,
) -> list[GuardViolation]:
    opaque = data != TRANSPARENT_INDEX
    interior = opaque & (data != style.outline_index) & (~emissive_lut[data])
    interior_count = int(np.count_nonzero(interior))
    if interior_count < _SHADING_MIN_PIXELS:
        return []

    lum_vals = lum_lut[data[interior]]
    if np.unique(lum_vals).size < 3 or float(np.std(lum_vals)) <= 8.0:
        return []

    violations: list[GuardViolation] = []
    proj = _light_projection(interior, style.lighting_angle)
    dir_corr = _pearson_corr(proj, lum_vals)

    dist = np.zeros(data.shape, dtype=np.int32)
    frontier = opaque.copy()
    for step in range(1, 7):
        padded = np.pad(frontier, 1, mode="constant", constant_values=False)
        eroded = (
            padded[1:-1, 1:-1]
            & padded[:-2, 1:-1]
            & padded[2:, 1:-1]
            & padded[1:-1, :-2]
            & padded[1:-1, 2:]
        )
        dist[frontier & (~eroded)] = step
        frontier = eroded
        if not np.any(frontier):
            break
    dist[frontier] = 7

    dist_vals = dist[interior].astype(np.float32)
    if float(np.std(dist_vals)) > 0.25:
        radial_corr = _pearson_corr(dist_vals, lum_vals)
        if radial_corr > 0.65 and abs(dir_corr) < 0.25:
            violations.append(
                GuardViolation(
                    file=file_path,
                    line=1,
                    col=0,
                    rule="craft-pillow-shading",
                    detail=(
                        f"Concentric pillow-shading detected (radial_corr={radial_corr:.2f}, "
                        f"dir_corr={dir_corr:.2f}) in {label}"
                    ),
                    severity=severity,
                )
            )

    lit_mask = proj > 0.15
    shadow_mask = proj < -0.15
    if int(np.count_nonzero(lit_mask)) >= 6 and int(np.count_nonzero(shadow_mask)) >= 6:
        lit_mean = float(np.mean(lum_vals[lit_mask]))
        shadow_mean = float(np.mean(lum_vals[shadow_mask]))
        if lit_mean < shadow_mean - 20.0 and dir_corr < -0.72:
            violations.append(
                GuardViolation(
                    file=file_path,
                    line=1,
                    col=0,
                    rule="craft-lighting",
                    detail=(
                        f"Shading opposes style.lighting_angle={style.lighting_angle!r} "
                        f"(lit_mean={lit_mean:.1f} < shadow_mean={shadow_mean:.1f}) in {label}"
                    ),
                    severity=severity,
                )
            )
    return violations


def _check_silhouette_contrast(
    data: NDArray[np.uint8],
    rgb_lut: NDArray[np.float32],
    *,
    file_path: str,
    label: str,
    severity: GuardSeverity,
) -> list[GuardViolation]:
    opaque = data != TRANSPARENT_INDEX
    opaque_count = int(np.count_nonzero(opaque))
    if opaque_count < 4:
        return []

    opaque_rgb = rgb_lut[data[opaque]]
    dist_dark = np.linalg.norm(opaque_rgb - _DARK_BG_RGB, axis=1)
    dist_light = np.linalg.norm(opaque_rgb - _LIGHT_BG_RGB, axis=1)

    dark_ratio = float(np.count_nonzero(dist_dark >= _CONTRAST_RGB_THRESHOLD)) / opaque_count
    light_ratio = float(np.count_nonzero(dist_light >= _CONTRAST_RGB_THRESHOLD)) / opaque_count

    violations: list[GuardViolation] = []
    if dark_ratio < _CONTRAST_MIN_READABLE_RATIO:
        violations.append(
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="craft-contrast",
                detail=(
                    f"Low 1x silhouette contrast against #0d1117 "
                    f"({dark_ratio * 100:.1f}% distinguishable pixels) in {label}"
                ),
                severity=severity,
            )
        )
    if light_ratio < _CONTRAST_MIN_READABLE_RATIO:
        violations.append(
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="craft-contrast",
                detail=(
                    f"Low 1x silhouette contrast against #e6edf3 "
                    f"({light_ratio * 100:.1f}% distinguishable pixels) in {label}"
                ),
                severity=severity,
            )
        )
    return violations


def _check_noop_deltas(
    frames: Sequence[RenderedFrame],
    spec: AssetSpec,
    *,
    file_path: str,
    severity: GuardSeverity,
) -> list[GuardViolation]:
    if spec.frames <= 1 and len(spec.states) <= 1:
        return []

    by_state: dict[str, list[str]] = {}
    for frame in frames:
        digest = hashlib.sha256(frame.surface.data.tobytes()).hexdigest()
        by_state.setdefault(frame.state, []).append(digest)

    violations: list[GuardViolation] = []
    seen_sequences: dict[tuple[str, ...], str] = {}
    static_states: list[str] = []
    for state, digests in by_state.items():
        if spec.frames > 1 and len(digests) > 1 and len(set(digests)) == 1:
            static_states.append(state)
        seq = tuple(digests)
        if seq in seen_sequences:
            violations.append(
                GuardViolation(
                    file=file_path,
                    line=1,
                    col=0,
                    rule="craft-noop-delta",
                    detail=(
                        f"State {state!r} is pixel-identical to state {seen_sequences[seq]!r} "
                        "(no-op state delta)"
                    ),
                    severity=severity,
                )
            )
        else:
            seen_sequences[seq] = state

    if spec.frames > 1 and len(static_states) == len(by_state):
        violations.append(
            GuardViolation(
                file=file_path,
                line=1,
                col=0,
                rule="craft-noop-delta",
                detail=(
                    f"All {spec.frames} frames across all state(s) are pixel-identical "
                    "(no-op animation delta)"
                ),
                severity=severity,
            )
        )
    return violations


def _check_anchor_hitbox_fidelity(
    frame: RenderedFrame,
    *,
    file_path: str,
    label: str,
    severity: GuardSeverity,
) -> list[GuardViolation]:
    opaque = frame.surface.data != TRANSPARENT_INDEX
    if not np.any(opaque):
        return []

    ys, xs = np.nonzero(opaque)
    min_x, max_x = int(xs.min()), int(xs.max())
    min_y, max_y = int(ys.min()), int(ys.max())
    h, w = opaque.shape
    violations: list[GuardViolation] = []

    for anchor in frame.anchors:
        if (
            anchor.x < min_x - _ANCHOR_BBOX_MARGIN
            or anchor.x > max_x + _ANCHOR_BBOX_MARGIN
            or anchor.y < min_y - _ANCHOR_BBOX_MARGIN
            or anchor.y > max_y + _ANCHOR_BBOX_MARGIN
        ):
            violations.append(
                GuardViolation(
                    file=file_path,
                    line=1,
                    col=0,
                    rule="craft-anchor-fidelity",
                    detail=(
                        f"Anchor {anchor.name!r} ({anchor.x}, {anchor.y}) lies outside opaque "
                        f"bbox [{min_x}..{max_x}]x[{min_y}..{max_y}] (+-{_ANCHOR_BBOX_MARGIN}px) "
                        f"in {label}"
                    ),
                    severity=severity,
                )
            )

    for hb in frame.hitboxes:
        if _is_container_hitbox(hb.name):
            continue
        x0, y0 = max(0, hb.x), max(0, hb.y)
        x1, y1 = min(w, hb.x + hb.w), min(h, hb.y + hb.h)
        if x1 <= x0 or y1 <= y0:
            continue
        region = opaque[y0:y1, x0:x1]
        fill_ratio = float(np.count_nonzero(region)) / float(region.size)
        if fill_ratio < _HITBOX_MIN_FILL_RATIO:
            violations.append(
                GuardViolation(
                    file=file_path,
                    line=1,
                    col=0,
                    rule="craft-anchor-fidelity",
                    detail=(
                        f"Hitbox {hb.name!r} ({hb.x}, {hb.y}, {hb.w}x{hb.h}) covers only "
                        f"{fill_ratio * 100:.1f}% opaque pixels in {label}"
                    ),
                    severity=severity,
                )
            )
    return violations


def check_asset_craft(
    asset: AssetModule,
    frames: Sequence[RenderedFrame],
    style: StylePack,
    *,
    file_path: str = "<asset>",
    strict_craft: bool = False,
) -> list[GuardViolation]:
    """Run deterministic numpy pixel-art craft diagnostics on rendered asset frames."""
    spec = asset.SPEC
    severity: GuardSeverity = "error" if strict_craft else "warning"
    violations: list[GuardViolation] = []
    rgb_lut, lum_lut, emissive_lut = _build_style_luts(style)

    is_atlas = spec.font is not None or spec.tilemap is not None
    is_nine_slice = spec.nine_slice is not None
    for frame in frames:
        label = f"({frame.state!r}, frame={frame.frame})"
        if not is_atlas and not is_nine_slice:
            violations.extend(
                _check_jaggies(
                    frame.surface.data,
                    style,
                    file_path=file_path,
                    label=label,
                    severity=severity,
                )
            )
        if not is_atlas:
            violations.extend(
                _check_shading_and_lighting(
                    frame.surface.data,
                    lum_lut,
                    emissive_lut,
                    style,
                    file_path=file_path,
                    label=label,
                    severity=severity,
                )
            )
        if spec.font is None and not is_nine_slice:
            violations.extend(
                _check_silhouette_contrast(
                    frame.surface.data,
                    rgb_lut,
                    file_path=file_path,
                    label=label,
                    severity=severity,
                )
            )
        violations.extend(
            _check_anchor_hitbox_fidelity(
                frame,
                file_path=file_path,
                label=label,
                severity=severity,
            )
        )

    violations.extend(_check_noop_deltas(frames, spec, file_path=file_path, severity=severity))
    return violations
