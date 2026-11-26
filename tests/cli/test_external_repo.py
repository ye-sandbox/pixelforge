"""Hermetic end-to-end tests for standalone `pixelforge` CLI against external repositories."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from pixelforge import __version__


def _cli_command() -> list[str]:
    candidate = Path(sys.executable).parent / "pixelforge"
    if candidate.is_file():
        return [str(candidate)]
    return [sys.executable, "-m", "pixelforge.cli.main"]


def _run_cli(
    args: list[str],
    *,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PIXELFORGE_")}
    return subprocess.run(
        [*_cli_command(), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _init_git_repo(repo_root: Path) -> None:
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test User"],
        ["git", "add", "."],
        ["git", "commit", "-m", "chore: initial external repo"],
    ):
        proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stderr


def test_standalone_cli_version_from_unrelated_cwd(tmp_path: Path) -> None:
    proc = _run_cli(["--version"], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert __version__ in proc.stdout


def test_external_repo_end_to_end_via_root(tmp_path: Path) -> None:
    caller_cwd = tmp_path / "caller"
    caller_cwd.mkdir()
    # Conflicting .env in caller CWD must not leak when --root targets ext_repo.
    (caller_cwd / ".env").write_text("PIXELFORGE_OUT_DIR=leaked_cwd_dir\n", encoding="utf-8")

    ext_repo = tmp_path / "svelte-consumer-app"
    ext_repo.mkdir()

    init_proc = _run_cli(["init", "--root", str(ext_repo)], cwd=caller_cwd)
    assert init_proc.returncode == 0, init_proc.stderr
    assert (ext_repo / "styles" / "sweetie_16.style.py").is_file()
    assert (ext_repo / "styles" / "sweetie_16_palette.py").is_file()
    assert (ext_repo / "assets" / "example_crate.asset.py").is_file()
    assert (ext_repo / ".env.example").is_file()

    (ext_repo / ".env").write_text("PIXELFORGE_OUT_DIR=static/sprites\n", encoding="utf-8")

    # Add a prop asset and a declarative scene to exercise inspect/compose/scene paths.
    (ext_repo / "assets" / "status_beacon.asset.py").write_text(
        '''"""Small beacon prop for external repo composition."""

from __future__ import annotations

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec

SPEC = AssetSpec(
    id="status_beacon",
    style_id="sweetie-16",
    perspective="iso-2:1",
    width=8,
    height=8,
    states=("idle",),
    frames=1,
    fps=4,
)


def render(a: Asset) -> None:
    p = a.pal
    with a.layer("lamp", outline=p.INK):
        a.put(3, 3, p.CYAN)
        a.put(4, 3, p.CYAN)
    a.anchor("base", 3, 4)
''',
        encoding="utf-8",
    )
    (ext_repo / "assets" / "crate_scene.scene.py").write_text(
        '''"""Declarative scene in external consumer repo."""

from __future__ import annotations

from pixelforge.export.scene import SceneMountSpec, SceneSpec

SCENE = SceneSpec(
    id="crate_scene",
    parent_id="example_crate",
    mounts=(
        SceneMountSpec(
            prop_id="status_beacon",
            anchor="foot",
            prop_anchor="base",
        ),
    ),
)
''',
        encoding="utf-8",
    )

    check_proc = _run_cli(
        ["check", "--sync-stubs", "--format", "json", "--root", str(ext_repo)],
        cwd=caller_cwd,
    )
    assert check_proc.returncode == 0, f"{check_proc.stdout}\n{check_proc.stderr}"
    check_payload = json.loads(check_proc.stdout)
    assert check_payload["passed"] is True

    render_proc = _run_cli(
        [
            "render",
            "--sheet",
            "--emissive",
            "--lut",
            "--indexed-ts",
            "--format",
            "json",
            "--root",
            str(ext_repo),
        ],
        cwd=caller_cwd,
    )
    assert render_proc.returncode == 0, render_proc.stderr
    assert not (caller_cwd / "leaked_cwd_dir").exists()
    assert (ext_repo / "static" / "sprites" / "manifest.json").is_file()
    assert (ext_repo / "static" / "sprites" / "manifest.d.ts").is_file()
    assert (ext_repo / "static" / "sprites" / "sprites" / "example_crate_idle.png").is_file()
    assert (
        ext_repo / "static" / "sprites" / "sprites" / "example_crate_idle_emissive.png"
    ).is_file()
    assert (ext_repo / "static" / "sprites" / "sprites" / "example_crate_idle_idx.png").is_file()
    assert (ext_repo / "static" / "sprites" / "indexed" / "palette.generated.ts").is_file()
    assert (ext_repo / "static" / "sprites" / "indexed" / "sprites.generated.ts").is_file()
    assert (ext_repo / "static" / "sprites" / "indexed" / "manifest.generated.ts").is_file()
    assert (ext_repo / ".pixelforge" / "sheets" / "example_crate.contact.png").is_file()

    inspect_proc = _run_cli(
        ["inspect", "scenes", "crate_scene", "--format", "json", "--root", str(ext_repo)],
        cwd=caller_cwd,
    )
    assert inspect_proc.returncode == 0, inspect_proc.stderr
    inspect_payload = json.loads(inspect_proc.stdout)
    assert inspect_payload["scenes"][0]["id"] == "crate_scene"

    compose_proc = _run_cli(
        [
            "compose",
            "example_crate",
            "--mount",
            "status_beacon@foot:base",
            "--format",
            "json",
            "--root",
            str(ext_repo),
        ],
        cwd=caller_cwd,
    )
    assert compose_proc.returncode == 0, compose_proc.stderr

    watch_proc = _run_cli(
        ["watch", "--max-cycles", "1", "--format", "json", "--root", str(ext_repo)],
        cwd=caller_cwd,
    )
    assert watch_proc.returncode == 0, watch_proc.stderr

    # Exercise `diff --root` against an external git repository.
    _init_git_repo(ext_repo)
    crate_path = ext_repo / "assets" / "example_crate.asset.py"
    crate_src = crate_path.read_text(encoding="utf-8")
    crate_path.write_text(
        crate_src.replace("a.put(13, 11, p.CYAN)", "a.put(13, 12, p.CYAN)"),
        encoding="utf-8",
    )
    diff_proc = _run_cli(
        ["diff", "example_crate", "--base", "HEAD", "--format", "json", "--root", str(ext_repo)],
        cwd=caller_cwd,
    )
    assert diff_proc.returncode == 0, diff_proc.stderr
    diff_payload = json.loads(diff_proc.stdout)
    assert diff_payload["total_changed_pixels"] > 0
