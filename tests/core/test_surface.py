"""Unit tests for IndexedSurface framebuffer and pixel-art primitives."""

from __future__ import annotations

import numpy as np
import pytest

from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import TRANSPARENT_INDEX


def test_surface_init_bounds_put_get_erase_and_clone() -> None:
    """Verify uint8 initialization, integer truncation, OOB clamping, and cloning."""
    with pytest.raises(ValueError, match="positive"):
        IndexedSurface(0, 8)

    surf = IndexedSurface(8, 6)
    assert surf.data.shape == (6, 8)
    assert surf.data.dtype == np.uint8
    assert np.all(surf.data == TRANSPARENT_INDEX)

    surf.put(2.9, 1.8, 4)
    assert surf.get(2, 1) == 4
    assert surf.in_bounds(7, 5)
    assert not surf.in_bounds(8, 5)

    # Out-of-bounds reads/writes are silent and safe
    surf.put(-1, 0, 3)
    surf.put(99, 99, 3)
    assert surf.get(-1, 0) == TRANSPARENT_INDEX

    with pytest.raises(ValueError, match="out of range"):
        surf.put(0, 0, 256)

    cloned = surf.clone()
    surf.erase(2, 1)
    assert surf.get(2, 1) == TRANSPARENT_INDEX
    assert cloned.get(2, 1) == 4

    cloned.clear(7)
    assert np.all(cloned.data == 7)


def test_rect_and_rounded_rect() -> None:
    """Verify filled/stroked rect and pixel-crisp rounded_rect corners."""
    surf = IndexedSurface(10, 10)
    surf.rect(1, 1, 4, 3, 2, fill=True)
    assert np.count_nonzero(surf.data == 2) == 12

    surf.clear()
    surf.rect(1, 1, 4, 4, 5, fill=False)
    assert np.count_nonzero(surf.data == 5) == 12
    assert surf.get(2, 2) == TRANSPARENT_INDEX

    surf.clear()
    surf.rounded_rect(1, 1, 6, 6, radius=1, color=3, fill=True)
    # 6x6 minus 4 corner pixels = 32 pixels
    assert np.count_nonzero(surf.data == 3) == 32
    assert surf.get(1, 1) == TRANSPARENT_INDEX
    assert surf.get(6, 6) == TRANSPARENT_INDEX
    assert surf.get(2, 1) == 3

    surf.clear()
    surf.rounded_rect(0, 0, 8, 8, radius=2, color=4, fill=False)
    assert surf.get(0, 0) == TRANSPARENT_INDEX
    assert surf.get(2, 0) == 4
    assert surf.get(0, 2) == 4
    assert surf.get(4, 4) == TRANSPARENT_INDEX


def test_line_circle_ellipse_polygon_quad_and_fill() -> None:
    """Verify Bresenham line, midpoint circle/ellipse, polygon/quad, and flood fill."""
    surf = IndexedSurface(16, 16)
    surf.line(1, 1, 5, 5, 1)
    for i in range(1, 6):
        assert surf.get(i, i) == 1

    surf.clear()
    surf.circle(8, 8, 3, 2, fill=False)
    assert surf.get(8, 5) == 2
    assert surf.get(8, 8) == TRANSPARENT_INDEX
    surf.fill(8, 8, 6)
    assert surf.get(8, 8) == 6
    assert surf.get(0, 0) == TRANSPARENT_INDEX

    surf.clear()
    surf.ellipse(8, 8, 5, 3, 4, fill=True)
    assert surf.get(8, 8) == 4
    assert surf.get(3, 8) == 4
    assert surf.get(13, 8) == 4
    assert surf.get(8, 4) == TRANSPARENT_INDEX

    surf.clear()
    surf.quad((2, 2), (10, 2), (12, 8), (4, 8), 9)
    assert surf.get(7, 5) == 9
    assert surf.get(2, 2) == 9
    assert surf.get(12, 8) == 9


def test_dither_patterns_and_masks() -> None:
    """Verify Bayer 2x2, Bayer 4x4, and checker dithering with opaque mask."""
    surf = IndexedSurface(8, 8)
    surf.dither(0, 0, 4, 4, 1, 2, pattern="bayer2", ratio=0.5)
    assert np.count_nonzero(surf.data[0:4, 0:4] == 1) == 8
    assert np.count_nonzero(surf.data[0:4, 0:4] == 2) == 8

    surf.clear()
    surf.dither(0, 0, 4, 4, 1, 2, pattern="bayer4", ratio=0.25)
    assert np.count_nonzero(surf.data[0:4, 0:4] == 2) == 4
    assert np.count_nonzero(surf.data[0:4, 0:4] == 1) == 12

    surf.clear()
    surf.rect(1, 1, 2, 2, 9)
    surf.dither(0, 0, 4, 4, 1, 2, pattern="checker", ratio=0.5, mask="opaque")
    assert surf.get(0, 0) == TRANSPARENT_INDEX
    assert {surf.get(1, 1), surf.get(2, 1)} == {1, 2}


def test_spr_blit_mirror_flip_outline_sel_out_and_edge_mask() -> None:
    """Verify ASCII sprites, layer blits, symmetry transforms, and outline passes."""
    layer = IndexedSurface(4, 4)
    layer.spr(
        [
            ".AA.",
            "ABBA",
            ".AA.",
        ],
        0,
        0,
        {"A": 1, "B": 2},
    )
    assert layer.get(0, 0) == TRANSPARENT_INDEX
    assert layer.get(1, 0) == 1
    assert layer.get(1, 1) == 2

    canvas = IndexedSurface(8, 8)
    canvas.blit_layer(layer, 2, 2)
    assert canvas.get(3, 2) == 1
    assert canvas.get(3, 3) == 2

    # Mirror left half to right half
    sym = IndexedSurface(6, 3)
    sym.put(0, 1, 3)
    sym.put(1, 0, 4)
    sym.mirror_x("left")
    assert sym.get(5, 1) == 3
    assert sym.get(4, 0) == 4

    sym.flip_x()
    assert sym.get(0, 1) == 3
    sym.flip_y()
    assert sym.get(4, 2) == 4

    # Auto outline
    outlined = IndexedSurface(5, 5)
    outlined.put(2, 2, 1)
    outlined.auto_outline(9)
    assert outlined.get(2, 1) == 9
    assert outlined.get(2, 3) == 9
    assert outlined.get(1, 2) == 9
    assert outlined.get(3, 2) == 9
    assert outlined.get(1, 1) == TRANSPARENT_INDEX

    # Selective outline
    sel = IndexedSurface(5, 5)
    sel.put(2, 2, 1)
    sel.sel_out(top_color=7, bottom_color=8, side_color=6)
    assert sel.get(2, 1) == 7
    assert sel.get(2, 3) == 8
    assert sel.get(1, 2) == 6
    assert sel.get(3, 2) == 6

    # Edge mask
    bevel = IndexedSurface(5, 5)
    bevel.rect(1, 1, 3, 3, 2)
    bevel.edge_mask(top_color=10, bottom_color=11)
    assert bevel.get(2, 1) == 10
    assert bevel.get(2, 2) == 2
    assert bevel.get(2, 3) == 11


def test_bevel_rect_directional_angles_recessed_and_outline() -> None:
    """Verify `bevel_rect` respects lighting_angle, recessed mode, thickness, and outline."""
    surf = IndexedSurface(8, 8)
    surf.bevel_rect(0, 0, 8, 8, (1, 2, 3), lighting_angle="top-left", outline=0)
    # 1px outer border
    assert surf.get(0, 0) == 0
    assert surf.get(7, 7) == 0
    # Interior top-left highlight (3) and bottom-right shadow (1) with mid fill (2)
    assert surf.get(1, 1) == 3
    assert surf.get(2, 1) == 3
    assert surf.get(1, 2) == 3
    assert surf.get(6, 6) == 1
    assert surf.get(5, 6) == 1
    assert surf.get(6, 5) == 1
    assert surf.get(3, 3) == 2

    # Top-right angle swaps left/right highlight vs shadow
    surf_tr = IndexedSurface(6, 6)
    surf_tr.bevel_rect(0, 0, 6, 6, (1, 2, 3), lighting_angle="top-right")
    assert surf_tr.get(5, 0) == 3
    assert surf_tr.get(0, 5) == 1

    # Recessed swaps highlight and shadow
    surf_rec = IndexedSurface(6, 6)
    surf_rec.bevel_rect(0, 0, 6, 6, (1, 2, 3), lighting_angle="top-left", recessed=True)
    assert surf_rec.get(0, 0) == 1
    assert surf_rec.get(5, 5) == 3


def test_shade_volume_directional_dither_and_outline_preservation() -> None:
    """Verify `shade_volume` shades opaque pixels dark-to-light and preserves outlines."""
    surf = IndexedSurface(10, 10)
    surf.rect(1, 1, 8, 8, 2)
    surf.rect(1, 1, 8, 8, 0, fill=False)
    shaded = surf.shade_volume((1, 2, 3, 4), lighting_angle="top-left", outline_color=0)
    assert shaded == 36
    # Outline stays untouched
    assert surf.get(1, 1) == 0
    assert surf.get(8, 8) == 0
    # Lit corner (top-left interior) is brightest, shadow corner (bottom-right) is darkest
    assert surf.get(2, 2) == 4
    assert surf.get(7, 7) == 1

    # Top-right lighting moves highlight to top-right
    surf_tr = IndexedSurface(8, 8)
    surf_tr.rect(1, 1, 6, 6, 2)
    surf_tr.shade_volume((1, 2, 3, 4), lighting_angle="top-right", dither=True)
    assert surf_tr.get(6, 1) >= surf_tr.get(1, 6)


def test_asset_and_layer_ramp_primitives() -> None:
    """Verify `Asset` and `Layer` resolve named StylePack ramps in `bevel_rect`/`shade_volume`."""
    from pixelforge.core.builder import Asset
    from pixelforge.core.types import AssetSpec
    from pixelforge.presets import load_preset_style

    style = load_preset_style("sweetie-16")
    spec = AssetSpec(
        id="ramp_probe",
        style_id="sweetie-16",
        perspective="iso-2:1",
        width=16,
        height=16,
    )
    a = Asset(spec, style)
    a.bevel_rect(1, 1, 6, 6, ramp="slate", outline=a.pal.INK)
    slate = a.pal.ramp("slate")
    assert a.get(1, 1) == a.pal.INK
    assert a.get(2, 2) == slate[-1]
    assert a.get(5, 5) == slate[0]

    with a.layer("orb", outline=a.pal.INK) as layer:
        layer.circle(11, 11, 3, a.pal.SLATE_M, fill=True)
        count = layer.shade_volume("slate")
        assert count > 0
        assert slate.index(layer.get(10, 9)) > slate.index(layer.get(12, 13))
