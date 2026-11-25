"""Tests for side-by-side + magenta pixel-diff PNG generation."""

from __future__ import annotations

import numpy as np

from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import AnchorPoint, HitboxRect, PaletteColor, StylePack
from pixelforge.export.diff import (
    diff_anchors,
    diff_hitboxes,
    format_metadata_deltas,
    generate_pixel_diff,
    generate_surface_diff,
)
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


def test_generate_surface_diff_detects_palette_only_changes() -> None:
    base_style = _style()
    curr_style = StylePack(
        id="diff-style",
        perspective="side",
        lighting_angle="top",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#101218", flags=("outline",)),
            PaletteColor(index=1, name="FILL", hex="#22aa44"),
            PaletteColor(index=2, name="ACCENT", hex="#ff5555"),
        ),
    )
    surface = IndexedSurface(4, 4)
    surface.rect(1, 1, 2, 2, 1)

    result = generate_surface_diff(surface, surface, curr_style, baseline_style=base_style)
    assert result.changed_pixels == 4
    decoded = decode_png_to_rgba(result.png)
    diff_panel_x = 8 + 4 + 4 + 4 + 4
    assert tuple(decoded[8 + 1, diff_panel_x + 1].tolist()) == (255, 42, 133, 255)


def test_diff_anchors_and_hitboxes_detects_all_delta_kinds() -> None:
    base_anchors = (
        AnchorPoint(name="same", x=2, y=3),
        AnchorPoint(name="mount", x=10, y=12),
        AnchorPoint(name="old", x=1, y=1),
    )
    curr_anchors = (
        AnchorPoint(name="same", x=2, y=3),
        AnchorPoint(name="mount", x=14, y=10),
        AnchorPoint(name="muzzle", x=8, y=4),
    )
    anchor_deltas = diff_anchors(base_anchors, curr_anchors)
    assert [(d.name, d.status, d.dx, d.dy) for d in anchor_deltas] == [
        ("mount", "moved", 4, -2),
        ("muzzle", "added", None, None),
        ("old", "removed", None, None),
    ]

    base_hitboxes = (
        HitboxRect(name="same", x=0, y=0, w=4, h=4),
        HitboxRect(name="body", x=2, y=2, w=10, h=10),
        HitboxRect(name="legacy", x=1, y=1, w=4, h=4),
    )
    curr_hitboxes = (
        HitboxRect(name="same", x=0, y=0, w=4, h=4),
        HitboxRect(name="body", x=2, y=3, w=12, h=8),
        HitboxRect(name="hurt", x=0, y=0, w=8, h=8),
    )
    hitbox_deltas = diff_hitboxes(base_hitboxes, curr_hitboxes)
    assert [(d.name, d.status, d.dx, d.dy, d.dw, d.dh) for d in hitbox_deltas] == [
        ("body", "changed", 0, 1, 2, -2),
        ("hurt", "added", None, None, None, None),
        ("legacy", "removed", None, None, None, None),
    ]

    lines = format_metadata_deltas(anchor_deltas, hitbox_deltas)
    assert any("anchor 'mount': moved (10, 12) -> (14, 10) (dx=+4, dy=-2)" in ln for ln in lines)
    assert any("anchor 'muzzle': added (8, 4)" in ln for ln in lines)
    assert any("anchor 'old': removed (1, 1)" in ln for ln in lines)
    assert any("hitbox 'body': changed (2, 2, 10x10) -> (2, 3, 12x8)" in ln for ln in lines)
    assert any("hitbox 'hurt': added (0, 0, 8x8)" in ln for ln in lines)
    assert any("hitbox 'legacy': removed (1, 1, 4x4)" in ln for ln in lines)
