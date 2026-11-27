"""Hermetic CLI and guard tests for `pixelforge new ui-kit`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelforge.cli.main import main
from pixelforge.core.prefabs.ui import UI_THEME_NAMES, UiThemeName
from pixelforge.guard.runner import run_checks


def _init_project(tmp_path: Path, *, style: str = "sweetie-16") -> None:
    rc = main(["init", "--style", style, "--root", str(tmp_path)])
    assert rc == 0


@pytest.mark.parametrize("theme", UI_THEME_NAMES)
def test_new_ui_kit_all_themes_pass_check_and_render(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    theme: UiThemeName,
) -> None:
    """Every `pixelforge new ui-kit --theme` must pass `check`, `render`, and emit styleguide."""
    _init_project(tmp_path)
    capsys.readouterr()
    kit_name = f"hud_{theme}"

    rc = main(
        [
            "new",
            "ui-kit",
            kit_name,
            "--theme",
            theme,
            "--format",
            "json",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "new"
    assert payload["target"] == "ui-kit"
    assert payload["id"] == kit_name
    assert payload["theme"] == theme
    assert payload["style_id"] == "sweetie-16"
    assert len(payload["files"]) == 7

    for file_str in payload["files"]:
        assert Path(file_str).is_file()

    sheet_path = Path(payload["styleguide_path"])
    assert sheet_path.is_file()
    assert sheet_path.name == f"{kit_name}_styleguide.contact.png"
    assert sheet_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

    report = run_checks(tmp_path)
    assert report.passed, [v.detail for v in report.violations]

    rc_render = main(["render", f"{kit_name}_panel", "--root", str(tmp_path)])
    assert rc_render == 0


def test_new_ui_kit_formats_no_sheet_and_overwrite_guard(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `--no-sheet`, `llm`/`human` output, and `--force` overwrite protection."""
    _init_project(tmp_path, style="scifi-neon")
    capsys.readouterr()

    rc_llm = main(
        [
            "new",
            "ui-kit",
            "neon_hud",
            "--theme",
            "flat_crt",
            "--no-sheet",
            "--format",
            "llm",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc_llm == 0
    out_llm = capsys.readouterr().out
    assert "NEW ui-kit neon_hud theme=flat_crt" in out_llm
    assert not (tmp_path / ".pixelforge" / "sheets" / "neon_hud_styleguide.contact.png").exists()

    # Overwrite without --force must fail with exit code 2.
    rc_dup = main(["new", "ui-kit", "neon_hud", "--root", str(tmp_path)])
    assert rc_dup == 2
    assert "Refusing to overwrite" in capsys.readouterr().err

    # Overwrite with --force and human format succeeds.
    rc_force = main(
        [
            "new",
            "ui-kit",
            "neon_hud",
            "--theme",
            "minimal_1bit",
            "--force",
            "--format",
            "human",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc_force == 0
    out_human = capsys.readouterr().out
    assert "Created ui-kit 'neon_hud'" in out_human
    assert (tmp_path / ".pixelforge" / "sheets" / "neon_hud_styleguide.contact.png").is_file()
