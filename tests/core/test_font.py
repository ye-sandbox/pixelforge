"""Unit tests for deterministic bitmap fonts, text measurement, and atlas compilation."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from pixelforge import (
    PTBR_HUD_CHARSET,
    TRANSPARENT_INDEX,
    Asset,
    AssetSpec,
    BitmapFontPreset,
    BitmapFontSpec,
    IndexedSurface,
    PaletteColor,
    StylePack,
    compute_font_atlas_size,
    draw_indexed_text,
    format_bmfont_fnt,
    make_bitmap_font_spec,
    measure_bitmap_text,
    render_font_atlas,
)
from pixelforge.core.font import get_font_definition


def _sample_style() -> StylePack:
    return StylePack(
        id="font-test-style",
        perspective="front-2.5d",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="INK", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="WHITE", hex="#ffffff", flags=("bright",)),
            PaletteColor(index=2, name="SHADOW", hex="#1b2230", flags=("shadow",)),
            PaletteColor(index=3, name="CYAN", hex="#39c5cf", flags=("emissive",)),
        ),
    )


def test_measure_bitmap_text_single_and_multiline() -> None:
    assert measure_bitmap_text("", font="4x6") == (0, 6)
    assert measure_bitmap_text("A", font="4x6") == (4, 6)
    assert measure_bitmap_text("AB", font="4x6") == (9, 6)
    assert measure_bitmap_text("AB", font="4x6", scale=2) == (18, 12)

    assert measure_bitmap_text("A\nBCD", font="5x7") == (17, 16)


def test_draw_indexed_text_with_shadow_and_clipping() -> None:
    surf = IndexedSurface(24, 16)
    draw_indexed_text(surf, "HI!", 2, 2, color=1, font="4x6", shadow=2)

    assert np.count_nonzero(surf.data == 1) > 0
    assert np.count_nonzero(surf.data == 2) > 0
    # Unwritten pixels remain TRANSPARENT_INDEX.
    assert int(surf.data[0, 0]) == TRANSPARENT_INDEX

    # Out-of-bounds drawing clips safely without raising.
    draw_indexed_text(surf, "CLIP", 20, 12, color=3, font="5x7", scale=2)
    assert np.count_nonzero(surf.data == 3) > 0


def test_asset_and_layer_text_helper() -> None:
    style = _sample_style()
    spec = AssetSpec(
        id="hud_text_test",
        style_id=style.id,
        width=32,
        height=16,
        perspective="front-2.5d",
    )
    asset = Asset(spec, style)
    with asset.layer("hud") as layer:
        layer.text("OK", 2, 2, asset.pal["CYAN"], font="4x6")
    asset.text("5X7", 2, 8, asset.pal["WHITE"], font="5x7")

    assert np.count_nonzero(asset.root_surface.data == 3) > 0
    assert np.count_nonzero(asset.root_surface.data == 1) > 0


def test_make_bitmap_font_spec_and_render_atlas() -> None:
    font_spec = make_bitmap_font_spec("4x6", charset=" ABC", columns=2, margin=1, spacing=1)
    w, h = compute_font_atlas_size(font_spec)
    assert (w, h) == (11, 15)
    assert font_spec.rows == 2
    assert len(font_spec.glyphs) == 4
    assert font_spec.glyphs[0].x == 1 and font_spec.glyphs[0].y == 1
    assert font_spec.glyphs[1].x == 6 and font_spec.glyphs[1].y == 1
    assert font_spec.glyphs[2].x == 1 and font_spec.glyphs[2].y == 8

    surf = IndexedSurface(w, h)
    render_font_atlas(surf, font_spec, color=1)
    # Space glyph cell remains transparent; A, B, C cells contain pixels.
    assert np.all(surf.data[1:7, 1:5] == TRANSPARENT_INDEX)
    assert np.any(surf.data[1:7, 6:10] == 1)
    assert np.any(surf.data[8:14, 1:5] == 1)


def test_bitmap_font_spec_validation_guards() -> None:
    font_spec = make_bitmap_font_spec("4x6", charset="AB", columns=2, margin=0, spacing=1)
    with pytest.raises(ValidationError, match="exceed canvas"):
        AssetSpec(
            id="too_small_font",
            style_id="font-test-style",
            width=4,
            height=6,
            perspective="front-2.5d",
            font=font_spec,
        )

    with pytest.raises(ValidationError, match="duplicate"):
        BitmapFontSpec(
            preset="4x6",
            glyph_width=4,
            glyph_height=6,
            line_height=7,
            letter_spacing=1,
            space_advance=5,
            columns=2,
            rows=1,
            charset="AA",
            glyphs=font_spec.glyphs,
        )


def test_ptbr_diacritics_and_hud_symbols_across_all_presets() -> None:
    presets: tuple[BitmapFontPreset, ...] = ("4x6", "5x7", "6x8", "8x10")
    for preset in presets:
        defn = get_font_definition(preset)
        for ch in PTBR_HUD_CHARSET:
            assert ch in defn.glyphs, f"Missing {ch!r} in {preset}"
            rows = defn.glyphs[ch]
            assert len(rows) == defn.glyph_height
            if ch != " ":
                assert any(r != 0 for r in rows), f"Empty glyph {ch!r} in {preset}"


def test_proportional_and_tabular_digits() -> None:
    # 'i' in 4x6 is 1px wide; with spacing=1, "ii" is 1 + 1 + 1 = 3px wide.
    assert measure_bitmap_text("ii", font="4x6", proportional=False) == (9, 6)
    assert measure_bitmap_text("ii", font="4x6", proportional=True) == (3, 6)

    # Tabular digits keep counters aligned even when proportional=True.
    assert measure_bitmap_text(
        "100", font="5x7", proportional=True, tabular_digits=True
    ) == measure_bitmap_text("888", font="5x7", proportional=True, tabular_digits=True)

    spec = make_bitmap_font_spec(
        "4x6",
        charset=" i18",
        columns=4,
        margin=0,
        spacing=1,
        proportional=True,
        tabular_digits=True,
    )
    by_char = {g.char: g for g in spec.glyphs}
    assert by_char["i"].width == 1
    assert by_char["i"].x_advance == 2
    assert by_char["1"].x_advance == by_char["8"].x_advance

    w, h = compute_font_atlas_size(spec)
    surf = IndexedSurface(w, h)
    render_font_atlas(surf, spec, color=1)
    # Trimmed 'i' draws at its exact cell x=5, width=1 (column 6 remains transparent).
    assert np.any(surf.data[:, 5] == 1)
    assert np.all(surf.data[:, 6] == TRANSPARENT_INDEX)


def test_display_presets_and_native_outline() -> None:
    assert measure_bitmap_text("TÍTULO", font="6x8") == (41, 8)
    assert measure_bitmap_text("AÇÃO", font="8x10") == (35, 10)

    surf = IndexedSurface(48, 20)
    draw_indexed_text(surf, "♥ 10", 4, 4, color=1, font="6x8", outline=0)
    assert np.count_nonzero(surf.data == 1) > 0
    assert np.count_nonzero(surf.data == 0) > 0
    # Foreground pixel at top-left of heart (x=5, y=4) must not be overwritten by outline.
    assert int(surf.data[4, 5]) == 1
    assert int(surf.data[3, 5]) == 0


def test_format_bmfont_fnt() -> None:
    spec = make_bitmap_font_spec("6x8", charset=" A1♥", columns=4, proportional=True)
    fnt = format_bmfont_fnt(spec, page_file="hud_font.png", face="hud_title", scale=2)
    assert 'info face="hud_title" size=16 bold=1' in fnt
    assert "common lineHeight=20 base=16" in fnt
    assert 'page id=0 file="hud_font.png"' in fnt
    assert "chars count=4" in fnt
    assert f"char id={ord('♥')} " in fnt
