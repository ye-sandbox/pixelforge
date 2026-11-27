"""Hermetic tests for `pixelforge.toml` and `[tool.pixelforge]` build profiles."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pixelforge.cli.main import main
from pixelforge.cli.settings import load_project_config, resolve_build_profile


def test_load_project_config_defaults_when_missing(tmp_path: Path) -> None:
    """Missing TOML files yield default `PixelforgeProjectConfig` and `None` source."""
    config, source = load_project_config(tmp_path)
    assert source is None
    assert config.profiles == {}
    resolved = resolve_build_profile(tmp_path)
    assert resolved.profile_name == "default"
    assert resolved.scale == 1
    assert resolved.indexed_ts is False
    assert resolved.ui_css is False


def test_load_pixelforge_toml_and_builtin_profiles(tmp_path: Path) -> None:
    """`pixelforge.toml` merges top-level defaults with built-in and custom profiles."""
    (tmp_path / "pixelforge.toml").write_text(
        """
style = "sweetie-16"
out = "static/sprites"
scale = 2
targets = ["png", "lut"]

[profiles.web-ui]
variant = "high_contrast"

[profiles.custom]
targets = ["indexed-ts-lazy", "aseprite", "texturepacker", "normals", "height", "sheet", "animate"]
emissive = true
scale = 3
""".strip(),
        encoding="utf-8",
    )

    config, source = load_project_config(tmp_path)
    assert source == tmp_path / "pixelforge.toml"
    assert config.style == "sweetie-16"

    default_profile = resolve_build_profile(tmp_path)
    assert default_profile.profile_name == "default"
    assert default_profile.out == "static/sprites"
    assert default_profile.scale == 2
    assert default_profile.lut is True
    assert default_profile.indexed_ts is False

    web_profile = resolve_build_profile(tmp_path, "web-ui")
    assert web_profile.profile_name == "web-ui"
    assert web_profile.style == "sweetie-16"
    assert web_profile.out == "static/sprites"
    assert web_profile.scale == 2
    assert web_profile.variant == "high_contrast"
    assert web_profile.ui_css is True
    assert web_profile.indexed_ts is False
    assert web_profile.targets == ("png", "ui-css")

    fb_profile = resolve_build_profile(tmp_path, "framebuffer-ui")
    assert fb_profile.profile_name == "framebuffer-ui"
    assert fb_profile.style == "sweetie-16"
    assert fb_profile.indexed_ts is True
    assert fb_profile.ui_css is False
    assert fb_profile.targets == ("indexed-ts",)

    custom = resolve_build_profile(tmp_path, "custom")
    assert custom.indexed_ts is True
    assert custom.indexed_ts_lazy is True
    assert custom.atlas == "all"
    assert custom.normals is True
    assert custom.height is True
    assert custom.sheet is True
    assert custom.animate is True
    assert custom.emissive is True
    assert custom.scale == 3


def test_pyproject_tool_pixelforge_and_precedence(tmp_path: Path) -> None:
    """`[tool.pixelforge]` loads when `pixelforge.toml` is absent, and loses when both exist."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "sample-game"
version = "0.1.0"

[tool.pixelforge]
out = "assets_dist"
targets = ["indexed-ts", "aseprite"]
scale = 2
""".strip(),
        encoding="utf-8",
    )

    resolved = resolve_build_profile(tmp_path)
    assert resolved.out == "assets_dist"
    assert resolved.indexed_ts is True
    assert resolved.atlas == "aseprite"
    assert resolved.scale == 2

    (tmp_path / "pixelforge.toml").write_text(
        'out = "override_dist"\nscale = 4\n',
        encoding="utf-8",
    )
    resolved_override = resolve_build_profile(tmp_path)
    assert resolved_override.out == "override_dist"
    assert resolved_override.scale == 4
    assert resolved_override.indexed_ts is False


@pytest.mark.parametrize(
    ("filename", "content", "profile", "expected_substr"),
    [
        ("pixelforge.toml", "unknown_key = true\n", None, "invalid pixelforge config"),
        ("pixelforge.toml", "scale = 0\n", None, "invalid pixelforge config"),
        ("pixelforge.toml", 'targets = ["bogus"]\n', None, "invalid pixelforge config"),
        ("pixelforge.toml", "not = [valid\n", None, "invalid TOML"),
        ("pixelforge.toml", 'out = "dist"\n', "missing-prof", "unknown build profile"),
        (
            "pyproject.toml",
            '[tool]\npixelforge = "bad"\n',
            None,
            "expected a TOML table",
        ),
    ],
)
def test_build_profile_validation_errors(
    tmp_path: Path,
    filename: str,
    content: str,
    profile: str | None,
    expected_substr: str,
) -> None:
    """Malformed TOML, unknown keys, bad values, and unknown profiles raise `ValueError`."""
    (tmp_path / filename).write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=expected_substr):
        resolve_build_profile(tmp_path, profile)


def test_cli_render_watch_check_with_profiles_and_overrides(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`render`, `watch`, and `check` honor `pixelforge.toml` and explicit CLI overrides."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    (tmp_path / "pixelforge.toml").write_text(
        """
style = "sweetie-16"
out = "prof_dist"
targets = ["lut", "aseprite"]
emissive = true
scale = 2

[profiles.framebuffer-ui]
out = "fb_dist"
""".strip(),
        encoding="utf-8",
    )
    capsys.readouterr()

    # check passes with valid profile and fails on unknown --profile
    assert main(["check", "--root", str(tmp_path), "--profile", "framebuffer-ui"]) == 0
    assert main(["check", "--root", str(tmp_path), "--profile", "does-not-exist"]) == 1

    # render uses default profile from pixelforge.toml without extra flags
    assert main(["render", "--root", str(tmp_path)]) == 0
    prof_dist = tmp_path / "prof_dist"
    assert (prof_dist / "sprites" / "example_crate_idle_idx.png").is_file()
    assert (prof_dist / "sprites" / "example_crate_idle_emissive.png").is_file()
    assert (prof_dist / "sprites" / "example_crate.aseprite.json").is_file()
    with Image.open(prof_dist / "sprites" / "example_crate_idle.png") as img:
        assert img.size == (48, 48)  # 24x24 * scale 2

    # render --profile framebuffer-ui emits indexed TS into fb_dist
    assert main(["render", "--root", str(tmp_path), "--profile", "framebuffer-ui"]) == 0
    fb_dist = tmp_path / "fb_dist"
    assert (fb_dist / "indexed" / "sprites.generated.ts").is_file()
    assert (fb_dist / "indexed" / "palette.generated.ts").is_file()

    # explicit CLI flags override profile settings
    override_dist = tmp_path / "cli_dist"
    assert (
        main(
            [
                "render",
                "--root",
                str(tmp_path),
                "--out",
                str(override_dist),
                "--scale",
                "1",
                "--no-emissive",
                "--atlas",
                "texturepacker",
            ]
        )
        == 0
    )
    assert not (override_dist / "sprites" / "example_crate_idle_emissive.png").exists()
    assert (override_dist / "sprites" / "example_crate.texturepacker.json").is_file()
    with Image.open(override_dist / "sprites" / "example_crate_idle.png") as img:
        assert img.size == (24, 24)

    # watch honors profile and CLI overrides
    watch_out = tmp_path / "watch_dist"
    assert (
        main(
            [
                "watch",
                "--root",
                str(tmp_path),
                "--profile",
                "framebuffer-ui",
                "--out",
                str(watch_out),
                "--max-cycles",
                "1",
                "--interval",
                "0.01",
            ]
        )
        == 0
    )
    assert (watch_out / "indexed" / "sprites.generated.ts").is_file()
