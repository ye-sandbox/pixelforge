"""Hermetic CLI and workflow tests for `pixelforge inspect`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelforge.cli.main import main


def _write_sample_scene(root: Path) -> None:
    scene_file = root / "assets" / "sample_scene.scene.py"
    scene_file.write_text(
        """from pixelforge import SceneMountSpec, SceneSpec

SCENE = SceneSpec(
    id="sample_scene",
    parent_id="example_crate",
    style_id="homelab-16bit",
    depth_sort="iso_y",
    strict_bounds=True,
    strict_perspective=False,
    mounts=(
        SceneMountSpec(
            prop_id="example_crate",
            anchor="top",
            state_map={"idle": "idle"},
        ),
    ),
)
""",
        encoding="utf-8",
    )


def test_inspect_no_subcommand_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `pixelforge inspect` without a target prints help and exits 0."""
    assert main(["inspect"]) == 0
    out = capsys.readouterr().out
    assert "style" in out
    assert "prefabs" in out
    assert "assets" in out
    assert "scenes" in out


def test_inspect_style_formats_and_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `inspect style` groups tokens by paint/emissive/bright/reflections."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    capsys.readouterr()

    # Default LLM-first output
    assert main(["inspect", "style", "--root", str(tmp_path)]) == 0
    llm_out = capsys.readouterr().out
    assert "style=homelab-16bit" in llm_out
    assert "paint(" in llm_out
    assert "emissive(" in llm_out
    assert "bright(" in llm_out
    assert "reflections(" in llm_out

    # Strict JSON output
    assert main(["inspect", "style", "homelab-16bit", "--json", "--root", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total"] == 1
    style_obj = payload["styles"][0]
    assert style_obj["id"] == "homelab-16bit"
    assert set(style_obj["groups"]) == {"paint", "emissive", "bright", "reflections"}
    assert len(style_obj["groups"]["emissive"]) >= 1
    assert all("emissive" in tok["flags"] for tok in style_obj["groups"]["emissive"])
    assert all("emissive" not in tok["flags"] for tok in style_obj["groups"]["paint"])

    # Human output
    assert main(["inspect", "style", "--human", "--root", str(tmp_path)]) == 0
    human_out = capsys.readouterr().out
    assert "Style: homelab-16bit" in human_out
    assert "Emissive (" in human_out

    # Unknown style error with fuzzy suggestion
    assert main(["inspect", "style", "homelab-16bt", "--root", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "Unknown style" in err
    assert "homelab-16bit" in err


def test_inspect_prefabs_categories_filter_and_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `inspect prefabs` exposes categories, signatures, and filters."""
    assert main(["inspect", "prefabs"]) == 0
    llm_out = capsys.readouterr().out
    assert "categories=architecture,furniture,details,atmosphere" in llm_out
    assert "[architecture]" in llm_out
    assert "[furniture]" in llm_out
    assert "iso_room_shell(" in llm_out

    assert main(["inspect", "prefabs", "iso_desk", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total"] == 1
    assert payload["categories"]["furniture"][0]["name"] == "iso_desk"
    assert "leg_h" in payload["categories"]["furniture"][0]["signature"]

    assert main(["inspect", "prefabs", "atmosphere", "--human"]) == 0
    human_out = capsys.readouterr().out
    assert "[atmosphere]" in human_out
    assert "day_night_cycle(" in human_out

    assert main(["inspect", "prefabs", "nonexistent_prefab"]) == 1
    assert "No prefabs matching" in capsys.readouterr().err


def test_inspect_assets_and_scenes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `inspect assets` and `inspect scenes` expose states, anchors, and mounts."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    _write_sample_scene(tmp_path)
    capsys.readouterr()

    # Assets (LLM default + JSON)
    assert main(["inspect", "assets", "--root", str(tmp_path)]) == 0
    assets_llm = capsys.readouterr().out
    assert "assets=1" in assets_llm
    assert "example_crate 24x24" in assets_llm
    assert "states=idle" in assets_llm

    assert main(["inspect", "assets", "example_crate", "--json", "--root", str(tmp_path)]) == 0
    assets_json = json.loads(capsys.readouterr().out)
    assert assets_json["total"] == 1
    assert assets_json["assets"][0]["id"] == "example_crate"
    assert len(assets_json["assets"][0]["anchors"]) >= 1

    # Missing asset error
    assert main(["inspect", "assets", "example_crat", "--root", str(tmp_path)]) == 1
    assert "example_crate" in capsys.readouterr().err

    # Scenes (LLM default + JSON + Human)
    assert main(["inspect", "scenes", "--root", str(tmp_path)]) == 0
    scenes_llm = capsys.readouterr().out
    assert "scenes=1" in scenes_llm
    assert "scene=sample_scene parent=example_crate size=24x24" in scenes_llm
    assert "mount=example_crate@top" in scenes_llm

    assert main(["inspect", "scenes", "sample_scene", "--json", "--root", str(tmp_path)]) == 0
    scenes_json = json.loads(capsys.readouterr().out)
    assert scenes_json["total"] == 1
    assert scenes_json["scenes"][0]["strict_bounds"] is True
    assert scenes_json["scenes"][0]["mounts"][0]["prop_id"] == "example_crate"

    assert main(["inspect", "scenes", "--human", "--root", str(tmp_path)]) == 0
    assert "Scenes (1):" in capsys.readouterr().out

    # Missing scene error
    assert main(["inspect", "scenes", "sample_scen", "--root", str(tmp_path)]) == 1
    assert "sample_scene" in capsys.readouterr().err
