"""Tests for upgraded diagnostic contact sheet generation and metrics."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from pixelforge.core.builder import Asset
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack
from pixelforge.export._font import measure_text
from pixelforge.export.bundle import LoadedAsset
from pixelforge.export.contact_sheet import (
    ContactSheetOptions,
    compute_surface_metrics,
    generate_contact_sheet,
)
from pixelforge.export.png import assert_binary_alpha, decode_png_to_rgba


def _style() -> StylePack:
    return StylePack(
        id="sheet-style",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="DEEP_OUTLINE_TOKEN", hex="#101218", flags=("outline",)),
            PaletteColor(index=1, name="CHASSIS_MID_GREY", hex="#556677", flags=("surface",)),
            PaletteColor(index=2, name="STATUS_CYAN_GLOW", hex="#39c5cf", flags=("emissive",)),
        ),
        variants={"amber": {"STATUS_CYAN_GLOW": "#ffb000"}},
    )


def test_compute_surface_metrics_bbox_and_orphans() -> None:
    surf = IndexedSurface(10, 10)
    surf.rect(2, 3, 3, 2, 1)  # 6 connected pixels
    surf.put(8, 8, 2)  # 1 isolated 8-connected orphan pixel

    metrics = compute_surface_metrics(surf)
    assert metrics.opaque_pixels == 7
    assert metrics.total_pixels == 100
    assert metrics.bbox == (2, 3, 7, 6)
    assert metrics.orphan_pixels == 1


def test_generate_contact_sheet_renders_all_panels_deterministically() -> None:
    style = _style()
    spec = AssetSpec(
        id="thinkpad_mini",
        style_id="sheet-style",
        width=16,
        height=16,
        perspective="iso-2:1",
        states=("healthy", "faulty"),
        frames=2,
        fps=2,
    )

    def render(a: Asset) -> None:
        a.rect(3, 4, 10, 8, a.pal.CHASSIS_MID_GREY)
        a.put(7 + a.frame, 7, a.pal.STATUS_CYAN_GLOW)
        a.anchor("trackpoint", 7, 7)
        a.hitbox("body", 3, 4, 10, 8)

    asset = LoadedAsset(SPEC=spec, render=render)
    res_a = generate_contact_sheet(asset, style, ContactSheetOptions(zoom=6))
    res_b = generate_contact_sheet(asset, style, ContactSheetOptions(zoom=6))

    assert res_a.png == res_b.png
    assert res_a.width >= 460
    assert res_a.height > 200
    assert res_a.metrics.opaque_pixels == 80
    assert res_a.metrics.bbox == (3, 4, 10, 8)
    assert res_a.metrics.orphan_pixels == 0

    decoded = decode_png_to_rgba(res_a.png)
    assert_binary_alpha(decoded)
    assert np.array_equal(decoded, res_a.rgba)


def _non_emissive_style() -> StylePack:
    return StylePack(
        id="flat-style",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="DEEP_OUTLINE_TOKEN", hex="#101218", flags=("outline",)),
            PaletteColor(index=1, name="CHASSIS_MID_GREY", hex="#556677", flags=("surface",)),
        ),
    )


def test_contact_sheet_emissive_column_renders_only_emissive_pixels() -> None:
    style = _style()
    spec = AssetSpec(
        id="emit_box",
        style_id="sheet-style",
        width=16,
        height=16,
        perspective="iso-2:1",
        states=("healthy", "faulty"),
        frames=2,
        fps=2,
    )

    def render(a: Asset) -> None:
        a.rect(2, 2, 12, 12, a.pal.CHASSIS_MID_GREY)
        if a.state == "healthy":
            a.put(8, 8, a.pal.STATUS_CYAN_GLOW)
            if a.frame == 1:
                a.put(10, 10, a.pal.STATUS_CYAN_GLOW)

    asset = LoadedAsset(SPEC=spec, render=render)
    res = generate_contact_sheet(asset, style, ContactSheetOptions(zoom=4, include_variants=False))

    # Locate the matrix origin deterministically from the layout constants
    pad = 16
    ruler_left = 28
    header_h = 44
    zoomed_w = spec.width * 4
    right_x = pad + ruler_left + zoomed_w + 16 + zoomed_w + 24
    right_y = header_h + pad
    sil_y = right_y + 10 + spec.height + 10
    matrix_y = sil_y + 10 + (spec.height * 2) + 12

    # state_label_w = max(measure_text("healthy")[0], measure_text("faulty")[0]) + 10 = 44
    state_label_w = 44
    cell_scale = 2
    cell_w = spec.width * cell_scale
    cell_h = spec.height * cell_scale
    cell_gap = 6
    emit_x = right_x + state_label_w + spec.frames * (cell_w + cell_gap)

    healthy_row_y = matrix_y + 20
    faulty_row_y = healthy_row_y + cell_h + cell_gap

    # Emissive pixel at (8, 8) -> scaled 2x at (+16, +16) in healthy row must be cyan (#39c5cf)
    cyan_rgb = tuple(int(c) for c in res.rgba[healthy_row_y + 16, emit_x + 16, :3])
    assert cyan_rgb == (0x39, 0xC5, 0xCF)

    # Blinking emissive pixel active only on frame 1 at (10, 10) -> (+20, +20) must also appear
    blink_rgb = tuple(int(c) for c in res.rgba[healthy_row_y + 20, emit_x + 20, :3])
    assert blink_rgb == (0x39, 0xC5, 0xCF)

    # Non-emissive pixel at (3, 3) -> scaled 2x at (+6, +6) must be dark checkerboard
    non_emit_rgb = tuple(int(c) for c in res.rgba[healthy_row_y + 6, emit_x + 6, :3])
    assert non_emit_rgb in {(13, 17, 23), (24, 30, 40)}

    # Faulty state has no emissive pixel at (8, 8) -> checkerboard background
    faulty_rgb = tuple(int(c) for c in res.rgba[faulty_row_y + 16, emit_x + 16, :3])
    assert faulty_rgb in {(13, 17, 23), (24, 30, 40)}


def test_contact_sheet_non_emissive_style_omits_emissive_column() -> None:
    emit_style = _style()
    flat_style = _non_emissive_style()
    spec = AssetSpec(
        id="wide_panel",
        style_id="flat-style",
        width=64,
        height=48,
        perspective="iso-2:1",
        states=("idle", "active"),
        frames=4,
        fps=4,
    )

    def render(a: Asset) -> None:
        a.rect(4, 4, 56, 40, a.pal.CHASSIS_MID_GREY)

    flat_asset = LoadedAsset(SPEC=spec, render=render)
    emit_spec = AssetSpec(
        id="wide_panel",
        style_id="sheet-style",
        width=64,
        height=48,
        perspective="iso-2:1",
        states=("idle", "active"),
        frames=4,
        fps=4,
    )
    emit_asset = LoadedAsset(SPEC=emit_spec, render=render)

    flat_res = generate_contact_sheet(
        flat_asset, flat_style, ContactSheetOptions(zoom=2, include_variants=False)
    )
    emit_res = generate_contact_sheet(
        emit_asset, emit_style, ContactSheetOptions(zoom=2, include_variants=False)
    )

    # Non-emissive style omits the extra emissive column and column-header row
    assert flat_res.width < emit_res.width
    assert flat_res.height < emit_res.height


def test_contact_sheet_static_png_for_single_frame_asset() -> None:
    style = _style()
    spec = AssetSpec(
        id="static_box",
        style_id="sheet-style",
        width=16,
        height=16,
        perspective="iso-2:1",
        states=("idle",),
        frames=1,
        fps=6,
    )

    def render(a: Asset) -> None:
        a.rect(2, 2, 12, 12, a.pal.CHASSIS_MID_GREY)

    res = generate_contact_sheet(LoadedAsset(SPEC=spec, render=render), style)
    with Image.open(io.BytesIO(res.png)) as img:
        assert getattr(img, "is_animated", False) is False
        assert getattr(img, "n_frames", 1) == 1


def test_contact_sheet_apng_for_multiframe_asset() -> None:
    style = _style()
    spec = AssetSpec(
        id="blinker_box",
        style_id="sheet-style",
        width=16,
        height=16,
        perspective="iso-2:1",
        states=("idle", "fault"),
        frames=3,
        fps=5,
    )

    def render(a: Asset) -> None:
        a.rect(2, 2, 12, 12, a.pal.CHASSIS_MID_GREY)
        # Move an emissive pixel across x=4, 5, 6 in frame 0, 1, 2
        a.put(4 + a.frame, 8, a.pal.STATUS_CYAN_GLOW)

    asset = LoadedAsset(SPEC=spec, render=render)
    res_a = generate_contact_sheet(asset, style, ContactSheetOptions(zoom=4))
    res_b = generate_contact_sheet(asset, style, ContactSheetOptions(zoom=4))
    assert res_a.png == res_b.png

    # Layout coordinates for zoom=4, 16x16
    zoom_x = 16 + 28
    zoom_y = 44 + 16 + 24
    zoomed_w = 16 * 4
    clean_zoom_x = zoom_x + zoomed_w + 16
    right_x = clean_zoom_x + zoomed_w + 24
    preview_1x_y = (44 + 16) + 10
    sil_y = preview_1x_y + 16 + 10
    matrix_y = sil_y + 10 + (16 * 2) + 12

    with Image.open(io.BytesIO(res_a.png)) as apng:
        assert getattr(apng, "is_animated", False) is True
        assert getattr(apng, "n_frames", 1) == 3
        assert apng.info.get("loop") == 0

        for frame_idx in range(3):
            apng.seek(frame_idx)
            assert apng.info.get("duration") == 200  # round(1000 / 5 fps)
            rgba = np.asarray(apng.convert("RGBA"))
            assert_binary_alpha(rgba)
            if frame_idx == 0:
                assert np.array_equal(rgba, res_a.rgba)

            # Check zoomed pixel at (4 + frame_idx, 8) -> center of 4x4 block (annotated & clean)
            zx = zoom_x + (4 + frame_idx) * 4 + 2
            czx = clean_zoom_x + (4 + frame_idx) * 4 + 2
            zy = zoom_y + 8 * 4 + 2
            assert tuple(int(c) for c in rgba[zy, zx, :3]) == (0x39, 0xC5, 0xCF)
            assert tuple(int(c) for c in rgba[zy, czx, :3]) == (0x39, 0xC5, 0xCF)

            # Check 1x dark preview pixel at (4 + frame_idx, 8)
            px = right_x + (4 + frame_idx)
            py = preview_1x_y + 8
            assert tuple(int(c) for c in rgba[py, px, :3]) == (0x39, 0xC5, 0xCF)

            # Check `anim` column in state matrix animates non-primary state ("fault") too
            state_label_w = max(measure_text("idle")[0], measure_text("fault")[0]) + 10
            fault_row_y = matrix_y + 20 + (16 * 2 + 6)
            emit_step = max(16 * 2, measure_text("emissive")[0]) + 6
            anim_x = right_x + state_label_w + 3 * (16 * 2 + 6) + emit_step
            ax = anim_x + (4 + frame_idx) * 2 + 1
            ay = fault_row_y + 8 * 2 + 1
            assert tuple(int(c) for c in rgba[ay, ax, :3]) == (0x39, 0xC5, 0xCF)


def test_contact_sheet_clean_zoom_panel_silhouettes_and_dense_rulers() -> None:
    style = _non_emissive_style()
    spec = AssetSpec(
        id="dense_tile",
        style_id="flat-style",
        width=16,
        height=16,
        perspective="iso-2:1",
        states=("idle",),
        frames=1,
        fps=1,
    )

    def render(a: Asset) -> None:
        a.rect(2, 2, 12, 12, a.pal.CHASSIS_MID_GREY)
        a.anchor("center", 8, 8)
        a.hitbox("body", 2, 2, 12, 12)

    asset = LoadedAsset(SPEC=spec, render=render)
    zoom = 6
    res = generate_contact_sheet(
        asset, style, ContactSheetOptions(zoom=zoom, include_variants=False)
    )
    rgba = res.rgba

    zoom_x = 16 + 28
    zoom_y = 44 + 16 + 24
    zoomed_w = 16 * zoom
    clean_zoom_x = zoom_x + zoomed_w + 16
    right_x = clean_zoom_x + zoomed_w + 24
    sil_y = (44 + 16) + 10 + 16 + 10

    # Annotated panel has anchor crosshair at (8, 8); clean panel has pure CHASSIS_MID_GREY.
    ann_cx = zoom_x + 8 * zoom + (zoom // 2)
    clean_cx = clean_zoom_x + 8 * zoom + (zoom // 2)
    cy = zoom_y + 8 * zoom + (zoom // 2)
    assert tuple(int(c) for c in rgba[cy, ann_cx, :3]) == (255, 123, 114)
    assert tuple(int(c) for c in rgba[cy, clean_cx, :3]) == (0x55, 0x66, 0x77)

    # Denser 2px ruler tick on <= 32px sprite at x=2
    tick_2px_x = zoom_x + 2 * zoom
    assert tuple(int(c) for c in rgba[zoom_y - 1, tick_2px_x, :3]) == (121, 192, 255)

    # Pure silhouette strips: sil 1x w/b at right_x, sil 1x b/w at right_x + sil_1x_col_w
    sil_1x_col_w = max(16, measure_text("sil 1x b/w")[0]) + 8
    sil_wb_x = right_x
    sil_bw_x = right_x + sil_1x_col_w
    sil_img_y = sil_y + 10
    # Background pixel (0, 0) vs opaque pixel (8, 8)
    assert tuple(int(c) for c in rgba[sil_img_y, sil_wb_x, :3]) == (0, 0, 0)
    assert tuple(int(c) for c in rgba[sil_img_y + 8, sil_wb_x + 8, :3]) == (255, 255, 255)
    assert tuple(int(c) for c in rgba[sil_img_y, sil_bw_x, :3]) == (255, 255, 255)
    assert tuple(int(c) for c in rgba[sil_img_y + 8, sil_bw_x + 8, :3]) == (0, 0, 0)


def test_contact_sheet_layers_explode_view() -> None:
    style = _non_emissive_style()
    spec = AssetSpec(
        id="layered_crate",
        style_id="flat-style",
        width=16,
        height=16,
        perspective="iso-2:1",
        states=("idle",),
        frames=1,
        fps=1,
    )

    def render(a: Asset) -> None:
        with a.layer("base"):
            a.rect(2, 6, 12, 8, a.pal.CHASSIS_MID_GREY)
        with a.layer("rim"):
            a.rect(4, 2, 8, 4, a.pal.DEEP_OUTLINE_TOKEN)

    asset = LoadedAsset(SPEC=spec, render=render)
    res_plain = generate_contact_sheet(
        asset, style, ContactSheetOptions(zoom=4, include_variants=False, layers=False)
    )
    res_layers = generate_contact_sheet(
        asset, style, ContactSheetOptions(zoom=4, include_variants=False, layers=True)
    )
    assert res_layers.height > res_plain.height
    assert_binary_alpha(res_layers.rgba)
