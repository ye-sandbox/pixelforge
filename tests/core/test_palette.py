"""Unit tests for fail-loud PaletteLookup, reflection LUTs, and variant RGBA LUTs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from pixelforge.core.builder import Asset
from pixelforge.core.palette import (
    PaletteLookup,
    PaletteLookupError,
    UniversalPalette,
    build_reflection_lut,
    build_rgba_lut,
    hex_to_rgb,
    resolve_reflections,
    resolve_variant_colors,
)
from pixelforge.core.types import TRANSPARENT_INDEX, AssetSpec, PaletteColor, StylePack


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

    with pytest.raises(PaletteLookupError, match="did you mean 'CYAN_GLOW'"):
        pal.with_overrides({"CYAN_GLW": "CYAN_REFL"})

    kw_swapped = pal.with_overrides(CYAN_GLOW="CYAN_REFL")
    assert kw_swapped.CYAN_GLOW == pal.CYAN_REFL
    assert pal.CYAN_GLOW == 2

    with pytest.raises(PaletteLookupError, match="did you mean 'overload'"):
        build_rgba_lut(style, variant="overlod")


def test_style_pack_aliases_validation_and_lookup() -> None:
    """Verify `StylePack.aliases` validation and `PaletteLookup` alias resolution."""
    with pytest.raises(ValidationError, match="targets unknown token"):
        StylePack(
            id="bad-alias-target",
            perspective="top-down",
            lighting_angle="top-left",
            outline_index=0,
            palette=(PaletteColor(index=0, name="OUTLINE", hex="#000000", flags=("outline",)),),
            aliases={"INK": "MISSING_TOKEN"},
        )

    with pytest.raises(ValidationError, match="collides with existing palette token"):
        StylePack(
            id="bad-alias-collision",
            perspective="top-down",
            lighting_angle="top-left",
            outline_index=0,
            palette=(
                PaletteColor(index=0, name="INK", hex="#000000", flags=("outline",)),
                PaletteColor(index=1, name="PAPER", hex="#ffffff", flags=("surface",)),
            ),
            aliases={"INK": "PAPER"},
        )

    with pytest.raises(ValidationError, match="non-empty"):
        StylePack(
            id="bad-alias-empty",
            perspective="top-down",
            lighting_angle="top-left",
            outline_index=0,
            palette=(PaletteColor(index=0, name="INK", hex="#000000", flags=("outline",)),),
            aliases={"": "INK"},
        )

    style = StylePack(
        id="alias-ok",
        perspective="top-down",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="BASE_INK", hex="#111111", flags=("outline",)),
            PaletteColor(index=1, name="WALL", hex="#555555", flags=("surface",)),
        ),
        aliases={"INK": "BASE_INK", "SURFACE_M": "WALL"},
    )
    pal = PaletteLookup(style)
    assert pal.INK == 0
    assert pal["SURFACE_M"] == 1
    assert "INK" in pal
    assert pal.to_dict()["SURFACE_M"] == 1

    subset = PaletteLookup(style, tokens=("INK", "SURFACE_M"))
    assert subset.INK == 0
    assert subset.SURFACE_M == 1

    overridden = pal.with_overrides(INK="WALL")
    assert overridden.INK == 1
    assert overridden.BASE_INK == 0


def test_single_asset_compiles_across_presets_via_universal_palette(tmp_path: Path) -> None:
    """Verify one `Asset[UniversalPalette]` compiles across all 6 UniversalPalette presets."""
    from pixelforge.export.bundle import ExportBundleOptions, export_asset_bundle
    from pixelforge.guard.runner import load_asset_module
    from pixelforge.presets import load_all_presets

    presets = load_all_presets()
    universal_preset_ids = (
        "ink-1bit",
        "retro-pocket-4",
        "sweetie-16",
        "endesga-32",
        "cozy-pastel",
        "scifi-neon",
    )

    # Static Pyright check: Asset[UniversalPalette] accepts all UniversalPalette properties
    def draw_probe(a: Asset[UniversalPalette]) -> None:
        p = a.pal
        a.rect(0, 0, 8, 8, p.BG_D)
        a.rect(1, 1, 6, 6, p.SURFACE_M)
        a.put(2, 2, p.INK)
        a.put(3, 2, p.BG_M)
        a.put(4, 2, p.BG_L)
        a.put(2, 3, p.SURFACE_D)
        a.put(3, 3, p.SURFACE_L)
        a.put(4, 3, p.ACCENT_1)
        a.put(5, 3, p.ACCENT_2)
        a.put(2, 4, p.EMISSIVE_1)
        a.put(3, 4, p.EMISSIVE_2)

    asset_file = tmp_path / "universal_crate.asset.py"
    asset_file.write_text(
        "\n".join(
            [
                "from pixelforge import Asset, AssetSpec, UniversalPalette",
                "",
                "SPEC = AssetSpec(",
                '    id="universal_crate",',
                '    style_id="sweetie-16",',
                '    perspective="top-down",',
                "    width=8,",
                "    height=8,",
                ")",
                "",
                "def render(a: Asset[UniversalPalette]) -> None:",
                "    p = a.pal",
                "    a.rect(0, 0, 8, 8, p.BG_D)",
                "    a.rect(1, 1, 6, 6, p.SURFACE_M)",
                "    a.put(2, 2, p.INK)",
                "    a.put(3, 2, p.BG_M)",
                "    a.put(4, 2, p.BG_L)",
                "    a.put(2, 3, p.SURFACE_D)",
                "    a.put(3, 3, p.SURFACE_L)",
                "    a.put(4, 3, p.ACCENT_1)",
                "    a.put(5, 3, p.ACCENT_2)",
                "    a.put(2, 4, p.EMISSIVE_1)",
                "    a.put(3, 4, p.EMISSIVE_2)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    loaded = load_asset_module(asset_file)
    for preset_id in universal_preset_ids:
        style = presets[preset_id]
        probe_spec = AssetSpec(
            id="probe",
            style_id=preset_id,
            perspective=style.perspective,
            width=8,
            height=8,
        )
        probe_asset: Asset[UniversalPalette] = Asset(probe_spec, style)
        draw_probe(probe_asset)
        assert int(probe_asset.root_surface.data[2, 2]) == style.outline_index

        bundle = export_asset_bundle(loaded, style, ExportBundleOptions())
        assert bundle.manifest.styleId == "sweetie-16"
        assert len(bundle.rendered_frames) == 1
        assert bundle.rendered_frames[0].surface.data.shape == (8, 8)
        assert int(bundle.rendered_frames[0].surface.data[2, 2]) == style.outline_index
