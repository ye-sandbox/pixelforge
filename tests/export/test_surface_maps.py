"""Tests for derived 2D normal and height maps (`_normal.png` & `_height.png`)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from pixelforge.cli.main import main
from pixelforge.core.builder import Asset
from pixelforge.core.surface_maps import (
    NORMAL_FLAT,
    NORMAL_ISO_LEFT,
    NORMAL_ISO_RIGHT,
    NORMAL_ISO_TOP,
    infer_plane_normal,
)
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack
from pixelforge.export.bundle import (
    ExportBundleOptions,
    LoadedAsset,
    export_asset_bundle,
    write_export_bundle,
)
from pixelforge.export.indexed_ts import export_indexed_ts
from pixelforge.export.svelte_types import generate_svelte_manifest_dts


def _test_style() -> StylePack:
    return StylePack(
        id="maps-test",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="TOP", hex="#8b949e", flags=("bright",)),
            PaletteColor(index=2, name="LEFT", hex="#484f58", flags=("surface",)),
            PaletteColor(index=3, name="RIGHT", hex="#30363d", flags=("shadow",)),
        ),
    )


def _decode_png_rgba(payload: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(payload)) as img:
        return np.asarray(img.convert("RGBA"), dtype=np.uint8)


def test_infer_plane_normal_orientations() -> None:
    assert infer_plane_normal((16.0, 0.0), (0.0, 12.0)) == NORMAL_FLAT
    assert infer_plane_normal((20.0, 10.0), (-20.0, 10.0)) == NORMAL_ISO_TOP
    n_left = infer_plane_normal((16.0, 8.0), (0.0, 12.0))
    n_right = infer_plane_normal((16.0, -8.0), (0.0, 12.0))
    assert np.allclose(n_left, NORMAL_ISO_LEFT, atol=1e-5)
    assert np.allclose(n_right, NORMAL_ISO_RIGHT, atol=1e-5)


def test_iso_box_derives_face_normals_and_height_gradient() -> None:
    style = _test_style()
    spec = AssetSpec(
        id="iso_crate",
        style_id="maps-test",
        width=48,
        height=48,
        perspective="iso-2:1",
    )
    builder = Asset(spec, style, track_maps=True)
    builder.iso_box(24, 8, 12, 12, 10, top=1, left=2, right=3)

    assert builder.normal_map is not None
    assert builder.height_map is not None

    # Top face center pixel (24, 14) -> NORMAL_ISO_TOP and full height 10.0
    assert np.allclose(builder.normal_map[14, 24], NORMAL_ISO_TOP, atol=1e-4)
    assert np.isclose(builder.height_map[14, 24], 10.0, atol=0.5)

    # Left face pixel (18, 22) -> NORMAL_ISO_LEFT and mid-height
    assert np.allclose(builder.normal_map[22, 18], NORMAL_ISO_LEFT, atol=1e-4)
    assert 0.0 < float(builder.height_map[22, 18]) < 10.0

    # Right face pixel (30, 22) -> NORMAL_ISO_RIGHT and mid-height
    assert np.allclose(builder.normal_map[22, 30], NORMAL_ISO_RIGHT, atol=1e-4)
    assert 0.0 < float(builder.height_map[22, 30]) < 10.0


def test_layer_depth_and_mirror_x_normal_flip() -> None:
    style = _test_style()
    spec = AssetSpec(
        id="layered_widget",
        style_id="maps-test",
        width=32,
        height=32,
        perspective="front-2.5d",
    )
    builder = Asset(spec, style, track_maps=True)
    with builder.layer("base"):
        builder.rect(4, 4, 24, 24, 2)
    with builder.layer("top_plate"):
        builder.rect(8, 8, 16, 16, 1)
    with (
        builder.layer("mirrored_fin", mirror_x="left"),
        builder.plane(p0=(4, 10), p1=(10, 13), p2=(4, 20)) as fin,
    ):
        fin.rect(0.0, 0.0, 1.0, 1.0, fill=3)

    assert builder.normal_map is not None
    assert builder.height_map is not None
    # Overlapping top_plate is higher than base-only pixels
    assert float(builder.height_map[9, 9]) > float(builder.height_map[5, 5])
    # Mirrored right fin negates nx relative to left fin
    assert float(builder.normal_map[15, 6, 0]) < 0.0
    assert float(builder.normal_map[15, 25, 0]) > 0.0


def test_export_bundle_normal_and_height_pngs_and_typed_manifests() -> None:
    style = _test_style()
    spec = AssetSpec(
        id="anim_crate",
        style_id="maps-test",
        width=32,
        height=32,
        perspective="iso-2:1",
        states=("idle", "active"),
        frames=2,
        fps=4,
    )

    def render(a: Asset) -> None:
        a.iso_box(16, 4 + a.frame, 10, 10, 8, top=1, left=2, right=3)

    loaded = LoadedAsset(SPEC=spec, render=render)

    # Default export omits normal/height maps
    default_bundle = export_asset_bundle(loaded, style)
    assert default_bundle.manifest.files.normals is None
    assert default_bundle.manifest.files.height is None

    bundle = export_asset_bundle(
        loaded,
        style,
        ExportBundleOptions(normals=True, height=True, scale=2),
    )
    files_meta = bundle.manifest.files
    assert files_meta.normals == {
        "idle": "anim_crate_idle_normal.png",
        "active": "anim_crate_active_normal.png",
    }
    assert files_meta.sheetNormal == "anim_crate_sheet_normal.png"
    assert files_meta.height == {
        "idle": "anim_crate_idle_height.png",
        "active": "anim_crate_active_height.png",
    }
    assert files_meta.sheetHeight == "anim_crate_sheet_height.png"

    for state in spec.states:
        sprite_rgba = _decode_png_rgba(bundle.files[f"anim_crate_{state}.png"])
        normal_rgba = _decode_png_rgba(bundle.files[f"anim_crate_{state}_normal.png"])
        height_rgba = _decode_png_rgba(bundle.files[f"anim_crate_{state}_height.png"])

        assert normal_rgba.shape == sprite_rgba.shape == (64, 64, 4)
        assert height_rgba.shape == sprite_rgba.shape == (64, 64, 4)
        assert np.array_equal(normal_rgba[:, :, 3], sprite_rgba[:, :, 3])
        assert np.array_equal(height_rgba[:, :, 3], sprite_rgba[:, :, 3])
        assert np.all((normal_rgba[:, :, 3] == 0) | (normal_rgba[:, :, 3] == 255))
        assert np.all((height_rgba[:, :, 3] == 0) | (height_rgba[:, :, 3] == 255))

    sheet_rgba = _decode_png_rgba(bundle.files["anim_crate_sheet.png"])
    sheet_normal_rgba = _decode_png_rgba(bundle.files["anim_crate_sheet_normal.png"])
    sheet_height_rgba = _decode_png_rgba(bundle.files["anim_crate_sheet_height.png"])
    assert sheet_normal_rgba.shape == sheet_rgba.shape
    assert sheet_height_rgba.shape == sheet_rgba.shape

    dts = generate_svelte_manifest_dts([bundle.manifest])
    assert "readonly normals: {" in dts
    assert "readonly sheetNormal: string;" in dts
    assert "readonly height: {" in dts
    assert "readonly sheetHeight: string;" in dts

    ts_bundle = export_indexed_ts([bundle], style)
    assert '"normals"' in ts_bundle.manifest_ts
    assert '"sheetNormal": "anim_crate_sheet_normal.png"' in ts_bundle.manifest_ts
    assert '"height"' in ts_bundle.manifest_ts
    assert '"sheetHeight": "anim_crate_sheet_height.png"' in ts_bundle.manifest_ts


def test_cli_render_normals_and_height(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    assert main(["init", "--root", str(root)]) == 0
    out_dir = tmp_path / "dist"
    code = main(
        [
            "render",
            "--root",
            str(root),
            "--out",
            str(out_dir),
            "--normals",
            "--height",
            "--json",
        ]
    )
    assert code == 0

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 1
    entry = next(iter(manifest.values()))
    assert "normals" in entry["files"]
    assert "height" in entry["files"]
    for rel_path in entry["files"]["normals"].values():
        assert (out_dir / "sprites" / rel_path).is_file()
    for rel_path in entry["files"]["height"].values():
        assert (out_dir / "sprites" / rel_path).is_file()

    # Keep write_export_bundle exercised directly too
    style = _test_style()
    spec = AssetSpec(
        id="single_prop",
        style_id="maps-test",
        width=16,
        height=16,
        perspective="front-2.5d",
    )
    bundle = export_asset_bundle(
        LoadedAsset(SPEC=spec, render=lambda a: a.rect(2, 2, 12, 12, 1)),
        style,
        ExportBundleOptions(normals=True, height=True),
    )
    write_export_bundle(bundle, tmp_path / "dist2")
    assert (tmp_path / "dist2" / "sprites" / "single_prop_default_normal.png").is_file()
    assert (tmp_path / "dist2" / "sprites" / "single_prop_default_height.png").is_file()
