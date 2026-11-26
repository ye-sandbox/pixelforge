"""CLI `watch` incremental rebuild loop and dependency graph."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pixelforge.cli.render_cmd import (
    OutputFn,
    compile_and_write_asset,
    compile_and_write_scene,
    compile_style_indexed_bundles,
    emit_indexed_ts_bundles,
)
from pixelforge.core.types import StylePack
from pixelforge.export.atlas import AtlasFormat
from pixelforge.export.bundle import (
    ExportBundleOptions,
    ExportBundleResult,
    ExportedAssetManifestEntry,
    LoadedAsset,
    write_manifest,
)
from pixelforge.export.indexed_ts import export_indexed_ts, write_indexed_ts_bundle
from pixelforge.export.scene import LoadedScene
from pixelforge.guard.runner import (
    discover_asset_files,
    discover_scene_files,
    discover_style_files,
    load_all_styles,
    load_asset_module,
    load_scene_module,
    load_style_module,
    run_checks,
)


@dataclass
class _WatchGraph:
    """In-memory dependency graph and compiled bundle cache for incremental `watch`."""

    style_mtimes: dict[Path, int] = field(default_factory=dict[Path, int])
    asset_mtimes: dict[Path, int] = field(default_factory=dict[Path, int])
    scene_mtimes: dict[Path, int] = field(default_factory=dict[Path, int])
    style_ids_by_path: dict[Path, str] = field(default_factory=dict[Path, str])
    asset_meta_by_path: dict[Path, tuple[str, str]] = field(
        default_factory=dict[Path, tuple[str, str]]
    )
    scene_meta_by_path: dict[Path, tuple[str, str | None, tuple[str, ...]]] = field(
        default_factory=dict[Path, tuple[str, str | None, tuple[str, ...]]]
    )
    assets_by_id: dict[str, LoadedAsset] = field(default_factory=dict[str, LoadedAsset])
    bundles_by_id: dict[str, ExportBundleResult] = field(
        default_factory=dict[str, ExportBundleResult]
    )
    manifests_by_id: dict[str, ExportedAssetManifestEntry] = field(
        default_factory=dict[str, ExportedAssetManifestEntry]
    )
    initial_render_done: bool = False


def _snapshot_watch_mtimes(
    root: Path,
) -> tuple[dict[Path, int], dict[Path, int], dict[Path, int]]:
    style_mtimes = {
        p: p.stat().st_mtime_ns for p in discover_style_files(root / "styles") if p.exists()
    }
    asset_mtimes = {
        p: p.stat().st_mtime_ns for p in discover_asset_files(root / "assets") if p.exists()
    }
    scene_mtimes = {
        p: p.stat().st_mtime_ns for p in discover_scene_files(root / "assets") if p.exists()
    }
    return (style_mtimes, asset_mtimes, scene_mtimes)


def _scene_deps(scene: LoadedScene) -> tuple[str, str | None, tuple[str, ...]]:
    deps = (scene.SCENE.parent_id, *(m.prop_id for m in scene.SCENE.mounts))
    return (scene.SCENE.id, scene.SCENE.style_id, deps)


def _seed_watch_graph_metadata(graph: _WatchGraph) -> None:
    for style_path in graph.style_mtimes:
        try:
            graph.style_ids_by_path[style_path] = load_style_module(style_path).id
        except ImportError, SyntaxError, TypeError, ValueError, OSError:
            graph.style_ids_by_path.pop(style_path, None)
    for asset_path in graph.asset_mtimes:
        try:
            loaded = load_asset_module(asset_path)
            graph.asset_meta_by_path[asset_path] = (loaded.SPEC.id, loaded.SPEC.style_id)
            graph.assets_by_id[loaded.SPEC.id] = loaded
        except ImportError, SyntaxError, TypeError, ValueError, OSError:
            graph.asset_meta_by_path.pop(asset_path, None)
    for scene_path in graph.scene_mtimes:
        try:
            loaded_scene = load_scene_module(scene_path)
            graph.scene_meta_by_path[scene_path] = _scene_deps(loaded_scene)
        except ImportError, SyntaxError, TypeError, ValueError, OSError:
            graph.scene_meta_by_path.pop(scene_path, None)


def _diff_style_mtimes(graph: _WatchGraph, changed_styles: set[Path]) -> set[str]:
    changed_style_ids: set[str] = set()
    for style_path in changed_styles:
        if style_path in graph.style_ids_by_path:
            changed_style_ids.add(graph.style_ids_by_path[style_path])
        if style_path.exists():
            try:
                pack = load_style_module(style_path)
            except ImportError, SyntaxError, TypeError, ValueError, OSError:
                graph.style_ids_by_path.pop(style_path, None)
            else:
                graph.style_ids_by_path[style_path] = pack.id
                changed_style_ids.add(pack.id)
        else:
            graph.style_ids_by_path.pop(style_path, None)
    return changed_style_ids


def _diff_asset_mtimes(
    graph: _WatchGraph,
    changed_assets: set[Path],
    affected_style_ids: set[str],
    deleted_ids: set[str],
) -> tuple[set[Path], set[str]]:
    affected_asset_paths: set[Path] = set()
    changed_asset_ids: set[str] = set()
    for asset_path in changed_assets:
        old_meta = graph.asset_meta_by_path.get(asset_path)
        if not asset_path.exists():
            graph.asset_meta_by_path.pop(asset_path, None)
            if old_meta is not None:
                deleted_ids.add(old_meta[0])
                changed_asset_ids.add(old_meta[0])
                graph.assets_by_id.pop(old_meta[0], None)
                affected_style_ids.add(old_meta[1])
            continue

        affected_asset_paths.add(asset_path)
        try:
            loaded = load_asset_module(asset_path)
        except ImportError, SyntaxError, TypeError, ValueError, OSError:
            if old_meta is not None:
                affected_style_ids.add(old_meta[1])
                changed_asset_ids.add(old_meta[0])
            continue

        graph.asset_meta_by_path[asset_path] = (loaded.SPEC.id, loaded.SPEC.style_id)
        graph.assets_by_id[loaded.SPEC.id] = loaded
        affected_style_ids.add(loaded.SPEC.style_id)
        changed_asset_ids.add(loaded.SPEC.id)
        if old_meta is not None:
            changed_asset_ids.add(old_meta[0])
            if old_meta[0] != loaded.SPEC.id:
                deleted_ids.add(old_meta[0])
                graph.assets_by_id.pop(old_meta[0], None)
            if old_meta[1] != loaded.SPEC.style_id:
                affected_style_ids.add(old_meta[1])
    return (affected_asset_paths, changed_asset_ids)


def _diff_scene_mtimes(
    graph: _WatchGraph,
    changed_scenes: set[Path],
    affected_style_ids: set[str],
    deleted_ids: set[str],
) -> set[Path]:
    affected_scene_paths: set[Path] = set()
    for scene_path in changed_scenes:
        old_scene_meta = graph.scene_meta_by_path.get(scene_path)
        if not scene_path.exists():
            graph.scene_meta_by_path.pop(scene_path, None)
            if old_scene_meta is not None:
                deleted_ids.add(old_scene_meta[0])
            continue

        affected_scene_paths.add(scene_path)
        try:
            loaded_scene = load_scene_module(scene_path)
        except ImportError, SyntaxError, TypeError, ValueError, OSError:
            if old_scene_meta is not None and old_scene_meta[1] is not None:
                affected_style_ids.add(old_scene_meta[1])
            continue

        graph.scene_meta_by_path[scene_path] = _scene_deps(loaded_scene)
        if loaded_scene.SCENE.style_id is not None:
            affected_style_ids.add(loaded_scene.SCENE.style_id)
        if old_scene_meta is not None and old_scene_meta[0] != loaded_scene.SCENE.id:
            deleted_ids.add(old_scene_meta[0])
    return affected_scene_paths


def _diff_watch_graph(
    graph: _WatchGraph,
    cur_styles: dict[Path, int],
    cur_assets: dict[Path, int],
    cur_scenes: dict[Path, int],
) -> tuple[set[Path], set[Path], set[str], set[str]]:
    changed_styles = {
        p
        for p in set(cur_styles) | set(graph.style_mtimes)
        if cur_styles.get(p) != graph.style_mtimes.get(p)
    }
    changed_assets = {
        p
        for p in set(cur_assets) | set(graph.asset_mtimes)
        if cur_assets.get(p) != graph.asset_mtimes.get(p)
    }
    changed_scenes = {
        p
        for p in set(cur_scenes) | set(graph.scene_mtimes)
        if cur_scenes.get(p) != graph.scene_mtimes.get(p)
    }
    graph.style_mtimes = cur_styles
    graph.asset_mtimes = cur_assets
    graph.scene_mtimes = cur_scenes

    changed_style_ids = _diff_style_mtimes(graph, changed_styles)
    affected_style_ids: set[str] = set(changed_style_ids)
    deleted_ids: set[str] = set()

    affected_asset_paths, changed_asset_ids = _diff_asset_mtimes(
        graph, changed_assets, affected_style_ids, deleted_ids
    )
    affected_scene_paths = _diff_scene_mtimes(
        graph, changed_scenes, affected_style_ids, deleted_ids
    )

    # INVARIANT: Only `.style.py` edits invalidate sibling assets sharing that style;
    # single `.asset.py` edits only invalidate that asset, dependent scenes, and `--indexed-ts`.
    for asset_path, (aid, style_id) in graph.asset_meta_by_path.items():
        if style_id in changed_style_ids:
            affected_asset_paths.add(asset_path)
            changed_asset_ids.add(aid)

    for scene_path, (_, scene_style_id, deps) in graph.scene_meta_by_path.items():
        parent_style = (
            graph.assets_by_id[deps[0]].SPEC.style_id
            if deps and deps[0] in graph.assets_by_id
            else scene_style_id
        )
        if (parent_style in changed_style_ids) or any(d in changed_asset_ids for d in deps):
            affected_scene_paths.add(scene_path)

    return (affected_asset_paths, affected_scene_paths, affected_style_ids, deleted_ids)


def _emit_watch_full_indexed_ts(
    graph: _WatchGraph,
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
    graph: _WatchGraph,
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]],
    style: StylePack,
    bundle: ExportBundleResult,
) -> None:
    graph.bundles_by_id[bundle.manifest.id] = bundle
    graph.manifests_by_id[bundle.manifest.id] = bundle.manifest
    bundles_by_style.setdefault(style.id, (style, []))[1].append(bundle)


def _render_watch_full_scenes(
    root: Path,
    graph: _WatchGraph,
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
        graph.scene_meta_by_path[scene_path] = _scene_deps(loaded_scene)
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
        out(f"rendered {loaded_scene.SCENE.id} -> {out_dir}")
    return (all_scenes, rendered_count)


def _render_watch_full(
    root: Path,
    graph: _WatchGraph,
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
        out(f"rendered {loaded.SPEC.id} -> {out_dir}")

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
    graph: _WatchGraph,
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


def _render_watch_incremental(
    root: Path,
    graph: _WatchGraph,
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

    for dead_id in deleted_asset_ids:
        graph.bundles_by_id.pop(dead_id, None)
        graph.manifests_by_id.pop(dead_id, None)
        graph.assets_by_id.pop(dead_id, None)

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
        out(f"rendered {loaded.SPEC.id} -> {out_dir}")

    for scene_path in sorted(affected_scene_paths):
        if not scene_path.exists():
            continue
        loaded_scene = load_scene_module(scene_path)
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
        out(f"rendered {loaded_scene.SCENE.id} -> {out_dir}")

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


def _emit_check_violations(violations: Sequence[object], out: OutputFn, err: OutputFn) -> None:
    from pixelforge.guard.types import GuardViolation

    for v in violations:
        if isinstance(v, GuardViolation):
            (err if v.severity == "error" else out)(v.format_line())


def _filter_watch_targets_for_asset(
    asset_id: str,
    affected_paths: set[Path],
    affected_scene_paths: set[Path],
    cur_assets: dict[Path, int],
    cur_scenes: dict[Path, int],
    deleted_ids: set[str],
    graph: _WatchGraph,
) -> tuple[set[Path], set[Path]] | None:
    target_paths = {
        p
        for p in affected_paths
        if graph.asset_meta_by_path.get(p, (None, None))[0] == asset_id
        or (p in cur_assets and graph.asset_meta_by_path.get(p) is None)
    }
    target_scenes = {
        p
        for p in affected_scene_paths
        if graph.scene_meta_by_path.get(p, (None, None, ()))[0] == asset_id
        or (p in cur_scenes and graph.scene_meta_by_path.get(p) is None)
    }
    if not target_paths and not target_scenes and asset_id not in deleted_ids:
        return None
    return (target_paths, target_scenes)


def _process_watch_change(
    root: Path,
    graph: _WatchGraph,
    cur_styles: dict[Path, int],
    cur_assets: dict[Path, int],
    cur_scenes: dict[Path, int],
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
) -> None:
    affected_paths, affected_scene_paths, affected_styles, deleted_ids = _diff_watch_graph(
        graph, cur_styles, cur_assets, cur_scenes
    )
    if not graph.initial_render_done:
        report = run_checks(root, asset_id=asset_id)
        _emit_check_violations(report.violations, out, err)
        if report.passed:
            _render_watch_full(
                root,
                graph,
                asset_id=asset_id,
                out_dir=out_dir,
                sheets_dir=sheets_dir,
                sheet=sheet,
                options=options,
                indexed_ts=indexed_ts,
                indexed_ts_lazy=indexed_ts_lazy,
                out=out,
                err=err,
            )
        return

    if asset_id is not None:
        filtered = _filter_watch_targets_for_asset(
            asset_id,
            affected_paths,
            affected_scene_paths,
            cur_assets,
            cur_scenes,
            deleted_ids,
            graph,
        )
        if filtered is None:
            return
        affected_paths, affected_scene_paths = filtered

    check_paths = affected_paths | affected_scene_paths
    if check_paths:
        report = run_checks(root, asset_id=asset_id, asset_paths=check_paths)
        _emit_check_violations(report.violations, out, err)
        if not report.passed:
            return

    _render_watch_incremental(
        root,
        graph,
        affected_asset_paths=affected_paths,
        affected_scene_paths=affected_scene_paths,
        affected_style_ids=affected_styles,
        deleted_asset_ids=deleted_ids,
        asset_id=asset_id,
        out_dir=out_dir,
        sheets_dir=sheets_dir,
        sheet=sheet,
        options=options,
        indexed_ts=indexed_ts,
        indexed_ts_lazy=indexed_ts_lazy,
        out=out,
        err=err,
    )


def _init_watch_session(
    root: Path,
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
) -> _WatchGraph:
    style_mtimes, asset_mtimes, scene_mtimes = _snapshot_watch_mtimes(root)
    graph = _WatchGraph(
        style_mtimes=style_mtimes,
        asset_mtimes=asset_mtimes,
        scene_mtimes=scene_mtimes,
    )
    _seed_watch_graph_metadata(graph)
    report = run_checks(root, asset_id=asset_id)
    if report.passed:
        _render_watch_full(
            root,
            graph,
            asset_id=asset_id,
            out_dir=out_dir,
            sheets_dir=sheets_dir,
            sheet=sheet,
            options=options,
            indexed_ts=indexed_ts,
            indexed_ts_lazy=indexed_ts_lazy,
            out=out,
            err=err,
        )
    else:
        _emit_check_violations(report.violations, out, err)
    return graph


def watch_loop(
    root: Path,
    *,
    asset_id: str | None,
    out_dir: Path,
    sheets_dir: Path,
    previews_dir: Path,
    sheet: bool,
    emissive: bool | None,
    lut: bool,
    indexed_ts: bool,
    indexed_ts_lazy: bool = False,
    atlas: AtlasFormat | None = None,
    scale: int,
    variant: str | None,
    out: OutputFn,
    err: OutputFn,
    interval: float = 0.5,
    max_cycles: int | None = None,
) -> int:
    """Poll `.asset.py` and `.style.py` mtimes and incrementally rebuild affected assets."""
    _ = previews_dir
    options = ExportBundleOptions(
        variant=variant,
        scale=scale,
        emissive=emissive,
        lut=lut,
        animate=False,
        atlas=atlas,
    )
    graph = _init_watch_session(
        root,
        asset_id=asset_id,
        out_dir=out_dir,
        sheets_dir=sheets_dir,
        sheet=sheet,
        options=options,
        indexed_ts=indexed_ts,
        indexed_ts_lazy=indexed_ts_lazy,
        out=out,
        err=err,
    )

    cycles = 0
    try:
        while max_cycles is None or cycles < max_cycles:
            time.sleep(interval)
            cycles += 1
            cur_styles, cur_assets, cur_scenes = _snapshot_watch_mtimes(root)
            if (
                cur_styles == graph.style_mtimes
                and cur_assets == graph.asset_mtimes
                and cur_scenes == graph.scene_mtimes
            ):
                continue
            _process_watch_change(
                root,
                graph,
                cur_styles,
                cur_assets,
                cur_scenes,
                asset_id=asset_id,
                out_dir=out_dir,
                sheets_dir=sheets_dir,
                sheet=sheet,
                options=options,
                indexed_ts=indexed_ts,
                indexed_ts_lazy=indexed_ts_lazy,
                out=out,
                err=err,
            )
    except KeyboardInterrupt:
        out("watch stopped")
    return 0
