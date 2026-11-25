"""End-to-end hermetic tests for `pixelforge` CLI commands."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pixelforge.cli.main import main


def _git(repo: Path, *args: str) -> None:
    git_bin = shutil.which("git")
    assert git_bin is not None
    subprocess.run([git_bin, "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_cli_init_and_check(tmp_path: Path) -> None:
    """Verify `init` scaffolds starter files and `check` validates them."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    assert (tmp_path / "styles" / "homelab_16bit.style.py").is_file()
    assert (tmp_path / "assets" / "example_crate.asset.py").is_file()
    assert (tmp_path / ".env.example").is_file()

    assert main(["check", "--root", str(tmp_path)]) == 0

    asset_file = tmp_path / "assets" / "example_crate.asset.py"
    asset_file.write_text(
        f"import random\n{asset_file.read_text(encoding='utf-8')}",
        encoding="utf-8",
    )
    assert main(["check", "--root", str(tmp_path)]) == 1


def test_cli_render_with_all_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify `render` emits PNGs, manifest.d.ts, contact sheet, LUT, and --indexed-ts."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    monkeypatch.setenv("PIXELFORGE_OUT_DIR", str(tmp_path / "custom_dist"))
    monkeypatch.setenv("PIXELFORGE_SHEETS_DIR", str(tmp_path / "custom_sheets"))

    rc = main(
        [
            "render",
            "--root",
            str(tmp_path),
            "--sheet",
            "--emissive",
            "--lut",
            "--indexed-ts",
        ]
    )
    assert rc == 0

    out_dir = tmp_path / "custom_dist"
    assert (out_dir / "sprites" / "example_crate_idle.png").is_file()
    assert (out_dir / "sprites" / "example_crate_idle_emissive.png").is_file()
    assert (out_dir / "sprites" / "example_crate_idle_idx.png").is_file()
    assert (out_dir / "sprites" / "homelab-16bit_lut.png").is_file()
    assert (out_dir / "manifest.json").is_file()
    assert (out_dir / "manifest.d.ts").is_file()
    assert (out_dir / "indexed" / "palette.generated.ts").is_file()
    assert (out_dir / "indexed" / "sprites.generated.ts").is_file()
    assert (out_dir / "indexed" / "manifest.generated.ts").is_file()
    assert (tmp_path / "custom_sheets" / "example_crate.contact.png").is_file()

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "example_crate" in manifest


def test_cli_diff_against_git_head(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `diff` compares working tree asset against git HEAD."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")

    asset_file = tmp_path / "assets" / "example_crate.asset.py"
    updated = asset_file.read_text(encoding="utf-8").replace(
        "a.put(12, 11, p.ACCENT_CYAN)",
        "a.put(12, 10, p.ACCENT_CYAN)",
    )
    asset_file.write_text(updated, encoding="utf-8")

    rc = main(["diff", "example_crate", "--base", "HEAD", "--root", str(tmp_path)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "changed pixel(s)" in captured.out
    assert (tmp_path / ".pixelforge" / "diffs" / "example_crate_idle.diff.png").is_file()


def test_cli_diff_palette_only_against_git_head(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `diff` surfaces palette-only edits against historical StylePack at --base HEAD."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    capsys.readouterr()

    style_file = tmp_path / "styles" / "homelab_16bit.style.py"
    original_style = style_file.read_text(encoding="utf-8")
    updated_style = original_style.replace("#38bdf8", "#ff00aa")
    assert updated_style != original_style
    style_file.write_text(updated_style, encoding="utf-8")

    rc = main(["diff", "example_crate", "--base", "HEAD", "--root", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert ": 0/" not in out
    assert ": 2/576 changed pixel(s)" in out

    diff_path = tmp_path / ".pixelforge" / "diffs" / "example_crate_idle.diff.png"
    assert diff_path.is_file()
    decoded = np.asarray(Image.open(diff_path).convert("RGBA"), dtype=np.uint8)
    magenta_mask = np.all(decoded == np.array([255, 42, 133, 255], dtype=np.uint8), axis=2)
    assert int(np.count_nonzero(magenta_mask)) > 0

    # Variant added only in working tree falls back to current style without crashing
    variant_style = updated_style.replace(
        "variants={},",
        'variants={"night": {"ACCENT_CYAN": "#00ffcc"}},',
    )
    if variant_style == updated_style:
        variant_style = updated_style.replace(
            "    palette=(",
            '    variants={"night": {"ACCENT_CYAN": "#00ffcc"}},\n    palette=(',
        )
    style_file.write_text(variant_style, encoding="utf-8")
    rc_variant = main(
        ["diff", "example_crate", "--base", "HEAD", "--variant", "night", "--root", str(tmp_path)]
    )
    assert rc_variant == 0


def test_cli_watch_bounded_cycles(tmp_path: Path) -> None:
    """Verify `watch` runs initial check+render and exits cleanly after --max-cycles."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    rc = main(
        [
            "watch",
            "--root",
            str(tmp_path),
            "--max-cycles",
            "1",
            "--interval",
            "0.01",
            "--indexed-ts",
        ]
    )
    assert rc == 0
    assert (tmp_path / "dist" / "manifest.json").is_file()
    assert (tmp_path / "dist" / "indexed" / "sprites.generated.ts").is_file()


def test_cli_analyze_ref_ephemeral_and_guardrails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `analyze-ref` prints ephemeral sketch and refuses paths inside assets/ or styles/."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    capsys.readouterr()

    ref_dir = tmp_path / ".pixelforge" / "refs"
    ref_dir.mkdir(parents=True, exist_ok=True)
    ref_png = ref_dir / "crate_ref.png"
    rgba = np.full((24, 32, 4), (56, 189, 248, 255), dtype=np.uint8)
    Image.fromarray(rgba, mode="RGBA").save(ref_png, format="PNG")

    before_assets = sorted((tmp_path / "assets").rglob("*"))
    rc = main(
        [
            "analyze-ref",
            str(ref_png),
            "--style",
            "homelab-16bit",
            "--size",
            "8x6",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "EPHEMERAL REFERENCE SKETCH" in out
    assert "32x24" in out
    assert "4:3" in out
    assert "ACCENT_CYAN" in out
    assert sorted((tmp_path / "assets").rglob("*")) == before_assets
    assert not (tmp_path / "dist").exists()

    # Guardrail: refuse reference images placed inside assets/ or styles/
    bad_ref = tmp_path / "assets" / "forbidden_ref.png"
    Image.fromarray(rgba, mode="RGBA").save(bad_ref, format="PNG")
    assert main(["analyze-ref", str(bad_ref), "--root", str(tmp_path)]) == 1
    assert "must not be placed in assets/ or styles/" in capsys.readouterr().err

    # Guardrail: missing file and unknown style
    assert main(["analyze-ref", str(ref_dir / "missing.png"), "--root", str(tmp_path)]) == 1
    assert main(["analyze-ref", str(ref_png), "--style", "nope", "--root", str(tmp_path)]) == 1


def _add_sibling_asset(root: Path, asset_id: str) -> None:
    starter = (root / "assets" / "example_crate.asset.py").read_text(encoding="utf-8")
    sibling = starter.replace('id="example_crate"', f'id="{asset_id}"')
    (root / "assets" / f"{asset_id}.asset.py").write_text(sibling, encoding="utf-8")


def test_cli_filtered_indexed_ts_preserves_sibling_assets(tmp_path: Path) -> None:
    """Verify filtered `render`/`watch <asset_id> --indexed-ts` never drops sibling assets."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    _add_sibling_asset(tmp_path, "sibling_crate")

    out_dir = tmp_path / "dist"
    assert main(["render", "--root", str(tmp_path), "--indexed-ts"]) == 0
    full_sprites = (out_dir / "indexed" / "sprites.generated.ts").read_text(encoding="utf-8")
    full_manifest = (out_dir / "indexed" / "manifest.generated.ts").read_text(encoding="utf-8")
    assert '"example_crate"' in full_sprites
    assert '"sibling_crate"' in full_sprites
    assert '"example_crate"' in full_manifest
    assert '"sibling_crate"' in full_manifest

    # Remove sibling PNG to verify filtered render only writes PNGs for the requested asset
    sibling_png = out_dir / "sprites" / "sibling_crate_idle.png"
    sibling_png.unlink()

    assert main(["render", "example_crate", "--root", str(tmp_path), "--indexed-ts"]) == 0
    assert not sibling_png.exists()
    assert (out_dir / "sprites" / "example_crate_idle.png").is_file()
    filtered_sprites = (out_dir / "indexed" / "sprites.generated.ts").read_text(encoding="utf-8")
    filtered_manifest = (out_dir / "indexed" / "manifest.generated.ts").read_text(encoding="utf-8")
    assert '"example_crate"' in filtered_sprites
    assert '"sibling_crate"' in filtered_sprites
    assert '"example_crate"' in filtered_manifest
    assert '"sibling_crate"' in filtered_manifest

    # Same invariant holds for `watch <asset_id> --indexed-ts`
    rc_watch = main(
        [
            "watch",
            "example_crate",
            "--root",
            str(tmp_path),
            "--max-cycles",
            "1",
            "--interval",
            "0.01",
            "--indexed-ts",
        ]
    )
    assert rc_watch == 0
    watch_sprites = (out_dir / "indexed" / "sprites.generated.ts").read_text(encoding="utf-8")
    watch_manifest = (out_dir / "indexed" / "manifest.generated.ts").read_text(encoding="utf-8")
    assert '"example_crate"' in watch_sprites
    assert '"sibling_crate"' in watch_sprites
    assert '"example_crate"' in watch_manifest
    assert '"sibling_crate"' in watch_manifest
