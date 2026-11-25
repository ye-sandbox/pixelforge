"""Tests for side-by-side + magenta pixel-diff PNG generation."""

from __future__ import annotations

import numpy as np

from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import PaletteColor, StylePack
from pixelforge.export.diff import generate_pixel_diff, generate_surface_diff
from pixelforge.export.png import assert_binary_alpha, decode_png_to_rgba


def _style() -> StylePack:
    return StylePack(
        id="diff-style",
        perspective="side",
        lighting_angle="top",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#101218", flags=("outline",)),
            PaletteColor(index=1, name="FILL", hex="#8090a0"),
            PaletteColor(index=2, name="ACCENT", hex="#ff5555"),
        ),
    )


def test_generate_pixel_diff_identical_and_changed() -> None:
    base = np.zeros((6, 8, 4), dtype=np.uint8)
    base[1:4, 2:5] = (100, 120, 140, 255)

    same = generate_pixel_diff(base, base.copy())
    assert same.changed_pixels == 0
    assert same.total_pixels == 48
    assert same.width == 8 * 2 + 8 * 3 + 4 * 2
    assert same.height == 8 * 2 + 6

    curr = base.copy()
    curr[2, 3] = (255, 0, 0, 255)
    curr[5, 7] = (0, 255, 0, 255)

    diff = generate_pixel_diff(base, curr)
    assert diff.changed_pixels == 2
    decoded = decode_png_to_rgba(diff.png)
    assert_binary_alpha(decoded)

    diff_panel_x = 8 + 8 + 4 + 8 + 4
    assert tuple(decoded[8 + 2, diff_panel_x + 3].tolist()) == (255, 42, 133, 255)
    assert tuple(decoded[8 + 5, diff_panel_x + 7].tolist()) == (255, 42, 133, 255)
    # Unchanged opaque pixel is dimmed (rgb >> 2)
    assert tuple(decoded[8 + 1, diff_panel_x + 2].tolist()) == (25, 30, 35, 255)


def test_generate_surface_diff_handles_different_sizes() -> None:
    style = _style()
    s1 = IndexedSurface(4, 4)
    s1.rect(0, 0, 2, 2, 1)

    s2 = IndexedSurface(6, 4)
    s2.rect(0, 0, 2, 2, 1)
    s2.put(5, 3, 2)

    result = generate_surface_diff(s1, s2, style)
    assert result.changed_pixels == 1
    assert result.total_pixels == 24
