"""CLI `critic` multimodal visual regression workflow."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pixelforge.cli.diff_cmd import load_styles_with_paths, resolve_baseline_style
from pixelforge.cli.render_cmd import OutputFn
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import StylePack
from pixelforge.export.bundle import LoadedAsset, render_asset_frames
from pixelforge.export.contact_sheet import ContactSheetOptions, generate_contact_sheet
from pixelforge.export.diff import generate_surface_diff
from pixelforge.guard.critic import (
    CriticAssetInput,
    CriticBatchReport,
    CriticConfig,
    CriticError,
    discover_changed_paths_from_git,
    score_assets_batch,
)
from pixelforge.guard.runner import discover_asset_files, load_asset_from_git, load_asset_module


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


def _select_critic_targets(
    root: Path,
    loaded_assets: list[tuple[Path, LoadedAsset]],
    style_paths: dict[str, Path],
    *,
    asset_id: str | None,
    base_ref: str | None,
    threshold: int,
    json_output: bool,
    out: OutputFn,
    err: OutputFn,
) -> list[tuple[Path, LoadedAsset]] | int:
    if asset_id is not None:
        targets = [(p, a) for p, a in loaded_assets if a.SPEC.id == asset_id]
        if not targets:
            err(f"Asset {asset_id!r} not found under assets/")
            return 1
        return targets

    if base_ref is None:
        return loaded_assets

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
    return targets


def _emit_critic_report(report: CriticBatchReport, *, json_output: bool, out: OutputFn) -> None:
    if json_output:
        out(report.model_dump_json(indent=2))
        return
    for verdict in report.verdicts:
        status = "PASS" if verdict.passed else "FAIL"
        out(f"critic {verdict.asset_id}: {verdict.score}/100 [{status}] — {verdict.summary}")
        for finding in verdict.findings:
            out(f"  - {finding}")
    out(
        f"critic summary: {len(report.verdicts)} asset(s), "
        f"avg {report.average_score}/100, threshold {report.threshold}"
    )


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
    styles, style_paths = load_styles_with_paths(root / "styles")
    asset_files = discover_asset_files(root / "assets")
    if not asset_files:
        err("No .asset.py files found under assets/")
        return 1

    loaded_assets = [(path, load_asset_module(path)) for path in asset_files]
    selected = _select_critic_targets(
        root,
        loaded_assets,
        style_paths,
        asset_id=asset_id,
        base_ref=base_ref,
        threshold=threshold,
        json_output=json_output,
        out=out,
        err=err,
    )
    if isinstance(selected, int):
        return selected

    for _, loaded in selected:
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
        targets=selected,
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

    _emit_critic_report(report, json_output=json_output, out=out)
    return 0 if report.passed else 1
