"""CLI workflow orchestration for `render`, `diff`, and `watch` commands."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import StylePack
from pixelforge.export.atlas import AtlasFormat
from pixelforge.export.bundle import (
    ExportBundleOptions,
    ExportBundleResult,
    ExportedAssetManifestEntry,
    LoadedAsset,
    export_asset_bundle,
    render_asset_frames,
    write_export_bundle,
    write_manifest,
)
from pixelforge.export.contact_sheet import ContactSheetOptions, generate_contact_sheet
from pixelforge.export.diff import generate_surface_diff
from pixelforge.export.indexed_ts import export_indexed_ts, write_indexed_ts_bundle
from pixelforge.export.png import surface_to_png
from pixelforge.export.scene import (
    SceneCompositionError,
    SceneCompositionSpec,
    SceneMountSpec,
    compose_scene,
    generate_scene_sheet,
)
from pixelforge.guard.critic import (
    CriticAssetInput,
    CriticConfig,
    CriticError,
    discover_changed_paths_from_git,
    score_assets_batch,
)
from pixelforge.guard.runner import (
    discover_asset_files,
    discover_style_files,
    load_all_styles,
    load_asset_from_git,
    load_asset_module,
    load_style_from_git,
    load_style_module,
    run_checks,
)

OutputFn = Callable[[str], None]


def compile_style_indexed_bundles(
    style: StylePack,
    rendered_bundles: list[ExportBundleResult],
    all_loaded: Sequence[LoadedAsset],
    options: ExportBundleOptions,
) -> list[ExportBundleResult]:
    """Return full `StylePack` asset bundles in discovery order for `--indexed-ts`."""
    # INVARIANT: `dist/indexed/` is a single-bundle TypeScript module per StylePack;
    # filtered `render`/`watch <asset_id>` must still include sibling assets of that style
    # so `sprites.generated.ts` and `manifest.generated.ts` are never silently truncated.
    by_id = {bundle.manifest.id: bundle for bundle in rendered_bundles}
    full_bundles: list[ExportBundleResult] = []
    for loaded in all_loaded:
        if loaded.SPEC.style_id != style.id:
            continue
        existing = by_id.get(loaded.SPEC.id)
        full_bundles.append(
            existing if existing is not None else export_asset_bundle(loaded, style, options)
        )
    return full_bundles


def _emit_indexed_ts_bundles(
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]],
    all_loaded: Sequence[LoadedAsset],
    options: ExportBundleOptions,
    out_dir: Path,
    *,
    filtered: bool,
    lazy: bool = False,
) -> None:
    multi_style = len(bundles_by_style) > 1
    for style, style_bundles in bundles_by_style.values():
        full_bundles = (
            compile_style_indexed_bundles(style, style_bundles, all_loaded, options)
            if filtered
            else style_bundles
        )
        ts_result = export_indexed_ts(full_bundles, style, lazy=lazy)
        indexed_out = (
            out_dir / "indexed" / style.id.replace("-", "_") if multi_style else out_dir / "indexed"
        )
        write_indexed_ts_bundle(ts_result, indexed_out)


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

    all_loaded: list[LoadedAsset] = []
    seen_asset_ids: dict[str, Path] = {}
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]] = {}
    rendered_count = 0

    for asset_path in asset_files:
        loaded = load_asset_module(asset_path)
        if loaded.SPEC.id in seen_asset_ids:
            err(
                f"{asset_path}:1 [duplicate-id] Duplicate asset ID {loaded.SPEC.id!r} "
                f"(already declared in {seen_asset_ids[loaded.SPEC.id]})"
            )
            return 1
        seen_asset_ids[loaded.SPEC.id] = asset_path
        all_loaded.append(loaded)
        if asset_id is not None and loaded.SPEC.id != asset_id:
            continue

        style = styles.get(loaded.SPEC.style_id)
        if style is None:
            err(
                f"{asset_path}:1 [missing-style] Referenced style "
                f"{loaded.SPEC.style_id!r} not found in styles/"
            )
            return 1

        bundle = export_asset_bundle(loaded, style, options)
        write_export_bundle(
            bundle,
            out_dir,
            previews_dir=previews_dir if animate else None,
            update_manifest=asset_id is not None,
        )
        if sheet:
            sheets_dir.mkdir(parents=True, exist_ok=True)
            contact = generate_contact_sheet(loaded, style, ContactSheetOptions(variant=variant))
            (sheets_dir / f"{loaded.SPEC.id}.contact.png").write_bytes(contact.png)

        if style.id not in bundles_by_style:
            bundles_by_style[style.id] = (style, [])
        bundles_by_style[style.id][1].append(bundle)
        rendered_count += 1
        out(f"rendered {loaded.SPEC.id} -> {out_dir}")

    if rendered_count == 0:
        err(f"Asset {asset_id!r} not found under assets/")
        return 1

    if asset_id is None:
        all_manifests: dict[str, ExportedAssetManifestEntry] = {
            bundle.manifest.id: bundle.manifest
            for _, style_bundles in bundles_by_style.values()
            for bundle in style_bundles
        }
        write_manifest(all_manifests, out_dir)

    if indexed_ts:
        _emit_indexed_ts_bundles(
            bundles_by_style,
            all_loaded,
            options,
            out_dir,
            filtered=asset_id is not None,
            lazy=indexed_ts_lazy,
        )

    return 0


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


def diff_asset(
    root: Path,
    *,
    asset_id: str,
    base_ref: str,
    out_dir: Path,
    scale: int,
    variant: str | None,
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Generate side-by-side + magenta pixel-diff PNGs against a git ref baseline."""
    styles: dict[str, StylePack] = {}
    style_paths: dict[str, Path] = {}
    for style_path in discover_style_files(root / "styles"):
        pack = load_style_module(style_path)
        styles[pack.id] = pack
        style_paths[pack.id] = style_path

    target_path: Path | None = None
    for candidate in discover_asset_files(root / "assets"):
        loaded = load_asset_module(candidate)
        if loaded.SPEC.id == asset_id:
            target_path = candidate
            break

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
    baseline_map = (
        {
            (f.state, f.frame): f.surface
            for f in render_asset_frames(baseline_asset, base_style, variant=variant)
        }
        if baseline_asset is not None
        else {}
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    for frame in current_frames:
        base_surface = baseline_map.get(
            (frame.state, frame.frame),
            IndexedSurface(frame.surface.width, frame.surface.height),
        )
        diff = generate_surface_diff(
            base_surface,
            frame.surface,
            style,
            variant=variant,
            scale=scale,
            baseline_style=base_style,
        )
        suffix = (
            f"{frame.state}.diff.png"
            if current_asset.SPEC.frames == 1
            else f"{frame.state}_f{frame.frame}.diff.png"
        )
        diff_path = out_dir / f"{current_asset.SPEC.id}_{suffix}"
        diff_path.write_bytes(diff.png)
        out(f"diff {diff_path}: {diff.changed_pixels}/{diff.total_pixels} changed pixel(s)")
    return 0


@dataclass
class _WatchGraph:
    """In-memory dependency graph and compiled bundle cache for incremental `watch`."""

    style_mtimes: dict[Path, int] = field(default_factory=dict[Path, int])
    asset_mtimes: dict[Path, int] = field(default_factory=dict[Path, int])
    style_ids_by_path: dict[Path, str] = field(default_factory=dict[Path, str])
    asset_meta_by_path: dict[Path, tuple[str, str]] = field(
        default_factory=dict[Path, tuple[str, str]]
    )
    bundles_by_id: dict[str, ExportBundleResult] = field(
        default_factory=dict[str, ExportBundleResult]
    )
    manifests_by_id: dict[str, ExportedAssetManifestEntry] = field(
        default_factory=dict[str, ExportedAssetManifestEntry]
    )
    initial_render_done: bool = False


def _snapshot_watch_mtimes(root: Path) -> tuple[dict[Path, int], dict[Path, int]]:
    style_mtimes = {
        p: p.stat().st_mtime_ns for p in discover_style_files(root / "styles") if p.exists()
    }
    asset_mtimes = {
        p: p.stat().st_mtime_ns for p in discover_asset_files(root / "assets") if p.exists()
    }
    return (style_mtimes, asset_mtimes)


def _seed_watch_graph_metadata(graph: _WatchGraph) -> None:
    for style_path in graph.style_mtimes:
        try:
            graph.style_ids_by_path[style_path] = load_style_module(style_path).id
        except ImportError, SyntaxError, TypeError, ValueError, OSError:
            graph.style_ids_by_path.pop(style_path, None)
    for asset_path in graph.asset_mtimes:
        try:
            spec = load_asset_module(asset_path).SPEC
            graph.asset_meta_by_path[asset_path] = (spec.id, spec.style_id)
        except ImportError, SyntaxError, TypeError, ValueError, OSError:
            graph.asset_meta_by_path.pop(asset_path, None)


def _diff_watch_graph(
    graph: _WatchGraph,
    cur_styles: dict[Path, int],
    cur_assets: dict[Path, int],
) -> tuple[set[Path], set[str], set[str]]:
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
    graph.style_mtimes = cur_styles
    graph.asset_mtimes = cur_assets

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

    affected_asset_paths: set[Path] = set()
    affected_style_ids: set[str] = set(changed_style_ids)
    deleted_asset_ids: set[str] = set()
    for asset_path in changed_assets:
        old_meta = graph.asset_meta_by_path.get(asset_path)
        if asset_path.exists():
            affected_asset_paths.add(asset_path)
            try:
                spec = load_asset_module(asset_path).SPEC
            except ImportError, SyntaxError, TypeError, ValueError, OSError:
                if old_meta is not None:
                    affected_style_ids.add(old_meta[1])
            else:
                graph.asset_meta_by_path[asset_path] = (spec.id, spec.style_id)
                affected_style_ids.add(spec.style_id)
                if old_meta is not None:
                    if old_meta[0] != spec.id:
                        deleted_asset_ids.add(old_meta[0])
                    if old_meta[1] != spec.style_id:
                        affected_style_ids.add(old_meta[1])
        else:
            graph.asset_meta_by_path.pop(asset_path, None)
            if old_meta is not None:
                deleted_asset_ids.add(old_meta[0])
                affected_style_ids.add(old_meta[1])

    # INVARIANT: Only `.style.py` edits invalidate sibling assets sharing that style;
    # single `.asset.py` edits only invalidate that asset (plus `--indexed-ts` for its style).
    for asset_path, (_, style_id) in graph.asset_meta_by_path.items():
        if style_id in changed_style_ids:
            affected_asset_paths.add(asset_path)

    return (affected_asset_paths, affected_style_ids, deleted_asset_ids)


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
    all_loaded: list[LoadedAsset] = []
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]] = {}
    rendered_count = 0

    for asset_path in asset_files:
        loaded = load_asset_module(asset_path)
        all_loaded.append(loaded)
        graph.asset_meta_by_path[asset_path] = (loaded.SPEC.id, loaded.SPEC.style_id)
        if asset_id is not None and loaded.SPEC.id != asset_id:
            continue

        style = styles.get(loaded.SPEC.style_id)
        if style is None:
            err(
                f"{asset_path}:1 [missing-style] Referenced style "
                f"{loaded.SPEC.style_id!r} not found in styles/"
            )
            return False

        bundle = export_asset_bundle(loaded, style, options)
        write_export_bundle(bundle, out_dir, update_manifest=asset_id is not None)
        if sheet:
            sheets_dir.mkdir(parents=True, exist_ok=True)
            contact = generate_contact_sheet(
                loaded,
                style,
                ContactSheetOptions(variant=options.variant),
            )
            (sheets_dir / f"{loaded.SPEC.id}.contact.png").write_bytes(contact.png)

        graph.bundles_by_id[bundle.manifest.id] = bundle
        graph.manifests_by_id[bundle.manifest.id] = bundle.manifest
        if style.id not in bundles_by_style:
            bundles_by_style[style.id] = (style, [])
        bundles_by_style[style.id][1].append(bundle)
        rendered_count += 1
        out(f"rendered {loaded.SPEC.id} -> {out_dir}")

    if rendered_count == 0:
        err(f"Asset {asset_id!r} not found under assets/")
        return False

    if asset_id is None:
        write_manifest(graph.manifests_by_id, out_dir)

    if indexed_ts:
        for style, style_bundles in bundles_by_style.values():
            full_bundles = (
                compile_style_indexed_bundles(style, style_bundles, all_loaded, options)
                if asset_id is not None
                else style_bundles
            )
            for b in full_bundles:
                graph.bundles_by_id[b.manifest.id] = b
        _emit_indexed_ts_bundles(
            bundles_by_style,
            all_loaded,
            options,
            out_dir,
            filtered=asset_id is not None,
            lazy=indexed_ts_lazy,
        )

    graph.initial_render_done = True
    return True


def _render_watch_incremental(
    root: Path,
    graph: _WatchGraph,
    *,
    affected_asset_paths: set[Path],
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

    rendered_any = False
    for asset_path in sorted(affected_asset_paths):
        loaded = load_asset_module(asset_path)
        if asset_id is not None and loaded.SPEC.id != asset_id:
            continue
        style = styles.get(loaded.SPEC.style_id)
        if style is None:
            err(
                f"{asset_path}:1 [missing-style] Referenced style "
                f"{loaded.SPEC.style_id!r} not found in styles/"
            )
            return False

        bundle = export_asset_bundle(loaded, style, options)
        write_export_bundle(bundle, out_dir, update_manifest=asset_id is not None)
        if sheet:
            sheets_dir.mkdir(parents=True, exist_ok=True)
            contact = generate_contact_sheet(
                loaded,
                style,
                ContactSheetOptions(variant=options.variant),
            )
            (sheets_dir / f"{loaded.SPEC.id}.contact.png").write_bytes(contact.png)

        graph.bundles_by_id[bundle.manifest.id] = bundle
        graph.manifests_by_id[bundle.manifest.id] = bundle.manifest
        affected_style_ids.add(style.id)
        rendered_any = True
        out(f"rendered {loaded.SPEC.id} -> {out_dir}")

    if asset_id is None and (rendered_any or deleted_asset_ids):
        write_manifest(graph.manifests_by_id, out_dir)

    if indexed_ts and affected_style_ids:
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

    return True


def _emit_check_violations(violations: Sequence[object], out: OutputFn, err: OutputFn) -> None:
    from pixelforge.guard.types import GuardViolation

    for v in violations:
        if isinstance(v, GuardViolation):
            (err if v.severity == "error" else out)(v.format_line())


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
    style_mtimes, asset_mtimes = _snapshot_watch_mtimes(root)
    graph = _WatchGraph(style_mtimes=style_mtimes, asset_mtimes=asset_mtimes)
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

    cycles = 0
    try:
        while max_cycles is None or cycles < max_cycles:
            time.sleep(interval)
            cycles += 1
            cur_styles, cur_assets = _snapshot_watch_mtimes(root)
            if cur_styles == graph.style_mtimes and cur_assets == graph.asset_mtimes:
                continue

            affected_paths, affected_styles, deleted_ids = _diff_watch_graph(
                graph,
                cur_styles,
                cur_assets,
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
                continue

            if asset_id is not None:
                target_paths = {
                    p
                    for p in affected_paths
                    if graph.asset_meta_by_path.get(p, (None, None))[0] == asset_id
                    or (p in cur_assets and graph.asset_meta_by_path.get(p) is None)
                }
                if not target_paths and asset_id not in deleted_ids:
                    continue
                affected_paths = target_paths

            if affected_paths:
                report = run_checks(root, asset_id=asset_id, asset_paths=affected_paths)
                _emit_check_violations(report.violations, out, err)
                if not report.passed:
                    continue

            _render_watch_incremental(
                root,
                graph,
                affected_asset_paths=affected_paths,
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
    except KeyboardInterrupt:
        out("watch stopped")
    return 0


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


def compose_scene_workflow(
    root: Path,
    *,
    parent_id: str,
    mounts: Sequence[SceneMountSpec],
    state: str | None,
    frame: int,
    variant: str | None,
    strict_bounds: bool,
    strict_perspective: bool = False,
    scale: int,
    out_dir: Path,
    sheets_dir: Path,
    sheet: bool,
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Compose child props onto a parent scene and emit PNG + optional `.contact.png`."""
    try:
        styles = load_all_styles(root / "styles")
    except ValueError as exc:
        err(str(exc))
        return 1

    asset_files = discover_asset_files(root / "assets")
    if not asset_files:
        err("No .asset.py files found under assets/")
        return 1

    loaded_by_id: dict[str, LoadedAsset] = {}
    for asset_path in asset_files:
        loaded = load_asset_module(asset_path)
        if loaded.SPEC.id in loaded_by_id:
            err(f"{asset_path}:1 [duplicate-id] Duplicate asset ID {loaded.SPEC.id!r}")
            return 1
        loaded_by_id[loaded.SPEC.id] = loaded

    parent = loaded_by_id.get(parent_id)
    if parent is None:
        err(f"Parent asset {parent_id!r} not found under assets/")
        return 1

    style = styles.get(parent.SPEC.style_id)
    if style is None:
        err(f"Style {parent.SPEC.style_id!r} for parent {parent_id!r} not found in styles/")
        return 1

    comp_spec = SceneCompositionSpec(
        parent_id=parent_id,
        parent_state=state,
        parent_frame=frame,
        mounts=tuple(mounts),
        variant=variant,
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
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{parent_id}_{result.parent_state}_composed.png"
    png_path.write_bytes(surface_to_png(result.surface, style, variant=variant, scale=scale))
    out(f"composed {png_path} ({len(result.placements)} prop(s))")

    for warning in result.warnings:
        out(f"warning: {warning}")

    if sheet:
        sheets_dir.mkdir(parents=True, exist_ok=True)
        sheet_result = generate_scene_sheet(result, style, variant=variant)
        sheet_path = sheets_dir / f"{parent_id}_composed.contact.png"
        sheet_path.write_bytes(sheet_result.png)
        out(f"sheet {sheet_path}")

    return 0


def _build_critic_inputs(
    root: Path,
    *,
    targets: Sequence[tuple[Path, LoadedAsset]],
    styles: dict[str, StylePack],
    style_paths: dict[str, Path],
    base_ref: str | None,
    variant: str | None,
) -> list[CriticAssetInput]:
    """Render contact sheets and optional baseline diffs for critic targets."""
    items: list[CriticAssetInput] = []
    for asset_path, current_asset in targets:
        style = styles[current_asset.SPEC.style_id]
        sheet_res = generate_contact_sheet(
            current_asset,
            style,
            ContactSheetOptions(variant=variant),
        )
        diff_png: bytes | None = None
        diff_changed: int | None = None
        if base_ref is not None:
            baseline_asset = load_asset_from_git(root, asset_path, ref=base_ref)
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
            primary = current_frames[0]
            baseline_map = (
                {
                    (f.state, f.frame): f.surface
                    for f in render_asset_frames(baseline_asset, base_style, variant=variant)
                }
                if baseline_asset is not None
                else {}
            )
            base_surface = baseline_map.get(
                (primary.state, primary.frame),
                IndexedSurface(primary.surface.width, primary.surface.height),
            )
            diff_res = generate_surface_diff(
                base_surface,
                primary.surface,
                style,
                variant=variant,
                scale=2,
                baseline_style=base_style,
            )
            diff_png = diff_res.png
            diff_changed = diff_res.changed_pixels

        items.append(
            CriticAssetInput(
                asset=current_asset,
                contact_sheet_png=sheet_res.png,
                diff_png=diff_png,
                diff_changed_pixels=diff_changed,
            )
        )
    return items


def critic_workflow(
    root: Path,
    *,
    asset_id: str | None,
    base_ref: str | None,
    variant: str | None,
    base_url: str,
    api_key: str,
    model: str,
    timeout_seconds: float,
    threshold: int,
    json_output: bool,
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Run multimodal visual regression scoring on target or git-changed assets."""
    styles: dict[str, StylePack] = {}
    style_paths: dict[str, Path] = {}
    for style_path in discover_style_files(root / "styles"):
        pack = load_style_module(style_path)
        styles[pack.id] = pack
        style_paths[pack.id] = style_path

    asset_files = discover_asset_files(root / "assets")
    if not asset_files:
        err("No .asset.py files found under assets/")
        return 1

    loaded_assets: list[tuple[Path, LoadedAsset]] = [
        (path, load_asset_module(path)) for path in asset_files
    ]
    if asset_id is not None:
        targets = [(p, a) for p, a in loaded_assets if a.SPEC.id == asset_id]
        if not targets:
            err(f"Asset {asset_id!r} not found under assets/")
            return 1
    elif base_ref is not None:
        try:
            changed_paths = discover_changed_paths_from_git(root, base_ref=base_ref)
        except CriticError as exc:
            err(str(exc))
            return 1
        changed_style_ids = {
            sid for sid, spath in style_paths.items() if spath.resolve() in changed_paths
        }
        targets = [
            (p, a)
            for p, a in loaded_assets
            if p.resolve() in changed_paths or a.SPEC.style_id in changed_style_ids
        ]
        if not targets:
            if json_output:
                out('{"verdicts": [], "passed": true, "threshold": ' + str(threshold) + "}")
            else:
                out(f"no changed assets or styles vs {base_ref}; skipping critic")
            return 0
    else:
        targets = loaded_assets

    for _, loaded in targets:
        if loaded.SPEC.style_id not in styles:
            err(
                f"Referenced style {loaded.SPEC.style_id!r} for {loaded.SPEC.id!r} "
                "not found in styles/"
            )
            return 1

    try:
        config = CriticConfig(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            threshold=threshold,
        )
    except ValueError as exc:
        err(str(exc))
        return 1

    items = _build_critic_inputs(
        root,
        targets=targets,
        styles=styles,
        style_paths=style_paths,
        base_ref=base_ref,
        variant=variant,
    )
    try:
        report = score_assets_batch(items, config)
    except CriticError as exc:
        err(str(exc))
        return 1

    if json_output:
        out(report.model_dump_json(indent=2))
    else:
        for verdict in report.verdicts:
            status = "PASS" if verdict.passed else "FAIL"
            out(f"critic {verdict.asset_id}: {verdict.score}/100 [{status}] — {verdict.summary}")
            for finding in verdict.findings:
                out(f"  - {finding}")
        out(
            f"critic summary: {len(report.verdicts)} asset(s), "
            f"avg {report.average_score}/100, threshold {report.threshold}"
        )
    return 0 if report.passed else 1
