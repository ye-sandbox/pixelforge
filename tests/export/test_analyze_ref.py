"""Hermetic tests for reference image proportion and quantized ASCII sketch analyzer."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from pixelforge.core.types import PaletteColor, StylePack
from pixelforge.export.analyze_ref import (
    analyze_reference_image,
    parse_sketch_size,
)


def _sample_style() -> StylePack:
    return StylePack(
        id="test-style",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="CYAN_GLOW", hex="#00e5ff", flags=("emissive",)),
            PaletteColor(index=2, name="RUST_RED", hex="#dc2626", flags=("surface",)),
        ),
    )


def _make_png_bytes(rgba: np.ndarray) -> io.BytesIO:
    buf = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_analyze_reference_image_proportions_histogram_and_sketch() -> None:
    """Verify aspect ratio, quantized palette histogram, and ASCII sketch from in-memory PNG."""
    style = _sample_style()
    # 160x80 (2:1) image: left half cyan, right half dark outline, bottom-right transparent corner.
    rgba = np.zeros((80, 160, 4), dtype=np.uint8)
    rgba[:, :80] = (0, 229, 255, 255)
    rgba[:, 80:] = (13, 17, 23, 255)
    rgba[60:, 120:] = (0, 0, 0, 0)

    png_buf = _make_png_bytes(rgba)
    analysis = analyze_reference_image(png_buf, style, size=(8, 4))

    assert analysis.source_width == 160
    assert analysis.source_height == 80
    assert analysis.aspect_ratio == 2.0
    assert analysis.simplified_ratio == "2:1"
    assert analysis.target_width == 8
    assert analysis.target_height == 4
    assert analysis.style_id == "test-style"

    assert len(analysis.ascii_sketch) == 4
    assert all(len(row) == 8 for row in analysis.ascii_sketch)
    assert "." in analysis.ascii_sketch[3]

    tokens = {entry.token: entry for entry in analysis.histogram}
    assert set(tokens) == {"CYAN_GLOW", "OUTLINE"}
    assert tokens["CYAN_GLOW"].pixels > tokens["OUTLINE"].pixels
    assert round(sum(e.percentage for e in analysis.histogram), 1) == 100.0

    report = analysis.format_report()
    assert "EPHEMERAL REFERENCE SKETCH" in report
    assert "2:1" in report
    assert "CYAN_GLOW" in report


def test_analyze_reference_image_all_transparent() -> None:
    """Verify fully transparent PNGs produce an empty histogram and dot-filled sketch."""
    rgba = np.zeros((16, 16, 4), dtype=np.uint8)
    analysis = analyze_reference_image(_make_png_bytes(rgba), _sample_style(), size=(4, 4))

    assert analysis.histogram == ()
    assert analysis.legend == {}
    assert analysis.ascii_sketch == ("....", "....", "....", "....")
    assert "(no opaque pixels)" in analysis.format_report()


def test_parse_sketch_size_validation() -> None:
    """Verify `WxH` parsing and bounds enforcement."""
    assert parse_sketch_size("64x32") == (64, 32)
    assert parse_sketch_size(" 16X16 ") == (16, 16)

    for bad in ("64", "axb", "0x16", "129x32", "32x0"):
        with pytest.raises(ValueError):
            parse_sketch_size(bad)
