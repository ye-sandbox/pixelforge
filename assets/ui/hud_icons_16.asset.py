"""16x16 HUD icon pack showcasing all built-in `ui_icon_16` semantic glyphs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec, prefabs

if TYPE_CHECKING:
    from styles.homelab_16bit_palette import Homelab16bitPalette

SPEC = AssetSpec(
    id="hud_icons_16",
    style_id="homelab-16bit",
    width=16,
    height=16,
    perspective="front-2.5d",
    states=(
        "cpu",
        "ram",
        "disk",
        "network",
        "power",
        "alert",
        "bolt",
        "terminal",
        "check",
        "lock",
    ),
    frames=1,
    seed=803,
)

_ICON_MAP: dict[str, prefabs.UiIconKind] = {
    "cpu": "cpu",
    "ram": "ram",
    "disk": "disk",
    "network": "network",
    "power": "power",
    "alert": "alert",
    "bolt": "bolt",
    "terminal": "terminal",
    "check": "check",
    "lock": "lock",
}


def render(a: Asset[Homelab16bitPalette]) -> None:
    """Render each semantic 16x16 HUD icon state."""
    pal = prefabs.UiPalette.from_style(a)
    accent = pal.accent
    if a.state == "alert":
        accent = pal.danger
    elif a.state == "bolt":
        accent = pal.warning
    elif a.state in ("check", "power"):
        accent = pal.success

    prefabs.ui_icon_16(
        a,
        0,
        0,
        _ICON_MAP[a.state],
        pal.border_highlight,
        accent=accent,
        outline=pal.border_outer,
    )
    a.anchor("center", 8, 8, kind="ui_icon")
