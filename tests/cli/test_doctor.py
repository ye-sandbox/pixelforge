"""Unit and CLI tests for `pixelforge doctor`."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pytest import CaptureFixture, MonkeyPatch

from pixelforge.cli.doctor_cmd import run_doctor
from pixelforge.cli.main import main
from pixelforge.cli.scaffold import scaffold_project


def _ok_which(tool: str) -> str | None:
    return f"/usr/bin/{tool}"


def _ok_runner(cmd: list[str]) -> tuple[int, str]:
    exe = Path(cmd[0]).name
    if exe == "git" and "rev-parse" in cmd:
        return 1, ""
    return 0, f"{exe} 1.0.0"


def test_doctor_healthy_scaffolded_project(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    scaffold_project(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/v1")

    report = run_doctor(tmp_path, which=_ok_which, run_cmd=_ok_runner)
    assert report.passed is True
    assert report.fail_count == 0
    assert report.warn_count == 0
    assert report.pass_count == len(report.checks)


def test_doctor_detects_missing_and_stale_palette_stubs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    scaffold_project(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    stubs = list((tmp_path / "styles").glob("*_palette.py"))
    assert stubs
    stub = stubs[0]
    stub.unlink()

    missing_report = run_doctor(tmp_path, which=_ok_which, run_cmd=_ok_runner)
    assert missing_report.passed is True
    stub_check = next(c for c in missing_report.checks if c.name == "palette-stubs")
    assert stub_check.status == "warn"
    assert stub.name in stub_check.detail

    stub.write_text("# stale stub\n", encoding="utf-8")
    stale_report = run_doctor(tmp_path, which=_ok_which, run_cmd=_ok_runner)
    assert stale_report.passed is False
    stale_check = next(c for c in stale_report.checks if c.name == "palette-stubs")
    assert stale_check.status == "fail"
    assert "stale=" in stale_check.detail


def test_doctor_detects_duplicate_ids(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    scaffold_project(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    assets = list((tmp_path / "assets").rglob("*.asset.py"))
    assert assets
    dup_asset = tmp_path / "assets" / "dup_asset.asset.py"
    dup_asset.write_text(assets[0].read_text(encoding="utf-8"), encoding="utf-8")

    report = run_doctor(tmp_path, which=_ok_which, run_cmd=_ok_runner)
    assert report.passed is False
    dup_check = next(c for c in report.checks if c.name == "duplicate-ids")
    assert dup_check.status == "fail"
    assert "duplicates=" in dup_check.detail


def test_doctor_detects_missing_toolchain_and_unset_api_key(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    scaffold_project(tmp_path)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    def _missing_pyright(tool: str) -> str | None:
        return None if tool == "pyright" else f"/usr/bin/{tool}"

    report = run_doctor(tmp_path, which=_missing_pyright, run_cmd=_ok_runner)
    assert report.passed is False
    pyright_check = next(c for c in report.checks if c.name == "toolchain:pyright")
    assert pyright_check.status == "fail"
    critic_check = next(c for c in report.checks if c.name == "critic-config")
    assert critic_check.status == "warn"


def test_doctor_detects_tracked_pixelforge_scratch_files(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    scaffold_project(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    git_exe = shutil.which("git")
    assert git_exe is not None
    subprocess.run([git_exe, "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        [git_exe, "-C", str(tmp_path), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [git_exe, "-C", str(tmp_path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    scratch = tmp_path / ".pixelforge" / "sheets" / "leak.contact.png"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.write_bytes(b"png")
    subprocess.run(
        [git_exe, "-C", str(tmp_path), "add", "-f", str(scratch)],
        check=True,
        capture_output=True,
    )

    report = run_doctor(tmp_path, which=_ok_which)
    assert report.passed is False
    git_check = next(c for c in report.checks if c.name == "git-scratch")
    assert git_check.status == "fail"
    assert "leak.contact.png" in git_check.detail


def test_cli_doctor_formats(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    scaffold_project(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    code_json = main(["doctor", "--root", str(tmp_path), "--format", "json"])
    assert code_json in (0, 1)
    payload = json.loads(capsys.readouterr().out)
    assert payload["root"] == str(tmp_path)
    assert isinstance(payload["checks"], list)
    names = {item["name"] for item in payload["checks"]}
    assert {
        "toolchain:uv",
        "toolchain:ruff",
        "toolchain:pyright",
        "palette-stubs",
        "duplicate-ids",
        "git-scratch",
        "critic-config",
    }.issubset(names)

    code_llm = main(["doctor", "--root", str(tmp_path), "--format", "llm"])
    assert code_llm == code_json
    llm_out = capsys.readouterr().out
    assert llm_out.startswith("DOCTOR ")

    code_human = main(["doctor", "--root", str(tmp_path), "--human"])
    assert code_human == code_json
    human_out = capsys.readouterr().out
    assert "pixelforge doctor:" in human_out
