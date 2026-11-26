"""9-slice HUD panel asset using `ui_panel` and `NineSliceMargins`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec, NineSliceMargins, prefabs

if TYPE_CHECKING:
    from styles.homelab_16bit_palette import Homelab16bitPalette

SPEC = AssetSpec(
    id="hud_panel_9slice",
    style_id="homelab-16bit",
    width=28,
    height=28,
    perspective="front-2.5d",
    states=("default", "alert"),
    frames=1,
    seed=801,
    nine_slice=NineSliceMargins(left=8, right=8, top=8, bottom=8),
)


def render(a: Asset[Homelab16bitPalette]) -> None:
    """Render a 9-slice-ready beveled HUD panel in `default` and `alert` states."""
    p = a.pal
    is_alert = a.state == "alert"
    pal = prefabs.UiPalette(
        bg=p.WALL_M,
        bg_dark=p.WALL_D,
        bg_light=p.WALL_L,
        border_outer=p.INK,
        border_highlight=p.ORANGE if is_alert else p.METAL_H,
        border_shadow=p.VOID,
        accent=p.LED_R if is_alert else p.SOLAR_B,
        accent_bright=p.LED_R if is_alert else p.LED_C,
        text=p.WHITE,
        text_muted=p.SMOKE,
        success=p.LED_G,
        warning=p.LED_A,
        danger=p.LED_R,
    )
    prefabs.ui_panel(a, 2, 2, 24, 24, pal, title_bar_h=3, beveled=True, corner_cut=1)
    a.hitbox("content", 8, 8, 12, 12, kind="ui_content")
