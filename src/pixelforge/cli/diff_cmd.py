"""CLI `diff` workflow and git/metadata baseline resolution helpers."""

from __future__ import annotations

from pathlib import Path

from pixelforge.cli.output import OutputFn, OutputFormat
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import StylePack
from pixelforge.export.bundle import LoadedAsset, RenderedFrame, render_asset_frames
from pixelforge.export.diff import (
    AssetDiffReport,
    FrameDiffEntry,
    RemovedFrameRef,
    diff_anchors,
    diff_hitboxes,
    format_metadata_deltas,
    generate_surface_diff,
)
from pixelforge.guard.runner import (
    discover_asset_files,
    discover_style_files,
    load_asset_from_git,
    load_asset_module,
    load_style_from_git,
    load_style_module,
)


def load_styles_with_paths(styles_dir: Path) -> tuple[dict[str, StylePack], dict[str, Path]]:
    """Load all `.style.py` modules under `styles_dir`, returning packs and source paths."""
    styles: dict[str, StylePack] = {}
    style_paths: dict[str, Path] = {}
    for style_path in discover_style_files(styles_dir):
        pack = load_style_module(style_path)
        styles[pack.id] = pack
        style_paths[pack.id] = style_path
    return (styles, style_paths)


def resolve_baseline_style(
    root: Path,
    *,
    baseline_asset: LoadedAsset | None,
    current_style: StylePack,
    styles: dict[str, StylePack],
    style_paths: dict[str, Path],
    base_ref: str,
    variant: str | None,
) -> StylePack:
    """Load the historical `StylePack` at `base_ref`, falling back to current when needed."""
    if baseline_asset is None:
        return current_style

    fallback = styles.get(baseline_asset.SPEC.style_id, current_style)
    style_path = style_paths.get(baseline_asset.SPEC.style_id)
    if style_path is None:
        return fallback

    historical = load_style_from_git(root, style_path, ref=base_ref)
    if historical is None:
        return fallback
    # INVARIANT: Fall back to current style when --variant only exists in the working tree
    if variant is not None and variant not in historical.variants:
        return fallback
    return historical


def _find_asset_path(assets_dir: Path, asset_id: str) -> Path | None:
    for candidate in discover_asset_files(assets_dir):
        if load_asset_module(candidate).SPEC.id == asset_id:
            return candidate
    return None


def _diff_single_frame(
    frame: RenderedFrame,
    base_frame: RenderedFrame | None,
    *,
    current_asset: LoadedAsset,
    style: StylePack,
    base_style: StylePack,
    out_dir: Path,
    scale: int,
    variant: str | None,
    output_format: OutputFormat,
    out: OutputFn,
) -> tuple[FrameDiffEntry, int, int, bool]:
    base_surface = (
        base_frame.surface
        if base_frame is not None
        else IndexedSurface(frame.surface.width, frame.surface.height)
    )
    diff = generate_surface_diff(
        base_surface,
        frame.surface,
        style,
        variant=variant,
        scale=scale,
        baseline_style=base_style,
    )
    anchor_deltas = diff_anchors(
        base_frame.anchors if base_frame is not None else (),
        frame.anchors,
    )
    hitbox_deltas = diff_hitboxes(
        base_frame.hitboxes if base_frame is not None else (),
        frame.hitboxes,
    )
    has_meta = bool(anchor_deltas or hitbox_deltas)

    suffix = (
        f"{frame.state}.diff.png"
        if current_asset.SPEC.frames == 1
        else f"{frame.state}_f{frame.frame}.diff.png"
    )
    diff_path = out_dir / f"{current_asset.SPEC.id}_{suffix}"
    diff_path.write_bytes(diff.png)

    ratio = round(diff.changed_pixels / diff.total_pixels, 6) if diff.total_pixels > 0 else 0.0
    entry = FrameDiffEntry(
        state=frame.state,
        frame=frame.frame,
        diff_png=str(diff_path),
        changed_pixels=diff.changed_pixels,
        total_pixels=diff.total_pixels,
        changed_ratio=ratio,
        baseline_width=base_frame.surface.width if base_frame is not None else None,
        baseline_height=base_frame.surface.height if base_frame is not None else None,
        current_width=frame.surface.width,
        current_height=frame.surface.height,
        anchors=anchor_deltas,
        hitboxes=hitbox_deltas,
    )
    if output_format == "human":
        out(f"diff {diff_path}: {diff.changed_pixels}/{diff.total_pixels} changed pixel(s)")
        for line in format_metadata_deltas(anchor_deltas, hitbox_deltas):
            out(line)
    elif output_format == "llm":
        out(
            f"frame={frame.state}:f{frame.frame} "
            f"changed={diff.changed_pixels}/{diff.total_pixels} "
            f"ratio={ratio:.4f} diff={diff_path}"
        )
        for line in format_metadata_deltas(anchor_deltas, hitbox_deltas):
            out(line.strip())
    return (entry, diff.changed_pixels, diff.total_pixels, has_meta)


def _emit_diff_summary(
    *,
    asset_id: str,
    base_ref: str,
    variant: str | None,
    baseline_exists: bool,
    total_changed: int,
    total_pixels: int,
    has_metadata_changes: bool,
    frame_entries: list[FrameDiffEntry],
    removed_frames: list[RemovedFrameRef],
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    if output_format == "human":
        for removed in removed_frames:
            out(f"  removed frame: ({removed.state}, f{removed.frame})")
        return
    if output_format == "llm":
        for removed in removed_frames:
            out(f"removed_frame={removed.state}:f{removed.frame}")
        out(
            f"summary asset={asset_id} base={base_ref} "
            f"changed={total_changed}/{total_pixels} "
            f"pixel_changed={str(total_changed > 0).lower()} "
            f"meta_changed={str(has_metadata_changes).lower()} "
            f"baseline={str(baseline_exists).lower()}"
        )
        return
    report = AssetDiffReport(
        asset_id=asset_id,
        base_ref=base_ref,
        variant=variant,
        baseline_exists=baseline_exists,
        total_changed_pixels=total_changed,
        total_pixels=total_pixels,
        has_pixel_changes=total_changed > 0,
        has_metadata_changes=has_metadata_changes,
        has_changes=total_changed > 0 or has_metadata_changes or bool(removed_frames),
        frames=frame_entries,
        removed_frames=removed_frames,
    )
    out(report.model_dump_json(indent=2))


def diff_asset(
    root: Path,
    *,
    asset_id: str,
    base_ref: str,
    out_dir: Path,
    scale: int,
    variant: str | None,
    output_format: OutputFormat = "llm",
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Generate side-by-side + magenta pixel-diff PNGs and metadata deltas against a git ref."""
    styles, style_paths = load_styles_with_paths(root / "styles")
    target_path = _find_asset_path(root / "assets", asset_id)
    if target_path is None:
        err(f"Asset {asset_id!r} not found under assets/")
        return 1

    current_asset = load_asset_module(target_path)
    style = styles.get(current_asset.SPEC.style_id)
    if style is None:
        err(f"Referenced style {current_asset.SPEC.style_id!r} not found in styles/")
        return 1

    baseline_asset = load_asset_from_git(root, target_path, ref=base_ref)
    base_style = resolve_baseline_style(
        root,
        baseline_asset=baseline_asset,
        current_style=style,
        styles=styles,
        style_paths=style_paths,
        base_ref=base_ref,
        variant=variant,
    )
    current_frames = render_asset_frames(current_asset, style, variant=variant)
    baseline_frames: dict[tuple[str, int], RenderedFrame] = (
        {
            (f.state, f.frame): f
            for f in render_asset_frames(baseline_asset, base_style, variant=variant)
        }
        if baseline_asset is not None
        else {}
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    frame_entries: list[FrameDiffEntry] = []
    total_changed = 0
    total_pixels = 0
    has_metadata_changes = False
    seen_keys: set[tuple[str, int]] = set()

    for frame in current_frames:
        key = (frame.state, frame.frame)
        seen_keys.add(key)
        entry, changed, total, has_meta = _diff_single_frame(
            frame,
            baseline_frames.get(key),
            current_asset=current_asset,
            style=style,
            base_style=base_style,
            out_dir=out_dir,
            scale=scale,
            variant=variant,
            output_format=output_format,
            out=out,
        )
        frame_entries.append(entry)
        total_changed += changed
        total_pixels += total
        has_metadata_changes = has_metadata_changes or has_meta

    removed_frames = [
        RemovedFrameRef(state=state, frame=frame_idx)
        for (state, frame_idx) in sorted(baseline_frames)
        if (state, frame_idx) not in seen_keys
    ]
    _emit_diff_summary(
        asset_id=current_asset.SPEC.id,
        base_ref=base_ref,
        variant=variant,
        baseline_exists=baseline_asset is not None,
        total_changed=total_changed,
        total_pixels=total_pixels,
        has_metadata_changes=has_metadata_changes,
        frame_entries=frame_entries,
        removed_frames=removed_frames,
        output_format=output_format,
        out=out,
    )
    return 0
