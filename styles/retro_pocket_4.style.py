"""4-color `retro-pocket-4` StylePack preset inspired by classic handheld LCDs."""

from __future__ import annotations

from pixelforge.core.types import PaletteColor, StylePack

STYLE = StylePack(
    id="retro-pocket-4",
    perspective="top-down",
    lighting_angle="top-left",
    outline_index=0,
    palette=(
        PaletteColor(index=0, name="INK", hex="#0f380f", flags=("outline", "shadow")),
        PaletteColor(index=1, name="SHADE_D", hex="#306230", flags=("surface", "shadow")),
        PaletteColor(index=2, name="SHADE_L", hex="#8bac0f", flags=("surface",)),
        PaletteColor(index=3, name="HIGHLIGHT", hex="#9bbc0f", flags=("bright", "surface")),
    ),
    aliases={
        "BG_D": "INK",
        "BG_M": "SHADE_D",
        "BG_L": "SHADE_L",
        "SURFACE_D": "SHADE_D",
        "SURFACE_M": "SHADE_L",
        "SURFACE_L": "HIGHLIGHT",
        "ACCENT_1": "SHADE_L",
        "ACCENT_2": "HIGHLIGHT",
        "EMISSIVE_1": "HIGHLIGHT",
        "EMISSIVE_2": "HIGHLIGHT",
    },
    ramps={
        "lcd": ("INK", "SHADE_D", "SHADE_L", "HIGHLIGHT"),
    },
    variants={
        "pocket": {
            "INK": "#1e1b18",
            "SHADE_D": "#5a534a",
            "SHADE_L": "#9e9788",
            "HIGHLIGHT": "#d6d0c0",
        },
    },
)
