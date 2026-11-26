"""Tests for batch pack contact sheet generation and cross-asset consistency metrics."""

from __future__ import annotations

import numpy as np
import pytest

from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import AssetSpec, LightingAngle, PaletteColor, PerspectiveMode, StylePack
from pixelforge.export.pack_sheet import (
    PackSheetEntry,
    PackSheetOptions,
    compute_pack_consistency_metrics,
    generate_pack_sheet,
)
from pixelforge.export.png import assert_binary_alpha, decode_png_to_rgba


def _make_style(
    style_id: str = "pack-style",
    *,
    perspective: PerspectiveMode = "iso-2:1",
    lighting_angle: LightingAngle = "top-left",
) -> StylePack:
    return StylePack(
        id=style_id,
        perspective=perspective,
        lighting_angle=lighting_angle,
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#101218", flags=("outline",)),
            PaletteColor(index=1, name="DARK", hex="#303844"),
            PaletteColor(index=2, name="MID", hex="#687888"),
            PaletteColor(index=3, name="LIGHT", hex="#c8d8e8", flags=("bright",)),
        ),
        variants={"warm": {"LIGHT": "#ffd8a8"}},
    )


def _outlined_box_entry(
    asset_id: str,
    style: StylePack,
    w: int,
    h: int,
    *,
    with_outline: bool = True,
    bright_tl: bool = True,
) -> PackSheetEntry:
    surf = IndexedSurface(w, h)
    fill_tl = 3 if bright_tl else 1
    fill_br = 1 if bright_tl else 3
    for y in range(2, h - 2):
        for x in range(2, w - 2):
            is_edge = x == 2 or x == w - 3 or y == 2 or y == h - 3
            if is_edge and with_outline:
                surf.put(x, y, 0)
            elif (x - 2) + (y - 2) < ((w - 4) + (h - 4)) // 2:
                surf.put(x, y, fill_tl)
            else:
                surf.put(x, y, fill_br)
    spec = AssetSpec(
        id=asset_id,
        style_id=style.id,
        width=w,
        height=h,
        perspective=style.perspective,
    )
    return PackSheetEntry(spec=spec, style=style, surface=surf)


def test_generate_pack_sheet_deterministic_and_binary_alpha() -> None:
    style = _make_style()
    entries = [
        _outlined_box_entry("prop_b", style, 16, 16),
        _outlined_box_entry("prop_a", style, 12, 20),
        _outlined_box_entry("prop_c", style, 24, 14),
    ]

    res_a = generate_pack_sheet(entries, PackSheetOptions(title="PROPS"))
    res_b = generate_pack_sheet(list(reversed(entries)), PackSheetOptions(title="PROPS"))

    assert res_a.png == res_b.png
    assert res_a.width >= 200
    assert res_a.height >= 120
    assert res_a.metrics.asset_count == 3
    assert res_a.metrics.scale_consistent is True
    assert res_a.metrics.lighting_consistent is True
    assert res_a.metrics.outline_consistent is True
    assert res_a.metrics.min_size == (12, 14)
    assert res_a.metrics.max_size == (24, 20)
    assert res_a.metrics.warnings == ()

    decoded = decode_png_to_rgba(res_a.png)
    assert_binary_alpha(decoded)
    assert np.array_equal(decoded, res_a.rgba)


def test_pack_consistency_metrics_flags_mismatches() -> None:
    style_iso = _make_style("iso", perspective="iso-2:1", lighting_angle="top-left")
    style_td = _make_style("td", perspective="top-down", lighting_angle="top-right")

    entries = [
        _outlined_box_entry("a_iso", style_iso, 16, 16, with_outline=True, bright_tl=True),
        _outlined_box_entry("b_td", style_td, 16, 16, with_outline=False, bright_tl=False),
    ]
    metrics = compute_pack_consistency_metrics(entries)

    assert metrics.scale_consistent is False
    assert metrics.lighting_consistent is False
    assert metrics.outline_consistent is False
    assert metrics.outline_spread_pct == 100.0
    assert any("mixed perspectives" in w for w in metrics.warnings)
    assert any("mixed lighting angles" in w for w in metrics.warnings)
    assert any("outline coverage spread" in w for w in metrics.warnings)


def test_pack_sheet_empty_raises() -> None:
    with pytest.raises(ValueError, match="zero"):
        generate_pack_sheet([])
