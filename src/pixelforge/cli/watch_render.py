"""Full and incremental asset/scene compilation helpers for `pixelforge watch`."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from pixelforge.cli.output import OutputFn, OutputFormat
from pixelforge.cli.render_cmd import (
    compile_and_write_asset,
    compile_and_write_scene,
    compile_style_indexed_bundles,
    emit_indexed_ts_bundles,
)
from pixelforge.cli.watch_graph import WatchGraph, scene_deps
from pixelforge.core.types import StylePack
from pixelforge.export.bundle import (
    ExportBundleOptions,
    ExportBundleResult,
    LoadedAsset,
    write_manifest,
)
from pixelforge.export.indexed_ts import export_indexed_ts, write_indexed_ts_bundle
from pixelforge.export.scene import LoadedScene
from pixelforge.guard.runner import (
    discover_asset_files,
    discover_scene_files,
    load_all_styles,
    load_asset_module,
    load_scene_module,
)


def _emit_watch_render(
    target_id: str,
    out_dir: Path,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    if output_format == "json":
        out(json.dumps({"event": "render", "target": target_id, "out_dir": str(out_dir)}))
        return
    if output_format == "human":
        out(f"rendered {target_id} -> {out_dir}")
        return
    out(f"watch event=render target={target_id} out={out_dir}")


def _emit_watch_full_indexed_ts(
    graph: WatchGraph,
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]],
    all_loaded: Sequence[LoadedAsset],
    all_scenes: Sequence[LoadedScene],
    options: ExportBundleOptions,
    out_dir: Path,
    *,
    asset_id: str | None,
    indexed_ts_lazy: bool,
) -> None:
    for style, style_bundles in bundles_by_style.values():
        full_bundles = (
            compile_style_indexed_bundles(
                style,
                style_bundles,
                all_loaded,
                options,
                all_scenes=all_scenes,
                loaded_by_id=graph.assets_by_id,
            )
            if asset_id is not None
            else style_bundles
        )
        for bundle in full_bundles:
            graph.bundles_by_id[bundle.manifest.id] = bundle
    emit_indexed_ts_bundles(
        bundles_by_style,
        all_loaded,
        options,
        out_dir,
        filtered=asset_id is not None,
        lazy=indexed_ts_lazy,
        all_scenes=all_scenes,
        loaded_by_id=graph.assets_by_id,
    )


def _record_watch_bundle(
    graph: WatchGraph,
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]],
    style: StylePack,
    bundle: ExportBundleResult,
) -> None:
    graph.bundles_by_id[bundle.manifest.id] = bundle
    graph.manifests_by_id[bundle.manifest.id] = bundle.manifest
    bundles_by_style.setdefault(style.id, (style, []))[1].append(bundle)


def _render_watch_full_scenes(
    root: Path,
    graph: WatchGraph,
    styles: dict[str, StylePack],
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]],
    options: ExportBundleOptions,
    out_dir: Path,
    sheets_dir: Path,
    *,
    asset_id: str | None,
    sheet: bool,
    out: OutputFn,
    err: OutputFn,
) -> tuple[list[LoadedScene], int] | None:
    all_scenes: list[LoadedScene] = []
    rendered_count = 0
    for scene_path in discover_scene_files(root / "assets"):
        loaded_scene = load_scene_module(scene_path)
        all_scenes.append(loaded_scene)
        graph.scene_meta_by_path[scene_path] = scene_deps(loaded_scene)
        if asset_id is not None and loaded_scene.SCENE.id != asset_id:
            continue
        compiled = compile_and_write_scene(
            scene_path,
            loaded_scene,
            graph.assets_by_id,
            styles,
            options,
            out_dir,
            sheets_dir,
            out_dir,
            sheet=sheet,
            animate=False,
            update_manifest=asset_id is not None,
            err=err,
        )
        if compiled is None:
            return None
        _record_watch_bundle(graph, bundles_by_style, compiled[0], compiled[1])
        rendered_count += 1
        _emit_watch_render(loaded_scene.SCENE.id, out_dir, graph.output_format, out)
    return (all_scenes, rendered_count)


def render_watch_full(
    root: Path,
    graph: WatchGraph,
    *,
    asset_id: str | None,
    out_dir: Path,
    sheets_dir: Path,
    sheet: bool,
    options: ExportBundleOptions,
    indexed_ts: bool,
    indexed_ts_lazy: bool,
    out: OutputFn,
    err: OutputFn,
) -> bool:
    try:
        styles = load_all_styles(root / "styles")
    except ValueError as exc:
        err(str(exc))
        return False

    asset_files = discover_asset_files(root / "assets")
    if not asset_files:
        err("No .asset.py files found under assets/")
        return False

    graph.bundles_by_id.clear()
    graph.manifests_by_id.clear()
    graph.assets_by_id.clear()
    graph.scenes_by_id.clear()
    graph.styles_by_id = dict(styles)
    all_loaded: list[LoadedAsset] = []
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]] = {}
    rendered_count = 0

    for asset_path in asset_files:
        loaded = load_asset_module(asset_path)
        all_loaded.append(loaded)
        graph.assets_by_id[loaded.SPEC.id] = loaded
        graph.asset_meta_by_path[asset_path] = (loaded.SPEC.id, loaded.SPEC.style_id)
        if asset_id is not None and loaded.SPEC.id != asset_id:
            continue
        compiled = compile_and_write_asset(
            asset_path,
            loaded,
            styles,
            options,
            out_dir,
            sheets_dir,
            None,
            sheet=sheet,
            update_manifest=asset_id is not None,
            err=err,
        )
        if compiled is None:
            return False
        _record_watch_bundle(graph, bundles_by_style, compiled[0], compiled[1])
        rendered_count += 1
        _emit_watch_render(loaded.SPEC.id, out_dir, graph.output_format, out)

    scene_result = _render_watch_full_scenes(
        root,
        graph,
        styles,
        bundles_by_style,
        options,
        out_dir,
        sheets_dir,
        asset_id=asset_id,
        sheet=sheet,
        out=out,
        err=err,
    )
    if scene_result is None:
        return False
    all_scenes, scene_count = scene_result
    graph.scenes_by_id = {scene.SCENE.id: scene for scene in all_scenes}

    if rendered_count + scene_count == 0:
        err(f"Asset {asset_id!r} not found under assets/")
        return False
    if asset_id is None:
        write_manifest(graph.manifests_by_id, out_dir)
    if indexed_ts:
        _emit_watch_full_indexed_ts(
            graph,
            bundles_by_style,
            all_loaded,
            all_scenes,
            options,
            out_dir,
            asset_id=asset_id,
            indexed_ts_lazy=indexed_ts_lazy,
        )

    graph.initial_render_done = True
    return True


def _emit_watch_incremental_indexed_ts(
    graph: WatchGraph,
    styles: dict[str, StylePack],
    affected_style_ids: set[str],
    out_dir: Path,
    *,
    indexed_ts_lazy: bool,
) -> None:
    active_styles = {b.manifest.styleId for b in graph.bundles_by_id.values()}
    multi_style = len(active_styles) > 1
    for sid in sorted(affected_style_ids):
        style = styles.get(sid)
        if style is None:
            continue
        style_bundles = [b for b in graph.bundles_by_id.values() if b.manifest.styleId == sid]
        if not style_bundles:
            continue
        ts_result = export_indexed_ts(style_bundles, style, lazy=indexed_ts_lazy)
        indexed_out = (
            out_dir / "indexed" / sid.replace("-", "_") if multi_style else out_dir / "indexed"
        )
        write_indexed_ts_bundle(ts_result, indexed_out)


def render_watch_incremental(
    root: Path,
    graph: WatchGraph,
    *,
    affected_asset_paths: set[Path],
    affected_scene_paths: set[Path],
    affected_style_ids: set[str],
    deleted_asset_ids: set[str],
    asset_id: str | None,
    out_dir: Path,
    sheets_dir: Path,
    sheet: bool,
    options: ExportBundleOptions,
    indexed_ts: bool,
    indexed_ts_lazy: bool,
    out: OutputFn,
    err: OutputFn,
) -> bool:
    try:
        styles = load_all_styles(root / "styles")
    except ValueError as exc:
        err(str(exc))
        return False

    graph.styles_by_id = dict(styles)
    for dead_id in deleted_asset_ids:
        graph.bundles_by_id.pop(dead_id, None)
        graph.manifests_by_id.pop(dead_id, None)
        graph.assets_by_id.pop(dead_id, None)
        graph.scenes_by_id.pop(dead_id, None)

    rendered_any = False
    for asset_path in sorted(affected_asset_paths):
        loaded = load_asset_module(asset_path)
        graph.assets_by_id[loaded.SPEC.id] = loaded
        if asset_id is not None and loaded.SPEC.id != asset_id:
            continue
        compiled = compile_and_write_asset(
            asset_path,
            loaded,
            styles,
            options,
            out_dir,
            sheets_dir,
            None,
            sheet=sheet,
            update_manifest=asset_id is not None,
            err=err,
        )
        if compiled is None:
            return False
        style, bundle = compiled
        graph.bundles_by_id[bundle.manifest.id] = bundle
        graph.manifests_by_id[bundle.manifest.id] = bundle.manifest
        affected_style_ids.add(style.id)
        rendered_any = True
        _emit_watch_render(loaded.SPEC.id, out_dir, graph.output_format, out)

    for scene_path in sorted(affected_scene_paths):
        if not scene_path.exists():
            continue
        loaded_scene = load_scene_module(scene_path)
        graph.scenes_by_id[loaded_scene.SCENE.id] = loaded_scene
        if asset_id is not None and loaded_scene.SCENE.id != asset_id:
            continue
        compiled = compile_and_write_scene(
            scene_path,
            loaded_scene,
            graph.assets_by_id,
            styles,
            options,
            out_dir,
            sheets_dir,
            out_dir,
            sheet=sheet,
            animate=False,
            update_manifest=asset_id is not None,
            err=err,
        )
        if compiled is None:
            return False
        style, bundle = compiled
        graph.bundles_by_id[bundle.manifest.id] = bundle
        graph.manifests_by_id[bundle.manifest.id] = bundle.manifest
        affected_style_ids.add(style.id)
        rendered_any = True
        _emit_watch_render(loaded_scene.SCENE.id, out_dir, graph.output_format, out)

    if asset_id is None and (rendered_any or deleted_asset_ids):
        write_manifest(graph.manifests_by_id, out_dir)
    if indexed_ts and affected_style_ids:
        _emit_watch_incremental_indexed_ts(
            graph,
            styles,
            affected_style_ids,
            out_dir,
            indexed_ts_lazy=indexed_ts_lazy,
        )
    return True
