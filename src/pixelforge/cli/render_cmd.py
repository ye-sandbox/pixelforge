"""CLI `render` workflow and shared asset/scene compilation helpers."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pixelforge.cli.output import OutputFn, OutputFormat
from pixelforge.core.types import StylePack
from pixelforge.export.atlas import AtlasFormat
from pixelforge.export.bundle import (
    ExportBundleOptions,
    ExportBundleResult,
    ExportedAssetManifestEntry,
    LoadedAsset,
    export_asset_bundle,
    export_rendered_frames_bundle,
    write_export_bundle,
    write_manifest,
)
from pixelforge.export.contact_sheet import (
    ContactSheetOptions,
    generate_contact_sheet,
    generate_contact_sheet_from_frames,
)
from pixelforge.export.indexed_ts import export_indexed_ts, write_indexed_ts_bundle
from pixelforge.export.scene import (
    LoadedScene,
    SceneCompositionError,
    compose_scene_frames,
    export_scene_bundle,
)
from pixelforge.guard.runner import (
    discover_asset_files,
    discover_scene_files,
    load_all_styles,
    load_asset_module,
    load_scene_module,
)


def compile_style_indexed_bundles(
    style: StylePack,
    rendered_bundles: list[ExportBundleResult],
    all_loaded: Sequence[LoadedAsset],
    options: ExportBundleOptions,
    *,
    all_scenes: Sequence[LoadedScene] = (),
    loaded_by_id: dict[str, LoadedAsset] | None = None,
) -> list[ExportBundleResult]:
    """Return full `StylePack` asset and scene bundles in discovery order for `--indexed-ts`."""
    # INVARIANT: `dist/indexed/` is a single-bundle TypeScript module per StylePack;
    # filtered `render`/`watch <asset_id>` must still include sibling assets and scenes
    # of that style so `sprites.generated.ts` and `manifest.generated.ts` are never truncated.
    by_id = {bundle.manifest.id: bundle for bundle in rendered_bundles}
    assets_map = loaded_by_id if loaded_by_id is not None else {a.SPEC.id: a for a in all_loaded}
    full_bundles: list[ExportBundleResult] = []
    for loaded in all_loaded:
        if loaded.SPEC.style_id != style.id:
            continue
        existing = by_id.get(loaded.SPEC.id)
        full_bundles.append(
            existing if existing is not None else export_asset_bundle(loaded, style, options)
        )
    for scene in all_scenes:
        parent = assets_map.get(scene.SCENE.parent_id)
        if parent is None:
            continue
        scene_style_id = scene.SCENE.style_id or parent.SPEC.style_id
        if scene_style_id != style.id:
            continue
        existing = by_id.get(scene.SCENE.id)
        full_bundles.append(
            existing
            if existing is not None
            else export_scene_bundle(scene.SCENE, parent, assets_map, style, options)
        )
    return full_bundles


def emit_indexed_ts_bundles(
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]],
    all_loaded: Sequence[LoadedAsset],
    options: ExportBundleOptions,
    out_dir: Path,
    *,
    filtered: bool,
    lazy: bool = False,
    all_scenes: Sequence[LoadedScene] = (),
    loaded_by_id: dict[str, LoadedAsset] | None = None,
) -> None:
    """Emit `--indexed-ts` TypeScript modules for each compiled `StylePack`."""
    multi_style = len(bundles_by_style) > 1
    for style, style_bundles in bundles_by_style.values():
        full_bundles = (
            compile_style_indexed_bundles(
                style,
                style_bundles,
                all_loaded,
                options,
                all_scenes=all_scenes,
                loaded_by_id=loaded_by_id,
            )
            if filtered
            else style_bundles
        )
        ts_result = export_indexed_ts(full_bundles, style, lazy=lazy)
        indexed_out = (
            out_dir / "indexed" / style.id.replace("-", "_") if multi_style else out_dir / "indexed"
        )
        write_indexed_ts_bundle(ts_result, indexed_out)


def compile_and_write_asset(
    asset_path: Path,
    loaded: LoadedAsset,
    styles: dict[str, StylePack],
    options: ExportBundleOptions,
    out_dir: Path,
    sheets_dir: Path,
    previews_dir: Path | None,
    *,
    sheet: bool,
    update_manifest: bool,
    err: OutputFn,
) -> tuple[StylePack, ExportBundleResult] | None:
    """Compile one loaded asset and write its bundle and optional contact sheet."""
    style = styles.get(loaded.SPEC.style_id)
    if style is None:
        err(
            f"{asset_path}:1 [missing-style] Referenced style "
            f"{loaded.SPEC.style_id!r} not found in styles/"
        )
        return None

    bundle = export_asset_bundle(loaded, style, options)
    write_export_bundle(
        bundle,
        out_dir,
        previews_dir=previews_dir,
        update_manifest=update_manifest,
    )
    if sheet:
        sheets_dir.mkdir(parents=True, exist_ok=True)
        contact = generate_contact_sheet(
            loaded,
            style,
            ContactSheetOptions(variant=options.variant),
        )
        (sheets_dir / f"{loaded.SPEC.id}.contact.png").write_bytes(contact.png)
    return (style, bundle)


def compile_and_write_scene(
    scene_path: Path,
    scene: LoadedScene,
    loaded_by_id: dict[str, LoadedAsset],
    styles: dict[str, StylePack],
    options: ExportBundleOptions,
    out_dir: Path,
    sheets_dir: Path,
    previews_dir: Path,
    *,
    sheet: bool,
    animate: bool,
    update_manifest: bool,
    err: OutputFn,
) -> tuple[StylePack, ExportBundleResult] | None:
    """Compile one loaded `.scene.py` and write its bundle and optional contact sheet."""
    parent = loaded_by_id.get(scene.SCENE.parent_id)
    if parent is None:
        err(f"{scene_path}:1 [missing-parent] Parent asset {scene.SCENE.parent_id!r} not found")
        return None
    style_id = scene.SCENE.style_id or parent.SPEC.style_id
    style = styles.get(style_id)
    if style is None:
        err(f"{scene_path}:1 [missing-style] Referenced style {style_id!r} not found in styles/")
        return None
    try:
        asset_spec, rendered_frames, _ = compose_scene_frames(
            scene.SCENE,
            parent,
            loaded_by_id,
            style,
            variant=options.variant,
        )
    except SceneCompositionError as exc:
        err(f"{scene_path}:1 [scene-error] {exc}")
        return None

    bundle = export_rendered_frames_bundle(asset_spec, rendered_frames, style, options)
    write_export_bundle(
        bundle,
        out_dir,
        previews_dir=previews_dir if animate else None,
        update_manifest=update_manifest,
    )
    if sheet:
        sheets_dir.mkdir(parents=True, exist_ok=True)
        contact = generate_contact_sheet_from_frames(
            asset_spec,
            rendered_frames,
            style,
            ContactSheetOptions(variant=options.variant),
        )
        (sheets_dir / f"{scene.SCENE.id}.contact.png").write_bytes(contact.png)
    return (style, bundle)


def _render_asset_targets(
    asset_files: Sequence[Path],
    styles: dict[str, StylePack],
    options: ExportBundleOptions,
    out_dir: Path,
    sheets_dir: Path,
    previews_dir: Path | None,
    *,
    asset_id: str | None,
    sheet: bool,
    err: OutputFn,
) -> (
    tuple[
        list[LoadedAsset],
        dict[str, LoadedAsset],
        dict[str, Path],
        dict[str, tuple[StylePack, list[ExportBundleResult]]],
        int,
    ]
    | None
):
    all_loaded: list[LoadedAsset] = []
    loaded_by_id: dict[str, LoadedAsset] = {}
    seen_ids: dict[str, Path] = {}
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]] = {}
    rendered_count = 0

    for asset_path in asset_files:
        loaded = load_asset_module(asset_path)
        if loaded.SPEC.id in seen_ids:
            err(
                f"{asset_path}:1 [duplicate-id] Duplicate asset ID {loaded.SPEC.id!r} "
                f"(already declared in {seen_ids[loaded.SPEC.id]})"
            )
            return None
        seen_ids[loaded.SPEC.id] = asset_path
        all_loaded.append(loaded)
        loaded_by_id[loaded.SPEC.id] = loaded
        if asset_id is not None and loaded.SPEC.id != asset_id:
            continue

        compiled = compile_and_write_asset(
            asset_path,
            loaded,
            styles,
            options,
            out_dir,
            sheets_dir,
            previews_dir,
            sheet=sheet,
            update_manifest=asset_id is not None,
            err=err,
        )
        if compiled is None:
            return None
        style, bundle = compiled
        bundles_by_style.setdefault(style.id, (style, []))[1].append(bundle)
        rendered_count += 1

    return (all_loaded, loaded_by_id, seen_ids, bundles_by_style, rendered_count)


def _render_scene_targets(
    root: Path,
    loaded_by_id: dict[str, LoadedAsset],
    seen_ids: dict[str, Path],
    styles: dict[str, StylePack],
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]],
    options: ExportBundleOptions,
    out_dir: Path,
    sheets_dir: Path,
    previews_dir: Path,
    *,
    asset_id: str | None,
    sheet: bool,
    animate: bool,
    err: OutputFn,
) -> tuple[list[LoadedScene], int] | None:
    all_scenes: list[LoadedScene] = []
    rendered_count = 0
    for scene_path in discover_scene_files(root / "assets"):
        loaded_scene = load_scene_module(scene_path)
        if loaded_scene.SCENE.id in seen_ids:
            err(
                f"{scene_path}:1 [duplicate-id] Duplicate asset ID {loaded_scene.SCENE.id!r} "
                f"(already declared in {seen_ids[loaded_scene.SCENE.id]})"
            )
            return None
        seen_ids[loaded_scene.SCENE.id] = scene_path
        all_scenes.append(loaded_scene)
        if asset_id is not None and loaded_scene.SCENE.id != asset_id:
            continue

        compiled = compile_and_write_scene(
            scene_path,
            loaded_scene,
            loaded_by_id,
            styles,
            options,
            out_dir,
            sheets_dir,
            previews_dir,
            sheet=sheet,
            animate=animate,
            update_manifest=asset_id is not None,
            err=err,
        )
        if compiled is None:
            return None
        style, bundle = compiled
        bundles_by_style.setdefault(style.id, (style, []))[1].append(bundle)
        rendered_count += 1

    return (all_scenes, rendered_count)


def _finalize_render_outputs(
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]],
    all_loaded: Sequence[LoadedAsset],
    all_scenes: Sequence[LoadedScene],
    loaded_by_id: dict[str, LoadedAsset],
    options: ExportBundleOptions,
    out_dir: Path,
    *,
    asset_id: str | None,
    indexed_ts: bool,
    indexed_ts_lazy: bool,
) -> None:
    if asset_id is None:
        all_manifests: dict[str, ExportedAssetManifestEntry] = {
            bundle.manifest.id: bundle.manifest
            for _, style_bundles in bundles_by_style.values()
            for bundle in style_bundles
        }
        write_manifest(all_manifests, out_dir)

    if indexed_ts:
        emit_indexed_ts_bundles(
            bundles_by_style,
            all_loaded,
            options,
            out_dir,
            filtered=asset_id is not None,
            lazy=indexed_ts_lazy,
            all_scenes=all_scenes,
            loaded_by_id=loaded_by_id,
        )


def _emit_render_summary(
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]],
    *,
    out_dir: Path,
    indexed_ts: bool,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    entries = [
        bundle.manifest
        for _, style_bundles in bundles_by_style.values()
        for bundle in style_bundles
    ]
    if output_format == "json":
        payload = {
            "count": len(entries),
            "out_dir": str(out_dir),
            "manifest": str(out_dir / "manifest.json"),
            "indexed_ts": indexed_ts,
            "rendered": [
                {
                    "id": e.id,
                    "style_id": e.styleId,
                    "width": e.width,
                    "height": e.height,
                    "states": list(e.states),
                    "frames": e.frames,
                }
                for e in entries
            ],
        }
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        for entry in entries:
            out(f"rendered {entry.id} -> {out_dir}")
        return

    for entry in entries:
        states_csv = ",".join(entry.states)
        out(
            f"asset={entry.id} style={entry.styleId} size={entry.width}x{entry.height} "
            f"states={states_csv} frames={entry.frames} out={out_dir}"
        )
    ts_flag = " indexed_ts=true" if indexed_ts else ""
    out(
        f"summary rendered={len(entries)} out={out_dir} "
        f"manifest={out_dir / 'manifest.json'}{ts_flag}"
    )


def render_once(
    root: Path,
    *,
    asset_id: str | None,
    out_dir: Path,
    sheets_dir: Path,
    previews_dir: Path,
    sheet: bool,
    animate: bool,
    animate_format: Literal["gif", "apng"] = "gif",
    emissive: bool | None,
    lut: bool,
    indexed_ts: bool,
    indexed_ts_lazy: bool = False,
    atlas: AtlasFormat | None = None,
    scale: int,
    variant: str | None,
    output_format: OutputFormat = "llm",
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Compile matching assets under `root` into PNGs, manifests, sheets, and TS bundles."""
    try:
        styles = load_all_styles(root / "styles")
    except ValueError as exc:
        err(str(exc))
        return 1

    asset_files = discover_asset_files(root / "assets")
    if not asset_files:
        err("No .asset.py files found under assets/")
        return 1

    options = ExportBundleOptions(
        variant=variant,
        scale=scale,
        emissive=emissive,
        lut=lut,
        animate=animate,
        animate_format=animate_format,
        atlas=atlas,
    )
    asset_result = _render_asset_targets(
        asset_files,
        styles,
        options,
        out_dir,
        sheets_dir,
        previews_dir if animate else None,
        asset_id=asset_id,
        sheet=sheet,
        err=err,
    )
    if asset_result is None:
        return 1
    all_loaded, loaded_by_id, seen_ids, bundles_by_style, asset_count = asset_result

    scene_result = _render_scene_targets(
        root,
        loaded_by_id,
        seen_ids,
        styles,
        bundles_by_style,
        options,
        out_dir,
        sheets_dir,
        previews_dir,
        asset_id=asset_id,
        sheet=sheet,
        animate=animate,
        err=err,
    )
    if scene_result is None:
        return 1
    all_scenes, scene_count = scene_result

    if asset_count + scene_count == 0:
        err(f"Asset {asset_id!r} not found under assets/")
        return 1

    _finalize_render_outputs(
        bundles_by_style,
        all_loaded,
        all_scenes,
        loaded_by_id,
        options,
        out_dir,
        asset_id=asset_id,
        indexed_ts=indexed_ts,
        indexed_ts_lazy=indexed_ts_lazy,
    )
    _emit_render_summary(
        bundles_by_style,
        out_dir=out_dir,
        indexed_ts=indexed_ts,
        output_format=output_format,
        out=out,
    )
    return 0
