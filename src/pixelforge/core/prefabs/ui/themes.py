"""Cohesive UI theme presets parameterizing panels, controls, icons, and typography."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from pixelforge.core.font import BitmapFontPreset
from pixelforge.core.prefabs.ui.icons import UiIconPackName

UiThemeName = Literal["pixel_chamfer", "rpg_wood", "flat_crt", "minimal_1bit"]

UI_THEME_NAMES: Final[tuple[UiThemeName, ...]] = (
    "pixel_chamfer",
    "rpg_wood",
    "flat_crt",
    "minimal_1bit",
)


@dataclass(frozen=True)
class UiThemeConfig:
    """Deterministic visual parameters for a cohesive pixel UI theme kit."""

    name: UiThemeName
    description: str
    corner_cut: int
    beveled: bool
    title_bar_h: int
    recessed_panel: bool
    bar_segments: int
    bar_specular: bool
    badge_pill: bool
    icon_pack: UiIconPackName
    font_preset: BitmapFontPreset


UI_THEME_PRESETS: Final[dict[UiThemeName, UiThemeConfig]] = {
    "pixel_chamfer": UiThemeConfig(
        name="pixel_chamfer",
        description="Chamfered 1px corners with tactile bevels and balanced core icons.",
        corner_cut=1,
        beveled=True,
        title_bar_h=7,
        recessed_panel=False,
        bar_segments=0,
        bar_specular=True,
        badge_pill=True,
        icon_pack="core",
        font_preset="5x7",
    ),
    "rpg_wood": UiThemeConfig(
        name="rpg_wood",
        description="Warm beveled RPG frames, segmented bars, square badges, and RPG icons.",
        corner_cut=1,
        beveled=True,
        title_bar_h=8,
        recessed_panel=False,
        bar_segments=4,
        bar_specular=True,
        badge_pill=False,
        icon_pack="rpg",
        font_preset="6x8",
    ),
    "flat_crt": UiThemeConfig(
        name="flat_crt",
        description="Sharp recessed CRT panels, segmented telemetry bars, and tech icons.",
        corner_cut=0,
        beveled=False,
        title_bar_h=7,
        recessed_panel=True,
        bar_segments=8,
        bar_specular=False,
        badge_pill=False,
        icon_pack="tech",
        font_preset="4x6",
    ),
    "minimal_1bit": UiThemeConfig(
        name="minimal_1bit",
        description="Crisp 1px flat borders with zero bevels and compact 4x6 typography.",
        corner_cut=0,
        beveled=False,
        title_bar_h=6,
        recessed_panel=False,
        bar_segments=0,
        bar_specular=False,
        badge_pill=False,
        icon_pack="core",
        font_preset="4x6",
    ),
}


def get_ui_theme_config(theme: str) -> UiThemeConfig:
    """Return the `UiThemeConfig` for `theme` or raise `ValueError`."""
    for preset_name, config in UI_THEME_PRESETS.items():
        if preset_name == theme:
            return config
    available = ", ".join(UI_THEME_NAMES)
    msg = f"Unknown UI theme {theme!r}; available: {available}"
    raise ValueError(msg)
