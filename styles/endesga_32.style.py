"""32-color `endesga-32` StylePack preset for rich multi-genre pixel art."""

from __future__ import annotations

from pixelforge.core.types import PaletteColor, StylePack

STYLE = StylePack(
    id="endesga-32",
    perspective="top-down",
    lighting_angle="top-left",
    outline_index=0,
    palette=(
        PaletteColor(index=0, name="INK", hex="#181425", flags=("outline", "shadow")),
        PaletteColor(index=1, name="WOOD_D", hex="#3e2731", flags=("surface", "shadow")),
        PaletteColor(index=2, name="WOOD_M", hex="#733e39", flags=("surface",)),
        PaletteColor(index=3, name="WOOD_L", hex="#b86f50", flags=("surface",)),
        PaletteColor(index=4, name="TAN_L", hex="#e4a672", flags=("surface", "bright")),
        PaletteColor(index=5, name="GOLD", hex="#feae34", flags=("accent", "bright")),
        PaletteColor(index=6, name="YELLOW", hex="#fee761", flags=("bright", "accent")),
        PaletteColor(index=7, name="ORANGE", hex="#f77622", flags=("accent",)),
        PaletteColor(index=8, name="RED", hex="#e43b44", flags=("accent",)),
        PaletteColor(index=9, name="CRIMSON", hex="#a22633", flags=("surface", "shadow")),
        PaletteColor(index=10, name="BERRY", hex="#68386c", flags=("surface", "shadow")),
        PaletteColor(index=11, name="MAGENTA", hex="#b55088", flags=("accent",)),
        PaletteColor(index=12, name="PINK", hex="#f6757a", flags=("bright", "accent")),
        PaletteColor(index=13, name="PEACH", hex="#e8b796", flags=("surface",)),
        PaletteColor(index=14, name="BEIGE", hex="#c28569", flags=("surface",)),
        PaletteColor(index=15, name="LIME", hex="#63c74d", flags=("bright", "accent")),
        PaletteColor(index=16, name="GREEN", hex="#3e8948", flags=("surface",)),
        PaletteColor(index=17, name="FOREST", hex="#265c42", flags=("surface", "shadow")),
        PaletteColor(index=18, name="PINE", hex="#193c3e", flags=("surface", "shadow")),
        PaletteColor(index=19, name="NAVY", hex="#124e89", flags=("surface", "shadow")),
        PaletteColor(index=20, name="BLUE", hex="#0099db", flags=("accent", "surface")),
        PaletteColor(
            index=21, name="GLOW_CYAN", hex="#2ce8f5", flags=("emissive", "bright", "accent")
        ),
        PaletteColor(index=22, name="WHITE", hex="#ffffff", flags=("bright", "surface")),
        PaletteColor(index=23, name="SILVER", hex="#c0cbdc", flags=("metal", "bright")),
        PaletteColor(index=24, name="STEEL_L", hex="#8b9bb4", flags=("metal", "surface")),
        PaletteColor(index=25, name="STEEL_M", hex="#5a6988", flags=("metal", "surface")),
        PaletteColor(index=26, name="STEEL_D", hex="#3a4466", flags=("metal", "shadow")),
        PaletteColor(index=27, name="SLATE", hex="#262b44", flags=("surface", "shadow")),
        PaletteColor(index=28, name="VIOLET", hex="#7a444a", flags=("surface",)),
        PaletteColor(index=29, name="CORAL", hex="#ff0044", flags=("accent",)),
        PaletteColor(
            index=30, name="GLOW_GOLD", hex="#fff078", flags=("emissive", "bright", "accent")
        ),
        PaletteColor(index=31, name="ASH", hex="#4c5368", flags=("metal", "surface")),
    ),
    aliases={
        "BG_D": "SLATE",
        "BG_M": "PINE",
        "BG_L": "FOREST",
        "SURFACE_D": "STEEL_D",
        "SURFACE_M": "STEEL_M",
        "SURFACE_L": "STEEL_L",
        "ACCENT_1": "RED",
        "ACCENT_2": "GOLD",
        "EMISSIVE_1": "GLOW_CYAN",
        "EMISSIVE_2": "GLOW_GOLD",
    },
    reflections={
        "GLOW_CYAN": "BLUE",
        "GLOW_GOLD": "GOLD",
        "WHITE": "SILVER",
    },
)
