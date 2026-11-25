"""CLI workflow orchestration for `render`, `diff`, and `watch` commands."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import StylePack
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
) -> None:
    multi_style = len(bundles_by_style) > 1
    for style, style_bundles in bundles_by_style.values():
        full_bundles = (
            compile_style_indexed_bundles(style, style_bundles, all_loaded, options)
            if filtered
            else style_bundles
        )
        ts_result = export_indexed_ts(full_bundles, style)
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


def _snapshot_mtimes(root: Path) -> dict[Path, int]:
    files = [*discover_style_files(root / "styles"), *discover_asset_files(root / "assets")]
    return {p: p.stat().st_mtime_ns for p in files if p.exists()}


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
    scale: int,
    variant: str | None,
    out: OutputFn,
    err: OutputFn,
    interval: float = 0.5,
    max_cycles: int | None = None,
) -> int:
    """Poll `.asset.py` and `.style.py` mtimes and re-check + re-render on changes."""
    last_mtimes = _snapshot_mtimes(root)
    report = run_checks(root, asset_id=asset_id)
    if report.passed:
        render_once(
            root,
            asset_id=asset_id,
            out_dir=out_dir,
            sheets_dir=sheets_dir,
            previews_dir=previews_dir,
            sheet=sheet,
            animate=False,
            emissive=emissive,
            lut=lut,
            indexed_ts=indexed_ts,
            scale=scale,
            variant=variant,
            out=out,
            err=err,
        )
    else:
        for v in report.violations:
            err(v.format_line())

    cycles = 0
    try:
        while max_cycles is None or cycles < max_cycles:
            time.sleep(interval)
            cycles += 1
            current_mtimes = _snapshot_mtimes(root)
            if current_mtimes == last_mtimes:
                continue
            last_mtimes = current_mtimes
            report = run_checks(root, asset_id=asset_id)
            for v in report.violations:
                (err if v.severity == "error" else out)(v.format_line())
            if report.passed:
                render_once(
                    root,
                    asset_id=asset_id,
                    out_dir=out_dir,
                    sheets_dir=sheets_dir,
                    previews_dir=previews_dir,
                    sheet=sheet,
                    animate=False,
                    emissive=emissive,
                    lut=lut,
                    indexed_ts=indexed_ts,
                    scale=scale,
                    variant=variant,
                    out=out,
                    err=err,
                )
    except KeyboardInterrupt:
        out("watch stopped")
    return 0
