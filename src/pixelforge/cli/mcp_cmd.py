"""Native stdio Model Context Protocol (MCP) server for pixelforge."""

from __future__ import annotations

import asyncio
import base64
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ContentBlock, ImageContent, TextContent

from pixelforge import __version__
from pixelforge.cli.compose_cmd import compose_scene_workflow, parse_mount_arg
from pixelforge.cli.critic_cmd import critic_workflow
from pixelforge.cli.diff_cmd import diff_asset as diff_asset_workflow
from pixelforge.cli.inspect_cmd import (
    inspect_api_workflow,
    inspect_assets_workflow,
    inspect_prefabs_workflow,
    inspect_presets_workflow,
    inspect_scenes_workflow,
    inspect_style_workflow,
)
from pixelforge.cli.output import OutputFn, emit_check_report, emit_reference_analysis
from pixelforge.cli.probe_cmd import probe_asset_workflow
from pixelforge.cli.render_cmd import render_once
from pixelforge.cli.settings import (
    load_hydra_settings,
    load_pixelforge_settings,
    resolve_project_style_id,
)
from pixelforge.export.analyze_ref import (
    analyze_reference_image,
    sanitize_asset_id,
    scaffold_asset_from_analysis,
)
from pixelforge.export.scene_models import DepthSortMode
from pixelforge.guard.critic import CriticCategory, CriticTier
from pixelforge.guard.probe import probe_asset
from pixelforge.guard.runner import (
    discover_asset_files,
    load_all_styles,
    load_asset_module,
    run_checks,
)

_OutputBuf = tuple[list[str], list[str], Callable[[str], None], Callable[[str], None]]


def _capture() -> _OutputBuf:
    """Create isolated stdout/stderr line buffers for workflow calls."""
    out_lines: list[str] = []
    err_lines: list[str] = []
    return out_lines, err_lines, out_lines.append, err_lines.append


def _resolve_root(root: str | None, default_root: Path) -> Path:
    return Path(root).resolve() if root else default_root


def _format_lines(out_lines: list[str], err_lines: list[str]) -> str:
    combined = [*out_lines, *(f"ERROR: {line}" for line in err_lines)]
    return "\n".join(combined) if combined else "(no output)"


def _text_result(exit_code: int, out_lines: list[str], err_lines: list[str]) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=_format_lines(out_lines, err_lines))],
        is_error=exit_code != 0,
    )


def _png_content(png_path: Path) -> ImageContent:
    encoded = base64.b64encode(png_path.read_bytes()).decode("ascii")
    return ImageContent(type="image", data=encoded, mime_type="image/png")


def _append_compact_probe(
    project_root: Path,
    asset_id: str,
    *,
    layers: bool,
    out: OutputFn,
) -> None:
    """Append compact `probe` bbox/histogram/layer diagnostics for `asset_id` if present."""
    asset_files = discover_asset_files(project_root / "assets")
    loaded_match = None
    for path in asset_files:
        loaded = load_asset_module(path)
        if loaded.SPEC.id == asset_id:
            loaded_match = loaded
            break
    if loaded_match is None:
        return
    styles = load_all_styles(project_root / "styles")
    style = styles.get(loaded_match.SPEC.style_id)
    if style is None:
        return
    report = probe_asset(loaded_match, style)
    bbox_str = (
        f"({report.opaque_bbox[0]},{report.opaque_bbox[1]},"
        f"{report.opaque_bbox[2]},{report.opaque_bbox[3]})"
        if report.opaque_bbox is not None
        else "none"
    )
    out(
        f"probe: asset={report.asset_id} state={report.state} frame={report.frame} "
        f"bbox={bbox_str} opaque={report.opaque_pixels}/{report.total_pixels} "
        f"({report.coverage_pct}%) orphans={len(report.orphan_pixels)}"
    )
    if report.histogram:
        top_tokens = report.histogram[:8]
        hist_parts = [f"{item.name}({item.index})={item.count}({item.pct}%)" for item in top_tokens]
        if len(report.histogram) > 8:
            hist_parts.append(f"+{len(report.histogram) - 8} more")
        out(f"histogram: {', '.join(hist_parts)}")
    if layers and report.layers:
        layer_parts: list[str] = []
        for layer in report.layers:
            lb = (
                f"({layer.opaque_bbox[0]},{layer.opaque_bbox[1]},"
                f"{layer.opaque_bbox[2]},{layer.opaque_bbox[3]})"
                if layer.opaque_bbox is not None
                else "empty"
            )
            layer_parts.append(f"{layer.name}:{lb}:{layer.pixel_count}px")
        out(f"layers: {', '.join(layer_parts)}")


def _register_inspect_tools(server: MCPServer, base_root: Path) -> None:
    """Register read-only introspection tools on `server`."""

    @server.tool(
        name="inspect_style",
        description=(
            "Inspect project StylePack palette tokens (paint, emissive, bright, reflections)."
        ),
    )
    def inspect_style(
        style_id: str | None = None,
        presets: bool = False,
        root: str | None = None,
    ) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        code = inspect_style_workflow(
            _resolve_root(root, base_root),
            style_id=style_id,
            presets=presets,
            output_format="llm",
            out=out,
            err=err,
        )
        return _text_result(code, out_lines, err_lines)

    @server.tool(
        name="inspect_presets",
        description="Inspect built-in StylePack presets available for pixelforge init/new.",
    )
    def inspect_presets(preset_id: str | None = None) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        code = inspect_presets_workflow(
            preset_id=preset_id,
            output_format="llm",
            out=out,
            err=err,
        )
        return _text_result(code, out_lines, err_lines)

    @server.tool(
        name="inspect_prefabs",
        description="Inspect available prefab kits, categories, and function signatures.",
    )
    def inspect_prefabs(target: str | None = None) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        code = inspect_prefabs_workflow(
            target=target,
            output_format="llm",
            out=out,
            err=err,
        )
        return _text_result(code, out_lines, err_lines)

    @server.tool(
        name="inspect_api",
        description="Inspect core drawing API methods, signatures, and summaries.",
    )
    def inspect_api(target: str | None = None) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        code = inspect_api_workflow(
            target=target,
            output_format="llm",
            out=out,
            err=err,
        )
        return _text_result(code, out_lines, err_lines)

    @server.tool(
        name="inspect_assets",
        description="Inspect .asset.py dimensions, states, anchors, and hitboxes.",
    )
    def inspect_assets(asset_id: str | None = None, root: str | None = None) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        code = inspect_assets_workflow(
            _resolve_root(root, base_root),
            asset_id=asset_id,
            output_format="llm",
            out=out,
            err=err,
        )
        return _text_result(code, out_lines, err_lines)

    @server.tool(
        name="inspect_scenes",
        description="Inspect declarative .scene.py mounts, states, and strict flags.",
    )
    def inspect_scenes(scene_id: str | None = None, root: str | None = None) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        code = inspect_scenes_workflow(
            _resolve_root(root, base_root),
            scene_id=scene_id,
            output_format="llm",
            out=out,
            err=err,
        )
        return _text_result(code, out_lines, err_lines)


def _register_diagnostic_tools(server: MCPServer, base_root: Path) -> None:
    """Register guard, probe, render, compose, and diff tools on `server`."""

    @server.tool(
        name="check_asset",
        description="Run AST, style, palette, and determinism guards on assets.",
    )
    def check_asset(
        asset_id: str | None = None,
        strict_orphans: bool = False,
        strict_craft: bool = False,
        root: str | None = None,
    ) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        report = run_checks(
            _resolve_root(root, base_root),
            asset_id=asset_id,
            strict_orphans=strict_orphans,
            strict_craft=strict_craft,
        )
        emit_check_report(report, output_format="llm", out=out, err=err)
        return _text_result(0 if report.passed else 1, out_lines, err_lines)

    @server.tool(
        name="probe_canvas",
        description=(
            "Probe an asset's ASCII pixel slice, layer bboxes, token histogram, and orphans."
        ),
    )
    def probe_canvas(
        asset_id: str,
        region: str | None = None,
        state: str | None = None,
        frame: int = 0,
        layers: bool = False,
        root: str | None = None,
    ) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        code = probe_asset_workflow(
            _resolve_root(root, base_root),
            asset_id=asset_id,
            region=region,
            state=state,
            frame=frame,
            show_layers=layers,
            output_format="llm",
            out=out,
            err=err,
        )
        return _text_result(code, out_lines, err_lines)

    @server.tool(
        name="render_contact_sheet",
        description=(
            "Render an asset contact sheet and return compact probe diagnostics plus its PNG."
        ),
    )
    def render_contact_sheet(
        asset_id: str,
        scale: int = 4,
        variant: str | None = None,
        layers: bool = False,
        root: str | None = None,
    ) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        project_root = _resolve_root(root, base_root)
        with tempfile.TemporaryDirectory(prefix="pixelforge-mcp-sheet-") as tmp:
            tmp_path = Path(tmp)
            sheets_dir = tmp_path / "sheets"
            code = render_once(
                project_root,
                asset_id=asset_id,
                out_dir=tmp_path / "out",
                sheets_dir=sheets_dir,
                previews_dir=tmp_path / "previews",
                sheet=True,
                layers=layers,
                animate=False,
                emissive=None,
                lut=False,
                indexed_ts=False,
                scale=scale,
                variant=variant,
                output_format="llm",
                out=out,
                err=err,
            )
            if code == 0:
                _append_compact_probe(
                    project_root,
                    asset_id,
                    layers=layers,
                    out=out,
                )
            content: list[ContentBlock] = [
                TextContent(type="text", text=_format_lines(out_lines, err_lines))
            ]
            sheet_path = sheets_dir / f"{asset_id}.contact.png"
            if code == 0 and sheet_path.is_file():
                content.append(_png_content(sheet_path))
            return CallToolResult(content=content, is_error=code != 0)

    @server.tool(
        name="compose_dry_run",
        description=(
            "Validate and dry-run multi-prop scene composition without writing repo outputs."
        ),
    )
    def compose_dry_run(
        parent_id: str,
        mounts: list[str],
        state: str | None = None,
        frame: int = 0,
        variant: str | None = None,
        depth_sort: DepthSortMode = "z_index",
        strict_bounds: bool = False,
        strict_perspective: bool = False,
        root: str | None = None,
    ) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        try:
            parsed_mounts = [parse_mount_arg(item) for item in mounts]
        except ValueError as exc:
            return CallToolResult(
                content=[TextContent(type="text", text=f"ERROR: {exc}")],
                is_error=True,
            )
        with tempfile.TemporaryDirectory(prefix="pixelforge-mcp-compose-") as tmp:
            tmp_path = Path(tmp)
            code = compose_scene_workflow(
                _resolve_root(root, base_root),
                parent_id=parent_id,
                mounts=parsed_mounts,
                state=state,
                frame=frame,
                variant=variant,
                depth_sort=depth_sort,
                strict_bounds=strict_bounds,
                strict_perspective=strict_perspective,
                animate=False,
                scale=1,
                out_dir=tmp_path / "out",
                sheets_dir=tmp_path / "sheets",
                sheet=False,
                output_format="llm",
                out=out,
                err=err,
            )
        return _text_result(code, out_lines, err_lines)

    @server.tool(
        name="diff_asset",
        description=(
            "Diff an asset against a git ref and return diff metrics plus PNG image blocks."
        ),
    )
    def diff_asset(
        asset_id: str,
        base_ref: str = "HEAD",
        scale: int = 4,
        variant: str | None = None,
        root: str | None = None,
    ) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        project_root = _resolve_root(root, base_root)
        with tempfile.TemporaryDirectory(prefix="pixelforge-mcp-diff-") as tmp:
            diff_dir = Path(tmp) / "diffs"
            code = diff_asset_workflow(
                project_root,
                asset_id=asset_id,
                base_ref=base_ref,
                out_dir=diff_dir,
                scale=scale,
                variant=variant,
                output_format="llm",
                out=out,
                err=err,
            )
            content: list[ContentBlock] = [
                TextContent(type="text", text=_format_lines(out_lines, err_lines))
            ]
            if code == 0 and diff_dir.is_dir():
                for png_path in sorted(diff_dir.glob("*.diff.png")):
                    content.append(_png_content(png_path))
            return CallToolResult(content=content, is_error=code != 0)

    @server.tool(
        name="analyze_ref",
        description=(
            "Analyze a reference image into proportions, palette histogram, ASCII sketch, "
            "and optional starter .asset.py scaffold without writing files."
        ),
    )
    def analyze_ref(
        image_path: str,
        style_id: str | None = None,
        width: int = 32,
        height: int = 32,
        scaffold: bool = False,
        asset_id: str | None = None,
        root: str | None = None,
    ) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        project_root = _resolve_root(root, base_root)
        raw_img = Path(image_path)
        resolved_img = raw_img if raw_img.is_absolute() else (project_root / raw_img).resolve()
        if not resolved_img.is_file():
            err(f"reference image not found: {resolved_img}")
            return _text_result(1, out_lines, err_lines)
        settings = load_pixelforge_settings(project_root)
        styles = load_all_styles(project_root / "styles")
        try:
            resolved_style_id = resolve_project_style_id(
                explicit_style=style_id,
                default_style=settings.default_style,
                styles=styles,
                styles_dir=project_root / "styles",
            )
            analysis = analyze_reference_image(
                resolved_img,
                styles[resolved_style_id],
                size=(width, height),
            )
        except (OSError, ValueError) as exc:
            err(f"failed to analyze reference image {resolved_img}: {exc}")
            return _text_result(1, out_lines, err_lines)

        scaffold_source: str | None = None
        if scaffold:
            resolved_asset_id = (
                sanitize_asset_id(asset_id) if asset_id else sanitize_asset_id(resolved_img.stem)
            )
            scaffold_source = scaffold_asset_from_analysis(
                analysis,
                styles[resolved_style_id],
                asset_id=resolved_asset_id,
            )
        emit_reference_analysis(
            analysis,
            output_format="llm",
            out=out,
            scaffold_source=scaffold_source,
            scaffold_path=None,
        )
        return _text_result(0, out_lines, err_lines)

    @server.tool(
        name="critic_asset",
        description=(
            "Run multimodal visual critic scoring on target or git-changed assets and scenes."
        ),
    )
    def critic_asset(
        asset_id: str | None = None,
        base_ref: str | None = None,
        variant: str | None = None,
        category: CriticCategory | None = None,
        tier: CriticTier = "fast",
        model: str | None = None,
        threshold: int = 7,
        root: str | None = None,
    ) -> CallToolResult:
        out_lines, err_lines, out, err = _capture()
        project_root = _resolve_root(root, base_root)
        hydra = load_hydra_settings(project_root)
        if model:
            resolved_model = model
            allow_dev_model = True
        elif tier == "dev":
            resolved_model = hydra.model_dev or hydra.model_deep
            allow_dev_model = True
        else:
            resolved_model = hydra.model_fast
            allow_dev_model = False

        code = critic_workflow(
            project_root,
            asset_id=asset_id,
            base_ref=base_ref,
            variant=variant,
            category=category,
            base_url=hydra.base_url,
            api_key=hydra.api_key,
            model=resolved_model,
            allow_dev_model=allow_dev_model,
            timeout_seconds=hydra.timeout_seconds,
            threshold=threshold,
            summary_md=None,
            output_format="llm",
            out=out,
            err=err,
        )
        return _text_result(code, out_lines, err_lines)


def create_mcp_server(default_root: Path | None = None) -> MCPServer:
    """Create and configure the `pixelforge` MCP server instance."""
    base_root = default_root.resolve() if default_root else Path.cwd()
    server = MCPServer(
        name="pixelforge",
        version=__version__,
        instructions=(
            "Deterministic indexed pixel art compiler tools: inspect styles/presets/prefabs/API/"
            "assets/scenes, run guards, probe canvases, dry-run compositions, and render "
            "contact-sheet or git-diff PNGs."
        ),
    )
    _register_inspect_tools(server, base_root)
    _register_diagnostic_tools(server, base_root)
    return server


def run_mcp_stdio(
    root: Path | None = None,
    *,
    transport: Literal["stdio"] = "stdio",
) -> int:
    """Run the pixelforge MCP server over stdio and return a process exit code."""
    server = create_mcp_server(default_root=root)
    if transport == "stdio":
        asyncio.run(server.run_stdio_async())
    return 0
