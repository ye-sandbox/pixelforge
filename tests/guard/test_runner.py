"""Hermetic tests for module discovery, git-ref loading, and unified guard runner."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pixelforge.cli.main import main
from pixelforge.guard.runner import load_asset_from_git, run_checks


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
