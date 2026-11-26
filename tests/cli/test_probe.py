"""Hermetic unit and CLI tests for `pixelforge probe`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelforge.cli.main import main
from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack
from pixelforge.export.bundle import LoadedAsset
from pixelforge.guard.probe import parse_region, probe_asset


def _sample_style() -> StylePack:
    return StylePack(
        id="probe-style",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#1a1c2c", flags=("outline",)),
            PaletteColor(index=1, name="METAL", hex="#566c86"),
            PaletteColor(index=2, name="LED_CYAN", hex="#73eff7", flags=("emissive", "bright")),
        ),
    )


def _sample_loaded_asset() -> LoadedAsset:
    spec = AssetSpec(
        id="probe_widget",
        style_id="probe-style",
        width=12,
        height=10,
        perspective="iso-2:1",
        states=("idle", "active"),
        frames=2,
        fps=4,
        seed=7,
    )

    def _render(a: Asset) -> None:
        with a.layer("body") as body:
            body.rect(2, 2, 4, 3, a.pal.METAL)
            with a.layer("inner_led", offset=(1, 1)) as led:
                led.put(2, 1, a.pal.LED_CYAN)
        with a.layer("empty_fx"):
            pass
        if a.state == "active" and a.frame == 1:
            a.put(5, 3, a.pal.LED_CYAN)
        else:
            a.put(4, 3, a.pal.LED_CYAN)
        # Intentional 1x1 orphan pixel at (10, 8)
        a.put(10, 8, a.pal.OUTLINE)
        a.anchor("base", 4, 5)
        a.hitbox("body", 2, 2, 4, 3)

    return LoadedAsset(SPEC=spec, render=_render)


def test_parse_region_validation() -> None:
    """Verify `parse_region` accepts valid regions and rejects malformed or OOB inputs."""
    assert parse_region("1, 2, 4, 5", 12, 10) == (1, 2, 4, 5)

    for bad in ("1,2,3", "1,2,a,4", "0,0,0,4", "0,0,4,-1", "-1,0,2,2", "10,0,4,2", "0,8,2,3"):
        with pytest.raises(ValueError):
            parse_region(bad, 12, 10)


def test_probe_asset_unit_diagnostics() -> None:
    """Verify `probe_asset` computes region slices, layer bboxes, histogram, and orphan coords."""
    style = _sample_style()
    loaded = _sample_loaded_asset()

    report = probe_asset(loaded, style, state="active", frame=1, region=(2, 2, 5, 4))
    assert report.asset_id == "probe_widget"
    assert report.state == "active"
    assert report.frame == 1
    assert report.opaque_pixels == 13
    assert report.opaque_bbox == (2, 2, 9, 7)
    assert report.orphan_pixels == ((10, 8),)

    # Region (2, 2, 5, 4) covers x=2..6, y=2..5 (METAL->'0', LED_CYAN->'1')
    assert report.region.rows == (
        "0100.",
        "0001.",
        "0000.",
        ".....",
    )
    legend_by_idx = {entry.index: entry for entry in report.region.legend}
    assert legend_by_idx[1].name == "METAL"
    assert legend_by_idx[2].emissive is True

    # Histogram across full frame: METAL=10 (9 from rect + wait: 4x3=12 minus 2 overwritten LEDs)
    hist_by_name = {entry.name: entry for entry in report.histogram}
    assert hist_by_name["METAL"].count == 10
    assert hist_by_name["LED_CYAN"].count == 2
    assert hist_by_name["LED_CYAN"].emissive is True
    assert hist_by_name["OUTLINE"].count == 1

    # Layers: nested `inner_led` is recorded before parent `body`, plus `empty_fx`
    layers_by_name = {layer.name: layer for layer in report.layers}
    assert layers_by_name["inner_led"].depth == 1
    assert layers_by_name["inner_led"].opaque_bbox == (3, 2, 1, 1)
    assert layers_by_name["inner_led"].pixel_count == 1
    assert layers_by_name["body"].depth == 0
    assert layers_by_name["body"].opaque_bbox == (2, 2, 4, 3)
    assert layers_by_name["body"].pixel_count == 12
    assert layers_by_name["empty_fx"].opaque_bbox is None
    assert layers_by_name["empty_fx"].pixel_count == 0


def _write_probe_project(root: Path) -> None:
    assert main(["init", "--root", str(root)]) == 0
    asset_file = root / "assets" / "probe_box.asset.py"
    asset_file.write_text(
        """from pixelforge import Asset, AssetSpec

SPEC = AssetSpec(
    id="probe_box",
    style_id="sweetie-16",
    width=10,
    height=10,
    perspective="front-2.5d",
    states=("idle", "glow"),
    frames=2,
    fps=4,
    seed=1,
)


def render(a: Asset) -> None:
    with a.layer("frame_layer") as layer:
        layer.rect(1, 1, 4, 4, a.pal.SLATE_L)
        if a.state == "glow" and a.frame == 1:
            layer.put(2, 2, a.pal.CYAN)
    # Orphan pixel at (8, 7)
    a.put(8, 7, a.pal.INK)
""",
        encoding="utf-8",
    )


def test_cli_probe_formats_layers_and_fuzzy_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `pixelforge probe` CLI across llm/json/human formats, flags, and errors."""
    _write_probe_project(tmp_path)
    capsys.readouterr()

    # Default LLM format with --region, --state, --frame, --layers
    rc = main(
        [
            "probe",
            "probe_box",
            "--region",
            "1,1,4,4",
            "--state",
            "glow",
            "--frame",
            "1",
            "--layers",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    llm_out = capsys.readouterr().out
    assert "probe asset=probe_box style=sweetie-16 state=glow frame=1" in llm_out
    assert "slice region=(1,1,4,4)" in llm_out
    assert "CYAN" in llm_out
    assert "EMISSIVE" in llm_out
    assert "orphans count=1 coords=(8,7)" in llm_out
    assert "layer=frame_layer role=visual depth=0 bbox=(1,1,4,4) pixels=16" in llm_out

    # Strict JSON output
    rc = main(
        [
            "probe",
            "probe_box",
            "--state",
            "glow",
            "--frame",
            "1",
            "--json",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["asset_id"] == "probe_box"
    assert payload["orphan_pixels"] == [[8, 7]]
    assert payload["layers"][0]["name"] == "frame_layer"
    assert payload["layers"][0]["opaque_bbox"] == {"x": 1, "y": 1, "w": 4, "h": 4}
    assert any(item["name"] == "CYAN" and item["emissive"] is True for item in payload["histogram"])

    # Human output
    rc = main(["probe", "probe_box", "--layers", "--human", "--root", str(tmp_path)])
    assert rc == 0
    human_out = capsys.readouterr().out
    assert "Probe: probe_box" in human_out
    assert "Orphan Pixels (1): (8, 7)" in human_out
    assert "frame_layer [visual] bbox=(1,1,4,4) pixels=16" in human_out

    # Fuzzy asset suggestion
    assert main(["probe", "probe_bx", "--root", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "Unknown asset 'probe_bx'" in err
    assert "probe_box" in err

    # Invalid region and invalid state return exit code 2
    assert main(["probe", "probe_box", "--region", "0,0,99,99", "--root", str(tmp_path)]) == 2
    assert "out of bounds" in capsys.readouterr().err
    assert main(["probe", "probe_box", "--state", "missing", "--root", str(tmp_path)]) == 2
    assert "Invalid state" in capsys.readouterr().err
