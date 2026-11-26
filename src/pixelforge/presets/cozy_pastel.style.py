"""16-color `cozy-pastel` StylePack preset for warm slice-of-life and cozy sims."""

from __future__ import annotations

from pixelforge.core.types import PaletteColor, StylePack

STYLE = StylePack(
    id="cozy-pastel",
    perspective="iso-2:1",
    lighting_angle="top-left",
    outline_index=0,
    palette=(
        PaletteColor(index=0, name="COCOA_OUTLINE", hex="#3b2d38", flags=("outline", "shadow")),
        PaletteColor(index=1, name="ESPRESSO", hex="#59414a", flags=("surface", "shadow")),
        PaletteColor(index=2, name="OAK_M", hex="#8f675c", flags=("surface",)),
        PaletteColor(index=3, name="OAK_L", hex="#c49a84", flags=("surface",)),
        PaletteColor(index=4, name="CREAM", hex="#f5ebd6", flags=("bright", "surface")),
        PaletteColor(index=5, name="LINEN", hex="#dfd1bd", flags=("surface",)),
        PaletteColor(index=6, name="SAGE_D", hex="#5f8068", flags=("surface", "shadow")),
        PaletteColor(index=7, name="SAGE_L", hex="#96bd99", flags=("surface",)),
        PaletteColor(index=8, name="SKY_D", hex="#6b8eb3", flags=("surface",)),
        PaletteColor(index=9, name="SKY_L", hex="#a9cbe8", flags=("bright", "accent")),
        PaletteColor(index=10, name="LAVENDER", hex="#b8a1d9", flags=("accent",)),
        PaletteColor(index=11, name="BLUSH", hex="#e8a2a8", flags=("accent",)),
        PaletteColor(index=12, name="TERRACOTTA", hex="#cf7365", flags=("accent", "surface")),
        PaletteColor(index=13, name="BUTTER", hex="#f2cf7e", flags=("bright", "accent")),
        PaletteColor(
            index=14, name="WARM_GLOW", hex="#ffe49e", flags=("emissive", "bright", "accent")
        ),
        PaletteColor(index=15, name="PEBBLE", hex="#9e9599", flags=("metal", "surface")),
    ),
    reflections={
        "WARM_GLOW": "BUTTER",
        "CREAM": "LINEN",
    },
    variants={
        "evening": {
            "CREAM": "#d6c5ae",
            "LINEN": "#b8a691",
            "SKY_L": "#7a97b8",
            "SAGE_L": "#739478",
        },
    },
)
