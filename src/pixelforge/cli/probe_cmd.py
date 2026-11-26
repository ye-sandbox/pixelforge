"""CLI `probe` workflow for exact pixel, layer, histogram, and orphan diagnostics."""

from __future__ import annotations

import difflib
import json
from pathlib import Path

from pixelforge.cli.output import OutputFn, OutputFormat
from pixelforge.core.builder import LayerDiagnostic
from pixelforge.export.bundle import LoadedAsset
from pixelforge.guard.probe import AssetProbeReport, parse_region, probe_asset
from pixelforge.guard.runner import discover_asset_files, load_all_styles, load_asset_module


def _suggest_close(name: str, candidates: list[str]) -> str:
    matches = difflib.get_close_matches(name, candidates, n=3, cutoff=0.5)
    if not matches:
        return ""
    return f"; did you mean {', '.join(repr(m) for m in matches)}?"


def _bbox_dict(bbox: tuple[int, int, int, int] | None) -> dict[str, int] | None:
    if bbox is None:
        return None
    return {"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]}


def _format_bbox(bbox: tuple[int, int, int, int] | None) -> str:
    if bbox is None:
        return "none"
    return f"({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})"


def _layer_to_dict(layer: LayerDiagnostic) -> dict[str, object]:
    return {
        "name": layer.name,
        "role": layer.role,
        "depth": layer.depth,
        "offset": [layer.offset[0], layer.offset[1]],
        "size": [layer.size[0], layer.size[1]],
        "opaque_bbox": _bbox_dict(layer.opaque_bbox),
        "pixel_count": layer.pixel_count,
    }


def _report_to_dict(report: AssetProbeReport) -> dict[str, object]:
    return {
        "asset_id": report.asset_id,
        "style_id": report.style_id,
        "state": report.state,
        "frame": report.frame,
        "width": report.width,
        "height": report.height,
        "opaque_pixels": report.opaque_pixels,
        "total_pixels": report.total_pixels,
        "coverage_pct": report.coverage_pct,
        "opaque_bbox": _bbox_dict(report.opaque_bbox),
        "region": {
            "x": report.region.x,
            "y": report.region.y,
            "w": report.region.w,
            "h": report.region.h,
            "rows": list(report.region.rows),
            "legend": [
                {
                    "symbol": item.symbol,
                    "index": item.index,
                    "name": item.name,
                    "hex": item.hex,
                    "flags": list(item.flags),
                    "emissive": item.emissive,
                }
                for item in report.region.legend
            ],
        },
        "histogram": [
            {
                "index": item.index,
                "name": item.name,
                "hex": item.hex,
                "flags": list(item.flags),
                "emissive": item.emissive,
                "count": item.count,
                "pct": item.pct,
            }
            for item in report.histogram
        ],
        "orphan_pixels": [[x, y] for x, y in report.orphan_pixels],
        "layers": [_layer_to_dict(layer) for layer in report.layers],
        "anchors": [
            {
                "name": anchor.name,
                "x": anchor.x,
                "y": anchor.y,
                "kind": anchor.kind,
                "dir": list(anchor.dir) if anchor.dir is not None else None,
            }
            for anchor in report.anchors
        ],
        "hitboxes": [
            {
                "name": hb.name,
                "x": hb.x,
                "y": hb.y,
                "w": hb.w,
                "h": hb.h,
                "kind": hb.kind,
            }
            for hb in report.hitboxes
        ],
    }


def _emit_llm(report: AssetProbeReport, *, show_layers: bool, out: OutputFn) -> None:
    out(
        f"probe asset={report.asset_id} style={report.style_id} "
        f"state={report.state} frame={report.frame} size={report.width}x{report.height} "
        f"opaque={report.opaque_pixels}/{report.total_pixels} ({report.coverage_pct}%) "
        f"bbox={_format_bbox(report.opaque_bbox)}"
    )
    reg = report.region
    y_width = max(2, len(str(reg.y + reg.h - 1)))
    out(f"slice region=({reg.x},{reg.y},{reg.w},{reg.h}) x=[{reg.x}..{reg.x + reg.w - 1}]:")
    for offset_y, row in enumerate(reg.rows):
        out(f"  y={reg.y + offset_y:0{y_width}d}: {row}")

    legend_parts = [".=TRANSPARENT(255)"]
    for item in reg.legend:
        extra = ",".join(item.flags)
        meta = f"{item.hex},{extra}" if extra else item.hex
        em_tag = " [EMISSIVE]" if item.emissive else ""
        legend_parts.append(f"{item.symbol}={item.index}:{item.name}({meta}){em_tag}")
    out(f"legend: {' '.join(legend_parts)}")

    if report.histogram:
        hist_parts = [
            f"{item.index}:{item.name}"
            f"({item.count},{item.pct}%{',EMISSIVE' if item.emissive else ''})"
            for item in report.histogram
        ]
        out(f"histogram: {' '.join(hist_parts)}")
    else:
        out("histogram: (empty)")

    if report.orphan_pixels:
        coords = " ".join(f"({x},{y})" for x, y in report.orphan_pixels)
        out(f"orphans count={len(report.orphan_pixels)} coords={coords}")
    else:
        out("orphans count=0")

    if show_layers:
        out(f"layers count={len(report.layers)}:")
        for layer in report.layers:
            out(
                f"  layer={layer.name} role={layer.role} depth={layer.depth} "
                f"bbox={_format_bbox(layer.opaque_bbox)} pixels={layer.pixel_count}"
            )


def _emit_human(report: AssetProbeReport, *, show_layers: bool, out: OutputFn) -> None:
    out(
        f"Probe: {report.asset_id} ({report.style_id}) | state={report.state} frame={report.frame} "
        f"| {report.width}x{report.height} | opaque={report.opaque_pixels}/{report.total_pixels} "
        f"({report.coverage_pct}%) | bbox={_format_bbox(report.opaque_bbox)}"
    )
    reg = report.region
    y_width = max(2, len(str(reg.y + reg.h - 1)))
    out(f"ASCII Slice (x={reg.x}..{reg.x + reg.w - 1}, y={reg.y}..{reg.y + reg.h - 1}):")
    for offset_y, row in enumerate(reg.rows):
        out(f"  y={reg.y + offset_y:0{y_width}d} | {row}")

    out("Palette Legend:")
    out("  . -> 255:TRANSPARENT")
    for item in reg.legend:
        em_tag = " [EMISSIVE]" if item.emissive else ""
        flags = f" flags={','.join(item.flags)}" if item.flags else ""
        out(f"  {item.symbol} -> {item.index}:{item.name} ({item.hex}){flags}{em_tag}")

    out("Token Usage Histogram:")
    if not report.histogram:
        out("  (no opaque pixels)")
    else:
        for item in report.histogram:
            em_tag = " [EMISSIVE]" if item.emissive else ""
            out(
                f"  {item.index:>3}:{item.name:<18} {item.count:>6} px ({item.pct:>5.2f}%) "
                f"{item.hex}{em_tag}"
            )

    if report.orphan_pixels:
        coords = ", ".join(f"({x}, {y})" for x, y in report.orphan_pixels)
        out(f"Orphan Pixels ({len(report.orphan_pixels)}): {coords}")
    else:
        out("Orphan Pixels: 0")

    if show_layers:
        out(f"Layers ({len(report.layers)}):")
        if not report.layers:
            out("  (no layers recorded)")
        else:
            for layer in report.layers:
                indent = "  " * (layer.depth + 1)
                out(
                    f"{indent}{layer.name} [{layer.role}] bbox={_format_bbox(layer.opaque_bbox)} "
                    f"pixels={layer.pixel_count}"
                )


def probe_asset_workflow(
    root: Path,
    *,
    asset_id: str,
    region: str | None = None,
    state: str | None = None,
    frame: int = 0,
    show_layers: bool = False,
    output_format: OutputFormat = "llm",
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Load an asset, probe its pixels/layers/histogram/orphans, and emit formatted diagnostics."""
    styles = load_all_styles(root / "styles")
    asset_files = discover_asset_files(root / "assets")
    loaded_assets: dict[str, LoadedAsset] = {}
    for asset_path in asset_files:
        loaded = load_asset_module(asset_path)
        loaded_assets[loaded.SPEC.id] = loaded

    target = loaded_assets.get(asset_id)
    if target is None:
        suggestion = _suggest_close(asset_id, sorted(loaded_assets.keys()))
        err(f"Unknown asset {asset_id!r}{suggestion}")
        return 1

    style = styles.get(target.SPEC.style_id)
    if style is None:
        err(f"Missing StylePack {target.SPEC.style_id!r} for asset {asset_id!r}")
        return 1

    parsed_region: tuple[int, int, int, int] | None = None
    if region is not None:
        try:
            parsed_region = parse_region(region, target.SPEC.width, target.SPEC.height)
        except ValueError as exc:
            err(str(exc))
            return 2

    try:
        report = probe_asset(
            target,
            style,
            state=state,
            frame=frame,
            region=parsed_region,
        )
    except ValueError as exc:
        err(str(exc))
        return 2

    if output_format == "json":
        out(json.dumps(_report_to_dict(report), indent=2))
    elif output_format == "human":
        _emit_human(report, show_layers=show_layers, out=out)
    else:
        _emit_llm(report, show_layers=show_layers, out=out)
    return 0
