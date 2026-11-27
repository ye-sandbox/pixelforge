"""Shared CLI output format resolution and LLM-first formatters."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pixelforge.export.analyze_ref import ReferenceAnalysis
from pixelforge.guard.runner import CheckReport

OutputFormat = Literal["llm", "json", "human"]
OutputFn = Callable[[str], None]

_VIOLATION_HINTS: dict[str, str] = {
    "forbidden-import": (
        "Remove disallowed import; use pixelforge.core primitives and StylePack tokens."
    ),
    "forbidden-call": (
        "Replace non-deterministic or I/O call with seeded a.rng() and pure pixel ops."
    ),
    "forbidden-global": (
        "Move mutable state inside render(a) or use module-level constants/dataclasses."
    ),
    "raw-hex": "Replace raw hex color string with a StylePack token (e.g. a.pal.TOKEN).",
    "syntax-error": "Fix Python syntax error in module before re-running check.",
    "load-error": "Ensure module exports valid SPEC/STYLE/SCENE and imports cleanly.",
    "duplicate-id": "Assign a unique id to each StylePack, AssetSpec, and SceneSpec.",
    "asset-not-found": "Verify the asset_id exists in assets/*.asset.py or omit filter.",
    "valid-anchors": "Keep anchors and hitboxes within canvas bounds and required names.",
    "exact-dimensions": "Draw within declared AssetSpec width/height without resizing surface.",
    "closed-palette": (
        "Use only palette indices 0..254 from active StylePack or TRANSPARENT_INDEX (255)."
    ),
    "binary-alpha": (
        "Ensure every pixel is either opaque (255) or transparent (0) with zero partial alpha."
    ),
    "bit-determinism": (
        "Remove non-deterministic branching/state so repeated renders are bit-identical."
    ),
    "orphan-pixels": "Connect isolated 1x1 pixels to adjacent geometry or remove stray pixels.",
    "missing-style": "Ensure SPEC.style_id matches a valid StylePack in styles/*.style.py.",
    "missing-parent": "Ensure SCENE.parent_id matches an existing AssetSpec id.",
    "scene-error": "Verify mount anchors, bounds, and perspective alignment in *.scene.py.",
    "duplicate-mount": "Assign each SceneMountSpec in SCENE.mounts to a distinct parent anchor.",
    "scene-anchor-bounds": (
        "Place mounted parent anchors inside the parent asset's opaque bounding box."
    ),
    "scene-bounds": (
        "Adjust mount offsets, prop_anchor, or parent canvas size so props stay within bounds."
    ),
    "scene-perspective": (
        "Mount only props matching the parent asset's perspective (or update SceneSpec)."
    ),
    "scene-occlusion": (
        "Adjust z_index, anchor spacing, or offsets to reduce prop overlap below threshold."
    ),
    "duplicate-portal": "Assign each ScenePortalSpec in SCENE.portals a unique id.",
    "scene-portal-self-loop": (
        "Target another scene id or a distinct target_portal_id on self-transitions."
    ),
    "scene-portal-anchor": (
        "Ensure portal.anchor exists on the parent asset and lies inside its opaque bbox."
    ),
    "scene-portal-target": (
        "Ensure portal.target_scene_id matches an existing *.scene.py SceneSpec.id."
    ),
    "scene-portal-target-portal": (
        "Ensure portal.target_portal_id matches a declared portal id in the target scene."
    ),
    "scene-portal-reciprocal": (
        "Add a matching reciprocal portal in the target scene for bidirectional portals."
    ),
    "scene-graph-unreachable": (
        "Connect isolated scenes with incoming or outgoing portals in multi-scene worlds."
    ),
    "palette-stub-missing": (
        "Run `pixelforge check --sync-stubs` to generate typed *_palette.py stubs."
    ),
    "palette-stub-stale": (
        "Run `pixelforge check --sync-stubs` to regenerate out-of-date *_palette.py stubs."
    ),
    "emissive-bleed": (
        "Replace emissive tokens on large painted surfaces with non-emissive paint tokens."
    ),
    "canvas-coverage": (
        "Adjust asset geometry/margins so opaque coverage stays balanced inside the canvas."
    ),
    "door-obstruction": "Move furniture or mounted props out of the doorway clearance zone.",
    "furniture-overlap": ("Separate overlapping furniture hitboxes or adjust furniture placement."),
    "craft-jaggies": (
        "Smooth double-pixel L-corner jaggies on outlines into clean 1px curves/diagonals."
    ),
    "craft-pillow-shading": (
        "Replace concentric edge-following shading with directional volume shading."
    ),
    "craft-lighting": ("Align highlight and shadow placement with StylePack.lighting_angle."),
    "craft-contrast": (
        "Add outline or midtone contrast so 1x silhouette reads on dark and light backgrounds."
    ),
    "craft-noop-delta": (
        "Ensure distinct states and animation frames produce visible pixel differences."
    ),
    "craft-anchor-fidelity": (
        "Keep anchors near the opaque silhouette and hitboxes aligned over actual geometry."
    ),
}


def add_format_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach `--format`, `--json`, and `--human` output flags to a subcommand parser."""
    parser.add_argument(
        "--format",
        choices=("llm", "json", "human"),
        default=None,
        help="Output format (default: llm)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit strict JSON output (alias for --format json)",
    )
    parser.add_argument(
        "--human",
        action="store_true",
        help="Emit human-readable output (alias for --format human)",
    )


def resolve_output_format(args: argparse.Namespace) -> OutputFormat:
    """Resolve `--format` / `--json` / `--human` flags into a canonical `OutputFormat`."""
    fmt_raw: object = getattr(args, "format", None)
    as_json = bool(getattr(args, "json", False))
    as_human = bool(getattr(args, "human", False))

    if as_json and as_human:
        msg = "Cannot combine --json and --human"
        raise ValueError(msg)

    if fmt_raw is not None:
        if as_json and fmt_raw != "json":
            msg = f"Conflicting output flags: --format {fmt_raw} and --json"
            raise ValueError(msg)
        if as_human and fmt_raw != "human":
            msg = f"Conflicting output flags: --format {fmt_raw} and --human"
            raise ValueError(msg)
        if fmt_raw == "json":
            return "json"
        if fmt_raw == "human":
            return "human"
        if fmt_raw == "llm":
            return "llm"
        msg = f"Unsupported output format: {fmt_raw!r}"
        raise ValueError(msg)

    if as_json:
        return "json"
    if as_human:
        return "human"
    return "llm"


def violation_hint(rule: str) -> str:
    """Return a concise actionable fix hint for a guard rule."""
    return _VIOLATION_HINTS.get(rule, "Inspect the flagged line and fix the rule violation.")


def emit_check_report(
    report: CheckReport,
    *,
    output_format: OutputFormat,
    out: OutputFn,
    err: OutputFn,
) -> None:
    """Emit `pixelforge check` report in `llm`, `json`, or `human` format."""
    if output_format == "json":
        payload = {
            "passed": report.passed,
            "assets_checked": report.assets_checked,
            "styles_checked": report.styles_checked,
            "errors": report.errors,
            "warnings": report.warnings,
            "violations": [
                {
                    "file": v.file,
                    "line": v.line,
                    "col": v.col,
                    "rule": v.rule,
                    "severity": v.severity,
                    "detail": v.detail,
                    "hint": violation_hint(v.rule),
                }
                for v in report.violations
            ],
        }
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        for violation in report.violations:
            target = err if violation.severity == "error" else out
            target(violation.format_line())
        out(
            f"checked {report.assets_checked} asset(s), {report.styles_checked} style(s): "
            f"{report.errors} error(s), {report.warnings} warning(s)"
        )
        return

    for violation in report.violations:
        tag = "ERR" if violation.severity == "error" else "WARN"
        target = err if violation.severity == "error" else out
        hint = violation_hint(violation.rule)
        target(
            f"{tag} {violation.file}:{violation.line}:{violation.col} "
            f"rule={violation.rule} msg={violation.detail} fix={hint}"
        )
    status = "pass" if report.passed else "fail"
    out(
        f"status={status} assets={report.assets_checked} styles={report.styles_checked} "
        f"errors={report.errors} warnings={report.warnings}"
    )


def emit_reference_analysis(
    analysis: ReferenceAnalysis,
    *,
    output_format: OutputFormat,
    out: OutputFn,
    scaffold_source: str | None = None,
    scaffold_path: Path | None = None,
    spr_snippet: str | None = None,
) -> None:
    """Emit `pixelforge analyze-ref` output in `llm`, `json`, or `human` format."""
    if output_format == "json":
        payload: dict[str, object] = {
            "ephemeral": True,
            "style_id": analysis.style_id,
            "source_width": analysis.source_width,
            "source_height": analysis.source_height,
            "aspect_ratio": round(analysis.aspect_ratio, 6),
            "simplified_ratio": analysis.simplified_ratio,
            "target_width": analysis.target_width,
            "target_height": analysis.target_height,
            "histogram": [
                {
                    "token": entry.token,
                    "index": entry.index,
                    "hex": entry.hex,
                    "pixels": entry.pixels,
                    "percentage": round(entry.percentage, 2),
                }
                for entry in analysis.histogram
            ],
            "legend": analysis.legend,
            "ascii_sketch": list(analysis.ascii_sketch),
        }
        if analysis.trim_bbox is not None:
            payload["trim_bbox"] = list(analysis.trim_bbox)
        if spr_snippet is not None:
            payload["spr_snippet"] = spr_snippet
        if scaffold_source is not None:
            payload["scaffold_source"] = scaffold_source
        if scaffold_path is not None:
            payload["scaffold_path"] = str(scaffold_path)
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        out(analysis.format_report())
        if spr_snippet is not None:
            out("\n# --- spr() snippet ---")
            out(spr_snippet)
        if scaffold_path is not None:
            out(f"\nscaffold_written: {scaffold_path}")
        if scaffold_source is not None:
            out("\n# --- scaffolded .asset.py ---")
            out(scaffold_source)
        return

    sym_by_token = {token: sym for sym, token in analysis.legend.items()}
    trim_part = f" trim={analysis.trim_bbox}" if analysis.trim_bbox is not None else ""
    out(
        f"ephemeral=true style={analysis.style_id} "
        f"src={analysis.source_width}x{analysis.source_height} "
        f"ratio={analysis.aspect_ratio:.4f}({analysis.simplified_ratio}) "
        f"sketch={analysis.target_width}x{analysis.target_height}{trim_part}"
    )
    if analysis.histogram:
        tokens_summary = " ".join(
            f"{sym_by_token.get(e.token, '?')}={e.token}({e.hex},{e.pixels}px,{e.percentage:.1f}%)"
            for e in analysis.histogram
        )
        out(f"tokens: {tokens_summary}")
    else:
        out("tokens: none")
    out("ascii:")
    for row in analysis.ascii_sketch:
        out(row)
    if spr_snippet is not None:
        out("spr_snippet:")
        out(spr_snippet)
    if scaffold_path is not None:
        out(f"scaffold_path={scaffold_path}")
    if scaffold_source is not None:
        out("scaffold_source:")
        out(scaffold_source)
