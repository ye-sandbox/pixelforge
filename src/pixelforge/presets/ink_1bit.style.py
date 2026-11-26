"""2-color `ink-1bit` StylePack preset for crisp 1-bit monochrome pixel art."""

from __future__ import annotations

from pixelforge.core.types import PaletteColor, StylePack

STYLE = StylePack(
    id="ink-1bit",
    perspective="side",
    lighting_angle="top-left",
    outline_index=0,
    palette=(
        PaletteColor(index=0, name="INK", hex="#111111", flags=("outline", "shadow")),
        PaletteColor(index=1, name="PAPER", hex="#f4f1ea", flags=("surface", "bright")),
    ),
    aliases={
        "BG_D": "INK",
        "BG_M": "INK",
        "BG_L": "PAPER",
        "SURFACE_D": "INK",
        "SURFACE_M": "PAPER",
        "SURFACE_L": "PAPER",
        "ACCENT_1": "PAPER",
        "ACCENT_2": "PAPER",
        "EMISSIVE_1": "PAPER",
        "EMISSIVE_2": "PAPER",
    },
    variants={
        "amber": {
            "INK": "#140e07",
            "PAPER": "#ffb000",
        },
        "phosphor": {
            "INK": "#07140a",
            "PAPER": "#33ff66",
        },
    },
)
