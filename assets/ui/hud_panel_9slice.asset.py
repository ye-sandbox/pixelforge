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
    if a.state == "alert":
        pal = prefabs.UiPalette.from_style(
            a,
            border_highlight=p.ORANGE,
            accent=p.LED_R,
            accent_bright=p.LED_R,
        )
    else:
        pal = prefabs.UiPalette.from_style(a)
    prefabs.ui_panel(a, 2, 2, 24, 24, pal, title_bar_h=3, beveled=True, corner_cut=1)
    a.hitbox("content", 8, 8, 12, 12, kind="ui_content")
