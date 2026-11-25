"""Tests for PNG, indexed texture, 1D LUT, GIF, and APNG encoding."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import PaletteColor, StylePack
from pixelforge.export.png import (
    assert_binary_alpha,
    decode_png_to_rgba,
    frames_to_apng,
    frames_to_gif,
    rgba_to_png,
    style_to_lut_png,
    style_to_lut_rgba,
    surface_to_indexed_png,
    surface_to_png,
    surface_to_rgba,
)


def _sample_style() -> StylePack:
    return StylePack(
        id="test-style",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#101218", flags=("outline",)),
            PaletteColor(index=1, name="CHASSIS", hex="#445566", flags=("surface",)),
            PaletteColor(index=2, name="LED_CYAN", hex="#00f0ff", flags=("emissive", "bright")),
        ),
        variants={
            "amber": {"LED_CYAN": "#ffaa00"},
        },
    )


def test_surface_to_rgba_and_emissive_mask() -> None:
    style = _sample_style()
    surf = IndexedSurface(4, 3)
    surf.put(0, 0, 0)
    surf.put(1, 0, 1)
    surf.put(2, 0, 2)

    rgba = surface_to_rgba(surf, style)
    assert rgba.shape == (3, 4, 4)
    assert tuple(rgba[0, 0].tolist()) == (0x10, 0x12, 0x18, 255)
    assert tuple(rgba[0, 1].tolist()) == (0x44, 0x55, 0x66, 255)
    assert tuple(rgba[0, 2].tolist()) == (0x00, 0xF0, 0xFF, 255)
    assert tuple(rgba[1, 1].tolist()) == (0, 0, 0, 0)

    emissive = surface_to_rgba(surf, style, emissive_only=True)
    assert tuple(emissive[0, 0].tolist()) == (0, 0, 0, 0)
    assert tuple(emissive[0, 1].tolist()) == (0, 0, 0, 0)
    assert tuple(emissive[0, 2].tolist()) == (0x00, 0xF0, 0xFF, 255)


def test_surface_to_png_nearest_scale_and_determinism() -> None:
    style = _sample_style()
    surf = IndexedSurface(2, 2)
    surf.put(0, 0, 1)
    surf.put(1, 1, 2)

    png_a = surface_to_png(surf, style, scale=3)
    png_b = surface_to_png(surf, style, scale=3)
    assert png_a == png_b

    decoded = decode_png_to_rgba(png_a)
    assert decoded.shape == (6, 6, 4)
    assert np.all(decoded[0:3, 0:3] == np.array([0x44, 0x55, 0x66, 255], dtype=np.uint8))
    assert np.all(decoded[0:3, 3:6] == 0)
    assert np.all(decoded[3:6, 3:6] == np.array([0x00, 0xF0, 0xFF, 255], dtype=np.uint8))


def test_assert_binary_alpha_rejects_intermediate_alpha() -> None:
    bad = np.zeros((2, 2, 4), dtype=np.uint8)
    bad[0, 0, 3] = 128
    with pytest.raises(ValueError, match="binary alpha"):
        assert_binary_alpha(bad)

    with pytest.raises(ValueError, match="binary alpha"):
        rgba_to_png(bad)


def test_indexed_png_and_1d_lut_png() -> None:
    style = _sample_style()
    surf = IndexedSurface(3, 2)
    surf.put(0, 0, 2)
    surf.put(2, 1, 0)

    idx_png = surface_to_indexed_png(surf)
    idx_rgba = decode_png_to_rgba(idx_png)
    assert tuple(idx_rgba[0, 0].tolist()) == (2, 0, 0, 255)
    assert tuple(idx_rgba[1, 2].tolist()) == (0, 0, 0, 255)
    assert tuple(idx_rgba[0, 1].tolist()) == (0, 0, 0, 0)

    lut_rgba = style_to_lut_rgba(style)
    assert lut_rgba.shape == (2, 256, 4)
    assert tuple(lut_rgba[0, 2].tolist()) == (0x00, 0xF0, 0xFF, 255)
    assert tuple(lut_rgba[1, 2].tolist()) == (0xFF, 0xAA, 0x00, 255)
    assert tuple(lut_rgba[0, 255].tolist()) == (0, 0, 0, 0)

    lut_decoded = decode_png_to_rgba(style_to_lut_png(style))
    assert np.array_equal(lut_decoded, lut_rgba)


def test_frames_to_gif_and_apng_preserve_frames_and_alpha() -> None:
    style = _sample_style()
    s0 = IndexedSurface(4, 4)
    s0.put(0, 0, 1)
    s1 = IndexedSurface(4, 4)
    s1.put(3, 3, 2)

    frames = [surface_to_rgba(s0, style), surface_to_rgba(s1, style)]
    gif_bytes = frames_to_gif(frames, fps=4)
    assert gif_bytes == frames_to_gif(frames, fps=4)

    with Image.open(io.BytesIO(gif_bytes)) as gif:
        assert getattr(gif, "n_frames", 1) == 2
        gif.seek(0)
        f0 = np.asarray(gif.convert("RGBA"))
        gif.seek(1)
        f1 = np.asarray(gif.convert("RGBA"))
        assert tuple(f0[0, 0].tolist()) == (0x44, 0x55, 0x66, 255)
        assert int(f0[3, 3, 3]) == 0
        assert tuple(f1[3, 3].tolist()) == (0x00, 0xF0, 0xFF, 255)
        assert int(f1[0, 0, 3]) == 0

    apng_bytes = frames_to_apng(frames, fps=4)
    assert apng_bytes == frames_to_apng(frames, fps=4)
    with Image.open(io.BytesIO(apng_bytes)) as apng:
        assert getattr(apng, "n_frames", 1) == 2
        apng.seek(1)
        a1 = np.asarray(apng.convert("RGBA"))
        assert tuple(a1[3, 3].tolist()) == (0x00, 0xF0, 0xFF, 255)
        assert int(a1[0, 0, 3]) == 0
