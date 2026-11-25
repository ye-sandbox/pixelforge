"""Tests for upgraded diagnostic contact sheet generation and metrics."""

from __future__ import annotations

import numpy as np

from pixelforge.core.builder import Asset
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack
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

    asset = LoadedAsset(SPEC=spec, render=render)
    res = generate_contact_sheet(asset, style, ContactSheetOptions(zoom=4, include_variants=False))

    # Locate the matrix origin deterministically from the layout constants
    pad = 16
    ruler_left = 28
    header_h = 44
    zoomed_w = spec.width * 4
    right_x = pad + ruler_left + zoomed_w + 24
    right_y = header_h + pad
    matrix_y = right_y + spec.height + 24

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
