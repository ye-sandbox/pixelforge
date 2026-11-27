"""Reproducible multi-genre evaluation harness scoring craft lints and 5-axis critic verdicts."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import httpx2
import numpy as np
from pydantic import BaseModel, Field

from pixelforge.core.types import TRANSPARENT_INDEX, StylePack
from pixelforge.export.bundle import LoadedAsset, RenderedFrame, render_asset_frames
from pixelforge.export.contact_sheet import generate_contact_sheet_from_frames
from pixelforge.guard.ast_rules import check_ast_file
from pixelforge.guard.critic import (
    CriticAssetInput,
    CriticCategory,
    CriticConfig,
    CriticCriteria,
    CriticVerdict,
    infer_critic_category,
    score_asset_via_hydra,
)
from pixelforge.guard.runner import (
    discover_asset_files,
    discover_style_files,
    load_asset_module,
    load_style_module,
)
from pixelforge.guard.runtime_rules import check_asset_runtime
from pixelforge.guard.types import GuardViolation

EvalMode = Literal["offline", "hydra"]
EvalFormat = Literal["llm", "json", "human"]


@dataclass(frozen=True)
class EvalCase:
    """Single reproducible multi-genre benchmark target."""

    asset_id: str
    genre: str
    category: CriticCategory
    style_id: str
    min_critic_score: int = 70
    strict_craft: bool = True


DEFAULT_EVAL_CASES: Final[tuple[EvalCase, ...]] = (
    EvalCase(
        asset_id="sysadmin_avatar",
        genre="homelab-character",
        category="character",
        style_id="homelab-16bit",
    ),
    EvalCase(
        asset_id="retro_pocket_slime",
        genre="retro-handheld",
        category="character",
        style_id="retro-pocket-4",
    ),
    EvalCase(
        asset_id="ink_1bit_knight",
        genre="1bit-side",
        category="character",
        style_id="ink-1bit",
    ),
    EvalCase(
        asset_id="ai_cluster_node_iso",
        genre="homelab-iso",
        category="iso_prop",
        style_id="homelab-16bit",
    ),
    EvalCase(
        asset_id="dungeon_chest",
        genre="topdown-rpg",
        category="iso_prop",
        style_id="topdown-rpg",
    ),
    EvalCase(
        asset_id="cozy_teahouse_lantern_iso",
        genre="cozy-pastel",
        category="iso_prop",
        style_id="cozy-pastel",
    ),
    EvalCase(
        asset_id="scifi_neon_terminal",
        genre="scifi-neon",
        category="iso_prop",
        style_id="scifi-neon",
    ),
    EvalCase(
        asset_id="endesga_forge_anvil",
        genre="fantasy-forge",
        category="iso_prop",
        style_id="endesga-32",
    ),
    EvalCase(
        asset_id="hud_icons_16",
        genre="ui-icons",
        category="ui_tilemap",
        style_id="homelab-16bit",
    ),
    EvalCase(
        asset_id="hud_button_9slice",
        genre="ui-9slice",
        category="ui_tilemap",
        style_id="homelab-16bit",
    ),
)


class EvalCaseResult(BaseModel):
    """Per-asset craft lint and 5-axis critic evaluation result."""

    asset_id: str
    genre: str
    category: CriticCategory
    style_id: str
    craft_passed: bool
    craft_errors: int = Field(ge=0)
    craft_warnings: int = Field(ge=0)
    craft_rules: list[str] = Field(default_factory=list)
    critic_verdict: CriticVerdict
    passed: bool


class EvalBenchmarkReport(BaseModel):
    """Aggregated multi-genre evaluation report across craft lints and 5-axis critic."""

    mode: EvalMode
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    mean_critic_score: float = Field(ge=0.0, le=100.0)
    craft_pass_rate: float = Field(ge=0.0, le=1.0)
    critic_pass_rate: float = Field(ge=0.0, le=1.0)
    passed: bool
    results: list[EvalCaseResult] = Field(default_factory=lambda: list[EvalCaseResult]())


def _clamp_axis(value: int) -> int:
    return max(0, min(20, value))


def _count_rule_hits(violations: Sequence[GuardViolation]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for v in violations:
        counts[v.rule] = counts.get(v.rule, 0) + 1
    return counts


def score_asset_deterministic(
    asset: LoadedAsset,
    frames: Sequence[RenderedFrame],
    style: StylePack,
    violations: Sequence[GuardViolation],
    *,
    category: CriticCategory | None = None,
    threshold: int = 70,
) -> CriticVerdict:
    """Compute a deterministic 5-axis `CriticVerdict` from rendered pixels and craft lints."""
    spec = asset.SPEC
    resolved_category = category or infer_critic_category(spec)
    hits = _count_rule_hits(violations)

    # INVARIANT: Penalize each 5-axis dimension strictly from its corresponding deterministic
    # guard/craft rules so offline eval scores remain 100% reproducible without network calls.
    primary = frames[0]
    opaque_ratio = float(np.count_nonzero(primary.surface.data != TRANSPARENT_INDEX)) / float(
        max(1, spec.width * spec.height)
    )
    silhouette_penalty = 6 * hits.get("craft-contrast", 0) + (8 if opaque_ratio < 0.05 else 0)
    lighting_penalty = 5 * hits.get("craft-lighting", 0) + 6 * hits.get("craft-pillow-shading", 0)
    cluster_penalty = 4 * hits.get("craft-jaggies", 0) + 3 * hits.get("orphan-pixel", 0)
    state_penalty = 6 * hits.get("craft-noop-delta", 0)
    anchor_penalty = 5 * hits.get("craft-anchor-fidelity", 0) + 8 * hits.get("missing-anchors", 0)

    criteria = CriticCriteria(
        silhouette_1x=_clamp_axis(20 - silhouette_penalty),
        lighting_consistency=_clamp_axis(20 - lighting_penalty),
        cluster_cleanliness=_clamp_axis(20 - cluster_penalty),
        state_frame_legibility=_clamp_axis(20 - state_penalty),
        anchors_and_palette=_clamp_axis(20 - anchor_penalty),
    )
    score = criteria.total
    findings = [f"[{v.rule}] {v.detail}" for v in violations]
    fixes = [
        f"Resolve {rule} ({count} hit{'s' if count != 1 else ''})"
        for rule, count in sorted(hits.items())
    ]
    strengths = [
        f"Deterministic craft clean across {len(frames)} rendered state/frame cells"
        if not findings
        else f"Evaluated {len(frames)} rendered state/frame cells against {style.id}"
    ]
    summary = (
        f"Offline craft+critic score {score}/100 ({resolved_category}, {style.id})."
        if not findings
        else f"Offline craft+critic score {score}/100 with {len(findings)} finding(s)."
    )
    return CriticVerdict(
        asset_id=spec.id,
        kind="asset",
        category=resolved_category,
        score=score,
        passed=score >= threshold,
        criteria=criteria,
        summary=summary,
        strengths=strengths,
        findings=findings,
        fixes=fixes,
        model="deterministic-craft-v1",
        threshold=threshold,
    )


def _index_workspace_modules(
    root: Path,
) -> tuple[dict[str, StylePack], dict[str, tuple[Path, LoadedAsset]]]:
    styles: dict[str, StylePack] = {}
    for style_path in discover_style_files(root / "styles"):
        pack = load_style_module(style_path)
        styles[pack.id] = pack

    assets: dict[str, tuple[Path, LoadedAsset]] = {}
    for asset_path in discover_asset_files(root / "assets"):
        loaded = load_asset_module(asset_path)
        assets[loaded.SPEC.id] = (asset_path, loaded)
    return styles, assets


def _evaluate_single_case(
    case: EvalCase,
    asset_path: Path,
    loaded: LoadedAsset,
    style: StylePack,
    *,
    critic_config: CriticConfig | None,
    client: httpx2.Client | None,
) -> EvalCaseResult:
    ast_violations = check_ast_file(asset_path, scope="asset")
    runtime_violations = check_asset_runtime(
        loaded,
        style,
        file_path=str(asset_path),
        strict_craft=case.strict_craft,
    )
    all_violations = [*ast_violations, *runtime_violations]
    errors = sum(1 for v in all_violations if v.severity == "error")
    warnings = sum(1 for v in all_violations if v.severity == "warning")
    craft_passed = errors == 0
    craft_rules = sorted({v.rule for v in all_violations})

    frames = render_asset_frames(loaded, style)
    if critic_config is not None:
        sheet = generate_contact_sheet_from_frames(loaded.SPEC, frames, style)
        cfg = CriticConfig(
            base_url=critic_config.base_url,
            api_key=critic_config.api_key,
            model=critic_config.model,
            allow_dev_model=critic_config.allow_dev_model,
            timeout_seconds=critic_config.timeout_seconds,
            threshold=case.min_critic_score,
            session_id=critic_config.session_id,
        )
        verdict = score_asset_via_hydra(
            CriticAssetInput(asset=loaded, contact_sheet_png=sheet.png),
            cfg,
            client=client,
        )
    else:
        verdict = score_asset_deterministic(
            loaded,
            frames,
            style,
            all_violations,
            category=case.category,
            threshold=case.min_critic_score,
        )

    return EvalCaseResult(
        asset_id=case.asset_id,
        genre=case.genre,
        category=case.category,
        style_id=style.id,
        craft_passed=craft_passed,
        craft_errors=errors,
        craft_warnings=warnings,
        craft_rules=craft_rules,
        critic_verdict=verdict,
        passed=craft_passed and verdict.passed,
    )


def run_multi_genre_eval(
    root: Path,
    *,
    cases: Sequence[EvalCase] = DEFAULT_EVAL_CASES,
    critic_config: CriticConfig | None = None,
    client: httpx2.Client | None = None,
) -> EvalBenchmarkReport:
    """Run the reproducible multi-genre benchmark across craft lints and 5-axis critic verdicts."""
    if not cases:
        msg = "cases must contain at least one EvalCase"
        raise ValueError(msg)

    styles, assets = _index_workspace_modules(root)
    results: list[EvalCaseResult] = []
    for case in cases:
        if case.asset_id not in assets:
            msg = f"EvalCase asset_id {case.asset_id!r} not found under {root / 'assets'}"
            raise FileNotFoundError(msg)
        asset_path, loaded = assets[case.asset_id]
        style_id = loaded.SPEC.style_id
        if style_id not in styles:
            msg = f"StylePack {style_id!r} for {case.asset_id!r} not found under {root / 'styles'}"
            raise FileNotFoundError(msg)
        results.append(
            _evaluate_single_case(
                case,
                asset_path,
                loaded,
                styles[style_id],
                critic_config=critic_config,
                client=client,
            )
        )

    total = len(results)
    passed_cases = sum(1 for r in results if r.passed)
    craft_passed_count = sum(1 for r in results if r.craft_passed)
    critic_passed_count = sum(1 for r in results if r.critic_verdict.passed)
    mean_score = sum(r.critic_verdict.score for r in results) / float(total)

    return EvalBenchmarkReport(
        mode="hydra" if critic_config is not None else "offline",
        total_cases=total,
        passed_cases=passed_cases,
        failed_cases=total - passed_cases,
        mean_critic_score=round(mean_score, 2),
        craft_pass_rate=round(craft_passed_count / float(total), 4),
        critic_pass_rate=round(critic_passed_count / float(total), 4),
        passed=passed_cases == total,
        results=results,
    )


def format_eval_report(
    report: EvalBenchmarkReport,
    *,
    output_format: EvalFormat = "llm",
) -> str:
    """Format an `EvalBenchmarkReport` as compact LLM text, strict JSON, or human table."""
    if output_format == "json":
        return report.model_dump_json(indent=2)

    if output_format == "llm":
        lines = [
            f"status={'pass' if report.passed else 'fail'} "
            f"mode={report.mode} cases={report.passed_cases}/{report.total_cases} "
            f"mean_score={report.mean_critic_score:.1f} "
            f"craft_rate={report.craft_pass_rate:.2f} "
            f"critic_rate={report.critic_pass_rate:.2f}",
        ]
        for r in report.results:
            c = r.critic_verdict.criteria
            axes = (
                f"{c.silhouette_1x}/{c.lighting_consistency}/{c.cluster_cleanliness}/"
                f"{c.state_frame_legibility}/{c.anchors_and_palette}"
                if c is not None
                else "n/a"
            )
            craft_tag = "pass" if r.craft_passed else "fail"
            lines.append(
                f"{r.asset_id} genre={r.genre} cat={r.category} style={r.style_id} "
                f"craft={craft_tag}({r.craft_errors}e,{r.craft_warnings}w) "
                f"critic={r.critic_verdict.score}({axes}) pass={str(r.passed).lower()}"
            )
        return "\n".join(lines)

    lines = [
        f"Multi-Genre Eval Benchmark ({report.mode}) — "
        f"{report.passed_cases}/{report.total_cases} passed, "
        f"mean score {report.mean_critic_score:.1f}/100",
    ]
    for r in report.results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(
            f"  [{status}] {r.asset_id:<26} {r.genre:<18} "
            f"craft={r.craft_errors}e/{r.craft_warnings}w  critic={r.critic_verdict.score}/100"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for running the reproducible multi-genre eval harness."""
    parser = argparse.ArgumentParser(description="Run pixelforge multi-genre craft+critic eval.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root path")
    parser.add_argument(
        "--format",
        choices=("llm", "json", "human"),
        default="llm",
        help="Output format",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = run_multi_genre_eval(args.root.resolve())
    sys.stdout.write(format_eval_report(report, output_format=args.format) + "\n")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
