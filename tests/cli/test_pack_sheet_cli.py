"""Hermetic CLI tests for `pixelforge render --pack-sheet` and filters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelforge.cli.main import main
from pixelforge.export.png import assert_binary_alpha, decode_png_to_rgba

_STYLE_CODE = """
from pixelforge.core.types import PaletteColor, StylePack

STYLE = StylePack(
    id="{style_id}",
    perspective="iso-2:1",
    lighting_angle="top-left",
    outline_index=0,
    palette=(
        PaletteColor(index=0, name="OUTLINE", hex="#101218", flags=("outline",)),
        PaletteColor(index=1, name="FILL", hex="#556677"),
    ),
)
"""

_ASSET_CODE = """
from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec

SPEC = AssetSpec(
    id="{asset_id}",
    style_id="{style_id}",
    width={w},
    height={h},
    perspective="iso-2:1",
)

def render(a: Asset) -> None:
    a.rect(1, 1, {w} - 2, {h} - 2, a.pal.FILL)
"""


def _write_project(tmp_path: Path) -> None:
    (tmp_path / "styles").mkdir(parents=True)
    (tmp_path / "assets" / "props").mkdir(parents=True)
    (tmp_path / "assets" / "extra").mkdir(parents=True)

    (tmp_path / "styles" / "pack_a.style.py").write_text(
        _STYLE_CODE.format(style_id="pack_a"), encoding="utf-8"
    )
    (tmp_path / "styles" / "pack_b.style.py").write_text(
        _STYLE_CODE.format(style_id="pack_b"), encoding="utf-8"
    )

    (tmp_path / "assets" / "props" / "crate.asset.py").write_text(
        _ASSET_CODE.format(asset_id="crate", style_id="pack_a", w=12, h=12),
        encoding="utf-8",
    )
    (tmp_path / "assets" / "props" / "lamp.asset.py").write_text(
        _ASSET_CODE.format(asset_id="lamp", style_id="pack_a", w=10, h=16),
        encoding="utf-8",
    )
    (tmp_path / "assets" / "extra" / "sign.asset.py").write_text(
        _ASSET_CODE.format(asset_id="sign", style_id="pack_b", w=14, h=10),
        encoding="utf-8",
    )


def test_cli_render_pack_sheet_with_dir_and_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path)
    code = main(
        [
            "render",
            "--pack-sheet",
            "--dir",
            "props",
            "--format",
            "json",
            "--root",
            str(tmp_path),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 2
    sheet_path = Path(payload["pack_sheet"])
    assert sheet_path.name == "props.contact.png"
    assert sheet_path.is_file()
    assert payload["pack_metrics"]["asset_count"] == 2
    assert payload["pack_metrics"]["scale_consistent"] is True
    assert payload["pack_metrics"]["lighting_consistent"] is True
    assert payload["pack_metrics"]["outline_consistent"] is True

    decoded = decode_png_to_rgba(sheet_path.read_bytes())
    assert_binary_alpha(decoded)


def test_cli_render_pack_sheet_with_pack_and_ids_filters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path)

    code_pack = main(
        [
            "render",
            "--pack-sheet",
            "--pack",
            "pack_b",
            "--root",
            str(tmp_path),
        ]
    )
    assert code_pack == 0
    out_pack = capsys.readouterr().out
    assert "pack_sheet=" in out_pack
    assert "pack_b.contact.png" in out_pack
    assert "assets=1" in out_pack

    code_ids = main(
        [
            "render",
            "--pack-sheet",
            "--ids",
            "crate,sign",
            "--format",
            "json",
            "--root",
            str(tmp_path),
        ]
    )
    assert code_ids == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 2
    assert {item["id"] for item in payload["rendered"]} == {"crate", "sign"}
    assert Path(payload["pack_sheet"]).name == "pack.contact.png"


def test_cli_render_filter_no_match_returns_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path)
    code = main(["render", "--pack-sheet", "--pack", "missing_pack", "--root", str(tmp_path)])
    assert code == 1
    assert "No matching assets" in capsys.readouterr().err
