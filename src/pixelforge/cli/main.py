"""Thin CLI entrypoint for pixelforge commands."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pixelforge import __version__
from pixelforge.cli.scaffold import scaffold_project
from pixelforge.cli.settings import HydraSettings, PixelforgeSettings
from pixelforge.cli.workflow import (
    compose_scene_workflow,
    critic_workflow,
    diff_asset,
    parse_mount_arg,
    render_once,
    watch_loop,
)
from pixelforge.export.analyze_ref import analyze_reference_image, parse_sketch_size
from pixelforge.guard.runner import load_all_styles, run_checks


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
    root = _resolve_root(args.root)
    report = run_checks(
        root,
        asset_id=args.asset_id,
        strict_orphans=bool(args.strict_orphans),
    )
    for violation in report.violations:
        target = _err if violation.severity == "error" else _out
        target(violation.format_line())
    _out(
        f"checked {report.assets_checked} asset(s), {report.styles_checked} style(s): "
        f"{report.errors} error(s), {report.warnings} warning(s)"
    )
    return 0 if report.passed else 1


def _cmd_render(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
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
        indexed_ts=bool(args.indexed_ts or args.indexed_ts_lazy),
        indexed_ts_lazy=bool(args.indexed_ts_lazy),
        atlas=args.atlas,
        scale=int(args.scale),
        variant=args.variant,
        out=_out,
        err=_err,
    )


def _cmd_diff(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
    root = _resolve_root(args.root)
    return diff_asset(
        root,
        asset_id=str(args.asset_id),
        base_ref=str(args.base),
        out_dir=_resolve_dir(root, settings.diffs_dir, args.out),
        scale=int(args.scale),
        variant=args.variant,
        json_output=bool(args.json),
        out=_out,
        err=_err,
    )


def _cmd_watch(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
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
        indexed_ts=bool(args.indexed_ts or args.indexed_ts_lazy),
        indexed_ts_lazy=bool(args.indexed_ts_lazy),
        atlas=args.atlas,
        scale=int(args.scale),
        variant=args.variant,
        out=_out,
        err=_err,
        interval=float(args.interval),
        max_cycles=args.max_cycles,
    )


def _cmd_analyze_ref(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
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

    _out(analysis.format_report())
    return 0


def _cmd_compose(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
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
        strict_bounds=bool(args.strict_bounds),
        strict_perspective=bool(args.strict_perspective),
        scale=int(args.scale),
        out_dir=_resolve_dir(root, settings.previews_dir, args.out),
        sheets_dir=_resolve_dir(root, settings.sheets_dir),
        sheet=bool(args.sheet),
        out=_out,
        err=_err,
    )


def _cmd_critic(args: argparse.Namespace) -> int:
    root = _resolve_root(args.root)
    hydra = HydraSettings()
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
        json_output=bool(args.json),
        out=_out,
        err=_err,
    )


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
    render_p.add_argument("--root", default=None, help="Project root directory")

    check_p = sub.add_parser("check", help="Run AST static and runtime guard checks")
    check_p.add_argument("asset_id", nargs="?", default=None, help="Optional asset ID filter")
    check_p.add_argument(
        "--strict-orphans",
        action="store_true",
        help="Treat isolated 1x1 orphan pixels as errors",
    )
    check_p.add_argument("--root", default=None, help="Project root directory")

    diff_p = sub.add_parser("diff", help="Generate visual pixel-diff PNG against a git ref")
    diff_p.add_argument("asset_id", help="Asset ID to compare")
    diff_p.add_argument("--base", default="HEAD", help="Git ref baseline (default: HEAD)")
    diff_p.add_argument("--out", default=None, help="Output directory for diff PNGs")
    diff_p.add_argument("--scale", type=int, default=1, help="Integer nearest-neighbor scale")
    diff_p.add_argument("--variant", default=None, help="Optional StylePack variant name")
    diff_p.add_argument("--json", action="store_true", help="Emit JSON diff summary")
    diff_p.add_argument("--root", default=None, help="Project root directory")

    watch_p = sub.add_parser("watch", help="Watch .asset.py/.style.py and hot-reload outputs")
    watch_p.add_argument("asset_id", nargs="?", default=None, help="Optional asset ID filter")
    watch_p.add_argument("--out", default=None, help="Output directory")
    watch_p.add_argument("--sheet", action="store_true", help="Generate diagnostic .contact.png")
    watch_p.add_argument("--emissive", action="store_true", help="Force emissive mask emission")
    watch_p.add_argument("--lut", action="store_true", help="Emit indexed PNGs + 1D LUT")
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
    compose_p.add_argument("--root", default=None, help="Project root directory")

    critic_p = sub.add_parser(
        "critic",
        help="Score assets via internal hydra-llm-router multimodal critic (OpenAI v1)",
    )
    critic_p.add_argument("asset_id", nargs="?", default=None, help="Optional asset ID filter")
    critic_p.add_argument(
        "--base",
        default=None,
        help="Git ref baseline; when set, scores only changed assets/styles with diff context",
    )
    critic_p.add_argument(
        "--threshold",
        type=int,
        default=70,
        help="Minimum passing visual score 0-100 (default: 70)",
    )
    critic_p.add_argument("--variant", default=None, help="Optional StylePack variant name")
    critic_p.add_argument("--json", action="store_true", help="Emit JSON report")
    critic_p.add_argument("--root", default=None, help="Project root directory")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the pixelforge CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command is None:
        parser.print_help()
        return 0

    settings = PixelforgeSettings()
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

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
