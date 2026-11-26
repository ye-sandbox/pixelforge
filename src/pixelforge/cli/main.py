"""Thin CLI entrypoint for pixelforge commands."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pixelforge import __version__
from pixelforge.cli.compose_cmd import compose_scene_workflow, parse_mount_arg
from pixelforge.cli.critic_cmd import critic_workflow
from pixelforge.cli.diff_cmd import diff_asset
from pixelforge.cli.inspect_cmd import (
    inspect_assets_workflow,
    inspect_prefabs_workflow,
    inspect_scenes_workflow,
    inspect_style_workflow,
)
from pixelforge.cli.output import (
    OutputFormat,
    add_format_arguments,
    emit_check_report,
    emit_reference_analysis,
    resolve_output_format,
)
from pixelforge.cli.render_cmd import render_once
from pixelforge.cli.scaffold import scaffold_project
from pixelforge.cli.settings import (
    PixelforgeSettings,
    load_hydra_settings,
    load_pixelforge_settings,
)
from pixelforge.cli.watch_cmd import watch_loop
from pixelforge.export.analyze_ref import (
    analyze_reference_image,
    parse_sketch_size,
    sanitize_asset_id,
    scaffold_asset_from_analysis,
)
from pixelforge.guard.runner import load_all_styles, run_checks, sync_palette_stubs


def _out(line: str) -> None:
    sys.stdout.write(f"{line}\n")


def _err(line: str) -> None:
    sys.stderr.write(f"{line}\n")


def _resolve_root(root_arg: str | None) -> Path:
    return Path(root_arg).resolve() if root_arg else Path.cwd()


def _resolve_dir(root: Path, configured: Path, override: str | None = None) -> Path:
    target = Path(override) if override else configured
    return target if target.is_absolute() else root / target


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _resolve_format_or_err(args: argparse.Namespace) -> OutputFormat | None:
    try:
        return resolve_output_format(args)
    except ValueError as exc:
        _err(str(exc))
        return None


def _cmd_init(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
    root = _resolve_root(args.root)
    style_id: str = args.style or settings.default_style
    created = scaffold_project(root, style_id=style_id, force=bool(args.force))
    for path in created:
        _out(f"created {path}")
    if not created:
        _out("nothing created (use --force to overwrite existing files)")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    output_format = _resolve_format_or_err(args)
    if output_format is None:
        return 2
    root = _resolve_root(args.root)
    if getattr(args, "sync_stubs", False):
        sync_palette_stubs(root)
    report = run_checks(
        root,
        asset_id=args.asset_id,
        strict_orphans=bool(args.strict_orphans),
    )
    emit_check_report(report, output_format=output_format, out=_out, err=_err)
    return 0 if report.passed else 1


def _cmd_render(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
    output_format = _resolve_format_or_err(args)
    if output_format is None:
        return 2
    root = _resolve_root(args.root)
    return render_once(
        root,
        asset_id=args.asset_id,
        out_dir=_resolve_dir(root, settings.out_dir, args.out),
        sheets_dir=_resolve_dir(root, settings.sheets_dir),
        previews_dir=_resolve_dir(root, settings.previews_dir),
        sheet=bool(args.sheet),
        animate=bool(args.animate),
        animate_format=args.animate_format,
        emissive=args.emissive,
        lut=bool(args.lut),
        normals=bool(args.normals),
        height=bool(args.height),
        indexed_ts=bool(args.indexed_ts or args.indexed_ts_lazy),
        indexed_ts_lazy=bool(args.indexed_ts_lazy),
        atlas=args.atlas,
        scale=int(args.scale),
        variant=args.variant,
        output_format=output_format,
        out=_out,
        err=_err,
    )


def _cmd_diff(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
    output_format = _resolve_format_or_err(args)
    if output_format is None:
        return 2
    root = _resolve_root(args.root)
    summary_md = _resolve_dir(root, Path(args.summary_md)) if args.summary_md else None
    return diff_asset(
        root,
        asset_id=str(args.asset_id),
        base_ref=str(args.base),
        out_dir=_resolve_dir(root, settings.diffs_dir, args.out),
        scale=int(args.scale),
        variant=args.variant,
        summary_md=summary_md,
        output_format=output_format,
        out=_out,
        err=_err,
    )


def _cmd_watch(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
    output_format = _resolve_format_or_err(args)
    if output_format is None:
        return 2
    root = _resolve_root(args.root)
    emissive: bool | None = True if args.emissive else None
    return watch_loop(
        root,
        asset_id=args.asset_id,
        out_dir=_resolve_dir(root, settings.out_dir, args.out),
        sheets_dir=_resolve_dir(root, settings.sheets_dir),
        previews_dir=_resolve_dir(root, settings.previews_dir),
        sheet=bool(args.sheet),
        emissive=emissive,
        lut=bool(args.lut),
        normals=bool(args.normals),
        height=bool(args.height),
        indexed_ts=bool(args.indexed_ts or args.indexed_ts_lazy),
        indexed_ts_lazy=bool(args.indexed_ts_lazy),
        atlas=args.atlas,
        scale=int(args.scale),
        variant=args.variant,
        output_format=output_format,
        out=_out,
        err=_err,
        interval=float(args.interval),
        max_cycles=args.max_cycles,
        serve=bool(args.serve),
        serve_host=str(args.host),
        serve_port=int(args.port),
    )


def _cmd_analyze_ref(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
    output_format = _resolve_format_or_err(args)
    if output_format is None:
        return 2
    root = _resolve_root(args.root)
    image_path = Path(args.image_path).resolve()

    if not image_path.is_file():
        _err(f"reference image not found: {image_path}")
        return 1

    # INVARIANT: Reference rasters must remain strictly ephemeral and must never live
    # inside `assets/` or `styles/`.
    for forbidden_dir in (root / "assets", root / "styles"):
        if _is_within(image_path, forbidden_dir):
            _err(
                f"refusing reference image inside {forbidden_dir.name}/: "
                "external rasters must not be placed in assets/ or styles/"
            )
            return 1

    try:
        size = parse_sketch_size(str(args.size))
    except ValueError as exc:
        _err(str(exc))
        return 1

    style_id = str(args.style or settings.default_style)
    styles = load_all_styles(root / "styles")
    if style_id not in styles:
        available = ", ".join(sorted(styles)) or "(none)"
        _err(f"unknown style {style_id!r}; available in {root / 'styles'}: {available}")
        return 1

    try:
        analysis = analyze_reference_image(image_path, styles[style_id], size=size)
    except (OSError, ValueError) as exc:
        _err(f"failed to analyze reference image {image_path}: {exc}")
        return 1

    scaffold_source: str | None = None
    scaffold_path: Path | None = None
    if bool(args.scaffold):
        asset_id = (
            sanitize_asset_id(str(args.id)) if args.id else sanitize_asset_id(image_path.stem)
        )
        scaffold_source = scaffold_asset_from_analysis(
            analysis, styles[style_id], asset_id=asset_id
        )
        if args.out is not None:
            raw_out = Path(str(args.out))
            target_path = (
                raw_out / f"{asset_id}.asset.py"
                if raw_out.is_dir() or raw_out.suffix != ".py"
                else raw_out
            )
            if target_path.exists() and not bool(args.force):
                _err(f"refusing to overwrite existing {target_path} (pass --force to overwrite)")
                return 1
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(scaffold_source, encoding="utf-8")
            scaffold_path = target_path

    emit_reference_analysis(
        analysis,
        output_format=output_format,
        out=_out,
        scaffold_source=scaffold_source,
        scaffold_path=scaffold_path,
    )
    return 0


def _cmd_compose(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
    output_format = _resolve_format_or_err(args)
    if output_format is None:
        return 2
    root = _resolve_root(args.root)
    try:
        mounts = [parse_mount_arg(str(raw)) for raw in (args.mount or ())]
    except ValueError as exc:
        _err(str(exc))
        return 1

    return compose_scene_workflow(
        root,
        parent_id=str(args.parent_id),
        mounts=mounts,
        state=args.state,
        frame=int(args.frame),
        variant=args.variant,
        depth_sort=args.depth_sort,
        strict_bounds=bool(args.strict_bounds),
        strict_perspective=bool(args.strict_perspective),
        animate=bool(args.animate),
        animate_format=args.animate_format,
        scale=int(args.scale),
        out_dir=_resolve_dir(root, settings.previews_dir, args.out),
        sheets_dir=_resolve_dir(root, settings.sheets_dir),
        sheet=bool(args.sheet),
        output_format=output_format,
        out=_out,
        err=_err,
    )


def _cmd_critic(args: argparse.Namespace) -> int:
    output_format = _resolve_format_or_err(args)
    if output_format is None:
        return 2
    root = _resolve_root(args.root)
    summary_md = _resolve_dir(root, Path(args.summary_md)) if args.summary_md else None
    hydra = load_hydra_settings(root)
    return critic_workflow(
        root,
        asset_id=args.asset_id,
        base_ref=args.base,
        variant=args.variant,
        base_url=hydra.base_url,
        api_key=hydra.api_key,
        model=hydra.model_fast,
        timeout_seconds=hydra.timeout_seconds,
        threshold=int(args.threshold),
        summary_md=summary_md,
        output_format=output_format,
        out=_out,
        err=_err,
    )


def _cmd_inspect(args: argparse.Namespace) -> int:
    target = getattr(args, "inspect_target", None)
    if target is None:
        inspect_parser = getattr(args, "_inspect_parser", None)
        if isinstance(inspect_parser, argparse.ArgumentParser):
            inspect_parser.print_help()
        return 0
    output_format = _resolve_format_or_err(args)
    if output_format is None:
        return 2
    if target == "prefabs":
        return inspect_prefabs_workflow(
            target=args.target,
            output_format=output_format,
            out=_out,
            err=_err,
        )
    root = _resolve_root(args.root)
    if target == "style":
        return inspect_style_workflow(
            root,
            style_id=args.style_id,
            output_format=output_format,
            out=_out,
            err=_err,
        )
    if target == "assets":
        return inspect_assets_workflow(
            root,
            asset_id=args.asset_id,
            output_format=output_format,
            out=_out,
            err=_err,
        )
    if target == "scenes":
        return inspect_scenes_workflow(
            root,
            scene_id=args.scene_id,
            output_format=output_format,
            out=_out,
            err=_err,
        )
    return 2


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level pixelforge CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="pixelforge",
        description="Deterministic compositional indexed pixel art compiler.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command")

    init_p = sub.add_parser("init", help="Scaffold starter style, asset, and .env.example")
    init_p.add_argument("--style", default=None, help="Starter StylePack ID")
    init_p.add_argument("--force", action="store_true", help="Overwrite existing starter files")
    init_p.add_argument("--root", default=None, help="Project root directory")

    render_p = sub.add_parser("render", help="Compile .asset.py modules into PNGs and manifests")
    render_p.add_argument("asset_id", nargs="?", default=None, help="Optional asset ID filter")
    render_p.add_argument("--out", default=None, help="Output directory")
    render_p.add_argument("--sheet", action="store_true", help="Generate diagnostic .contact.png")
    render_p.add_argument(
        "--animate",
        action="store_true",
        help="Generate animated GIF/APNG previews",
    )
    render_p.add_argument(
        "--animate-format",
        choices=("gif", "apng"),
        default="gif",
        help="Animated preview format when --animate is set (default: gif)",
    )
    render_p.add_argument(
        "--emissive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Force or disable emissive mask emission",
    )
    render_p.add_argument("--lut", action="store_true", help="Emit indexed PNGs + 1D LUT")
    render_p.add_argument(
        "--normals",
        action="store_true",
        help="Emit derived 2D normal map PNGs (_normal.png)",
    )
    render_p.add_argument(
        "--height",
        action="store_true",
        help="Emit derived 2D height map PNGs (_height.png)",
    )
    render_p.add_argument(
        "--indexed-ts",
        action="store_true",
        help="Emit RLE Uint8Array + palette/manifest TypeScript modules",
    )
    render_p.add_argument(
        "--indexed-ts-lazy",
        action="store_true",
        help="Defer RLE decoding in --indexed-ts sprites.generated.ts until frame access",
    )
    render_p.add_argument(
        "--atlas",
        choices=("aseprite", "texturepacker", "all"),
        default=None,
        help="Emit Aseprite JSON and/or TexturePacker atlas metadata alongside sprites",
    )
    render_p.add_argument("--scale", type=int, default=1, help="Integer nearest-neighbor scale")
    render_p.add_argument("--variant", default=None, help="Optional StylePack variant name")
    add_format_arguments(render_p)
    render_p.add_argument("--root", default=None, help="Project root directory")

    check_p = sub.add_parser("check", help="Run AST static and runtime guard checks")
    check_p.add_argument("asset_id", nargs="?", default=None, help="Optional asset ID filter")
    check_p.add_argument(
        "--strict-orphans",
        action="store_true",
        help="Treat isolated 1x1 orphan pixels as errors",
    )
    check_p.add_argument(
        "--sync-stubs",
        action="store_true",
        help="Generate or refresh typed *_palette.py stubs before running checks",
    )
    add_format_arguments(check_p)
    check_p.add_argument("--root", default=None, help="Project root directory")

    diff_p = sub.add_parser("diff", help="Generate visual pixel-diff PNG against a git ref")
    diff_p.add_argument("asset_id", help="Asset ID to compare")
    diff_p.add_argument("--base", default="HEAD", help="Git ref baseline (default: HEAD)")
    diff_p.add_argument("--out", default=None, help="Output directory for diff PNGs")
    diff_p.add_argument("--scale", type=int, default=1, help="Integer nearest-neighbor scale")
    diff_p.add_argument("--variant", default=None, help="Optional StylePack variant name")
    diff_p.add_argument(
        "--summary-md",
        default=None,
        help="Optional output path for a Markdown PR regression summary",
    )
    add_format_arguments(diff_p)
    diff_p.add_argument("--root", default=None, help="Project root directory")

    watch_p = sub.add_parser("watch", help="Watch .asset.py/.style.py and hot-reload outputs")
    watch_p.add_argument("asset_id", nargs="?", default=None, help="Optional asset ID filter")
    watch_p.add_argument("--out", default=None, help="Output directory")
    watch_p.add_argument("--sheet", action="store_true", help="Generate diagnostic .contact.png")
    watch_p.add_argument("--emissive", action="store_true", help="Force emissive mask emission")
    watch_p.add_argument("--lut", action="store_true", help="Emit indexed PNGs + 1D LUT")
    watch_p.add_argument(
        "--normals",
        action="store_true",
        help="Emit derived 2D normal map PNGs (_normal.png)",
    )
    watch_p.add_argument(
        "--height",
        action="store_true",
        help="Emit derived 2D height map PNGs (_height.png)",
    )
    watch_p.add_argument(
        "--indexed-ts",
        action="store_true",
        help="Emit RLE Uint8Array + palette/manifest TypeScript modules",
    )
    watch_p.add_argument(
        "--indexed-ts-lazy",
        action="store_true",
        help="Defer RLE decoding in --indexed-ts sprites.generated.ts until frame access",
    )
    watch_p.add_argument(
        "--atlas",
        choices=("aseprite", "texturepacker", "all"),
        default=None,
        help="Emit Aseprite JSON and/or TexturePacker atlas metadata alongside sprites",
    )
    watch_p.add_argument("--scale", type=int, default=1, help="Integer nearest-neighbor scale")
    watch_p.add_argument("--variant", default=None, help="Optional StylePack variant name")
    watch_p.add_argument("--interval", type=float, default=0.5, help="Poll interval in seconds")
    watch_p.add_argument("--max-cycles", type=int, default=None, help="Stop after N poll cycles")
    watch_p.add_argument(
        "--serve",
        action="store_true",
        help="Start zero-dependency local Preview Studio HTTP server",
    )
    watch_p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Preview Studio bind host when --serve is set (default: 127.0.0.1)",
    )
    watch_p.add_argument(
        "--port",
        type=int,
        default=4173,
        help="Preview Studio bind port when --serve is set (default: 4173, 0 for ephemeral)",
    )
    add_format_arguments(watch_p)
    watch_p.add_argument("--root", default=None, help="Project root directory")

    analyze_p = sub.add_parser(
        "analyze-ref",
        help="Extract ephemeral aspect ratio, palette histogram, and ASCII sketch from a reference",
    )
    analyze_p.add_argument(
        "image_path",
        help="Local reference image path (must not be in assets/ or styles/)",
    )
    analyze_p.add_argument("--style", default=None, help="Target StylePack ID")
    analyze_p.add_argument("--size", default="32x32", help="Sketch dimensions WxH (default: 32x32)")
    analyze_p.add_argument(
        "--scaffold",
        action="store_true",
        help="Generate an initial Layer/Plane/StylePack-tokenized .asset.py skeleton",
    )
    analyze_p.add_argument(
        "--id", default=None, help="Asset ID for --scaffold (default: image stem)"
    )
    analyze_p.add_argument(
        "--out",
        default=None,
        help="Optional output .asset.py path or directory when --scaffold is set",
    )
    analyze_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing file when --scaffold --out is set",
    )
    add_format_arguments(analyze_p)
    analyze_p.add_argument("--root", default=None, help="Project root directory")

    compose_p = sub.add_parser(
        "compose",
        help="Mount child prop assets onto declared parent scene anchors and render preview",
    )
    compose_p.add_argument("parent_id", help="Parent scene asset ID (e.g. bedroom_desk_iso)")
    compose_p.add_argument(
        "--mount",
        action="append",
        default=[],
        help="Mount spec 'prop_id@anchor[:prop_anchor]' (repeatable)",
    )
    compose_p.add_argument("--state", default=None, help="Parent scene state")
    compose_p.add_argument("--frame", type=int, default=0, help="Parent scene frame (default: 0)")
    compose_p.add_argument("--variant", default=None, help="Optional StylePack variant name")
    compose_p.add_argument(
        "--depth-sort",
        choices=("z_index", "iso_y"),
        default="z_index",
        help="Mount ordering: explicit z_index (default) or isometric Y + z_index",
    )
    compose_p.add_argument(
        "--animate",
        action="store_true",
        help="Emit synchronized multi-frame animated GIF/APNG preview",
    )
    compose_p.add_argument(
        "--animate-format",
        choices=("gif", "apng"),
        default="gif",
        help="Animated preview format when --animate is set (default: gif)",
    )
    compose_p.add_argument(
        "--strict-bounds",
        action="store_true",
        help="Fail if any mounted prop clips outside the parent canvas",
    )
    compose_p.add_argument(
        "--strict-perspective",
        action="store_true",
        help="Fail if any mounted prop's perspective differs from the parent scene",
    )
    compose_p.add_argument("--scale", type=int, default=1, help="Integer nearest-neighbor scale")
    compose_p.add_argument("--out", default=None, help="Output directory for composed PNG")
    compose_p.add_argument("--sheet", action="store_true", help="Generate composed .contact.png")
    add_format_arguments(compose_p)
    compose_p.add_argument("--root", default=None, help="Project root directory")

    critic_p = sub.add_parser(
        "critic",
        help="Score assets and scenes via internal hydra-llm-router multimodal critic (OpenAI v1)",
    )
    critic_p.add_argument(
        "asset_id",
        nargs="?",
        default=None,
        help="Optional asset or scene ID filter",
    )
    critic_p.add_argument(
        "--base",
        default=None,
        help="Git ref baseline; scores changed assets/styles/scenes with diff context",
    )
    critic_p.add_argument(
        "--threshold",
        type=int,
        default=70,
        help="Minimum passing visual score 0-100 (default: 70)",
    )
    critic_p.add_argument("--variant", default=None, help="Optional StylePack variant name")
    critic_p.add_argument(
        "--summary-md",
        default=None,
        help="Optional output path for a Markdown PR regression summary",
    )
    add_format_arguments(critic_p)
    critic_p.add_argument("--root", default=None, help="Project root directory")

    inspect_p = sub.add_parser(
        "inspect",
        help="Introspect StylePacks, prefabs, assets, and scenes",
    )
    inspect_p.set_defaults(_inspect_parser=inspect_p)
    inspect_sub = inspect_p.add_subparsers(dest="inspect_target")

    inspect_style_p = inspect_sub.add_parser(
        "style",
        help="Inspect StylePack palette tokens grouped by paint/emissive/bright/reflections",
    )
    inspect_style_p.add_argument("style_id", nargs="?", default=None, help="Optional StylePack ID")
    add_format_arguments(inspect_style_p)
    inspect_style_p.add_argument("--root", default=None, help="Project root directory")

    inspect_prefabs_p = inspect_sub.add_parser(
        "prefabs",
        help="Inspect prefab kit signatures and categories",
    )
    inspect_prefabs_p.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Optional category (architecture|furniture|details|atmosphere) or name filter",
    )
    add_format_arguments(inspect_prefabs_p)

    inspect_assets_p = inspect_sub.add_parser(
        "assets",
        help="Inspect asset dimensions, states, anchors, and hitboxes",
    )
    inspect_assets_p.add_argument("asset_id", nargs="?", default=None, help="Optional asset ID")
    add_format_arguments(inspect_assets_p)
    inspect_assets_p.add_argument("--root", default=None, help="Project root directory")

    inspect_scenes_p = inspect_sub.add_parser(
        "scenes",
        help="Inspect declarative .scene.py mounts, states, and strict flags",
    )
    inspect_scenes_p.add_argument("scene_id", nargs="?", default=None, help="Optional scene ID")
    add_format_arguments(inspect_scenes_p)
    inspect_scenes_p.add_argument("--root", default=None, help="Project root directory")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the pixelforge CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command is None:
        parser.print_help()
        return 0

    root = _resolve_root(getattr(args, "root", None))
    settings = load_pixelforge_settings(root)
    if args.command == "init":
        return _cmd_init(args, settings)
    if args.command == "check":
        return _cmd_check(args)
    if args.command == "render":
        return _cmd_render(args, settings)
    if args.command == "diff":
        return _cmd_diff(args, settings)
    if args.command == "watch":
        return _cmd_watch(args, settings)
    if args.command == "analyze-ref":
        return _cmd_analyze_ref(args, settings)
    if args.command == "compose":
        return _cmd_compose(args, settings)
    if args.command == "critic":
        return _cmd_critic(args)
    if args.command == "inspect":
        return _cmd_inspect(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
