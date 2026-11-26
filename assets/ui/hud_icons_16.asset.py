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
    p = a.pal
    accent = p.SHIRT_BLUE
    if a.state == "alert":
        accent = p.ORANGE
    elif a.state == "bolt":
        accent = p.SHIRT_YEL
    elif a.state in ("check", "power"):
        accent = p.SHIRT_EMER

    prefabs.ui_icon_16(
        a,
        0,
        0,
        _ICON_MAP[a.state],
        p.METAL_H,
        accent=accent,
        outline=p.INK,
    )
    a.anchor("center", 8, 8, kind="ui_icon")
