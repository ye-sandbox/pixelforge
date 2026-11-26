"""Side-by-side + magenta pixel-diff PNG generator and structured metadata diff."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict

from pixelforge.core.surface import IndexedSurface, orphan_pixel_mask
from pixelforge.core.types import TRANSPARENT_INDEX, AnchorPoint, HitboxRect, StylePack
from pixelforge.export._canvas import Rgb, composite_rgba, draw_checkerboard
from pixelforge.export.png import rgba_to_png, surface_to_rgba

_GAP: Final[int] = 4
_PADDING: Final[int] = 8
_MAGENTA: Final[tuple[int, int, int, int]] = (255, 42, 133, 255)
_FRAME_BG: Final[tuple[int, int, int, int]] = (13, 17, 23, 255)
_CHECKER_A: Final[Rgb] = (22, 24, 28)
_CHECKER_B: Final[Rgb] = (30, 32, 36)


@dataclass(frozen=True)
class DiffResult:
    """Pixel-diff summary and 3-panel PNG output (`baseline | current | diff`)."""

    changed_pixels: int
    total_pixels: int
    width: int
    height: int
    png: bytes


def generate_pixel_diff(
    baseline: NDArray[np.uint8],
    current: NDArray[np.uint8],
) -> DiffResult:
    """Compare two RGBA arrays into a `(baseline | current | magenta diff)` PNG."""
    if baseline.ndim != 3 or baseline.shape[2] != 4:
        msg = f"Expected (H, W, 4) baseline RGBA array, got shape {baseline.shape}"
        raise ValueError(msg)
    if current.ndim != 3 or current.shape[2] != 4:
        msg = f"Expected (H, W, 4) current RGBA array, got shape {current.shape}"
        raise ValueError(msg)

    bh, bw, _ = baseline.shape
    ch, cw, _ = current.shape
    panel_w = max(bw, cw)
    panel_h = max(bh, ch)

    total_w = _PADDING * 2 + panel_w * 3 + _GAP * 2
    total_h = _PADDING * 2 + panel_h
    canvas = np.empty((total_h, total_w, 4), dtype=np.uint8)
    canvas[:, :] = _FRAME_BG

    base_x = _PADDING
    curr_x = _PADDING + panel_w + _GAP
    diff_x = _PADDING + (panel_w + _GAP) * 2

    draw_checkerboard(canvas, base_x, _PADDING, panel_w, panel_h, _CHECKER_A, _CHECKER_B, 4)
    draw_checkerboard(canvas, curr_x, _PADDING, panel_w, panel_h, _CHECKER_A, _CHECKER_B, 4)
    draw_checkerboard(canvas, diff_x, _PADDING, panel_w, panel_h, _CHECKER_A, _CHECKER_B, 4)

    composite_rgba(canvas, baseline, base_x, _PADDING)
    composite_rgba(canvas, current, curr_x, _PADDING)

    padded_base = np.zeros((panel_h, panel_w, 4), dtype=np.uint8)
    padded_curr = np.zeros((panel_h, panel_w, 4), dtype=np.uint8)
    padded_base[:bh, :bw] = baseline
    padded_curr[:ch, :cw] = current

    diff_mask = np.any(padded_base != padded_curr, axis=2)
    changed_pixels = int(np.count_nonzero(diff_mask))

    diff_panel = canvas[_PADDING : _PADDING + panel_h, diff_x : diff_x + panel_w]
    unchanged_opaque = (~diff_mask) & (padded_curr[:, :, 3] > 0)
    diff_panel[unchanged_opaque, :3] = padded_curr[unchanged_opaque, :3] >> 2
    diff_panel[unchanged_opaque, 3] = 255
    diff_panel[diff_mask] = _MAGENTA

    return DiffResult(
        changed_pixels=changed_pixels,
        total_pixels=panel_w * panel_h,
        width=total_w,
        height=total_h,
        png=rgba_to_png(canvas),
    )


def generate_surface_diff(
    baseline: IndexedSurface,
    current: IndexedSurface,
    style: StylePack,
    *,
    variant: str | None = None,
    scale: int = 1,
    baseline_style: StylePack | None = None,
) -> DiffResult:
    """Render and diff two `IndexedSurface` buffers under their `StylePack`s."""
    base_rgba = surface_to_rgba(
        baseline,
        baseline_style if baseline_style is not None else style,
        variant=variant,
        scale=scale,
    )
    curr_rgba = surface_to_rgba(current, style, variant=variant, scale=scale)
    return generate_pixel_diff(base_rgba, curr_rgba)


class AnchorDelta(BaseModel):
    """Coordinate delta for a named anchor between baseline and current renders."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["added", "removed", "moved", "changed"]
    before: AnchorPoint | None = None
    after: AnchorPoint | None = None
    dx: int | None = None
    dy: int | None = None


class HitboxDelta(BaseModel):
    """Bounding-box delta for a named hitbox between baseline and current renders."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["added", "removed", "changed"]
    before: HitboxRect | None = None
    after: HitboxRect | None = None
    dx: int | None = None
    dy: int | None = None
    dw: int | None = None
    dh: int | None = None


class SurfaceMetrics(BaseModel):
    """Per-surface opaque, canvas-coverage, emissive, and orphan-pixel metrics."""

    model_config = ConfigDict(frozen=True)

    opaque_pixels: int = 0
    total_pixels: int = 0
    coverage_ratio: float = 0.0
    emissive_pixels: int = 0
    emissive_ratio: float = 0.0
    orphan_pixels: int = 0


class SurfaceMetricsDelta(BaseModel):
    """Baseline vs current surface metrics and their signed deltas."""

    model_config = ConfigDict(frozen=True)

    baseline: SurfaceMetrics
    current: SurfaceMetrics
    opaque_pixel_delta: int
    coverage_delta: float
    emissive_pixel_delta: int
    emissive_ratio_delta: float
    orphan_pixel_delta: int


def compute_surface_metrics(surface: IndexedSurface, style: StylePack) -> SurfaceMetrics:
    """Compute opaque, canvas-coverage, emissive, and orphan-pixel metrics for one surface."""
    data = surface.data
    total_pixels = int(data.size)
    opaque_pixels = int(np.count_nonzero(data != TRANSPARENT_INDEX))
    coverage_ratio = round(opaque_pixels / total_pixels, 6) if total_pixels > 0 else 0.0
    emissive_indices = [entry.index for entry in style.palette if "emissive" in entry.flags]
    emissive_pixels = (
        int(np.count_nonzero(np.isin(data, emissive_indices)))
        if emissive_indices and opaque_pixels > 0
        else 0
    )
    emissive_ratio = round(emissive_pixels / opaque_pixels, 6) if opaque_pixels > 0 else 0.0
    orphan_pixels = int(np.count_nonzero(orphan_pixel_mask(surface))) if opaque_pixels > 0 else 0
    return SurfaceMetrics(
        opaque_pixels=opaque_pixels,
        total_pixels=total_pixels,
        coverage_ratio=coverage_ratio,
        emissive_pixels=emissive_pixels,
        emissive_ratio=emissive_ratio,
        orphan_pixels=orphan_pixels,
    )


def diff_surface_metrics(
    baseline: SurfaceMetrics,
    current: SurfaceMetrics,
) -> SurfaceMetricsDelta:
    """Compute signed deltas between baseline and current `SurfaceMetrics`."""
    return SurfaceMetricsDelta(
        baseline=baseline,
        current=current,
        opaque_pixel_delta=current.opaque_pixels - baseline.opaque_pixels,
        coverage_delta=round(current.coverage_ratio - baseline.coverage_ratio, 6),
        emissive_pixel_delta=current.emissive_pixels - baseline.emissive_pixels,
        emissive_ratio_delta=round(current.emissive_ratio - baseline.emissive_ratio, 6),
        orphan_pixel_delta=current.orphan_pixels - baseline.orphan_pixels,
    )


def aggregate_surface_metrics(items: Sequence[SurfaceMetrics]) -> SurfaceMetrics:
    """Aggregate `SurfaceMetrics` across multiple frames into an asset-level summary."""
    if not items:
        return SurfaceMetrics()
    total_pixels = sum(m.total_pixels for m in items)
    opaque_pixels = sum(m.opaque_pixels for m in items)
    emissive_pixels = sum(m.emissive_pixels for m in items)
    orphan_pixels = sum(m.orphan_pixels for m in items)
    return SurfaceMetrics(
        opaque_pixels=opaque_pixels,
        total_pixels=total_pixels,
        coverage_ratio=round(opaque_pixels / total_pixels, 6) if total_pixels > 0 else 0.0,
        emissive_pixels=emissive_pixels,
        emissive_ratio=round(emissive_pixels / opaque_pixels, 6) if opaque_pixels > 0 else 0.0,
        orphan_pixels=orphan_pixels,
    )


class RemovedFrameRef(BaseModel):
    """Reference to a `(state, frame)` present in baseline but absent in current."""

    model_config = ConfigDict(frozen=True)

    state: str
    frame: int


class FrameDiffEntry(BaseModel):
    """Per-frame pixel and anchor/hitbox metadata diff summary."""

    model_config = ConfigDict(frozen=True)

    state: str
    frame: int
    diff_png: str
    changed_pixels: int
    total_pixels: int
    changed_ratio: float
    baseline_width: int | None
    baseline_height: int | None
    current_width: int
    current_height: int
    metrics: SurfaceMetricsDelta
    anchors: list[AnchorDelta]
    hitboxes: list[HitboxDelta]


class AssetDiffReport(BaseModel):
    """Structured machine-readable summary emitted by `pixelforge diff --json`."""

    model_config = ConfigDict(frozen=True)

    asset_id: str
    base_ref: str
    variant: str | None = None
    baseline_exists: bool
    total_changed_pixels: int
    total_pixels: int
    has_pixel_changes: bool
    has_metadata_changes: bool
    has_changes: bool
    metrics: SurfaceMetricsDelta
    frames: list[FrameDiffEntry]
    removed_frames: list[RemovedFrameRef]


def diff_anchors(
    baseline: Sequence[AnchorPoint],
    current: Sequence[AnchorPoint],
) -> list[AnchorDelta]:
    """Return sorted `AnchorDelta` entries between baseline and current anchor tuples."""
    base_by_name = {a.name: a for a in baseline}
    curr_by_name = {a.name: a for a in current}
    deltas: list[AnchorDelta] = []
    for name in sorted(set(base_by_name) | set(curr_by_name)):
        b = base_by_name.get(name)
        c = curr_by_name.get(name)
        if b is None and c is not None:
            deltas.append(AnchorDelta(name=name, status="added", after=c))
        elif b is not None and c is None:
            deltas.append(AnchorDelta(name=name, status="removed", before=b))
        elif b is not None and c is not None and (b.x, b.y) != (c.x, c.y):
            deltas.append(
                AnchorDelta(
                    name=name,
                    status="moved",
                    before=b,
                    after=c,
                    dx=c.x - b.x,
                    dy=c.y - b.y,
                )
            )
        elif b is not None and c is not None and (b.kind, b.dir) != (c.kind, c.dir):
            deltas.append(
                AnchorDelta(
                    name=name,
                    status="changed",
                    before=b,
                    after=c,
                    dx=0,
                    dy=0,
                )
            )
    return deltas


def diff_hitboxes(
    baseline: Sequence[HitboxRect],
    current: Sequence[HitboxRect],
) -> list[HitboxDelta]:
    """Return sorted `HitboxDelta` entries between baseline and current hitbox tuples."""
    base_by_name = {h.name: h for h in baseline}
    curr_by_name = {h.name: h for h in current}
    deltas: list[HitboxDelta] = []
    for name in sorted(set(base_by_name) | set(curr_by_name)):
        b = base_by_name.get(name)
        c = curr_by_name.get(name)
        if b is None and c is not None:
            deltas.append(HitboxDelta(name=name, status="added", after=c))
        elif b is not None and c is None:
            deltas.append(HitboxDelta(name=name, status="removed", before=b))
        elif (
            b is not None
            and c is not None
            and (b.x, b.y, b.w, b.h, b.kind) != (c.x, c.y, c.w, c.h, c.kind)
        ):
            deltas.append(
                HitboxDelta(
                    name=name,
                    status="changed",
                    before=b,
                    after=c,
                    dx=c.x - b.x,
                    dy=c.y - b.y,
                    dw=c.w - b.w,
                    dh=c.h - b.h,
                )
            )
    return deltas


def format_metadata_deltas(
    anchors: Sequence[AnchorDelta],
    hitboxes: Sequence[HitboxDelta],
) -> list[str]:
    """Format anchor and hitbox deltas as human-readable CLI summary lines."""
    lines: list[str] = []
    for anchor in anchors:
        if anchor.status == "added" and anchor.after is not None:
            lines.append(f"  anchor {anchor.name!r}: added ({anchor.after.x}, {anchor.after.y})")
        elif anchor.status == "removed" and anchor.before is not None:
            lines.append(
                f"  anchor {anchor.name!r}: removed ({anchor.before.x}, {anchor.before.y})"
            )
        elif anchor.status == "moved" and anchor.before is not None and anchor.after is not None:
            lines.append(
                f"  anchor {anchor.name!r}: moved ({anchor.before.x}, {anchor.before.y}) -> "
                f"({anchor.after.x}, {anchor.after.y}) (dx={anchor.dx:+d}, dy={anchor.dy:+d})"
            )
        elif anchor.status == "changed" and anchor.before is not None and anchor.after is not None:
            lines.append(
                f"  anchor {anchor.name!r}: changed "
                f"(kind={anchor.before.kind!r}, dir={anchor.before.dir!r}) -> "
                f"(kind={anchor.after.kind!r}, dir={anchor.after.dir!r})"
            )
    for hitbox in hitboxes:
        if hitbox.status == "added" and hitbox.after is not None:
            lines.append(
                f"  hitbox {hitbox.name!r}: added "
                f"({hitbox.after.x}, {hitbox.after.y}, {hitbox.after.w}x{hitbox.after.h})"
            )
        elif hitbox.status == "removed" and hitbox.before is not None:
            lines.append(
                f"  hitbox {hitbox.name!r}: removed "
                f"({hitbox.before.x}, {hitbox.before.y}, {hitbox.before.w}x{hitbox.before.h})"
            )
        elif hitbox.status == "changed" and hitbox.before is not None and hitbox.after is not None:
            lines.append(
                f"  hitbox {hitbox.name!r}: changed "
                f"({hitbox.before.x}, {hitbox.before.y}, {hitbox.before.w}x{hitbox.before.h}) -> "
                f"({hitbox.after.x}, {hitbox.after.y}, {hitbox.after.w}x{hitbox.after.h}) "
                f"(dx={hitbox.dx:+d}, dy={hitbox.dy:+d}, dw={hitbox.dw:+d}, dh={hitbox.dh:+d})"
            )
    return lines


def format_diff_markdown(report: AssetDiffReport) -> str:
    """Format an `AssetDiffReport` as a concise Markdown PR regression summary."""
    m = report.metrics
    b = m.baseline
    c = m.current
    lines = [
        f"### Pixelforge Diff: `{report.asset_id}`",
        "",
        (
            f"- **Base:** `{report.base_ref}` | "
            f"**Changed Pixels:** {report.total_changed_pixels}/{report.total_pixels} | "
            f"**Baseline Exists:** {'yes' if report.baseline_exists else 'no'}"
        ),
        "",
        "| Metric | Baseline | Current | Delta |",
        "|---|---:|---:|---:|",
        f"| Opaque Pixels | {b.opaque_pixels} | {c.opaque_pixels} | {m.opaque_pixel_delta:+d} |",
        (
            f"| Canvas Coverage | {b.coverage_ratio:.1%} | "
            f"{c.coverage_ratio:.1%} | {m.coverage_delta:+.1%} |"
        ),
        (
            f"| Emissive Pixels | {b.emissive_pixels} | "
            f"{c.emissive_pixels} | {m.emissive_pixel_delta:+d} |"
        ),
        (
            f"| Emissive Ratio | {b.emissive_ratio:.1%} | "
            f"{c.emissive_ratio:.1%} | {m.emissive_ratio_delta:+.1%} |"
        ),
        f"| Orphan Pixels | {b.orphan_pixels} | {c.orphan_pixels} | {m.orphan_pixel_delta:+d} |",
    ]
    meta_lines: list[str] = []
    for frame in report.frames:
        frame_deltas = format_metadata_deltas(frame.anchors, frame.hitboxes)
        if frame_deltas:
            meta_lines.append(f"- `{frame.state}:f{frame.frame}`:")
            for delta in frame_deltas:
                meta_lines.append(f"  - {delta.strip()}")
    if report.removed_frames:
        for rem in report.removed_frames:
            meta_lines.append(f"- Removed frame `{rem.state}:f{rem.frame}`")
    if meta_lines:
        lines.extend(["", "#### Metadata & Frame Deltas", "", *meta_lines])
    return "\n".join(lines) + "\n"
