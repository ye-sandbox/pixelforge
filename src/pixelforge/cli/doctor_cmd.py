"""CLI `doctor` environment and repository health diagnostics."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pixelforge.cli.output import OutputFn, OutputFormat
from pixelforge.cli.settings import load_hydra_settings
from pixelforge.core.palette_stub import generate_palette_stub, palette_stub_path
from pixelforge.guard.runner import (
    discover_asset_files,
    discover_scene_files,
    discover_style_files,
    load_asset_module,
    load_scene_module,
    load_style_module,
)

DoctorStatus = Literal["pass", "warn", "fail"]
ToolRunner = Callable[[list[str]], tuple[int, str]]


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """Single health check result emitted by `pixelforge doctor`."""

    name: str
    status: DoctorStatus
    detail: str
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Aggregated health report for `pixelforge doctor`."""

    root: str
    passed: bool
    pass_count: int
    warn_count: int
    fail_count: int
    checks: tuple[DoctorCheck, ...]


def _default_run_cmd(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=5.0,
        check=False,
    )
    output = (proc.stdout or proc.stderr or "").strip().splitlines()
    first_line = output[0].strip() if output else ""
    return proc.returncode, first_line


def _check_toolchain_binary(
    tool: str,
    *,
    which: Callable[[str], str | None],
    run_cmd: ToolRunner,
) -> DoctorCheck:
    exe = which(tool)
    if exe is None:
        return DoctorCheck(
            name=f"toolchain:{tool}",
            status="fail",
            detail=f"{tool} not found on PATH",
            hint=f"Install {tool} or run via 'uv run pixelforge doctor'.",
        )
    try:
        code, line = run_cmd([exe, "--version"])
    except (OSError, subprocess.SubprocessError) as exc:
        return DoctorCheck(
            name=f"toolchain:{tool}",
            status="fail",
            detail=f"failed to execute {tool} --version ({exc})",
            hint=f"Verify {tool} installation on PATH.",
        )
    if code != 0:
        return DoctorCheck(
            name=f"toolchain:{tool}",
            status="fail",
            detail=f"{tool} --version exited with code {code}",
            hint=f"Reinstall or repair {tool}.",
        )
    return DoctorCheck(
        name=f"toolchain:{tool}",
        status="pass",
        detail=line or f"{tool} available at {exe}",
    )


def _check_palette_stubs(root: Path) -> DoctorCheck:
    style_files = discover_style_files(root / "styles")
    if not style_files:
        return DoctorCheck(
            name="palette-stubs",
            status="warn",
            detail="no *.style.py files found in styles/",
            hint="Run 'pixelforge init' or 'pixelforge new style <name>' to create a StylePack.",
        )

    missing: list[str] = []
    stale: list[str] = []
    load_errors: list[str] = []

    for style_path in style_files:
        try:
            pack = load_style_module(style_path)
        except Exception as exc:
            load_errors.append(f"{style_path.name}: {exc}")
            continue
        stub_path = palette_stub_path(style_path)
        expected = generate_palette_stub(pack)
        if not stub_path.is_file():
            missing.append(stub_path.name)
        elif stub_path.read_text(encoding="utf-8") != expected:
            stale.append(stub_path.name)

    if load_errors or stale:
        parts: list[str] = []
        if load_errors:
            parts.append(f"load_errors=[{'; '.join(load_errors)}]")
        if stale:
            parts.append(f"stale=[{', '.join(stale)}]")
        if missing:
            parts.append(f"missing=[{', '.join(missing)}]")
        return DoctorCheck(
            name="palette-stubs",
            status="fail",
            detail="; ".join(parts),
            hint="Run 'pixelforge check --sync-stubs' to regenerate *_palette.py stubs.",
        )

    if missing:
        return DoctorCheck(
            name="palette-stubs",
            status="warn",
            detail=f"missing=[{', '.join(missing)}]",
            hint="Run 'pixelforge check --sync-stubs' to generate typed *_palette.py stubs.",
        )

    return DoctorCheck(
        name="palette-stubs",
        status="pass",
        detail=f"{len(style_files)} palette stub(s) present and up to date",
    )


def _check_duplicate_ids(root: Path) -> DoctorCheck:
    style_files = discover_style_files(root / "styles")
    asset_files = discover_asset_files(root / "assets")
    scene_files = discover_scene_files(root / "assets")

    duplicates: list[str] = []
    load_errors: list[str] = []

    style_origins: dict[str, Path] = {}
    for style_path in style_files:
        try:
            pack = load_style_module(style_path)
        except Exception as exc:
            load_errors.append(f"{style_path.name}: {exc}")
            continue
        if pack.id in style_origins:
            duplicates.append(
                f"style {pack.id!r} ({style_path.name} vs {style_origins[pack.id].name})"
            )
        else:
            style_origins[pack.id] = style_path

    module_origins: dict[str, Path] = {}
    for asset_path in asset_files:
        try:
            loaded = load_asset_module(asset_path)
        except Exception as exc:
            load_errors.append(f"{asset_path.name}: {exc}")
            continue
        spec_id = loaded.SPEC.id
        if spec_id in module_origins:
            duplicates.append(
                f"asset {spec_id!r} ({asset_path.name} vs {module_origins[spec_id].name})"
            )
        else:
            module_origins[spec_id] = asset_path

    for scene_path in scene_files:
        try:
            loaded_scene = load_scene_module(scene_path)
        except Exception as exc:
            load_errors.append(f"{scene_path.name}: {exc}")
            continue
        scene_id = loaded_scene.SCENE.id
        if scene_id in module_origins:
            duplicates.append(
                f"scene {scene_id!r} ({scene_path.name} vs {module_origins[scene_id].name})"
            )
        else:
            module_origins[scene_id] = scene_path

    if duplicates or load_errors:
        parts: list[str] = []
        if duplicates:
            parts.append(f"duplicates=[{'; '.join(duplicates)}]")
        if load_errors:
            parts.append(f"load_errors=[{'; '.join(load_errors)}]")
        return DoctorCheck(
            name="duplicate-ids",
            status="fail",
            detail="; ".join(parts),
            hint="Assign unique id values across all StylePack, AssetSpec, and SceneSpec modules.",
        )

    return DoctorCheck(
        name="duplicate-ids",
        status="pass",
        detail=(
            f"checked {len(style_files)} style(s), {len(asset_files)} asset(s), "
            f"{len(scene_files)} scene(s); 0 duplicates"
        ),
    )


def _check_tracked_scratch(
    root: Path,
    *,
    which: Callable[[str], str | None],
    run_cmd: ToolRunner,
) -> DoctorCheck:
    git_exe = which("git")
    if git_exe is None:
        return DoctorCheck(
            name="git-scratch",
            status="warn",
            detail="git not found on PATH; skipped tracked .pixelforge/ check",
        )
    try:
        in_repo_code, _ = run_cmd([git_exe, "-C", str(root), "rev-parse", "--is-inside-work-tree"])
    except (OSError, subprocess.SubprocessError) as exc:
        return DoctorCheck(
            name="git-scratch",
            status="warn",
            detail=f"git check failed ({exc})",
        )
    if in_repo_code != 0:
        return DoctorCheck(
            name="git-scratch",
            status="pass",
            detail="not a git repository; skipped tracked .pixelforge/ check",
        )

    proc = subprocess.run(
        [git_exe, "-C", str(root), "ls-files", "--", ".pixelforge"],
        capture_output=True,
        text=True,
        timeout=5.0,
        check=False,
    )
    tracked = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if tracked:
        preview = ", ".join(tracked[:5])
        suffix = f" (+{len(tracked) - 5} more)" if len(tracked) > 5 else ""
        return DoctorCheck(
            name="git-scratch",
            status="fail",
            detail=f"{len(tracked)} tracked file(s) under .pixelforge/: {preview}{suffix}",
            hint=(
                "Run 'git rm -r --cached .pixelforge' and ensure '.pixelforge/' is in .gitignore."
            ),
        )
    return DoctorCheck(
        name="git-scratch",
        status="pass",
        detail="0 tracked files under .pixelforge/",
    )


def _check_critic_config(root: Path) -> DoctorCheck:
    settings = load_hydra_settings(root)
    base_url = settings.base_url.strip()
    model_fast = settings.model_fast.strip()
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        return DoctorCheck(
            name="critic-config",
            status="fail",
            detail=f"invalid LLM_BASE_URL {base_url!r}",
            hint="Set LLM_BASE_URL to an http:// or https:// OpenAI-compatible /v1 endpoint.",
        )
    if not model_fast:
        return DoctorCheck(
            name="critic-config",
            status="fail",
            detail="LLM_MODEL_FAST is empty",
            hint="Set LLM_MODEL_FAST in .env or environment (e.g. 'fast').",
        )
    if settings.timeout_seconds <= 0:
        return DoctorCheck(
            name="critic-config",
            status="fail",
            detail=f"LLM_TIMEOUT_SECONDS must be positive (got {settings.timeout_seconds})",
            hint="Set LLM_TIMEOUT_SECONDS to a positive number of seconds.",
        )
    if not settings.api_key.strip():
        return DoctorCheck(
            name="critic-config",
            status="warn",
            detail=f"LLM_API_KEY is unset (base_url={base_url}, model={model_fast})",
            hint="Set LLM_API_KEY in .env or environment to enable 'pixelforge critic'.",
        )
    return DoctorCheck(
        name="critic-config",
        status="pass",
        detail=f"configured (base_url={base_url}, model={model_fast}, api_key=set)",
    )


def run_doctor(
    root: Path,
    *,
    which: Callable[[str], str | None] = shutil.which,
    run_cmd: ToolRunner = _default_run_cmd,
) -> DoctorReport:
    """Run all environment and repository health checks and return a `DoctorReport`."""
    checks = (
        _check_toolchain_binary("uv", which=which, run_cmd=run_cmd),
        _check_toolchain_binary("ruff", which=which, run_cmd=run_cmd),
        _check_toolchain_binary("pyright", which=which, run_cmd=run_cmd),
        _check_palette_stubs(root),
        _check_duplicate_ids(root),
        _check_tracked_scratch(root, which=which, run_cmd=run_cmd),
        _check_critic_config(root),
    )
    pass_count = sum(1 for c in checks if c.status == "pass")
    warn_count = sum(1 for c in checks if c.status == "warn")
    fail_count = sum(1 for c in checks if c.status == "fail")
    return DoctorReport(
        root=str(root),
        passed=fail_count == 0,
        pass_count=pass_count,
        warn_count=warn_count,
        fail_count=fail_count,
        checks=checks,
    )


def _report_to_dict(report: DoctorReport) -> dict[str, object]:
    return {
        "root": report.root,
        "passed": report.passed,
        "pass_count": report.pass_count,
        "warn_count": report.warn_count,
        "fail_count": report.fail_count,
        "checks": [
            {
                "name": c.name,
                "status": c.status,
                "detail": c.detail,
                **({"hint": c.hint} if c.hint is not None else {}),
            }
            for c in report.checks
        ],
    }


def _emit_llm(report: DoctorReport, *, out: OutputFn) -> None:
    status = "OK" if report.passed else "FAIL"
    out(
        f"DOCTOR {status} root={report.root} "
        f"pass={report.pass_count} warn={report.warn_count} fail={report.fail_count}"
    )
    for check in report.checks:
        hint_suffix = f" | hint: {check.hint}" if check.hint is not None else ""
        out(f"{check.status.upper()} {check.name}: {check.detail}{hint_suffix}")


def _emit_human(report: DoctorReport, *, out: OutputFn) -> None:
    status = "HEALTHY" if report.passed else "ISSUES FOUND"
    out(f"pixelforge doctor: {status} ({report.root})")
    for check in report.checks:
        tag = {"pass": "[PASS]", "warn": "[WARN]", "fail": "[FAIL]"}[check.status]
        out(f"  {tag} {check.name}: {check.detail}")
        if check.hint is not None:
            out(f"         hint: {check.hint}")
    out(
        f"Summary: {report.pass_count} passed, {report.warn_count} warnings, "
        f"{report.fail_count} failed"
    )


def doctor_workflow(
    root: Path,
    *,
    output_format: OutputFormat = "llm",
    out: OutputFn,
) -> int:
    """Execute `pixelforge doctor`, emit formatted report, and return exit code."""
    report = run_doctor(root)
    if output_format == "json":
        out(json.dumps(_report_to_dict(report), indent=2))
    elif output_format == "human":
        _emit_human(report, out=out)
    else:
        _emit_llm(report, out=out)
    return 0 if report.passed else 1
