"""Hermetic tests for module discovery, git-ref loading, and unified guard runner."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pixelforge.cli.main import main
from pixelforge.guard.runner import (
    load_all_assets,
    load_all_styles,
    load_asset_from_git,
    run_checks,
    sync_palette_stubs,
)


def _git(repo: Path, *args: str) -> None:
    git_bin = shutil.which("git")
    assert git_bin is not None
    subprocess.run([git_bin, "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_run_checks_on_initialized_project(tmp_path: Path) -> None:
    """Verify `run_checks` passes on a freshly initialized project."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    report = run_checks(tmp_path)
    assert report.passed
    assert report.assets_checked == 1
    assert report.styles_checked == 1
    assert report.errors == 0


def test_load_asset_from_git(tmp_path: Path) -> None:
    """Load a historical `.asset.py` revision from git HEAD."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")

    asset_path = tmp_path / "assets" / "example_crate.asset.py"
    baseline = load_asset_from_git(tmp_path, asset_path, ref="HEAD")
    assert baseline is not None
    assert baseline.SPEC.id == "example_crate"

    missing = load_asset_from_git(tmp_path, tmp_path / "assets" / "missing.asset.py", ref="HEAD")
    assert missing is None


def test_run_checks_and_loaders_fail_on_duplicate_ids(tmp_path: Path) -> None:
    """Emit `duplicate-id` in `run_checks` and raise `ValueError` in loaders."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    style_copy = tmp_path / "styles" / "homelab_dup.style.py"
    style_copy.write_text(
        (tmp_path / "styles" / "homelab_16bit.style.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    asset_copy = tmp_path / "assets" / "example_crate_dup.asset.py"
    asset_copy.write_text(
        (tmp_path / "assets" / "example_crate.asset.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    report = run_checks(tmp_path)
    assert not report.passed
    dup_violations = [v for v in report.violations if v.rule == "duplicate-id"]
    assert len(dup_violations) == 2

    with pytest.raises(ValueError, match="Duplicate style ID"):
        load_all_styles(tmp_path / "styles")
    with pytest.raises(ValueError, match="Duplicate asset ID"):
        load_all_assets(tmp_path / "assets")


def test_run_checks_missing_asset_id_returns_error(tmp_path: Path) -> None:
    """Emit `asset-not-found` and exit 1 when `check <asset_id>` matches zero assets."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    report = run_checks(tmp_path, asset_id="nonexistent")
    assert not report.passed
    assert any(v.rule == "asset-not-found" for v in report.violations)
    assert main(["check", "nonexistent", "--root", str(tmp_path)]) == 1


def test_run_checks_detects_stale_and_missing_palette_stubs(tmp_path: Path) -> None:
    """Detect missing/stale `*_palette.py` stubs and refresh them via `--sync-stubs`."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    stub_path = tmp_path / "styles" / "homelab_16bit_palette.py"
    assert stub_path.is_file()

    # Stale stub triggers an error
    stub_path.write_text("# stale\n", encoding="utf-8")
    stale_report = run_checks(tmp_path)
    assert not stale_report.passed
    assert any(
        v.rule == "palette-stub-stale" and v.severity == "error" for v in stale_report.violations
    )

    # `--sync-stubs` regenerates and passes
    assert main(["check", "--sync-stubs", "--root", str(tmp_path)]) == 0
    assert run_checks(tmp_path).passed

    # Missing stub triggers an advisory warning (exit 0) and `sync_palette_stubs` restores it
    stub_path.unlink()
    missing_report = run_checks(tmp_path)
    assert missing_report.passed
    assert any(
        v.rule == "palette-stub-missing" and v.severity == "warning"
        for v in missing_report.violations
    )
    restored = sync_palette_stubs(tmp_path)
    assert restored == [stub_path]
    assert run_checks(tmp_path).passed
