"""Unit tests for fail-loud PaletteLookup, reflection LUTs, and variant RGBA LUTs."""

from __future__ import annotations

import numpy as np
import pytest

from pixelforge.core.palette import (
    PaletteLookup,
    PaletteLookupError,
    build_reflection_lut,
    build_rgba_lut,
    hex_to_rgb,
    resolve_reflections,
    resolve_variant_colors,
)
from pixelforge.core.types import TRANSPARENT_INDEX, PaletteColor, StylePack


def _make_style() -> StylePack:
    return StylePack(
        id="homelab-test",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#090a0d", flags=("outline",)),
            PaletteColor(index=1, name="SLATE_MID", hex="#334155", flags=("surface",)),
            PaletteColor(index=2, name="CYAN_GLOW", hex="#38bdf8", flags=("emissive", "bright")),
            PaletteColor(index=3, name="CYAN_REFL", hex="#0c4a6e", flags=("surface",)),
        ),
        reflections={"CYAN_GLOW": "CYAN_REFL"},
        variants={"overload": {"CYAN_GLOW": "#ef4444"}},
    )


def test_palette_lookup_attribute_and_item_access() -> None:
    """Verify attribute and key lookup succeed for declared tokens and fail loudly otherwise."""
    style = _make_style()
    pal = PaletteLookup(style)

    assert pal.style_id == "homelab-test"
    assert pal.OUTLINE == 0
    assert pal["SLATE_MID"] == 1
    assert pal.CYAN_GLOW == 2
    assert "CYAN_REFL" in pal
    assert len(pal) == 4
    assert list(pal) == ["OUTLINE", "SLATE_MID", "CYAN_GLOW", "CYAN_REFL"]
    assert pal.to_dict()["CYAN_GLOW"] == 2

    with pytest.raises(PaletteLookupError, match="MISSING_TOKEN"):
        _ = pal.MISSING_TOKEN
    with pytest.raises(PaletteLookupError, match="MISSING_TOKEN"):
        _ = pal["MISSING_TOKEN"]


def test_palette_lookup_subset_fails_loud_on_missing() -> None:
    """Verify explicit token subset validation rejects undeclared tokens."""
    style = _make_style()
    subset = PaletteLookup(style, tokens=("OUTLINE", "CYAN_GLOW"))
    assert subset.OUTLINE == 0
    with pytest.raises(PaletteLookupError):
        _ = subset.SLATE_MID

    with pytest.raises(PaletteLookupError, match="NO_SUCH_TOKEN"):
        PaletteLookup(style, tokens=("OUTLINE", "NO_SUCH_TOKEN"))


def test_reflection_table_and_lut() -> None:
    """Verify REFL mapping and 256-entry reflection LUT resolution."""
    style = _make_style()
    assert resolve_reflections(style) == {2: 3}

    lut_sparse = build_reflection_lut(style)
    assert lut_sparse.shape == (256,)
    assert lut_sparse.dtype == np.uint8
    assert int(lut_sparse[2]) == 3
    assert int(lut_sparse[0]) == TRANSPARENT_INDEX
    assert int(lut_sparse[TRANSPARENT_INDEX]) == TRANSPARENT_INDEX

    lut_self = build_reflection_lut(style, fallback_self=True)
    assert int(lut_self[2]) == 3
    assert int(lut_self[1]) == 1
    assert int(lut_self[TRANSPARENT_INDEX]) == TRANSPARENT_INDEX


def test_variant_resolution_and_binary_alpha_rgba_lut() -> None:
    """Verify variant color overrides and binary-alpha (256, 4) RGBA LUT construction."""
    style = _make_style()
    assert hex_to_rgb("#38bdf8") == (56, 189, 248)

    lut_default = build_rgba_lut(style)
    assert lut_default.shape == (256, 4)
    assert lut_default.dtype == np.uint8
    assert tuple(int(v) for v in lut_default[2]) == (56, 189, 248, 255)
    assert int(lut_default[TRANSPARENT_INDEX, 3]) == 0
    assert int(lut_default[200, 3]) == 0

    overloaded = resolve_variant_colors(style, "overload")
    assert overloaded[2].hex == "#ef4444"
    lut_overload = build_rgba_lut(style, variant="overload")
    assert tuple(int(v) for v in lut_overload[2]) == (239, 68, 68, 255)

    with pytest.raises(PaletteLookupError, match="Unknown variant"):
        build_rgba_lut(style, variant="nonexistent")


def test_palette_lookup_fuzzy_suggestions() -> None:
    """Verify typo errors include close-match token and variant suggestions."""
    style = _make_style()
    pal = PaletteLookup(style)

    with pytest.raises(PaletteLookupError, match="did you mean 'CYAN_GLOW'"):
        _ = pal.CYAN_GLW

    with pytest.raises(PaletteLookupError, match="did you mean 'SLATE_MID'"):
        _ = pal["SLATE_MD"]

    with pytest.raises(PaletteLookupError, match="did you mean 'OUTLINE'"):
        PaletteLookup(style, tokens=("OUTLIN",))

    with pytest.raises(KeyError, match="did you mean 'CYAN_GLOW'"):
        pal.with_overrides({"CYAN_GLW": "CYAN_REFL"})

    with pytest.raises(PaletteLookupError, match="did you mean 'overload'"):
        build_rgba_lut(style, variant="overlod")
