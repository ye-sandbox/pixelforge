"""9-slice tactile HUD button asset across interactive states."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec, prefabs

if TYPE_CHECKING:
    from styles.homelab_16bit_palette import Homelab16bitPalette

_CANVAS_W = 28
_CANVAS_H = 20
_BUTTON_X = 2
_BUTTON_Y = 2
_BUTTON_W = 24
_BUTTON_H = 16

SPEC = AssetSpec(
    id="hud_button_9slice",
    style_id="homelab-16bit",
    width=_CANVAS_W,
    height=_CANVAS_H,
    perspective="front-2.5d",
    states=("normal", "hover", "pressed", "disabled"),
    frames=1,
    seed=802,
    nine_slice=prefabs.ui_button_margins(
        _BUTTON_X,
        _BUTTON_Y,
        _BUTTON_W,
        _BUTTON_H,
        canvas_w=_CANVAS_W,
        canvas_h=_CANVAS_H,
        corner_cut=1,
        content_padding=1,
    ),
)

_STATE_MAP: dict[str, prefabs.UiButtonState] = {
    "normal": "normal",
    "hover": "hover",
    "pressed": "pressed",
    "disabled": "disabled",
}


def render(a: Asset[Homelab16bitPalette]) -> None:
    """Render a 9-slice HUD button across `normal`, `hover`, `pressed`, and `disabled`."""
    pal = prefabs.UiPalette.from_style(a)
    prefabs.ui_button(
        a,
        _BUTTON_X,
        _BUTTON_Y,
        _BUTTON_W,
        _BUTTON_H,
        pal,
        state=_STATE_MAP[a.state],
        accent=True,
        corner_cut=1,
        emit_content_hitbox=True,
        content_padding=1,
    )
    a.hitbox("bounds", _BUTTON_X, _BUTTON_Y, _BUTTON_W, _BUTTON_H, kind="ui_button")
