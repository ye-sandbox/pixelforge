"""16-color `sweetie-16` StylePack preset (versatile general-purpose default)."""

from __future__ import annotations

from pixelforge.core.types import PaletteColor, StylePack

# INVARIANT: Non-emissive painted accents (CRIMSON, ORANGE, GOLD, LIME, BLUE, SKY)
# stay excluded from `emissive` so bloom masks only isolate CYAN.
STYLE = StylePack(
    id="sweetie-16",
    perspective="iso-2:1",
    lighting_angle="top-left",
    outline_index=0,
    palette=(
        PaletteColor(index=0, name="INK", hex="#1a1c2c", flags=("outline", "shadow")),
        PaletteColor(index=1, name="PLUM", hex="#5d275d", flags=("surface", "shadow")),
        PaletteColor(index=2, name="CRIMSON", hex="#b13e53", flags=("accent", "surface")),
        PaletteColor(index=3, name="ORANGE", hex="#ef7d57", flags=("accent",)),
        PaletteColor(index=4, name="GOLD", hex="#ffcd75", flags=("bright", "accent")),
        PaletteColor(index=5, name="LIME", hex="#a7f070", flags=("bright", "accent")),
        PaletteColor(index=6, name="GREEN", hex="#38b764", flags=("surface",)),
        PaletteColor(index=7, name="TEAL", hex="#257179", flags=("surface", "shadow")),
        PaletteColor(index=8, name="NAVY", hex="#29366f", flags=("surface", "shadow")),
        PaletteColor(index=9, name="BLUE", hex="#3b5dc9", flags=("accent", "surface")),
        PaletteColor(index=10, name="SKY", hex="#41a6f6", flags=("bright", "accent")),
        PaletteColor(index=11, name="CYAN", hex="#73eff7", flags=("emissive", "bright", "accent")),
        PaletteColor(index=12, name="WHITE", hex="#f4f4f4", flags=("bright", "surface")),
        PaletteColor(index=13, name="SLATE_L", hex="#94b0c2", flags=("metal", "surface")),
        PaletteColor(index=14, name="SLATE_M", hex="#566c86", flags=("metal", "surface")),
        PaletteColor(index=15, name="SLATE_D", hex="#333c57", flags=("metal", "shadow")),
    ),
    reflections={
        "CYAN": "SKY",
        "WHITE": "SLATE_L",
    },
    variants={
        "dusk": {
            "SLATE_L": "#7892a8",
            "SLATE_M": "#43556e",
            "SLATE_D": "#262d45",
            "GREEN": "#288a4c",
        },
    },
)
