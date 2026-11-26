"""CLI `watch` incremental rebuild loop and studio server orchestration."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from pathlib import Path

from pixelforge.cli.output import OutputFn, OutputFormat
from pixelforge.cli.watch_graph import (
    WatchGraph,
    diff_watch_graph,
    seed_watch_graph_metadata,
    snapshot_watch_mtimes,
)
from pixelforge.cli.watch_render import (
    render_watch_full,
    render_watch_incremental,
)
from pixelforge.export.atlas import AtlasFormat
from pixelforge.export.bundle import ExportBundleOptions
from pixelforge.export.studio import StudioServer, StudioState
from pixelforge.guard.runner import CheckReport, run_checks


def _emit_watch_serve(url: str, output_format: OutputFormat, out: OutputFn) -> None:
    if output_format == "json":
        out(json.dumps({"event": "serve", "url": url}))
        return
    if output_format == "human":
        out(f"preview studio listening at {url}")
        return
    out(f"watch event=serve url={url}")


def _sync_studio(
    graph: WatchGraph,
    studio_state: StudioState | None,
    *,
    last_error: str | None = None,
) -> None:
    if studio_state is None:
        return
    studio_state.sync(
        graph.styles_by_id,
        graph.bundles_by_id,
        scenes=graph.scenes_by_id,
        assets_by_id=graph.assets_by_id,
        last_error=last_error,
    )


def _format_check_errors(report: CheckReport) -> str:
    return "; ".join(v.format_line() for v in report.violations if v.severity == "error")


def _emit_watch_stop(output_format: OutputFormat, out: OutputFn) -> None:
    if output_format == "json":
        out(json.dumps({"event": "stop"}))
        return
    if output_format == "human":
        out("watch stopped")
        return
    out("watch event=stop")


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
    graph: WatchGraph,
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
    graph: WatchGraph,
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
    studio_state: StudioState | None = None,
    out: OutputFn,
    err: OutputFn,
) -> None:
    affected_paths, affected_scene_paths, affected_styles, deleted_ids = diff_watch_graph(
        graph, cur_styles, cur_assets, cur_scenes
    )
    if not graph.initial_render_done:
        report = run_checks(root, asset_id=asset_id)
        _emit_check_violations(report.violations, out, err)
        if report.passed:
            ok = render_watch_full(
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
            if ok:
                _sync_studio(graph, studio_state, last_error=None)
        elif studio_state is not None:
            studio_state.set_error(_format_check_errors(report))
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
            if studio_state is not None:
                studio_state.set_error(_format_check_errors(report))
            return

    ok = render_watch_incremental(
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
    if ok:
        _sync_studio(graph, studio_state, last_error=None)


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
    output_format: OutputFormat,
    studio_state: StudioState | None = None,
    out: OutputFn,
    err: OutputFn,
) -> WatchGraph:
    style_mtimes, asset_mtimes, scene_mtimes = snapshot_watch_mtimes(root)
    graph = WatchGraph(
        style_mtimes=style_mtimes,
        asset_mtimes=asset_mtimes,
        scene_mtimes=scene_mtimes,
        output_format=output_format,
    )
    seed_watch_graph_metadata(graph)
    report = run_checks(root, asset_id=asset_id)
    if report.passed:
        ok = render_watch_full(
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
        if ok:
            _sync_studio(graph, studio_state, last_error=None)
    else:
        _emit_check_violations(report.violations, out, err)
        if studio_state is not None:
            studio_state.set_error(_format_check_errors(report))
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
    normals: bool = False,
    height: bool = False,
    indexed_ts: bool,
    indexed_ts_lazy: bool = False,
    atlas: AtlasFormat | None = None,
    scale: int,
    variant: str | None,
    output_format: OutputFormat = "llm",
    out: OutputFn,
    err: OutputFn,
    interval: float = 0.5,
    max_cycles: int | None = None,
    serve: bool = False,
    serve_host: str = "127.0.0.1",
    serve_port: int = 4173,
) -> int:
    """Poll `.asset.py` and `.style.py` mtimes and incrementally rebuild affected assets."""
    _ = previews_dir
    options = ExportBundleOptions(
        variant=variant,
        scale=scale,
        emissive=emissive,
        lut=lut,
        normals=normals,
        height=height,
        animate=False,
        atlas=atlas,
    )
    studio_state = StudioState() if serve else None
    studio_server = (
        StudioServer(studio_state, host=serve_host, port=serve_port)
        if studio_state is not None
        else None
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
        output_format=output_format,
        studio_state=studio_state,
        out=out,
        err=err,
    )

    cycles = 0
    try:
        if studio_server is not None:
            url = studio_server.start()
            _emit_watch_serve(url, output_format, out)
        while max_cycles is None or cycles < max_cycles:
            time.sleep(interval)
            cycles += 1
            cur_styles, cur_assets, cur_scenes = snapshot_watch_mtimes(root)
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
                studio_state=studio_state,
                out=out,
                err=err,
            )
    except KeyboardInterrupt:
        _emit_watch_stop(output_format, out)
    finally:
        if studio_server is not None:
            studio_server.stop()
    return 0


__all__ = ["watch_loop"]
