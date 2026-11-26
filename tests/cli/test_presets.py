"""Hermetic tests for dynamic `default_style` resolution and built-in presets."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pixelforge.cli.main import main
from pixelforge.cli.settings import load_pixelforge_settings, resolve_project_style_id
from pixelforge.presets import (
    DEFAULT_INIT_PRESET,
    PRESET_IDS,
    get_preset_path,
    load_all_presets,
)


def test_settings_default_style_is_none(tmp_path: Path) -> None:
    """Verify `PixelforgeSettings.default_style` is `None` by default."""
    settings = load_pixelforge_settings(tmp_path)
    assert settings.default_style is None


def test_resolve_project_style_id_rules(tmp_path: Path) -> None:
    """Verify deterministic resolution: explicit > env default > single style > error."""
    presets = load_all_presets()
    single = {"sweetie-16": presets["sweetie-16"]}
    multi = {
        "sweetie-16": presets["sweetie-16"],
        "scifi-neon": presets["scifi-neon"],
    }
    styles_dir = tmp_path / "styles"

    # Explicit style wins
    assert (
        resolve_project_style_id(
            explicit_style="scifi-neon",
            default_style="sweetie-16",
            styles=multi,
            styles_dir=styles_dir,
        )
        == "scifi-neon"
    )

    # Env/config default wins when explicit is None
    assert (
        resolve_project_style_id(
            explicit_style=None,
            default_style="sweetie-16",
            styles=multi,
            styles_dir=styles_dir,
        )
        == "sweetie-16"
    )

    # Single style in styles/ auto-resolves
    assert (
        resolve_project_style_id(
            explicit_style=None,
            default_style=None,
            styles=single,
            styles_dir=styles_dir,
        )
        == "sweetie-16"
    )

    # Multiple styles without explicit/default raises actionable error listing available styles
    with pytest.raises(ValueError, match="scifi-neon, sweetie-16"):
        resolve_project_style_id(
            explicit_style=None,
            default_style=None,
            styles=multi,
            styles_dir=styles_dir,
        )

    # Empty styles/ raises actionable error
    with pytest.raises(ValueError, match=r"no \.style\.py files found"):
        resolve_project_style_id(
            explicit_style=None,
            default_style=None,
            styles={},
            styles_dir=styles_dir,
        )


def test_builtin_presets_catalog_pure_python() -> None:
    """Verify all 8 built-in presets load cleanly with zero `.toml`/`.json` files."""
    expected = (
        "ink-1bit",
        "retro-pocket-4",
        "sweetie-16",
        "endesga-32",
        "cozy-pastel",
        "scifi-neon",
        "topdown-rpg",
        "homelab-16bit",
    )
    assert set(PRESET_IDS) == set(expected)
    assert len(PRESET_IDS) == len(expected)
    presets_dir = get_preset_path(DEFAULT_INIT_PRESET).parent
    assert list(presets_dir.glob("*.toml")) == []
    assert list(presets_dir.glob("*.json")) == []

    loaded = load_all_presets()
    assert set(loaded) == set(expected)
    assert len(loaded["ink-1bit"].palette) == 2
    assert len(loaded["retro-pocket-4"].palette) == 4
    assert len(loaded["sweetie-16"].palette) == 16
    assert len(loaded["endesga-32"].palette) == 32
    assert len(loaded["cozy-pastel"].palette) == 16
    assert len(loaded["scifi-neon"].palette) == 16
    assert len(loaded["topdown-rpg"].palette) == 32
    assert len(loaded["homelab-16bit"].palette) == 64


@pytest.mark.parametrize("preset_id", PRESET_IDS)
def test_cli_init_with_preset_check_and_render(
    tmp_path: Path,
    preset_id: str,
) -> None:
    """Verify `pixelforge init --style <preset>` scaffolds valid style, stub, and asset."""
    slug = preset_id.replace("-", "_")
    assert main(["init", "--style", preset_id, "--root", str(tmp_path)]) == 0
    assert (tmp_path / "styles" / f"{slug}.style.py").is_file()
    assert (tmp_path / "styles" / f"{slug}_palette.py").is_file()
    assert (tmp_path / "assets" / "example_crate.asset.py").is_file()
    env_text = (tmp_path / ".env.example").read_text(encoding="utf-8")
    assert f"PIXELFORGE_DEFAULT_STYLE={preset_id}" in env_text

    assert main(["check", "--root", str(tmp_path)]) == 0
    assert main(["render", "--root", str(tmp_path)]) == 0
    assert (tmp_path / "dist" / "sprites" / "example_crate_idle.png").is_file()


def test_cli_inspect_presets_and_style_presets_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `inspect presets` and `inspect style --presets` expose built-in presets."""
    assert main(["inspect", "presets"]) == 0
    llm_out = capsys.readouterr().out
    assert f"presets={len(PRESET_IDS)} default={DEFAULT_INIT_PRESET}" in llm_out
    assert "preset=ink-1bit" in llm_out
    assert "preset=scifi-neon" in llm_out

    assert main(["inspect", "presets", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total"] == len(PRESET_IDS)
    assert payload["default"] == DEFAULT_INIT_PRESET
    assert {entry["id"] for entry in payload["presets"]} == set(PRESET_IDS)

    assert main(["inspect", "presets", "retro-pocket-4", "--human"]) == 0
    human_out = capsys.readouterr().out
    assert "Style: retro-pocket-4" in human_out

    assert main(["inspect", "style", "--presets", "--json"]) == 0
    style_presets_payload = json.loads(capsys.readouterr().out)
    assert style_presets_payload["total"] == len(PRESET_IDS)

    assert main(["inspect", "presets", "swetie-16"]) == 1
    err = capsys.readouterr().err
    assert "Unknown preset" in err
    assert "sweetie-16" in err


def test_cli_analyze_ref_dynamic_style_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `analyze-ref` resolves single style automatically and errors on ambiguity."""
    assert main(["init", "--style", "sweetie-16", "--root", str(tmp_path)]) == 0
    ref_png = tmp_path / ".pixelforge" / "refs" / "sample.png"
    ref_png.parent.mkdir(parents=True, exist_ok=True)
    rgba = np.full((8, 8, 4), (65, 166, 246, 255), dtype=np.uint8)
    Image.fromarray(rgba, mode="RGBA").save(ref_png, format="PNG")
    capsys.readouterr()

    # Single style in styles/ resolves without --style or PIXELFORGE_DEFAULT_STYLE
    assert main(["analyze-ref", str(ref_png), "--size", "4x4", "--root", str(tmp_path)]) == 0
    capsys.readouterr()

    # Add a second style -> ambiguous without --style or PIXELFORGE_DEFAULT_STYLE
    second_style = get_preset_path("scifi-neon").read_text(encoding="utf-8")
    (tmp_path / "styles" / "scifi_neon.style.py").write_text(second_style, encoding="utf-8")
    assert main(["analyze-ref", str(ref_png), "--size", "4x4", "--root", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "multiple styles found" in err
    assert "scifi-neon" in err
    assert "sweetie-16" in err

    # PIXELFORGE_DEFAULT_STYLE disambiguates
    monkeypatch.setenv("PIXELFORGE_DEFAULT_STYLE", "scifi-neon")
    assert main(["analyze-ref", str(ref_png), "--size", "4x4", "--root", str(tmp_path)]) == 0
