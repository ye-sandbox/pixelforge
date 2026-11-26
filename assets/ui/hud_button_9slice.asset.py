"""9-slice tactile HUD button asset across interactive states."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec, NineSliceMargins, prefabs

if TYPE_CHECKING:
    from styles.homelab_16bit_palette import Homelab16bitPalette

SPEC = AssetSpec(
    id="hud_button_9slice",
    style_id="homelab-16bit",
    width=28,
    height=20,
    perspective="front-2.5d",
    states=("normal", "hover", "pressed", "disabled"),
    frames=1,
    seed=802,
    nine_slice=NineSliceMargins(left=7, right=7, top=6, bottom=6),
)

_STATE_MAP: dict[str, prefabs.UiButtonState] = {
    "normal": "normal",
    "hover": "hover",
    "pressed": "pressed",
    "disabled": "disabled",
}


def render(a: Asset[Homelab16bitPalette]) -> None:
    """Render a 9-slice HUD button across `normal`, `hover`, `pressed`, and `disabled`."""
    p = a.pal
    pal = prefabs.UiPalette(
        bg=p.WALL_M,
        bg_dark=p.WALL_D,
        bg_light=p.WALL_L,
        border_outer=p.INK,
        border_highlight=p.METAL_H,
        border_shadow=p.VOID,
        accent=p.SOLAR_B,
        accent_bright=p.SHIRT_BLUE,
        text=p.WHITE,
        text_muted=p.SMOKE,
        success=p.LED_G,
        warning=p.LED_A,
        danger=p.LED_R,
    )
    prefabs.ui_button(a, 2, 2, 24, 16, pal, state=_STATE_MAP[a.state], accent=True, corner_cut=1)
    a.hitbox("bounds", 2, 2, 24, 16, kind="ui_button")
