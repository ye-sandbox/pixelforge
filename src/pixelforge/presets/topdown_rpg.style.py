"""32-color `topdown-rpg` reference StylePack preset."""

from __future__ import annotations

from pixelforge.core.types import PaletteColor, StylePack

STYLE = StylePack(
    id="topdown-rpg",
    perspective="top-down",
    lighting_angle="top-left",
    outline_index=1,
    palette=(
        PaletteColor(index=0, name="VOID", hex="#0b0e14", flags=("shadow",)),
        PaletteColor(index=1, name="INK", hex="#141013", flags=("outline",)),
        PaletteColor(index=2, name="SOIL_D", hex="#2b1e19", flags=("surface", "shadow")),
        PaletteColor(index=3, name="SOIL_M", hex="#422c23", flags=("surface",)),
        PaletteColor(index=4, name="SOIL_L", hex="#5c3e31", flags=("surface",)),
        PaletteColor(index=5, name="GRASS_D", hex="#1f472a", flags=("surface", "shadow")),
        PaletteColor(index=6, name="GRASS_M", hex="#2f6b3c", flags=("surface",)),
        PaletteColor(index=7, name="GRASS_L", hex="#4b944f", flags=("surface",)),
        PaletteColor(index=8, name="LEAF_L", hex="#72b85a", flags=("accent", "surface")),
        PaletteColor(index=9, name="STONE_D", hex="#2b303a", flags=("surface", "shadow")),
        PaletteColor(index=10, name="STONE_M", hex="#434b59", flags=("surface",)),
        PaletteColor(index=11, name="STONE_L", hex="#646f82", flags=("surface",)),
        PaletteColor(index=12, name="STONE_H", hex="#8c98ad", flags=("bright", "surface")),
        PaletteColor(index=13, name="BARK_D", hex="#362218", flags=("surface", "shadow")),
        PaletteColor(index=14, name="BARK_M", hex="#573726", flags=("surface",)),
        PaletteColor(index=15, name="BARK_L", hex="#7d5239", flags=("surface",)),
        PaletteColor(index=16, name="WATER_D", hex="#173452", flags=("surface", "shadow")),
        PaletteColor(index=17, name="WATER_M", hex="#23527c", flags=("surface",)),
        PaletteColor(index=18, name="WATER_L", hex="#3b7cb3", flags=("accent", "surface")),
        PaletteColor(index=19, name="IRON_D", hex="#272d38", flags=("metal", "shadow")),
        PaletteColor(index=20, name="IRON_M", hex="#4c5666", flags=("metal", "surface")),
        PaletteColor(index=21, name="IRON_L", hex="#8895a8", flags=("metal", "bright")),
        PaletteColor(index=22, name="GOLD_D", hex="#7a5116", flags=("metal", "shadow")),
        PaletteColor(index=23, name="GOLD_M", hex="#b88425", flags=("metal", "accent")),
        PaletteColor(index=24, name="GOLD_L", hex="#e8bc4a", flags=("metal", "bright")),
        PaletteColor(index=25, name="RUBY_D", hex="#691923", flags=("surface", "shadow")),
        PaletteColor(index=26, name="RUBY_M", hex="#a82a39", flags=("accent",)),
        PaletteColor(
            index=27, name="TORCH_GLOW", hex="#eb6b2d", flags=("emissive", "bright", "accent")
        ),
        PaletteColor(
            index=28, name="TORCH_CORE", hex="#ffd966", flags=("emissive", "bright", "accent")
        ),
        PaletteColor(
            index=29, name="MANA_GLOW", hex="#3b9eff", flags=("emissive", "bright", "accent")
        ),
        PaletteColor(
            index=30, name="MANA_CORE", hex="#9ce3ff", flags=("emissive", "bright", "accent")
        ),
        PaletteColor(
            index=31, name="RUNE_GOLD", hex="#ffe885", flags=("emissive", "bright", "accent")
        ),
    ),
    reflections={
        "TORCH_CORE": "TORCH_GLOW",
        "MANA_CORE": "MANA_GLOW",
        "GOLD_L": "GOLD_M",
        "IRON_L": "STONE_L",
    },
    ramps={
        "soil": ("INK", "SOIL_D", "SOIL_M", "SOIL_L"),
        "grass": ("INK", "GRASS_D", "GRASS_M", "GRASS_L", "LEAF_L"),
        "stone": ("INK", "STONE_D", "STONE_M", "STONE_L", "STONE_H"),
        "bark": ("INK", "BARK_D", "BARK_M", "BARK_L"),
        "water": ("INK", "WATER_D", "WATER_M", "WATER_L"),
        "iron": ("INK", "IRON_D", "IRON_M", "IRON_L"),
        "gold": ("BARK_D", "GOLD_D", "GOLD_M", "GOLD_L"),
    },
    variants={
        "dusk": {
            "GRASS_D": "#142f1e",
            "GRASS_M": "#1f472b",
            "GRASS_L": "#31663b",
            "STONE_D": "#1e222b",
            "STONE_M": "#2e3542",
            "STONE_L": "#475163",
            "WATER_D": "#102338",
            "WATER_M": "#193957",
        }
    },
)
