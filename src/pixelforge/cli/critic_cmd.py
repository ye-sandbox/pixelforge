"""CLI `critic` multimodal visual regression workflow."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from pixelforge.cli.diff_cmd import load_styles_with_paths, resolve_baseline_style
from pixelforge.cli.output import OutputFn, OutputFormat
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import StylePack
from pixelforge.export.bundle import LoadedAsset, render_asset_frames
from pixelforge.export.contact_sheet import ContactSheetOptions, generate_contact_sheet
from pixelforge.export.diff import generate_surface_diff
from pixelforge.export.scene import (
    LoadedScene,
    SceneCompositionError,
    compose_scene_results,
    generate_scene_sheet,
)
from pixelforge.guard.critic import (
    CriticAssetInput,
    CriticBatchReport,
    CriticCategory,
    CriticConfig,
    CriticError,
    discover_changed_paths_from_git,
    format_critic_markdown,
    infer_critic_category,
    score_assets_batch,
)
from pixelforge.guard.runner import (
    discover_asset_files,
    discover_scene_files,
    load_asset_from_git,
    load_asset_module,
    load_scene_from_git,
    load_scene_module,
)


def _write_summary_md(
    summary_md: Path | None,
    report: CriticBatchReport,
    *,
    base_ref: str | None,
) -> None:
    if summary_md is None:
        return
    summary_md.parent.mkdir(parents=True, exist_ok=True)
    summary_md.write_text(
        format_critic_markdown(report, base_ref=base_ref),
        encoding="utf-8",
    )


def _build_asset_critic_input(
    root: Path,
    *,
    asset_path: Path,
    current_asset: LoadedAsset,
    styles: dict[str, StylePack],
    style_paths: dict[str, Path],
    base_ref: str | None,
    variant: str | None,
    category: CriticCategory | None = None,
) -> CriticAssetInput:
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

    resolved_category = category or infer_critic_category(
        current_asset.SPEC,
        kind="asset",
        asset_path=asset_path,
    )
    return CriticAssetInput(
        asset=current_asset,
        contact_sheet_png=sheet_res.png,
        diff_png=diff_png,
        diff_changed_pixels=diff_changed,
        category=resolved_category,
    )


def _compose_baseline_scene_surface(
    root: Path,
    *,
    scene_path: Path,
    asset_paths_by_id: Mapping[str, Path],
    current_style: StylePack,
    styles: dict[str, StylePack],
    style_paths: dict[str, Path],
    base_ref: str,
    variant: str | None,
    target_state: str,
    target_frame: int,
    fallback_size: tuple[int, int],
) -> tuple[IndexedSurface, StylePack]:
    empty = IndexedSurface(fallback_size[0], fallback_size[1])
    baseline_scene = load_scene_from_git(root, scene_path, ref=base_ref)
    if baseline_scene is None:
        return (empty, current_style)

    parent_path = asset_paths_by_id.get(baseline_scene.SCENE.parent_id)
    if parent_path is None:
        return (empty, current_style)
    baseline_parent = load_asset_from_git(root, parent_path, ref=base_ref)
    if baseline_parent is None:
        return (empty, current_style)

    baseline_props: dict[str, LoadedAsset] = {baseline_parent.SPEC.id: baseline_parent}
    for mount in baseline_scene.SCENE.mounts:
        if mount.prop_id in baseline_props:
            continue
        prop_path = asset_paths_by_id.get(mount.prop_id)
        if prop_path is None:
            return (empty, current_style)
        loaded_prop = load_asset_from_git(root, prop_path, ref=base_ref)
        if loaded_prop is None:
            return (empty, current_style)
        baseline_props[mount.prop_id] = loaded_prop

    base_style = resolve_baseline_style(
        root,
        baseline_asset=baseline_parent,
        current_style=current_style,
        styles=styles,
        style_paths=style_paths,
        base_ref=base_ref,
        variant=variant,
    )
    try:
        _, base_results, _ = compose_scene_results(
            baseline_scene.SCENE,
            baseline_parent,
            baseline_props,
            base_style,
            variant=variant,
        )
    except SceneCompositionError:
        return (empty, base_style)

    for res in base_results:
        if res.parent_state == target_state and res.parent_frame == target_frame:
            return (res.surface, base_style)
    return (empty, base_style)


def _build_scene_critic_input(
    root: Path,
    *,
    scene_path: Path,
    current_scene: LoadedScene,
    assets_by_id: Mapping[str, LoadedAsset],
    asset_paths_by_id: Mapping[str, Path],
    styles: dict[str, StylePack],
    style_paths: dict[str, Path],
    base_ref: str | None,
    variant: str | None,
    category: CriticCategory | None = None,
) -> CriticAssetInput:
    scene_spec = current_scene.SCENE
    parent = assets_by_id[scene_spec.parent_id]
    style_id = scene_spec.style_id or parent.SPEC.style_id
    style = styles[style_id]
    resolved_spec, results, warnings = compose_scene_results(
        scene_spec,
        parent,
        assets_by_id,
        style,
        variant=variant,
    )
    primary = results[0]
    sheet_res = generate_scene_sheet(primary, style, variant=variant)

    diff_png: bytes | None = None
    diff_changed: int | None = None
    if base_ref is not None:
        base_surface, base_style = _compose_baseline_scene_surface(
            root,
            scene_path=scene_path,
            asset_paths_by_id=asset_paths_by_id,
            current_style=style,
            styles=styles,
            style_paths=style_paths,
            base_ref=base_ref,
            variant=variant,
            target_state=primary.parent_state,
            target_frame=primary.parent_frame,
            fallback_size=(primary.surface.width, primary.surface.height),
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

    mount_names = ", ".join(f"{m.prop_id}@{m.anchor}" for m in scene_spec.mounts) or "none"
    scene_context: list[str] = [
        f"Parent ID: {scene_spec.parent_id}",
        f"Mounts ({len(scene_spec.mounts)}): {mount_names}",
    ]
    if warnings:
        scene_context.append(f"Scene Warnings: {'; '.join(warnings)}")

    return CriticAssetInput(
        spec=resolved_spec,
        kind="scene",
        category=category or "scene",
        contact_sheet_png=sheet_res.png,
        diff_png=diff_png,
        diff_changed_pixels=diff_changed,
        scene_context=tuple(scene_context),
    )


def _select_critic_targets(
    root: Path,
    loaded_assets: list[tuple[Path, LoadedAsset]],
    loaded_scenes: list[tuple[Path, LoadedScene]],
    assets_by_id: Mapping[str, LoadedAsset],
    style_paths: dict[str, Path],
    *,
    asset_id: str | None,
    base_ref: str | None,
    threshold: int,
    summary_md: Path | None,
    output_format: OutputFormat,
    out: OutputFn,
    err: OutputFn,
) -> tuple[list[tuple[Path, LoadedAsset]], list[tuple[Path, LoadedScene]]] | int:
    if asset_id is not None:
        asset_targets = [(p, a) for p, a in loaded_assets if a.SPEC.id == asset_id]
        scene_targets = [(p, s) for p, s in loaded_scenes if s.SCENE.id == asset_id]
        if not asset_targets and not scene_targets:
            err(f"Asset or scene {asset_id!r} not found under assets/")
            return 1
        return (asset_targets, scene_targets)

    if base_ref is None:
        return (loaded_assets, loaded_scenes)

    try:
        changed_paths = discover_changed_paths_from_git(root, base_ref=base_ref)
    except CriticError as exc:
        err(str(exc))
        return 1

    changed_style_ids = {
        sid for sid, spath in style_paths.items() if spath.resolve() in changed_paths
    }
    asset_targets = [
        (p, a)
        for p, a in loaded_assets
        if p.resolve() in changed_paths or a.SPEC.style_id in changed_style_ids
    ]
    changed_asset_ids = {a.SPEC.id for _, a in asset_targets}

    scene_targets: list[tuple[Path, LoadedScene]] = []
    for scene_path, loaded_scene in loaded_scenes:
        spec = loaded_scene.SCENE
        parent = assets_by_id.get(spec.parent_id)
        scene_style_id = spec.style_id or (parent.SPEC.style_id if parent is not None else None)
        dep_ids = {spec.parent_id, *(m.prop_id for m in spec.mounts)}
        if (
            scene_path.resolve() in changed_paths
            or scene_style_id in changed_style_ids
            or bool(dep_ids & changed_asset_ids)
        ):
            scene_targets.append((scene_path, loaded_scene))

    if not asset_targets and not scene_targets:
        empty_report = CriticBatchReport(
            verdicts=[],
            passed=True,
            threshold=threshold,
            average_score=100.0,
        )
        _write_summary_md(summary_md, empty_report, base_ref=base_ref)
        if output_format == "json":
            out('{"verdicts": [], "passed": true, "threshold": ' + str(threshold) + "}")
        elif output_format == "human":
            out(f"no changed assets, styles, or scenes vs {base_ref}; skipping critic")
        else:
            out(f"status=skip reason=no_changes base={base_ref} threshold={threshold} passed=true")
        return 0
    return (asset_targets, scene_targets)


def _emit_critic_report(
    report: CriticBatchReport,
    *,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    if output_format == "json":
        out(report.model_dump_json(indent=2))
        return
    if output_format == "human":
        for verdict in report.verdicts:
            status = "PASS" if verdict.passed else "FAIL"
            out(
                f"critic [{verdict.kind}/{verdict.category}] {verdict.asset_id}: "
                f"{verdict.score}/100 [{status}] — {verdict.summary}"
            )
            if verdict.criteria is not None:
                c = verdict.criteria
                out(
                    f"  rubric: sil={c.silhouette_1x}/20 lit={c.lighting_consistency}/20 "
                    f"clu={c.cluster_cleanliness}/20 leg={c.state_frame_legibility}/20 "
                    f"anc={c.anchors_and_palette}/20"
                )
            for finding in verdict.findings:
                out(f"  - {finding}")
            for fix in verdict.fixes:
                out(f"  * fix: {fix}")
        out(
            f"critic summary: {len(report.verdicts)} target(s), "
            f"avg {report.average_score}/100, threshold {report.threshold}"
        )
        return
    for verdict in report.verdicts:
        status = "PASS" if verdict.passed else "FAIL"
        rubric_part = ""
        if verdict.criteria is not None:
            c = verdict.criteria
            rubric_part = (
                f" criteria=sil:{c.silhouette_1x},lit:{c.lighting_consistency},"
                f"clu:{c.cluster_cleanliness},leg:{c.state_frame_legibility},"
                f"anc:{c.anchors_and_palette}"
            )
        out(
            f"critic kind={verdict.kind} category={verdict.category} asset={verdict.asset_id} "
            f"score={verdict.score}/100 status={status}{rubric_part} summary={verdict.summary}"
        )
        for finding in verdict.findings:
            out(f"finding asset={verdict.asset_id} detail={finding}")
        for fix in verdict.fixes:
            out(f"fix asset={verdict.asset_id} detail={fix}")
    out(
        f"summary count={len(report.verdicts)} avg={report.average_score}/100 "
        f"threshold={report.threshold} passed={str(report.passed).lower()}"
    )


def _validate_target_dependencies(
    asset_targets: Sequence[tuple[Path, LoadedAsset]],
    scene_targets: Sequence[tuple[Path, LoadedScene]],
    assets_by_id: Mapping[str, LoadedAsset],
    styles: Mapping[str, StylePack],
    err: OutputFn,
) -> bool:
    for _, loaded in asset_targets:
        if loaded.SPEC.style_id not in styles:
            err(
                f"Referenced style {loaded.SPEC.style_id!r} for {loaded.SPEC.id!r} "
                "not found in styles/"
            )
            return False
    for _, loaded_scene in scene_targets:
        spec = loaded_scene.SCENE
        parent = assets_by_id.get(spec.parent_id)
        if parent is None:
            err(f"Referenced parent asset {spec.parent_id!r} for scene {spec.id!r} not found")
            return False
        style_id = spec.style_id or parent.SPEC.style_id
        if style_id not in styles:
            err(f"Referenced style {style_id!r} for scene {spec.id!r} not found in styles/")
            return False
        for mount in spec.mounts:
            if mount.prop_id not in assets_by_id:
                err(f"Referenced prop asset {mount.prop_id!r} for scene {spec.id!r} not found")
                return False
    return True


def critic_workflow(
    root: Path,
    *,
    asset_id: str | None,
    base_ref: str | None,
    variant: str | None,
    category: CriticCategory | None = None,
    base_url: str,
    api_key: str,
    model: str,
    allow_dev_model: bool = False,
    timeout_seconds: float,
    threshold: int,
    summary_md: Path | None = None,
    output_format: OutputFormat = "llm",
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Run multimodal visual regression scoring on target or git-changed assets and scenes."""
    styles, style_paths = load_styles_with_paths(root / "styles")
    asset_files = discover_asset_files(root / "assets")
    scene_files = discover_scene_files(root / "assets")
    if not asset_files and not scene_files:
        err("No .asset.py or .scene.py files found under assets/")
        return 1

    loaded_assets = [(path, load_asset_module(path)) for path in asset_files]
    loaded_scenes = [(path, load_scene_module(path)) for path in scene_files]
    assets_by_id = {loaded.SPEC.id: loaded for _, loaded in loaded_assets}
    asset_paths_by_id = {loaded.SPEC.id: path for path, loaded in loaded_assets}

    selected = _select_critic_targets(
        root,
        loaded_assets,
        loaded_scenes,
        assets_by_id,
        style_paths,
        asset_id=asset_id,
        base_ref=base_ref,
        threshold=threshold,
        summary_md=summary_md,
        output_format=output_format,
        out=out,
        err=err,
    )
    if isinstance(selected, int):
        return selected

    asset_targets, scene_targets = selected
    if not _validate_target_dependencies(
        asset_targets,
        scene_targets,
        assets_by_id,
        styles,
        err,
    ):
        return 1

    try:
        config = CriticConfig(
            base_url=base_url,
            api_key=api_key,
            model=model,
            allow_dev_model=allow_dev_model,
            timeout_seconds=timeout_seconds,
            threshold=threshold,
        )
    except ValueError as exc:
        err(str(exc))
        return 1

    items: list[CriticAssetInput] = [
        _build_asset_critic_input(
            root,
            asset_path=asset_path,
            current_asset=current_asset,
            styles=styles,
            style_paths=style_paths,
            base_ref=base_ref,
            variant=variant,
            category=category,
        )
        for asset_path, current_asset in asset_targets
    ]
    for scene_path, current_scene in scene_targets:
        try:
            items.append(
                _build_scene_critic_input(
                    root,
                    scene_path=scene_path,
                    current_scene=current_scene,
                    assets_by_id=assets_by_id,
                    asset_paths_by_id=asset_paths_by_id,
                    styles=styles,
                    style_paths=style_paths,
                    base_ref=base_ref,
                    variant=variant,
                    category=category,
                )
            )
        except SceneCompositionError as exc:
            err(str(exc))
            return 1

    try:
        report = score_assets_batch(items, config)
    except CriticError as exc:
        err(str(exc))
        return 1

    _write_summary_md(summary_md, report, base_ref=base_ref)
    _emit_critic_report(report, output_format=output_format, out=out)
    return 0 if report.passed else 1
