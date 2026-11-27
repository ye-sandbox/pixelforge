"""1x 4x6 bitmap font sprite atlas asset for HUDs, terminals, and dialogue boxes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import (
    Asset,
    AssetSpec,
    compute_font_atlas_size,
    make_bitmap_font_spec,
    prefabs,
    render_font_atlas,
)

if TYPE_CHECKING:
    from styles.homelab_16bit_palette import Homelab16bitPalette

_FONT_SPEC = make_bitmap_font_spec("4x6", columns=16, margin=0, spacing=1)
_ATLAS_W, _ATLAS_H = compute_font_atlas_size(_FONT_SPEC)

SPEC = AssetSpec(
    id="hud_font_4x6",
    style_id="homelab-16bit",
    width=_ATLAS_W,
    height=_ATLAS_H,
    perspective="front-2.5d",
    states=("default",),
    frames=1,
    seed=804,
    font=_FONT_SPEC,
)


def render(a: Asset[Homelab16bitPalette]) -> None:
    """Render the deterministic 4x6 ASCII glyph atlas at 1x resolution."""
    pal = prefabs.UiPalette.from_style(a)
    render_font_atlas(a, _FONT_SPEC, pal.text)
    a.anchor("origin", 0, 0, kind="font_atlas")
