"""In-memory dependency graph and mtime diffing for incremental `watch`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pixelforge.cli.output import OutputFormat
from pixelforge.core.types import StylePack
from pixelforge.export.bundle import (
    ExportBundleResult,
    ExportedAssetManifestEntry,
    LoadedAsset,
)
from pixelforge.export.scene import LoadedScene
from pixelforge.guard.runner import (
    discover_asset_files,
    discover_scene_files,
    discover_style_files,
    load_asset_module,
    load_scene_module,
    load_style_module,
)


@dataclass
class WatchGraph:
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
    styles_by_id: dict[str, StylePack] = field(default_factory=dict[str, StylePack])
    scenes_by_id: dict[str, LoadedScene] = field(default_factory=dict[str, LoadedScene])
    bundles_by_id: dict[str, ExportBundleResult] = field(
        default_factory=dict[str, ExportBundleResult]
    )
    manifests_by_id: dict[str, ExportedAssetManifestEntry] = field(
        default_factory=dict[str, ExportedAssetManifestEntry]
    )
    initial_render_done: bool = False
    output_format: OutputFormat = "llm"


def snapshot_watch_mtimes(
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


def scene_deps(scene: LoadedScene) -> tuple[str, str | None, tuple[str, ...]]:
    deps = (scene.SCENE.parent_id, *(m.prop_id for m in scene.SCENE.mounts))
    return (scene.SCENE.id, scene.SCENE.style_id, deps)


def seed_watch_graph_metadata(graph: WatchGraph) -> None:
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
            graph.scene_meta_by_path[scene_path] = scene_deps(loaded_scene)
        except ImportError, SyntaxError, TypeError, ValueError, OSError:
            graph.scene_meta_by_path.pop(scene_path, None)


def _diff_style_mtimes(graph: WatchGraph, changed_styles: set[Path]) -> set[str]:
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
    graph: WatchGraph,
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
    graph: WatchGraph,
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

        graph.scene_meta_by_path[scene_path] = scene_deps(loaded_scene)
        if loaded_scene.SCENE.style_id is not None:
            affected_style_ids.add(loaded_scene.SCENE.style_id)
        if old_scene_meta is not None and old_scene_meta[0] != loaded_scene.SCENE.id:
            deleted_ids.add(old_scene_meta[0])
    return affected_scene_paths


def diff_watch_graph(
    graph: WatchGraph,
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
