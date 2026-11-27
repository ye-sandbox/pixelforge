"""9-slice HUD panel asset using `ui_panel` and `NineSliceMargins`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec, prefabs

if TYPE_CHECKING:
    from styles.homelab_16bit_palette import Homelab16bitPalette

_CANVAS_W = 28
_CANVAS_H = 28
_PANEL_X = 2
_PANEL_Y = 2
_PANEL_W = 24
_PANEL_H = 24

SPEC = AssetSpec(
    id="hud_panel_9slice",
    style_id="homelab-16bit",
    width=_CANVAS_W,
    height=_CANVAS_H,
    perspective="front-2.5d",
    states=("default", "alert"),
    frames=1,
    seed=801,
    nine_slice=prefabs.ui_panel_margins(
        _PANEL_X,
        _PANEL_Y,
        _PANEL_W,
        _PANEL_H,
        canvas_w=_CANVAS_W,
        canvas_h=_CANVAS_H,
        title_bar_h=3,
        beveled=True,
        corner_cut=1,
    ),
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
    prefabs.ui_panel(
        a,
        _PANEL_X,
        _PANEL_Y,
        _PANEL_W,
        _PANEL_H,
        pal,
        title_bar_h=3,
        beveled=True,
        corner_cut=1,
        emit_content_hitbox=True,
    )
