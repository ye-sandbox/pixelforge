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
    render_asset_frames,
    write_export_bundle,
    write_manifest,
)
from pixelforge.export.contact_sheet import (
    ContactSheetOptions,
    generate_contact_sheet,
    generate_contact_sheet_from_frames,
)
from pixelforge.export.indexed_ts import export_indexed_ts, write_indexed_ts_bundle
from pixelforge.export.pack_sheet import (
    PackConsistencyMetrics,
    PackSheetEntry,
    PackSheetOptions,
    generate_pack_sheet,
)
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
    layers: bool = False,
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
            ContactSheetOptions(variant=options.variant, layers=layers),
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


def _resolve_filter_dir(root: Path, dir_filter: str | None) -> Path | None:
    if not dir_filter:
        return None
    candidate = Path(dir_filter)
    if candidate.is_absolute():
        return candidate.resolve()
    if candidate.parts and candidate.parts[0] == "assets":
        return (root / candidate).resolve()
    return (root / "assets" / candidate).resolve()


def _parse_ids_filter(ids_filter: str | None) -> set[str] | None:
    if not ids_filter:
        return None
    parsed = {part.strip() for part in ids_filter.split(",") if part.strip()}
    return parsed or None


def _matches_render_filters(
    source_path: Path,
    spec_id: str,
    style_id: str,
    *,
    asset_id: str | None,
    filter_dir: Path | None,
    pack_filter: str | None,
    ids_filter: set[str] | None,
) -> bool:
    if asset_id is not None and spec_id != asset_id:
        return False
    if ids_filter is not None and spec_id not in ids_filter:
        return False
    if pack_filter is not None and style_id != pack_filter:
        return False
    return filter_dir is None or source_path.resolve().is_relative_to(filter_dir)


def _render_asset_targets(
    asset_files: Sequence[Path],
    styles: dict[str, StylePack],
    options: ExportBundleOptions,
    out_dir: Path,
    sheets_dir: Path,
    previews_dir: Path | None,
    *,
    asset_id: str | None,
    filter_dir: Path | None,
    pack_filter: str | None,
    ids_filter: set[str] | None,
    filtered: bool,
    sheet: bool,
    layers: bool = False,
    pack_entries: list[PackSheetEntry] | None,
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
        if not _matches_render_filters(
            asset_path,
            loaded.SPEC.id,
            loaded.SPEC.style_id,
            asset_id=asset_id,
            filter_dir=filter_dir,
            pack_filter=pack_filter,
            ids_filter=ids_filter,
        ):
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
            layers=layers,
            update_manifest=filtered,
            err=err,
        )
        if compiled is None:
            return None
        style, bundle = compiled
        bundles_by_style.setdefault(style.id, (style, []))[1].append(bundle)
        if pack_entries is not None:
            primary_frame = render_asset_frames(loaded, style, variant=options.variant)[0]
            pack_entries.append(
                PackSheetEntry(
                    spec=loaded.SPEC,
                    style=style,
                    surface=primary_frame.surface,
                    source_path=asset_path,
                )
            )
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
    filter_dir: Path | None,
    pack_filter: str | None,
    ids_filter: set[str] | None,
    filtered: bool,
    sheet: bool,
    animate: bool,
    pack_entries: list[PackSheetEntry] | None,
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
        parent = loaded_by_id.get(loaded_scene.SCENE.parent_id)
        scene_style_id = loaded_scene.SCENE.style_id or (parent.SPEC.style_id if parent else "")
        if not _matches_render_filters(
            scene_path,
            loaded_scene.SCENE.id,
            scene_style_id,
            asset_id=asset_id,
            filter_dir=filter_dir,
            pack_filter=pack_filter,
            ids_filter=ids_filter,
        ):
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
            update_manifest=filtered,
            err=err,
        )
        if compiled is None:
            return None
        style, bundle = compiled
        bundles_by_style.setdefault(style.id, (style, []))[1].append(bundle)
        if pack_entries is not None and parent is not None:
            asset_spec, rendered_frames, _ = compose_scene_frames(
                loaded_scene.SCENE,
                parent,
                loaded_by_id,
                style,
                variant=options.variant,
            )
            pack_entries.append(
                PackSheetEntry(
                    spec=asset_spec,
                    style=style,
                    surface=rendered_frames[0].surface,
                    source_path=scene_path,
                )
            )
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
    filtered: bool,
    indexed_ts: bool,
    indexed_ts_lazy: bool,
) -> None:
    if not filtered:
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
            filtered=filtered,
            lazy=indexed_ts_lazy,
            all_scenes=all_scenes,
            loaded_by_id=loaded_by_id,
        )


def _pack_metrics_payload(metrics: PackConsistencyMetrics) -> dict[str, object]:
    return {
        "asset_count": metrics.asset_count,
        "style_ids": list(metrics.style_ids),
        "perspectives": list(metrics.perspectives),
        "lighting_angles": list(metrics.lighting_angles),
        "min_size": list(metrics.min_size),
        "max_size": list(metrics.max_size),
        "bbox_height_range": list(metrics.bbox_height_range),
        "luminance_range": list(metrics.luminance_range),
        "luminance_spread": metrics.luminance_spread,
        "light_bias_range": list(metrics.light_bias_range),
        "outline_coverage_range": list(metrics.outline_coverage_range),
        "outline_spread_pct": metrics.outline_spread_pct,
        "orphan_total": metrics.orphan_total,
        "scale_consistent": metrics.scale_consistent,
        "lighting_consistent": metrics.lighting_consistent,
        "outline_consistent": metrics.outline_consistent,
        "warnings": list(metrics.warnings),
    }


def _emit_render_summary(
    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]],
    *,
    out_dir: Path,
    indexed_ts: bool,
    pack_sheet_path: Path | None = None,
    pack_metrics: PackConsistencyMetrics | None = None,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    entries = [
        bundle.manifest
        for _, style_bundles in bundles_by_style.values()
        for bundle in style_bundles
    ]
    if output_format == "json":
        payload: dict[str, object] = {
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
        if pack_sheet_path is not None and pack_metrics is not None:
            payload["pack_sheet"] = str(pack_sheet_path)
            payload["pack_metrics"] = _pack_metrics_payload(pack_metrics)
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        for entry in entries:
            out(f"rendered {entry.id} -> {out_dir}")
        if pack_sheet_path is not None and pack_metrics is not None:
            out(f"pack_sheet {pack_sheet_path} ({pack_metrics.asset_count} assets)")
        return

    for entry in entries:
        states_csv = ",".join(entry.states)
        out(
            f"asset={entry.id} style={entry.styleId} size={entry.width}x{entry.height} "
            f"states={states_csv} frames={entry.frames} out={out_dir}"
        )
    if pack_sheet_path is not None and pack_metrics is not None:
        out(
            f"pack_sheet={pack_sheet_path} assets={pack_metrics.asset_count} "
            f"scale_ok={str(pack_metrics.scale_consistent).lower()} "
            f"lighting_ok={str(pack_metrics.lighting_consistent).lower()} "
            f"outline_ok={str(pack_metrics.outline_consistent).lower()} "
            f"lum_spread={pack_metrics.luminance_spread:.3f} "
            f"outline_spread={pack_metrics.outline_spread_pct:.1f}% "
            f"orphans={pack_metrics.orphan_total}"
        )
        if pack_metrics.warnings:
            out(f"pack_warnings={'; '.join(pack_metrics.warnings)}")
    ts_flag = " indexed_ts=true" if indexed_ts else ""
    out(
        f"summary rendered={len(entries)} out={out_dir} "
        f"manifest={out_dir / 'manifest.json'}{ts_flag}"
    )


def _resolve_pack_sheet_name(
    pack_filter: str | None,
    dir_filter: str | None,
) -> str:
    if pack_filter:
        return pack_filter
    if dir_filter:
        name = Path(dir_filter.rstrip("/")).name
        if name:
            return name
    return "pack"


def render_once(
    root: Path,
    *,
    asset_id: str | None,
    out_dir: Path,
    sheets_dir: Path,
    previews_dir: Path,
    sheet: bool,
    layers: bool = False,
    animate: bool,
    animate_format: Literal["gif", "apng"] = "gif",
    emissive: bool | None,
    lut: bool,
    normals: bool = False,
    height: bool = False,
    indexed_ts: bool,
    indexed_ts_lazy: bool = False,
    atlas: AtlasFormat | None = None,
    scale: int,
    variant: str | None,
    pack_sheet: bool = False,
    dir_filter: str | None = None,
    pack_filter: str | None = None,
    ids_filter: str | None = None,
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

    resolved_dir = _resolve_filter_dir(root, dir_filter)
    parsed_ids = _parse_ids_filter(ids_filter)
    filtered = any(val is not None for val in (asset_id, resolved_dir, pack_filter, parsed_ids))
    pack_entries: list[PackSheetEntry] | None = [] if pack_sheet else None

    options = ExportBundleOptions(
        variant=variant,
        scale=scale,
        emissive=emissive,
        lut=lut,
        normals=normals,
        height=height,
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
        filter_dir=resolved_dir,
        pack_filter=pack_filter,
        ids_filter=parsed_ids,
        filtered=filtered,
        sheet=sheet,
        layers=layers,
        pack_entries=pack_entries,
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
        filter_dir=resolved_dir,
        pack_filter=pack_filter,
        ids_filter=parsed_ids,
        filtered=filtered,
        sheet=sheet,
        animate=animate,
        pack_entries=pack_entries,
        err=err,
    )
    if scene_result is None:
        return 1
    all_scenes, scene_count = scene_result

    if asset_count + scene_count == 0:
        err("No matching assets found under assets/")
        return 1

    _finalize_render_outputs(
        bundles_by_style,
        all_loaded,
        all_scenes,
        loaded_by_id,
        options,
        out_dir,
        filtered=filtered,
        indexed_ts=indexed_ts,
        indexed_ts_lazy=indexed_ts_lazy,
    )

    pack_sheet_path: Path | None = None
    pack_metrics: PackConsistencyMetrics | None = None
    if pack_entries:
        sheets_dir.mkdir(parents=True, exist_ok=True)
        pack_name = _resolve_pack_sheet_name(pack_filter, dir_filter)
        pack_res = generate_pack_sheet(
            pack_entries,
            PackSheetOptions(variant=variant, title=f"PACK: {pack_name.upper()}"),
        )
        pack_sheet_path = sheets_dir / f"{pack_name}.contact.png"
        pack_sheet_path.write_bytes(pack_res.png)
        pack_metrics = pack_res.metrics

    _emit_render_summary(
        bundles_by_style,
        out_dir=out_dir,
        indexed_ts=indexed_ts,
        pack_sheet_path=pack_sheet_path,
        pack_metrics=pack_metrics,
        output_format=output_format,
        out=out,
    )
    return 0
