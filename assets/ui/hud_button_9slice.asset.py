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
    pal = prefabs.UiPalette.from_style(a)
    prefabs.ui_button(a, 2, 2, 24, 16, pal, state=_STATE_MAP[a.state], accent=True, corner_cut=1)
    a.hitbox("bounds", 2, 2, 24, 16, kind="ui_button")
