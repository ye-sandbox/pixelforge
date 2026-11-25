"""Thin CLI entrypoint for pixelforge (`init`, `render`, `check`, `diff`, `watch`)."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from pixelforge import __version__
from pixelforge.cli.settings import PixelforgeSettings
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import StylePack
from pixelforge.export.bundle import (
    ExportBundleOptions,
    ExportBundleResult,
    export_asset_bundle,
    render_asset_frames,
    write_export_bundle,
)
from pixelforge.export.contact_sheet import generate_contact_sheet
from pixelforge.export.diff import generate_surface_diff
from pixelforge.export.indexed_ts import export_indexed_ts, write_indexed_ts_bundle
from pixelforge.guard.runner import (
    discover_asset_files,
    discover_style_files,
    load_all_styles,
    load_asset_from_git,
    load_asset_module,
    run_checks,
)


def _out(line: str) -> None:
    sys.stdout.write(f"{line}\n")


def _err(line: str) -> None:
    sys.stderr.write(f"{line}\n")


def _resolve_root(root_arg: str | None) -> Path:
    return Path(root_arg).resolve() if root_arg else Path.cwd()


def _starter_style_source(style_id: str) -> str:
    return f'''"""Starter StylePack for {style_id}."""

from __future__ import annotations

from pixelforge.core.types import PaletteColor, StylePack

STYLE = StylePack(
    id={style_id!r},
    perspective="iso-2:1",
    lighting_angle="top-left",
    outline_index=0,
    palette=(
        PaletteColor(index=0, name="OUTLINE", hex="#0d1117", flags=("outline",)),
        PaletteColor(index=1, name="CHASSIS_DARK", hex="#1f2937", flags=("surface",)),
        PaletteColor(index=2, name="CHASSIS_MID", hex="#374151", flags=("surface",)),
        PaletteColor(index=3, name="CHASSIS_LIGHT", hex="#6b7280", flags=("bright",)),
        PaletteColor(index=4, name="ACCENT_CYAN", hex="#38bdf8", flags=("emissive",)),
    ),
)
'''


def _starter_asset_source(style_id: str) -> str:
    return f'''"""Starter compositional pixel asset."""

from __future__ import annotations

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec

SPEC = AssetSpec(
    id="example_crate",
    style_id={style_id!r},
    perspective="iso-2:1",
    width=24,
    height=24,
    states=("idle",),
    frames=1,
    fps=4,
)


def render(a: Asset) -> None:
    """Render a minimal isometric crate."""
    p = a.pal
    with a.layer("body", outline=p.OUTLINE):
        a.iso_box(
            x=12,
            y=10,
            w=8,
            d=8,
            h=6,
            top=p.CHASSIS_LIGHT,
            left=p.CHASSIS_MID,
            right=p.CHASSIS_DARK,
        )
    a.put(12, 11, p.ACCENT_CYAN)
    a.put(13, 11, p.ACCENT_CYAN)
    a.anchor("foot", 12, 20)
'''


def _write_if_allowed(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _cmd_init(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
    root = _resolve_root(args.root)
    style_id: str = args.style or settings.default_style
    force: bool = bool(args.force)
    slug = style_id.replace("-", "_")

    for d in ("styles", "assets", ".pixelforge"):
        (root / d).mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    style_path = root / "styles" / f"{slug}.style.py"
    asset_path = root / "assets" / "example_crate.asset.py"
    env_example = root / ".env.example"

    if _write_if_allowed(style_path, _starter_style_source(style_id), force=force):
        created.append(style_path)
    if _write_if_allowed(asset_path, _starter_asset_source(style_id), force=force):
        created.append(asset_path)
    env_content = (
        "PIXELFORGE_OUT_DIR=dist\n"
        "PIXELFORGE_SHEETS_DIR=.pixelforge/sheets\n"
        f"PIXELFORGE_DEFAULT_STYLE={style_id}\n"
    )
    if _write_if_allowed(env_example, env_content, force=force):
        created.append(env_example)

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


def _render_once(
    root: Path,
    *,
    asset_id: str | None,
    out_dir: Path,
    sheets_dir: Path,
    previews_dir: Path,
    sheet: bool,
    animate: bool,
    emissive: bool | None,
    lut: bool,
    indexed_ts: bool,
    scale: int,
    variant: str | None,
) -> int:
    styles = load_all_styles(root / "styles")
    asset_files = discover_asset_files(root / "assets")
    if not asset_files:
        _err("No .asset.py files found under assets/")
        return 1

    options = ExportBundleOptions(
        variant=variant,
        scale=scale,
        emissive=emissive,
        lut=lut,
        animate=animate,
    )

    bundles_by_style: dict[str, tuple[StylePack, list[ExportBundleResult]]] = {}
    rendered_count = 0

    for asset_path in asset_files:
        loaded = load_asset_module(asset_path)
        if asset_id is not None and loaded.SPEC.id != asset_id:
            continue

        style = styles.get(loaded.SPEC.style_id)
        if style is None:
            _err(
                f"{asset_path}:1 [missing-style] Referenced style "
                f"{loaded.SPEC.style_id!r} not found in styles/"
            )
            return 1

        bundle = export_asset_bundle(loaded, style, options)
        write_export_bundle(
            bundle,
            out_dir,
            previews_dir=previews_dir if animate else None,
        )
        if sheet:
            sheets_dir.mkdir(parents=True, exist_ok=True)
            contact = generate_contact_sheet(loaded, style)
            (sheets_dir / f"{loaded.SPEC.id}.contact.png").write_bytes(contact.png)

        if style.id not in bundles_by_style:
            bundles_by_style[style.id] = (style, [])
        bundles_by_style[style.id][1].append(bundle)
        rendered_count += 1
        _out(f"rendered {loaded.SPEC.id} -> {out_dir}")

    if rendered_count == 0:
        _err(f"Asset {asset_id!r} not found under assets/")
        return 1

    if indexed_ts:
        for style, style_bundles in bundles_by_style.values():
            ts_result = export_indexed_ts(style_bundles, style)
            write_indexed_ts_bundle(ts_result, out_dir / "indexed")

    return 0


def _cmd_render(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
    root = _resolve_root(args.root)
    out_dir = Path(args.out) if args.out else settings.out_dir
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    sheets_dir = (
        settings.sheets_dir if settings.sheets_dir.is_absolute() else root / settings.sheets_dir
    )
    previews_dir = (
        settings.previews_dir
        if settings.previews_dir.is_absolute()
        else root / settings.previews_dir
    )
    emissive: bool | None = True if args.emissive else None
    return _render_once(
        root,
        asset_id=args.asset_id,
        out_dir=out_dir,
        sheets_dir=sheets_dir,
        previews_dir=previews_dir,
        sheet=bool(args.sheet),
        animate=bool(args.animate),
        emissive=emissive,
        lut=bool(args.lut),
        indexed_ts=bool(args.indexed_ts),
        scale=int(args.scale),
        variant=args.variant,
    )


def _cmd_diff(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
    root = _resolve_root(args.root)
    styles = load_all_styles(root / "styles")
    asset_id: str = args.asset_id
    target_path: Path | None = None
    for candidate in discover_asset_files(root / "assets"):
        loaded = load_asset_module(candidate)
        if loaded.SPEC.id == asset_id:
            target_path = candidate
            break

    if target_path is None:
        _err(f"Asset {asset_id!r} not found under assets/")
        return 1

    current_asset = load_asset_module(target_path)
    style = styles.get(current_asset.SPEC.style_id)
    if style is None:
        _err(f"Referenced style {current_asset.SPEC.style_id!r} not found in styles/")
        return 1

    baseline_asset = load_asset_from_git(root, target_path, ref=args.base)
    current_frames = render_asset_frames(current_asset, style, variant=args.variant)
    baseline_map = (
        {(f.state, f.frame): f.surface for f in render_asset_frames(baseline_asset, style)}
        if baseline_asset is not None
        else {}
    )

    out_dir = Path(args.out) if args.out else settings.diffs_dir
    if not out_dir.is_absolute():
        out_dir = root / out_dir
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
            variant=args.variant,
            scale=int(args.scale),
        )
        suffix = (
            f"{frame.state}.diff.png"
            if current_asset.SPEC.frames == 1
            else f"{frame.state}_f{frame.frame}.diff.png"
        )
        diff_path = out_dir / f"{current_asset.SPEC.id}_{suffix}"
        diff_path.write_bytes(diff.png)
        _out(f"diff {diff_path}: {diff.changed_pixels}/{diff.total_pixels} changed pixel(s)")
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
    interval: float = 0.5,
    max_cycles: int | None = None,
) -> int:
    """Poll `.asset.py` and `.style.py` mtimes and re-check + re-render on changes."""
    last_mtimes = _snapshot_mtimes(root)
    report = run_checks(root, asset_id=asset_id)
    if report.passed:
        _render_once(
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
        )
    else:
        for v in report.violations:
            _err(v.format_line())

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
                (_err if v.severity == "error" else _out)(v.format_line())
            if report.passed:
                _render_once(
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
                )
    except KeyboardInterrupt:
        _out("watch stopped")
    return 0


def _cmd_watch(args: argparse.Namespace, settings: PixelforgeSettings) -> int:
    root = _resolve_root(args.root)
    out_dir = Path(args.out) if args.out else settings.out_dir
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    sheets_dir = (
        settings.sheets_dir if settings.sheets_dir.is_absolute() else root / settings.sheets_dir
    )
    previews_dir = (
        settings.previews_dir
        if settings.previews_dir.is_absolute()
        else root / settings.previews_dir
    )
    emissive: bool | None = True if args.emissive else None
    return watch_loop(
        root,
        asset_id=args.asset_id,
        out_dir=out_dir,
        sheets_dir=sheets_dir,
        previews_dir=previews_dir,
        sheet=bool(args.sheet),
        emissive=emissive,
        lut=bool(args.lut),
        indexed_ts=bool(args.indexed_ts),
        scale=int(args.scale),
        variant=args.variant,
        interval=float(args.interval),
        max_cycles=args.max_cycles,
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
    render_p.add_argument("--animate", action="store_true", help="Generate animated GIF previews")
    render_p.add_argument("--emissive", action="store_true", help="Force emissive mask emission")
    render_p.add_argument("--lut", action="store_true", help="Emit indexed PNGs + 1D LUT")
    render_p.add_argument(
        "--indexed-ts",
        action="store_true",
        help="Emit RLE Uint8Array + palette/manifest TypeScript modules",
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
    watch_p.add_argument("--scale", type=int, default=1, help="Integer nearest-neighbor scale")
    watch_p.add_argument("--variant", default=None, help="Optional StylePack variant name")
    watch_p.add_argument("--interval", type=float, default=0.5, help="Poll interval in seconds")
    watch_p.add_argument("--max-cycles", type=int, default=None, help="Stop after N poll cycles")
    watch_p.add_argument("--root", default=None, help="Project root directory")

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

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
