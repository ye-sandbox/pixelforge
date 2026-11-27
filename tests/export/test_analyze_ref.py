"""Hermetic tests for reference image proportion and quantized ASCII sketch analyzer."""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pixelforge.cli.main import main
from pixelforge.core.types import PaletteColor, StylePack
from pixelforge.export.analyze_ref import (
    analyze_reference_image,
    emit_spr_snippet,
    parse_sketch_size,
    sanitize_asset_id,
    scaffold_asset_from_analysis,
)
from pixelforge.guard.ast_rules import check_ast_file
from pixelforge.guard.runner import load_asset_module
from pixelforge.guard.runtime_rules import check_asset_runtime


def _sample_style() -> StylePack:
    return StylePack(
        id="test-style",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="CYAN_GLOW", hex="#00e5ff", flags=("emissive",)),
            PaletteColor(index=2, name="RUST_RED", hex="#dc2626", flags=("surface",)),
        ),
    )


def _make_png_bytes(rgba: np.ndarray) -> io.BytesIO:
    buf = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_analyze_reference_image_proportions_histogram_and_sketch() -> None:
    """Verify aspect ratio, quantized palette histogram, and ASCII sketch from in-memory PNG."""
    style = _sample_style()
    # 160x80 (2:1) image: left half cyan, right half dark outline, bottom-right transparent corner.
    rgba = np.zeros((80, 160, 4), dtype=np.uint8)
    rgba[:, :80] = (0, 229, 255, 255)
    rgba[:, 80:] = (13, 17, 23, 255)
    rgba[60:, 120:] = (0, 0, 0, 0)

    png_buf = _make_png_bytes(rgba)
    analysis = analyze_reference_image(png_buf, style, size=(8, 4), include_emissive=True)

    assert analysis.source_width == 160
    assert analysis.source_height == 80
    assert analysis.aspect_ratio == 2.0
    assert analysis.simplified_ratio == "2:1"
    assert analysis.target_width == 8
    assert analysis.target_height == 4
    assert analysis.style_id == "test-style"

    assert len(analysis.ascii_sketch) == 4
    assert all(len(row) == 8 for row in analysis.ascii_sketch)
    assert "." in analysis.ascii_sketch[3]

    tokens = {entry.token: entry for entry in analysis.histogram}
    assert set(tokens) == {"CYAN_GLOW", "OUTLINE"}
    assert tokens["CYAN_GLOW"].pixels > tokens["OUTLINE"].pixels
    assert round(sum(e.percentage for e in analysis.histogram), 1) == 100.0

    report = analysis.format_report()
    assert "EPHEMERAL REFERENCE SKETCH" in report
    assert "2:1" in report
    assert "CYAN_GLOW" in report


def test_analyze_reference_image_all_transparent() -> None:
    """Verify fully transparent PNGs produce an empty histogram and dot-filled sketch."""
    rgba = np.zeros((16, 16, 4), dtype=np.uint8)
    analysis = analyze_reference_image(_make_png_bytes(rgba), _sample_style(), size=(4, 4))

    assert analysis.histogram == ()
    assert analysis.legend == {}
    assert analysis.ascii_sketch == ("....", "....", "....", "....")
    assert "(no opaque pixels)" in analysis.format_report()


def test_parse_sketch_size_validation() -> None:
    """Verify `WxH` parsing and bounds enforcement."""
    assert parse_sketch_size("64x32") == (64, 32)
    assert parse_sketch_size(" 16X16 ") == (16, 16)

    for bad in ("64", "axb", "0x16", "129x32", "32x0"):
        with pytest.raises(ValueError):
            parse_sketch_size(bad)


def test_scaffold_asset_from_analysis_passes_guards(tmp_path: Path) -> None:
    """Generated Layer/Plane/StylePack-tokenized .asset.py skeleton passes AST & runtime guards."""
    style = _sample_style()
    rgba = np.zeros((32, 32, 4), dtype=np.uint8)
    rgba[4:28, 4:28] = (220, 38, 38, 255)
    rgba[10:14, 14:18] = (0, 229, 255, 255)

    analysis = analyze_reference_image(
        _make_png_bytes(rgba), style, size=(16, 16), include_emissive=True
    )
    source = scaffold_asset_from_analysis(analysis, style, asset_id="Server-Rack 01")

    assert 'id="server_rack_01"' in source
    assert "with a.layer(" in source
    assert "with a.plane(" in source
    assert "p.RUST_RED" in source
    assert "p.CYAN_GLOW" in source
    assert "TestStylePalette" in source

    asset_path = tmp_path / "server_rack_01.asset.py"
    asset_path.write_text(source, encoding="utf-8")
    assert check_ast_file(asset_path, scope="asset") == []

    loaded = load_asset_module(asset_path)
    assert check_asset_runtime(loaded, style, file_path=str(asset_path)) == []


def test_scaffold_asset_from_empty_reference(tmp_path: Path) -> None:
    """All-transparent reference still generates a valid non-degenerate Layer/Plane skeleton."""
    style = _sample_style()
    rgba = np.zeros((16, 16, 4), dtype=np.uint8)
    analysis = analyze_reference_image(_make_png_bytes(rgba), style, size=(8, 8))
    source = scaffold_asset_from_analysis(analysis, style, asset_id="123")

    assert sanitize_asset_id("123") == "asset_123"
    asset_path = tmp_path / "asset_123.asset.py"
    asset_path.write_text(source, encoding="utf-8")
    assert check_ast_file(asset_path, scope="asset") == []
    loaded = load_asset_module(asset_path)
    assert check_asset_runtime(loaded, style, file_path=str(asset_path)) == []


def test_cli_analyze_ref_scaffold_and_write(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `pixelforge analyze-ref --scaffold` JSON output and `--out` / `--force` behavior."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    capsys.readouterr()

    ref_path = tmp_path / "ref_rack.png"
    rgba = np.zeros((32, 32, 4), dtype=np.uint8)
    rgba[4:28, 4:28] = (55, 65, 81, 255)
    Image.fromarray(rgba, mode="RGBA").save(ref_path)

    rc = main(
        [
            "analyze-ref",
            str(ref_path),
            "--size",
            "16x16",
            "--scaffold",
            "--format",
            "json",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "scaffold_source" in payload
    assert "with a.layer(" in payload["scaffold_source"]
    assert "with a.plane(" in payload["scaffold_source"]

    out_dir = tmp_path / "assets"
    rc_write = main(
        [
            "analyze-ref",
            str(ref_path),
            "--size",
            "16x16",
            "--scaffold",
            "--id",
            "custom_rack",
            "--out",
            str(out_dir),
            "--format",
            "json",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc_write == 0
    capsys.readouterr()
    written = out_dir / "custom_rack.asset.py"
    assert written.is_file()

    # Refuses overwrite without --force
    assert (
        main(
            [
                "analyze-ref",
                str(ref_path),
                "--scaffold",
                "--id",
                "custom_rack",
                "--out",
                str(out_dir),
                "--root",
                str(tmp_path),
            ]
        )
        == 1
    )
    capsys.readouterr()

    # Overwrites when --force is set, and resulting project passes `pixelforge check`
    assert (
        main(
            [
                "analyze-ref",
                str(ref_path),
                "--scaffold",
                "--id",
                "custom_rack",
                "--out",
                str(out_dir),
                "--force",
                "--root",
                str(tmp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["check", "--format", "json", "--root", str(tmp_path)]) == 0
    check_payload = json.loads(capsys.readouterr().out)
    assert check_payload["passed"] is True


def test_analyze_ref_excludes_emissive_by_default_and_uses_oklab() -> None:
    """Verify emissive tokens are excluded by default and OKLab quantization is perceptual."""
    style = StylePack(
        id="oklab-test",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="CYAN_GLOW", hex="#00e5ff", flags=("emissive",)),
            PaletteColor(index=2, name="TEAL_PAINT", hex="#1b7a8a", flags=("surface",)),
            PaletteColor(index=3, name="RUST_RED", hex="#dc2626", flags=("surface",)),
        ),
    )
    rgba = np.zeros((8, 8, 4), dtype=np.uint8)
    rgba[:, :] = (0, 229, 255, 255)

    default_analysis = analyze_reference_image(_make_png_bytes(rgba), style, size=(4, 4))
    default_tokens = {e.token for e in default_analysis.histogram}
    assert "CYAN_GLOW" not in default_tokens
    assert default_tokens == {"TEAL_PAINT"}

    emissive_analysis = analyze_reference_image(
        _make_png_bytes(rgba), style, size=(4, 4), include_emissive=True
    )
    assert {e.token for e in emissive_analysis.histogram} == {"CYAN_GLOW"}


def test_analyze_ref_trim_and_edge_preserving_downscale() -> None:
    """Verify `--trim` auto-crops transparent margins and downscaling preserves crisp edges."""
    style = _sample_style()
    rgba = np.zeros((32, 32, 4), dtype=np.uint8)
    # 16x8 solid red bar surrounded by transparent margins, with 1px-sharp border.
    rgba[12:20, 8:24] = (220, 38, 38, 255)

    trimmed = analyze_reference_image(_make_png_bytes(rgba), style, size=(8, 4), trim=True)
    assert trimmed.source_width == 32
    assert trimmed.source_height == 32
    assert trimmed.trim_bbox == (8, 12, 23, 19)
    assert trimmed.simplified_ratio == "2:1"
    assert all(row == trimmed.ascii_sketch[0] for row in trimmed.ascii_sketch)
    assert "." not in "".join(trimmed.ascii_sketch)

    # All-transparent image with trim=True should not crash.
    empty = np.zeros((16, 16, 4), dtype=np.uint8)
    empty_analysis = analyze_reference_image(_make_png_bytes(empty), style, size=(4, 4), trim=True)
    assert empty_analysis.trim_bbox is None
    assert empty_analysis.histogram == ()


def test_analyze_ref_emit_spr_and_cli_flags(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `--emit-spr` standalone, `--scaffold --emit-spr`, and `--trim` CLI flags."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    capsys.readouterr()

    ref_path = tmp_path / "padded_box.png"
    rgba = np.zeros((32, 32, 4), dtype=np.uint8)
    rgba[8:24, 8:24] = (55, 65, 81, 255)
    Image.fromarray(rgba, mode="RGBA").save(ref_path)

    rc = main(
        [
            "analyze-ref",
            str(ref_path),
            "--size",
            "8x8",
            "--trim",
            "--emit-spr",
            "--scaffold",
            "--id",
            "spr_box",
            "--format",
            "json",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["trim_bbox"] == [8, 8, 23, 23]
    assert "a.spr(grid, 0, 0, color_map)" in payload["spr_snippet"]
    assert "a.spr(grid, 0, 0, color_map)" in payload["scaffold_source"]

    asset_path = tmp_path / "assets" / "spr_box.asset.py"
    asset_path.write_text(payload["scaffold_source"], encoding="utf-8")
    assert check_ast_file(asset_path, scope="asset") == []

    # Standalone snippet helper
    analysis = analyze_reference_image(ref_path, _sample_style(), size=(4, 4), trim=True)
    snippet = emit_spr_snippet(analysis)
    assert "grid = (" in snippet
    assert "a.spr(grid, 0, 0, color_map)" in snippet
