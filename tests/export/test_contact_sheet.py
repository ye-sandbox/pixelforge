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
