"""16-color `scifi-neon` StylePack preset for synthwave and cyberpunk assets."""

from __future__ import annotations

from pixelforge.core.types import PaletteColor, StylePack

# INVARIANT: Non-emissive painted trims (TRIM_BLUE, TRIM_PURPLE) stay excluded
# from `emissive` so bloom masks isolate only NEON_* and CORE_WHITE.
STYLE = StylePack(
    id="scifi-neon",
    perspective="front-2.5d",
    lighting_angle="top-left",
    outline_index=0,
    palette=(
        PaletteColor(index=0, name="INK", hex="#090712", flags=("outline", "shadow")),
        PaletteColor(index=1, name="VOID", hex="#120f24", flags=("surface", "shadow")),
        PaletteColor(index=2, name="HULL_D", hex="#1d1a36", flags=("metal", "shadow")),
        PaletteColor(index=3, name="HULL_M", hex="#2d2952", flags=("metal", "surface")),
        PaletteColor(index=4, name="HULL_L", hex="#484378", flags=("metal", "surface")),
        PaletteColor(index=5, name="CHROME", hex="#7d7ea8", flags=("metal", "bright")),
        PaletteColor(index=6, name="TRIM_BLUE", hex="#254c8a", flags=("accent", "surface")),
        PaletteColor(index=7, name="TRIM_PURPLE", hex="#5b2478", flags=("accent", "surface")),
        PaletteColor(index=8, name="GLASS_D", hex="#142d4c", flags=("surface",)),
        PaletteColor(index=9, name="GLASS_L", hex="#265c85", flags=("bright", "surface")),
        PaletteColor(
            index=10, name="NEON_CYAN", hex="#00f0ff", flags=("emissive", "bright", "accent")
        ),
        PaletteColor(
            index=11, name="NEON_MAGENTA", hex="#ff2a85", flags=("emissive", "bright", "accent")
        ),
        PaletteColor(
            index=12, name="NEON_LIME", hex="#39ff14", flags=("emissive", "bright", "accent")
        ),
        PaletteColor(
            index=13, name="NEON_AMBER", hex="#ffb800", flags=("emissive", "bright", "accent")
        ),
        PaletteColor(index=14, name="CORE_WHITE", hex="#f0fbff", flags=("emissive", "bright")),
        PaletteColor(index=15, name="RUST_D", hex="#4f2234", flags=("surface", "shadow")),
    ),
    aliases={
        "BG_D": "VOID",
        "BG_M": "GLASS_D",
        "BG_L": "GLASS_L",
        "SURFACE_D": "HULL_D",
        "SURFACE_M": "HULL_M",
        "SURFACE_L": "HULL_L",
        "ACCENT_1": "TRIM_BLUE",
        "ACCENT_2": "TRIM_PURPLE",
        "EMISSIVE_1": "NEON_CYAN",
        "EMISSIVE_2": "NEON_MAGENTA",
    },
    reflections={
        "NEON_CYAN": "GLASS_L",
        "NEON_MAGENTA": "TRIM_PURPLE",
        "CHROME": "HULL_L",
    },
    variants={
        "overdrive": {
            "NEON_CYAN": "#80f8ff",
            "NEON_MAGENTA": "#ff66aa",
            "HULL_D": "#151229",
        },
    },
)
