"""Hermetic unit and CLI tests for `pixelforge new {asset,scene,style}`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelforge.cli.main import main
from pixelforge.cli.new_cmd import ASSET_KINDS, AssetKind
from pixelforge.guard.runner import run_checks


def _init_project(tmp_path: Path, *, style: str = "sweetie-16") -> None:
    rc = main(["init", "--style", style, "--root", str(tmp_path)])
    assert rc == 0


@pytest.mark.parametrize("kind", ASSET_KINDS)
def test_new_asset_all_kinds_pass_check_and_render(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    kind: AssetKind,
) -> None:
    """Every `pixelforge new asset --kind` skeleton must pass `check` and `render`."""
    _init_project(tmp_path)
    capsys.readouterr()
    asset_name = f"sample_{kind.replace('-', '_')}"
    stub_path = tmp_path / "styles" / "sweetie_16_palette.py"
    stub_path.unlink()

    rc = main(
        [
            "new",
            "asset",
            asset_name,
            "--kind",
            kind,
            "--format",
            "json",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "new"
    assert payload["target"] == "asset"
    assert payload["id"] == asset_name
    assert payload["kind"] == kind
    assert payload["style_id"] == "sweetie-16"
    assert stub_path.is_file()
    assert str(stub_path) in payload["synced_stubs"]

    asset_path = Path(payload["path"])
    assert asset_path.is_file()
    source = asset_path.read_text(encoding="utf-8")
    assert "Asset[Sweetie16Palette]" in source
    assert "a.anchor(" in source
    assert "a.hitbox(" in source

    report = run_checks(tmp_path, asset_id=asset_name)
    assert report.passed, [v.detail for v in report.violations]

    rc_render = main(["render", asset_name, "--root", str(tmp_path)])
    assert rc_render == 0


def test_new_scene_with_and_without_parent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `pixelforge new scene` scaffolds valid `SceneSpec` modules."""
    _init_project(tmp_path)
    assert main(["new", "asset", "room_shell", "--root", str(tmp_path)]) == 0
    capsys.readouterr()

    rc = main(
        [
            "new",
            "scene",
            "main_room",
            "--parent",
            "room_shell",
            "--format",
            "llm",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out_llm = capsys.readouterr().out
    assert "NEW scene main_room" in out_llm
    assert "parent=room_shell" in out_llm

    scene_path = tmp_path / "assets" / "main_room.scene.py"
    assert scene_path.is_file()
    assert "parent_id='room_shell'" in scene_path.read_text(encoding="utf-8")

    report = run_checks(tmp_path)
    assert report.passed, [v.detail for v in report.violations]

    rc_default = main(
        [
            "new",
            "scene",
            "fallback_room",
            "--format",
            "human",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc_default == 0
    out_human = capsys.readouterr().out
    assert "Created scene 'fallback_room'" in out_human
    assert (tmp_path / "assets" / "fallback_room.scene.py").is_file()


def test_new_style_custom_and_from_preset_and_overwrite_guard(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `pixelforge new style` with `--from-preset`, stub sync, and `--force`."""
    rc_preset = main(
        [
            "new",
            "style",
            "cyber-grid",
            "--from-preset",
            "scifi-neon",
            "--format",
            "json",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc_preset == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["target"] == "style"
    assert payload["id"] == "cyber-grid"
    assert payload["from_preset"] == "scifi-neon"

    style_path = tmp_path / "styles" / "cyber_grid.style.py"
    stub_path = tmp_path / "styles" / "cyber_grid_palette.py"
    assert style_path.is_file()
    assert stub_path.is_file()
    assert "id='cyber-grid'" in style_path.read_text(encoding="utf-8")
    assert "class CyberGridPalette(Protocol):" in stub_path.read_text(encoding="utf-8")

    # Refuses overwrite without --force
    rc_dup = main(["new", "style", "cyber-grid", "--root", str(tmp_path)])
    assert rc_dup == 2
    assert "Refusing to overwrite" in capsys.readouterr().err

    # Allows overwrite with --force
    rc_force = main(["new", "style", "cyber-grid", "--force", "--root", str(tmp_path)])
    assert rc_force == 0
    capsys.readouterr()

    # Rejects unknown preset
    rc_bad = main(
        [
            "new",
            "style",
            "bad-style",
            "--from-preset",
            "nope-preset",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc_bad == 2
    assert "Unknown built-in preset" in capsys.readouterr().err
