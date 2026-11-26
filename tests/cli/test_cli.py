"""End-to-end hermetic tests for `pixelforge` CLI commands."""

from __future__ import annotations

import json
import os
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
    assert (tmp_path / "styles" / "sweetie_16.style.py").is_file()
    assert (tmp_path / "assets" / "example_crate.asset.py").is_file()
    env_example = tmp_path / ".env.example"
    assert env_example.is_file()
    env_text = env_example.read_text(encoding="utf-8")
    assert "PIXELFORGE_PREVIEWS_DIR=.pixelforge/previews" in env_text
    assert "PIXELFORGE_DIFFS_DIR=.pixelforge/diffs" in env_text

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
    assert (out_dir / "sprites" / "sweetie-16_lut.png").is_file()
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
        "a.put(12, 11, p.CYAN)",
        "a.put(12, 10, p.CYAN)",
    )
    asset_file.write_text(updated, encoding="utf-8")

    rc = main(["diff", "example_crate", "--base", "HEAD", "--root", str(tmp_path)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "changed=2/576" in captured.out
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

    style_file = tmp_path / "styles" / "sweetie_16.style.py"
    original_style = style_file.read_text(encoding="utf-8")
    updated_style = original_style.replace("#73eff7", "#ff00aa")
    assert updated_style != original_style
    style_file.write_text(updated_style, encoding="utf-8")

    rc = main(["diff", "example_crate", "--base", "HEAD", "--root", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "changed=0/" not in out
    assert "changed=2/576" in out

    diff_path = tmp_path / ".pixelforge" / "diffs" / "example_crate_idle.diff.png"
    assert diff_path.is_file()
    decoded = np.asarray(Image.open(diff_path).convert("RGBA"), dtype=np.uint8)
    magenta_mask = np.all(decoded == np.array([255, 42, 133, 255], dtype=np.uint8), axis=2)
    assert int(np.count_nonzero(magenta_mask)) > 0

    # Variant added only in working tree falls back to current style without crashing
    variant_style = updated_style.replace(
        '"dusk": {',
        '"night": {"CYAN": "#00ffcc"},\n        "dusk": {',
    )
    style_file.write_text(variant_style, encoding="utf-8")
    rc_variant = main(
        ["diff", "example_crate", "--base", "HEAD", "--variant", "night", "--root", str(tmp_path)]
    )
    assert rc_variant == 0


def test_cli_diff_json_and_metadata_deltas(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `diff --json` emits structured pixel + anchor/hitbox delta reports."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    asset_file = tmp_path / "assets" / "example_crate.asset.py"
    baseline_src = asset_file.read_text(encoding="utf-8") + '    a.hitbox("solid", 4, 5, 16, 15)\n'
    asset_file.write_text(baseline_src, encoding="utf-8")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    capsys.readouterr()

    updated = baseline_src.replace(
        'a.anchor("foot", 12, 20)',
        'a.anchor("foot", 14, 21)\n    a.anchor("side_port", 4, 12)',
    ).replace(
        'a.hitbox("solid", 4, 5, 16, 15)',
        'a.hitbox("solid", 4, 6, 18, 14)',
    )
    assert updated != baseline_src
    asset_file.write_text(updated, encoding="utf-8")

    rc = main(["diff", "example_crate", "--base", "HEAD", "--json", "--root", str(tmp_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["asset_id"] == "example_crate"
    assert payload["base_ref"] == "HEAD"
    assert payload["baseline_exists"] is True
    assert payload["has_pixel_changes"] is False
    assert payload["has_metadata_changes"] is True
    assert payload["has_changes"] is True
    assert payload["removed_frames"] == []
    assert len(payload["frames"]) == 1

    frame = payload["frames"][0]
    assert frame["changed_pixels"] == 0
    assert frame["anchors"] == [
        {
            "name": "foot",
            "status": "moved",
            "before": {"name": "foot", "x": 12, "y": 20},
            "after": {"name": "foot", "x": 14, "y": 21},
            "dx": 2,
            "dy": 1,
        },
        {
            "name": "side_port",
            "status": "added",
            "before": None,
            "after": {"name": "side_port", "x": 4, "y": 12},
            "dx": None,
            "dy": None,
        },
    ]
    assert frame["hitboxes"] == [
        {
            "name": "solid",
            "status": "changed",
            "before": {"name": "solid", "x": 4, "y": 5, "w": 16, "h": 15},
            "after": {"name": "solid", "x": 4, "y": 6, "w": 18, "h": 14},
            "dx": 0,
            "dy": 1,
            "dw": 2,
            "dh": -1,
        }
    ]

    # Human-readable diff also prints anchor/hitbox deltas
    assert main(["diff", "example_crate", "--base", "HEAD", "--root", str(tmp_path)]) == 0
    text_out = capsys.readouterr().out
    assert "anchor 'foot': moved (12, 20) -> (14, 21) (dx=+2, dy=+1)" in text_out
    assert "hitbox 'solid': changed (4, 5, 16x15) -> (4, 6, 18x14)" in text_out

    # Untracked new asset reports baseline_exists=False
    new_asset = tmp_path / "assets" / "new_prop.asset.py"
    new_asset.write_text(
        baseline_src.replace('id="example_crate"', 'id="new_prop"'),
        encoding="utf-8",
    )
    summary_md = tmp_path / ".pixelforge" / "diff-summary.md"
    assert (
        main(
            [
                "diff",
                "new_prop",
                "--base",
                "HEAD",
                "--json",
                "--summary-md",
                str(summary_md),
                "--root",
                str(tmp_path),
            ]
        )
        == 0
    )
    new_payload = json.loads(capsys.readouterr().out)
    assert new_payload["baseline_exists"] is False
    assert new_payload["has_pixel_changes"] is True
    assert new_payload["frames"][0]["baseline_width"] is None
    assert new_payload["metrics"]["current"]["opaque_pixels"] > 0
    assert new_payload["metrics"]["opaque_pixel_delta"] > 0
    assert "coverage_delta" in new_payload["metrics"]
    assert "emissive_pixel_delta" in new_payload["metrics"]
    assert "orphan_pixel_delta" in new_payload["metrics"]
    assert summary_md.is_file()
    md_text = summary_md.read_text(encoding="utf-8")
    assert "### Pixelforge Diff: `new_prop`" in md_text
    assert "| Opaque Pixels |" in md_text
    assert "| Canvas Coverage |" in md_text
    assert "| Emissive Pixels |" in md_text
    assert "| Orphan Pixels |" in md_text


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
            "sweetie-16",
            "--size",
            "8x6",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "ephemeral=true" in out
    assert "src=32x24" in out
    assert "4:3" in out
    assert "SKY" in out or "CYAN" in out
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


def test_cli_unfiltered_render_replaces_stale_manifest_and_filtered_merges(
    tmp_path: Path,
) -> None:
    """Unfiltered `render` replaces manifest atomically; filtered `render <id>` merges."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    _add_sibling_asset(tmp_path, "sibling_crate")
    out_dir = tmp_path / "dist"

    assert main(["render", "--root", str(tmp_path)]) == 0
    manifest_before = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest_before.keys()) == {"example_crate", "sibling_crate"}

    # Filtered render preserves sibling entry in manifest.json
    assert main(["render", "example_crate", "--root", str(tmp_path)]) == 0
    manifest_filtered = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest_filtered.keys()) == {"example_crate", "sibling_crate"}

    # Remove sibling asset and run unfiltered render: stale entry must be removed
    (tmp_path / "assets" / "sibling_crate.asset.py").unlink()
    assert main(["render", "--root", str(tmp_path)]) == 0
    manifest_after = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest_after.keys()) == {"example_crate"}
    dts = (out_dir / "manifest.d.ts").read_text(encoding="utf-8")
    assert '"example_crate"' in dts
    assert '"sibling_crate"' not in dts


def test_cli_multi_style_indexed_ts_namespaces_per_style(tmp_path: Path) -> None:
    """Multi-style `--indexed-ts` writes into `dist/indexed/<style_slug>/` without overwriting."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    second_style = (
        (tmp_path / "styles" / "sweetie_16.style.py")
        .read_text(encoding="utf-8")
        .replace("sweetie-16", "retro-amber")
    )
    (tmp_path / "styles" / "retro_amber.style.py").write_text(second_style, encoding="utf-8")
    second_asset = (
        (tmp_path / "assets" / "example_crate.asset.py")
        .read_text(encoding="utf-8")
        .replace('id="example_crate"', 'id="amber_crate"')
        .replace("'sweetie-16'", "'retro-amber'")
        .replace('"sweetie-16"', '"retro-amber"')
    )
    (tmp_path / "assets" / "amber_crate.asset.py").write_text(second_asset, encoding="utf-8")

    assert main(["render", "--root", str(tmp_path), "--indexed-ts"]) == 0
    out_dir = tmp_path / "dist" / "indexed"
    assert (out_dir / "sweetie_16" / "manifest.generated.ts").is_file()
    assert (out_dir / "retro_amber" / "manifest.generated.ts").is_file()
    assert not (out_dir / "manifest.generated.ts").exists()


def test_cli_render_no_emissive_animate_apng_and_sheet_variant(tmp_path: Path) -> None:
    """Verify `--no-emissive`, `--animate-format apng`, and `--sheet --variant`."""
    assert main(["init", "--root", str(tmp_path)]) == 0

    style_file = tmp_path / "styles" / "sweetie_16.style.py"
    style_src = style_file.read_text(encoding="utf-8").replace(
        '"dusk": {',
        '"amber": {"CYAN": "#ffaa00"},\n        "dusk": {',
    )
    style_file.write_text(style_src, encoding="utf-8")

    asset_file = tmp_path / "assets" / "example_crate.asset.py"
    asset_src = asset_file.read_text(encoding="utf-8").replace("frames=1,", "frames=2,")
    asset_file.write_text(asset_src, encoding="utf-8")

    rc = main(
        [
            "render",
            "--root",
            str(tmp_path),
            "--no-emissive",
            "--animate",
            "--animate-format",
            "apng",
            "--sheet",
            "--variant",
            "amber",
        ]
    )
    assert rc == 0

    out_dir = tmp_path / "dist"
    assert (out_dir / "sprites" / "example_crate_idle.png").is_file()
    assert not (out_dir / "sprites" / "example_crate_idle_emissive.png").exists()
    assert (tmp_path / ".pixelforge" / "previews" / "example_crate_idle.apng").is_file()

    sheet_path = tmp_path / ".pixelforge" / "sheets" / "example_crate.contact.png"
    assert sheet_path.is_file()
    sheet_rgba = np.asarray(Image.open(sheet_path).convert("RGBA"), dtype=np.uint8)
    amber_mask = np.all(sheet_rgba == np.array([255, 170, 0, 255], dtype=np.uint8), axis=2)
    assert int(np.count_nonzero(amber_mask)) > 0


def test_cli_compose_mounts_props_and_validates_anchors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `compose` mounts props onto parent anchors and rejects invalid anchors."""
    repo_root = Path(__file__).resolve().parents[2]
    rc = main(
        [
            "compose",
            "bedroom_desk_iso",
            "--mount",
            "old_laptop@hardware_0:foot",
            "--mount",
            "ai_cluster_node@hardware_2",
            "--state",
            "night",
            "--strict-bounds",
            "--sheet",
            "--out",
            str(tmp_path / "composed"),
            "--root",
            str(repo_root),
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "status=ok parent=bedroom_desk_iso" in captured.out
    assert "props=2" in captured.out
    assert (tmp_path / "composed" / "bedroom_desk_iso_night_composed.png").is_file()
    sheet_path = repo_root / ".pixelforge" / "sheets" / "bedroom_desk_iso_composed.contact.png"
    assert sheet_path.is_file()
    sheet_path.unlink(missing_ok=True)

    bad_rc = main(
        [
            "compose",
            "bedroom_desk_iso",
            "--mount",
            "old_laptop@nonexistent_anchor",
            "--root",
            str(repo_root),
        ]
    )
    assert bad_rc == 1
    bad_captured = capsys.readouterr()
    assert "Anchor 'nonexistent_anchor' not found" in bad_captured.err


def test_cli_compose_validates_perspective(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `compose` warns on perspective mismatch and fails under `--strict-perspective`."""
    repo_root = Path(__file__).resolve().parents[2]
    warn_rc = main(
        [
            "compose",
            "bedroom_desk_iso",
            "--mount",
            "old_laptop@hardware_0:foot",
            "--out",
            str(tmp_path / "warn"),
            "--root",
            str(repo_root),
        ]
    )
    assert warn_rc == 0
    warn_captured = capsys.readouterr()
    assert "warn=Prop 'old_laptop' has perspective 'front-2.5d'" in warn_captured.out

    strict_rc = main(
        [
            "compose",
            "bedroom_desk_iso",
            "--mount",
            "old_laptop@hardware_0:foot",
            "--strict-perspective",
            "--out",
            str(tmp_path / "strict"),
            "--root",
            str(repo_root),
        ]
    )
    assert strict_rc == 1
    strict_captured = capsys.readouterr()
    assert "Prop 'old_laptop' has perspective 'front-2.5d'" in strict_captured.err

    iso_rc = main(
        [
            "compose",
            "bedroom_desk_iso",
            "--mount",
            "old_laptop_iso@hardware_0:foot",
            "--mount",
            "used_gpu_rig_iso@hardware_1:foot",
            "--mount",
            "ai_cluster_node_iso@hardware_2:foot",
            "--state",
            "night",
            "--strict-bounds",
            "--strict-perspective",
            "--out",
            str(tmp_path / "iso"),
            "--root",
            str(repo_root),
        ]
    )
    assert iso_rc == 0
    iso_captured = capsys.readouterr()
    assert "props=3" in iso_captured.out
    assert "warn=" not in iso_captured.out


def test_cli_render_and_watch_with_atlas_flags(tmp_path: Path) -> None:
    """Verify `render --atlas all` and `watch --atlas aseprite` emit atlas JSON files."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    out_dir = tmp_path / "dist"

    rc = main(["render", "--root", str(tmp_path), "--out", str(out_dir), "--atlas", "all"])
    assert rc == 0

    aseprite_path = out_dir / "sprites" / "example_crate.aseprite.json"
    tp_path = out_dir / "sprites" / "example_crate.texturepacker.json"
    assert aseprite_path.is_file()
    assert tp_path.is_file()

    aseprite_doc = json.loads(aseprite_path.read_text(encoding="utf-8"))
    assert aseprite_doc["meta"]["image"] == "example_crate_idle.png"
    assert aseprite_doc["meta"]["frameTags"] == [
        {"name": "idle", "from": 0, "to": 0, "direction": "forward"}
    ]

    tp_doc = json.loads(tp_path.read_text(encoding="utf-8"))
    assert tp_doc["animations"] == {"idle": ["example_crate/idle/0"]}

    watch_out = tmp_path / "watch_dist"
    watch_rc = main(
        [
            "watch",
            "--root",
            str(tmp_path),
            "--out",
            str(watch_out),
            "--atlas",
            "aseprite",
            "--interval",
            "0.01",
            "--max-cycles",
            "0",
        ]
    )
    assert watch_rc == 0
    assert (watch_out / "sprites" / "example_crate.aseprite.json").is_file()
    assert not (watch_out / "sprites" / "example_crate.texturepacker.json").exists()


def test_cli_render_and_watch_indexed_ts_lazy(tmp_path: Path) -> None:
    """Verify `--indexed-ts-lazy` emits lazy-decoding sprites.generated.ts in render and watch."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    out_dir = tmp_path / "dist"

    rc_render = main(
        ["render", "--root", str(tmp_path), "--out", str(out_dir), "--indexed-ts-lazy"]
    )
    assert rc_render == 0
    sprites_ts = (out_dir / "indexed" / "sprites.generated.ts").read_text(encoding="utf-8")
    assert "createLazySpriteFrame(" in sprites_ts

    watch_out = tmp_path / "watch_dist"
    rc_watch = main(
        [
            "watch",
            "--root",
            str(tmp_path),
            "--out",
            str(watch_out),
            "--indexed-ts-lazy",
            "--interval",
            "0.01",
            "--max-cycles",
            "0",
        ]
    )
    assert rc_watch == 0
    watch_sprites = (watch_out / "indexed" / "sprites.generated.ts").read_text(encoding="utf-8")
    assert "createLazySpriteFrame(" in watch_sprites


def test_cli_watch_incremental_dependency_invalidation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `watch` incrementally rebuilds only affected assets on edits and deletes."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    _add_sibling_asset(tmp_path, "sibling_crate")

    alt_style_src = (
        (tmp_path / "styles" / "sweetie_16.style.py")
        .read_text(encoding="utf-8")
        .replace("sweetie-16", "alt-style")
    )
    (tmp_path / "styles" / "alt_style.style.py").write_text(alt_style_src, encoding="utf-8")

    alt_asset_src = (
        (tmp_path / "assets" / "example_crate.asset.py")
        .read_text(encoding="utf-8")
        .replace('id="example_crate"', 'id="alt_box"')
        .replace("sweetie-16", "alt-style")
    )
    (tmp_path / "assets" / "alt_box.asset.py").write_text(alt_asset_src, encoding="utf-8")
    capsys.readouterr()

    out_dir = tmp_path / "dist"
    cycle_idx = 0
    cycle_logs: list[str] = []

    def fake_sleep(_interval: float) -> None:
        nonlocal cycle_idx
        cycle_logs.append(capsys.readouterr().out)
        cycle_idx += 1
        if cycle_idx == 1:
            # Edit only sibling_crate.asset.py
            sib = tmp_path / "assets" / "sibling_crate.asset.py"
            text = sib.read_text(encoding="utf-8") + "\n# touch\n"
            sib.write_text(text, encoding="utf-8")
            os.utime(sib, ns=(sib.stat().st_atime_ns, sib.stat().st_mtime_ns + 1_000_000))
        elif cycle_idx == 2:
            # Edit sweetie_16.style.py -> rebuilds example_crate & sibling_crate, not alt_box
            sty = tmp_path / "styles" / "sweetie_16.style.py"
            text = sty.read_text(encoding="utf-8") + "\n# style touch\n"
            sty.write_text(text, encoding="utf-8")
            os.utime(sty, ns=(sty.stat().st_atime_ns, sty.stat().st_mtime_ns + 1_000_000))
        elif cycle_idx == 3:
            # Delete sibling_crate -> prunes manifest & indexed-ts without re-rendering others
            (tmp_path / "assets" / "sibling_crate.asset.py").unlink()

    monkeypatch.setattr("time.sleep", fake_sleep)
    rc = main(
        [
            "watch",
            "--root",
            str(tmp_path),
            "--out",
            str(out_dir),
            "--indexed-ts",
            "--interval",
            "0.01",
            "--max-cycles",
            "4",
        ]
    )
    assert rc == 0
    cycle_logs.append(capsys.readouterr().out)

    # Initial pass rendered all 3 assets
    assert "watch event=render target=example_crate" in cycle_logs[0]
    assert "watch event=render target=sibling_crate" in cycle_logs[0]
    assert "watch event=render target=alt_box" in cycle_logs[0]

    # Cycle 1: only sibling_crate rebuilt
    assert "watch event=render target=sibling_crate" in cycle_logs[1]
    assert "watch event=render target=example_crate" not in cycle_logs[1]
    assert "watch event=render target=alt_box" not in cycle_logs[1]

    # Cycle 2: homelab-16bit assets rebuilt, alt-style asset untouched
    assert "watch event=render target=example_crate" in cycle_logs[2]
    assert "watch event=render target=sibling_crate" in cycle_logs[2]
    assert "rendered alt_box" not in cycle_logs[2]

    # Cycle 3: deletion pruned sibling_crate from manifest and indexed-ts
    assert "rendered example_crate" not in cycle_logs[3]
    assert "rendered alt_box" not in cycle_logs[3]
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest.keys()) == {"alt_box", "example_crate"}
    homelab_sprites = (out_dir / "indexed" / "sweetie_16" / "sprites.generated.ts").read_text(
        encoding="utf-8"
    )
    assert '"example_crate"' in homelab_sprites
    assert '"sibling_crate"' not in homelab_sprites


def test_cli_declarative_scene_render_check_compose_and_watch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `.scene.py` integrates with `check`, `render`, `watch`, and `compose --animate`."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    _add_sibling_asset(tmp_path, "lamp_prop")
    lamp_path = tmp_path / "assets" / "lamp_prop.asset.py"
    lamp_src = (
        lamp_path.read_text(encoding="utf-8")
        .replace(
            "frames=1,",
            "frames=2,",
        )
        .replace(
            "a.put(12, 11, p.CYAN)",
            "a.put(12, 11, p.CYAN if a.frame == 0 else p.SLATE_L)",
        )
    )
    lamp_path.write_text(lamp_src, encoding="utf-8")

    scene_path = tmp_path / "assets" / "crate_scene.scene.py"
    scene_path.write_text(
        '"""Declarative test scene."""\n'
        "from __future__ import annotations\n"
        "from pixelforge.export.scene import SceneMountSpec, SceneSpec\n"
        "SCENE = SceneSpec(\n"
        '    id="crate_scene",\n'
        '    parent_id="example_crate",\n'
        '    depth_sort="iso_y",\n'
        "    mounts=(\n"
        '        SceneMountSpec(prop_id="lamp_prop", anchor="foot", prop_anchor="foot"),\n'
        "    ),\n"
        ")\n",
        encoding="utf-8",
    )

    assert main(["check", "--root", str(tmp_path)]) == 0

    out_dir = tmp_path / "dist"
    assert (
        main(
            [
                "render",
                "--root",
                str(tmp_path),
                "--out",
                str(out_dir),
                "--animate",
                "--sheet",
                "--indexed-ts",
            ]
        )
        == 0
    )
    assert (out_dir / "sprites" / "crate_scene_idle.png").is_file()
    assert (out_dir / "sprites" / "crate_scene_sheet.png").is_file()
    assert (tmp_path / ".pixelforge" / "previews" / "crate_scene_idle.gif").is_file()
    assert (tmp_path / ".pixelforge" / "sheets" / "crate_scene.contact.png").is_file()

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "crate_scene" in manifest
    assert manifest["crate_scene"]["frames"] == 2
    dts = (out_dir / "manifest.d.ts").read_text(encoding="utf-8")
    assert '"crate_scene"' in dts
    sprites_ts = (out_dir / "indexed" / "sprites.generated.ts").read_text(encoding="utf-8")
    assert '"crate_scene"' in sprites_ts

    # Verify `compose --depth-sort iso_y --animate` emits animated GIF
    assert (
        main(
            [
                "compose",
                "example_crate",
                "--mount",
                "lamp_prop@foot:foot",
                "--depth-sort",
                "iso_y",
                "--animate",
                "--root",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert (tmp_path / ".pixelforge" / "previews" / "example_crate_idle_composed.gif").is_file()

    # Verify `watch` rebuilds dependent scene when prop asset changes
    capsys.readouterr()
    cycle_logs: list[str] = []

    def fake_sleep(_interval: float) -> None:
        cycle_logs.append(capsys.readouterr().out)
        if len(cycle_logs) == 1:
            lamp_path.write_text(lamp_src.replace("fps=4,", "fps=6,"), encoding="utf-8")

    monkeypatch.setattr("time.sleep", fake_sleep)
    assert (
        main(
            [
                "watch",
                "--root",
                str(tmp_path),
                "--out",
                str(out_dir),
                "--indexed-ts",
                "--interval",
                "0.01",
                "--max-cycles",
                "1",
            ]
        )
        == 0
    )
    cycle_logs.append(capsys.readouterr().out)
    assert "watch event=render target=lamp_prop" in cycle_logs[1]
    assert "watch event=render target=crate_scene" in cycle_logs[1]
    assert "watch event=render target=example_crate" not in cycle_logs[1]


def test_cli_output_formats_llm_json_human_and_conflicts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `--format llm|json|human`, `--json`, `--human`, and conflict errors."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    capsys.readouterr()

    # 1. check: default llm, --json, --human, and violation hint
    assert main(["check", "--root", str(tmp_path)]) == 0
    out_llm = capsys.readouterr().out
    assert "status=pass assets=1 styles=1 errors=0 warnings=0" in out_llm

    assert main(["check", "--json", "--root", str(tmp_path)]) == 0
    check_json = json.loads(capsys.readouterr().out)
    assert check_json["passed"] is True
    assert check_json["assets_checked"] == 1

    assert main(["check", "--human", "--root", str(tmp_path)]) == 0
    assert "checked 1 asset(s), 1 style(s): 0 error(s), 0 warning(s)" in capsys.readouterr().out

    # 2. render: default llm, --format json, --format human
    assert main(["render", "--root", str(tmp_path)]) == 0
    render_llm = capsys.readouterr().out
    assert "asset=example_crate style=sweetie-16 size=24x24" in render_llm
    assert "summary rendered=1" in render_llm

    assert main(["render", "--format", "json", "--root", str(tmp_path)]) == 0
    render_json = json.loads(capsys.readouterr().out)
    assert render_json["count"] == 1
    assert render_json["rendered"][0]["id"] == "example_crate"

    assert main(["render", "--format", "human", "--root", str(tmp_path)]) == 0
    assert "rendered example_crate -> " in capsys.readouterr().out

    # 3. analyze-ref: --json and --human
    ref_png = tmp_path / ".pixelforge" / "refs" / "sample.png"
    ref_png.parent.mkdir(parents=True, exist_ok=True)
    rgba = np.full((16, 16, 4), (56, 189, 248, 255), dtype=np.uint8)
    Image.fromarray(rgba, mode="RGBA").save(ref_png, format="PNG")

    assert (
        main(["analyze-ref", str(ref_png), "--size", "4x4", "--json", "--root", str(tmp_path)]) == 0
    )
    ref_json = json.loads(capsys.readouterr().out)
    assert ref_json["ephemeral"] is True
    assert ref_json["target_width"] == 4

    assert (
        main(["analyze-ref", str(ref_png), "--size", "4x4", "--human", "--root", str(tmp_path)])
        == 0
    )
    assert "EPHEMERAL REFERENCE SKETCH" in capsys.readouterr().out

    # 4. compose: --json and --human
    repo_root = Path(__file__).resolve().parents[2]
    assert (
        main(
            [
                "compose",
                "bedroom_desk_iso",
                "--mount",
                "old_laptop_iso@hardware_0:foot",
                "--json",
                "--out",
                str(tmp_path / "comp"),
                "--root",
                str(repo_root),
            ]
        )
        == 0
    )
    comp_json = json.loads(capsys.readouterr().out)
    assert comp_json["parent_id"] == "bedroom_desk_iso"
    assert comp_json["props_count"] == 1

    # 5. watch: --json
    assert (
        main(
            [
                "watch",
                "--json",
                "--root",
                str(tmp_path),
                "--max-cycles",
                "1",
                "--interval",
                "0.01",
            ]
        )
        == 0
    )
    watch_lines = [line for line in capsys.readouterr().out.strip().splitlines() if line]
    assert json.loads(watch_lines[0])["event"] == "render"

    # 6. critic: --human and --json (with git no-changes skip)
    def _no_changes(_root: Path, *, base_ref: str) -> set[Path]:
        _ = base_ref
        return set()

    monkeypatch.setattr(
        "pixelforge.cli.critic_cmd.discover_changed_paths_from_git",
        _no_changes,
    )
    assert main(["critic", "--base", "HEAD", "--human", "--root", str(tmp_path)]) == 0
    assert "skipping critic" in capsys.readouterr().out
    assert main(["critic", "--base", "HEAD", "--json", "--root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True

    # 7. Conflicting format flags fail cleanly with exit code 2
    assert main(["check", "--json", "--human", "--root", str(tmp_path)]) == 2
    assert "Cannot combine --json and --human" in capsys.readouterr().err
    assert main(["render", "--format", "llm", "--json", "--root", str(tmp_path)]) == 2
    assert "Conflicting output flags" in capsys.readouterr().err


def test_cli_watch_serve_updates_studio_state_and_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `watch --serve` feeds StudioState across edits/errors and shuts down cleanly."""
    from pixelforge.export.studio import StudioState

    assert main(["init", "--root", str(tmp_path)]) == 0
    capsys.readouterr()

    captured: dict[str, object] = {}

    class _FakeStudioServer:
        def __init__(
            self, state: StudioState, *, host: str = "127.0.0.1", port: int = 4173
        ) -> None:
            self.state = state
            self.host = host
            self.port = port
            self.started = False
            self.stopped = False
            captured["server"] = self

        def start(self) -> str:
            self.started = True
            return f"http://{self.host}:{self.port}/"

        def stop(self) -> None:
            self.stopped = True

    asset_path = tmp_path / "assets" / "example_crate.asset.py"
    original_src = asset_path.read_text(encoding="utf-8")
    cycle = 0
    revisions: list[tuple[int, str | None]] = []

    def fake_sleep(_interval: float) -> None:
        nonlocal cycle
        srv = captured["server"]
        assert isinstance(srv, _FakeStudioServer)
        revisions.append((srv.state.revision, srv.state.last_error))
        cycle += 1
        if cycle == 1:
            # Introduce a guard error (raw hex) -> studio should keep serving with error banner
            asset_path.write_text(original_src + '\n_BAD = "#ff00ff"\n', encoding="utf-8")
            os.utime(
                asset_path,
                ns=(asset_path.stat().st_atime_ns, asset_path.stat().st_mtime_ns + 1_000_000),
            )
        elif cycle == 2:
            # Fix the error -> studio clears last_error and advances revision
            asset_path.write_text(original_src + "\n# fixed\n", encoding="utf-8")
            os.utime(
                asset_path,
                ns=(asset_path.stat().st_atime_ns, asset_path.stat().st_mtime_ns + 2_000_000),
            )

    monkeypatch.setattr("pixelforge.cli.watch_cmd.StudioServer", _FakeStudioServer)
    monkeypatch.setattr("time.sleep", fake_sleep)

    rc = main(
        [
            "watch",
            "--serve",
            "--host",
            "127.0.0.1",
            "--port",
            "4321",
            "--root",
            str(tmp_path),
            "--interval",
            "0.01",
            "--max-cycles",
            "3",
        ]
    )
    assert rc == 0
    out_text = capsys.readouterr().out
    assert "watch event=serve url=http://127.0.0.1:4321/" in out_text

    srv = captured["server"]
    assert isinstance(srv, _FakeStudioServer)
    assert srv.started is True
    assert srv.stopped is True
    assert revisions[0] == (1, None)
    assert revisions[1][0] == 2
    assert revisions[1][1] is not None and "raw-hex" in revisions[1][1]
    assert revisions[2] == (3, None)
    assert srv.state.render_png("example_crate", sheet=False)

    # Also verify `--json` serve event formatting
    assert (
        main(
            [
                "watch",
                "--serve",
                "--port",
                "4322",
                "--json",
                "--root",
                str(tmp_path),
                "--interval",
                "0.01",
                "--max-cycles",
                "1",
            ]
        )
        == 0
    )
    json_lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines() if line]
    assert any(
        ev.get("event") == "serve" and ev.get("url") == "http://127.0.0.1:4322/"
        for ev in json_lines
    )
