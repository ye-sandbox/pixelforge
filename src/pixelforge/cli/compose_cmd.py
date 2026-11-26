"""CLI `compose` scene-composition workflow."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pixelforge.cli.output import OutputFn, OutputFormat
from pixelforge.core.types import StylePack
from pixelforge.export.bundle import LoadedAsset
from pixelforge.export.png import frames_to_apng, frames_to_gif, surface_to_png, surface_to_rgba
from pixelforge.export.scene import (
    DepthSortMode,
    SceneCompositionError,
    SceneCompositionResult,
    SceneCompositionSpec,
    SceneMountSpec,
    SceneSpec,
    compose_scene,
    compose_scene_frames,
    generate_scene_sheet,
    resolve_scene_asset_spec,
)
from pixelforge.guard.runner import discover_asset_files, load_all_styles, load_asset_module


def parse_mount_arg(spec_text: str) -> SceneMountSpec:
    """Parse `--mount prop_id@anchor[:prop_anchor]` into a `SceneMountSpec`."""
    if "@" not in spec_text:
        msg = f"Invalid --mount {spec_text!r}: expected format 'prop_id@anchor[:prop_anchor]'"
        raise ValueError(msg)
    prop_id, anchor_part = spec_text.split("@", 1)
    if ":" in anchor_part:
        anchor, prop_anchor = anchor_part.split(":", 1)
    else:
        anchor, prop_anchor = anchor_part, None
    if not prop_id or not anchor or (prop_anchor is not None and not prop_anchor):
        msg = f"Invalid --mount {spec_text!r}: empty prop_id or anchor name"
        raise ValueError(msg)
    return SceneMountSpec(prop_id=prop_id, anchor=anchor, prop_anchor=prop_anchor)


def _load_assets_by_id(root: Path, err: OutputFn) -> dict[str, LoadedAsset] | None:
    asset_files = discover_asset_files(root / "assets")
    if not asset_files:
        err("No .asset.py files found under assets/")
        return None

    loaded_by_id: dict[str, LoadedAsset] = {}
    for asset_path in asset_files:
        loaded = load_asset_module(asset_path)
        if loaded.SPEC.id in loaded_by_id:
            err(f"{asset_path}:1 [duplicate-id] Duplicate asset ID {loaded.SPEC.id!r}")
            return None
        loaded_by_id[loaded.SPEC.id] = loaded
    return loaded_by_id


def _write_composed_animation(
    parent: LoadedAsset,
    loaded_by_id: dict[str, LoadedAsset],
    style: StylePack,
    *,
    parent_id: str,
    parent_state: str,
    mounts: Sequence[SceneMountSpec],
    depth_sort: DepthSortMode,
    variant: str | None,
    strict_bounds: bool,
    strict_perspective: bool,
    animate_format: Literal["gif", "apng"],
    scale: int,
    out_dir: Path,
    err: OutputFn,
) -> tuple[Path, int, int] | None:
    anim_spec = SceneSpec(
        id=f"{parent_id}_composed",
        parent_id=parent_id,
        states=(parent_state,),
        mounts=tuple(mounts),
        depth_sort=depth_sort,
        variant=variant,
        strict_bounds=strict_bounds,
        strict_perspective=strict_perspective,
    )
    try:
        resolved_spec = resolve_scene_asset_spec(anim_spec, parent, loaded_by_id)
        _, anim_frames, _ = compose_scene_frames(
            anim_spec,
            parent,
            loaded_by_id,
            style,
            variant=variant,
        )
    except SceneCompositionError as exc:
        err(str(exc))
        return None

    rgba_frames = [
        surface_to_rgba(item.surface, style, variant=variant, scale=scale) for item in anim_frames
    ]
    ext = "apng" if animate_format == "apng" else "gif"
    anim_bytes = (
        frames_to_apng(rgba_frames, fps=resolved_spec.fps)
        if animate_format == "apng"
        else frames_to_gif(rgba_frames, fps=resolved_spec.fps)
    )
    anim_path = out_dir / f"{parent_id}_{parent_state}_composed.{ext}"
    anim_path.write_bytes(anim_bytes)
    return (anim_path, len(rgba_frames), resolved_spec.fps)


def _compose_and_write_png(
    root: Path,
    *,
    parent_id: str,
    mounts: Sequence[SceneMountSpec],
    state: str | None,
    frame: int,
    variant: str | None,
    depth_sort: DepthSortMode,
    strict_bounds: bool,
    strict_perspective: bool,
    scale: int,
    out_dir: Path,
    err: OutputFn,
) -> tuple[LoadedAsset, dict[str, LoadedAsset], StylePack, SceneCompositionResult, Path] | None:
    try:
        styles = load_all_styles(root / "styles")
    except ValueError as exc:
        err(str(exc))
        return None
    loaded_by_id = _load_assets_by_id(root, err)
    if loaded_by_id is None:
        return None
    parent = loaded_by_id.get(parent_id)
    if parent is None:
        err(f"Parent asset {parent_id!r} not found under assets/")
        return None
    style = styles.get(parent.SPEC.style_id)
    if style is None:
        err(f"Style {parent.SPEC.style_id!r} for parent {parent_id!r} not found in styles/")
        return None
    comp_spec = SceneCompositionSpec(
        parent_id=parent_id,
        parent_state=state,
        parent_frame=frame,
        mounts=tuple(mounts),
        variant=variant,
        depth_sort=depth_sort,
    )
    try:
        result = compose_scene(
            parent,
            loaded_by_id,
            style,
            comp_spec,
            strict_bounds=strict_bounds,
            strict_perspective=strict_perspective,
        )
    except SceneCompositionError as exc:
        err(str(exc))
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{parent_id}_{result.parent_state}_composed.png"
    png_path.write_bytes(surface_to_png(result.surface, style, variant=variant, scale=scale))
    return (parent, loaded_by_id, style, result, png_path)


def _emit_compose_output(
    *,
    parent_id: str,
    frame: int,
    result: SceneCompositionResult,
    png_path: Path,
    anim_info: tuple[Path, int, int] | None,
    sheet_path: Path | None,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    if output_format == "json":
        payload: dict[str, object] = {
            "parent_id": parent_id,
            "state": result.parent_state,
            "frame": frame,
            "width": result.surface.width,
            "height": result.surface.height,
            "props_count": len(result.placements),
            "placements": [
                {
                    "prop_id": p.prop_id,
                    "anchor": p.anchor,
                    "prop_anchor": p.prop_anchor,
                    "x": p.dest_x,
                    "y": p.dest_y,
                }
                for p in result.placements
            ],
            "png": str(png_path),
            "animation": (
                {
                    "path": str(anim_info[0]),
                    "frames": anim_info[1],
                    "fps": anim_info[2],
                }
                if anim_info is not None
                else None
            ),
            "sheet": str(sheet_path) if sheet_path is not None else None,
            "warnings": list(result.warnings),
        }
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        out(f"composed {png_path} ({len(result.placements)} prop(s))")
        for warning in result.warnings:
            out(f"warning: {warning}")
        if anim_info is not None:
            out(f"animated {anim_info[0]} ({anim_info[1]} frame(s) @ {anim_info[2]} fps)")
        if sheet_path is not None:
            out(f"sheet {sheet_path}")
        return

    out(
        f"status=ok parent={parent_id} state={result.parent_state} frame={frame} "
        f"size={result.surface.width}x{result.surface.height} "
        f"props={len(result.placements)} png={png_path}"
    )
    if anim_info is not None:
        out(f"anim path={anim_info[0]} frames={anim_info[1]} fps={anim_info[2]}")
    if sheet_path is not None:
        out(f"sheet path={sheet_path}")
    for warning in result.warnings:
        out(f"warn={warning}")


def compose_scene_workflow(
    root: Path,
    *,
    parent_id: str,
    mounts: Sequence[SceneMountSpec],
    state: str | None,
    frame: int,
    variant: str | None,
    depth_sort: DepthSortMode = "z_index",
    strict_bounds: bool,
    strict_perspective: bool = False,
    animate: bool = False,
    animate_format: Literal["gif", "apng"] = "gif",
    scale: int,
    out_dir: Path,
    sheets_dir: Path,
    sheet: bool,
    output_format: OutputFormat = "llm",
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Compose child props onto a parent scene and emit PNG + optional animated/contact sheet."""
    composed = _compose_and_write_png(
        root,
        parent_id=parent_id,
        mounts=mounts,
        state=state,
        frame=frame,
        variant=variant,
        depth_sort=depth_sort,
        strict_bounds=strict_bounds,
        strict_perspective=strict_perspective,
        scale=scale,
        out_dir=out_dir,
        err=err,
    )
    if composed is None:
        return 1
    parent, loaded_by_id, style, result, png_path = composed

    anim_info: tuple[Path, int, int] | None = None
    if animate:
        anim_info = _write_composed_animation(
            parent,
            loaded_by_id,
            style,
            parent_id=parent_id,
            parent_state=result.parent_state,
            mounts=mounts,
            depth_sort=depth_sort,
            variant=variant,
            strict_bounds=strict_bounds,
            strict_perspective=strict_perspective,
            animate_format=animate_format,
            scale=scale,
            out_dir=out_dir,
            err=err,
        )
        if anim_info is None:
            return 1

    sheet_path: Path | None = None
    if sheet:
        sheets_dir.mkdir(parents=True, exist_ok=True)
        sheet_result = generate_scene_sheet(result, style, variant=variant)
        sheet_path = sheets_dir / f"{parent_id}_composed.contact.png"
        sheet_path.write_bytes(sheet_result.png)

    _emit_compose_output(
        parent_id=parent_id,
        frame=frame,
        result=result,
        png_path=png_path,
        anim_info=anim_info,
        sheet_path=sheet_path,
        output_format=output_format,
        out=out,
    )
    return 0
