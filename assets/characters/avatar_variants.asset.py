"""Shared-silhouette crew variants driven by `PaletteLookup.with_overrides`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec, prefabs

if TYPE_CHECKING:
    from styles.homelab_16bit_palette import Homelab16bitPalette

SPEC = AssetSpec(
    id="avatar_variants",
    style_id="homelab-16bit",
    width=24,
    height=32,
    perspective="front-2.5d",
    states=("engineer", "architect", "nightshift"),
    frames=2,
    fps=2,
    seed=603,
)

_VARIANT_OVERRIDES: dict[str, dict[str, str]] = {
    "engineer": {},
    "architect": {
        "SKIN_L": "SKIN_M",
        "SKIN_M": "SKIN_D",
        "SKIN_D": "WOOD_D",
        "HAIR_Y": "HAIR_B",
        "HAIR_B": "HAIR_K",
        "SHIRT_BLUE": "SHIRT_EMER",
        "SHIRT_TEAL": "LED_GD",
        "LED_C": "LED_G",
    },
    "nightshift": {
        "SKIN_L": "DUST_L",
        "SKIN_M": "SKIN_L",
        "SKIN_D": "SKIN_M",
        "HAIR_Y": "WHITE",
        "HAIR_B": "HAIR_S",
        "HAIR_K": "METAL_D",
        "SHIRT_BLUE": "SHIRT_PURP",
        "SHIRT_TEAL": "SHIRT_IND",
        "LED_C": "PINK_RGB",
    },
}


def _draw_shared_crew_rig(a: Asset[Homelab16bitPalette]) -> None:
    p = a.pal
    prefabs.contact_shadow(a, 12, 30, 5, 1, color=p.VOID, dither_ratio=0.5)
    pal = prefabs.CharacterPalette(
        skin_light=p.SKIN_L,
        skin_mid=p.SKIN_M,
        skin_dark=p.SKIN_D,
        hair_base=p.HAIR_B,
        hair_highlight=p.HAIR_Y,
        hair_shadow=p.HAIR_K,
        shirt_base=p.SHIRT_BLUE,
        shirt_shade=p.SOLAR_B,
        shirt_highlight=p.SHIRT_TEAL,
        pants_base=p.METAL_M,
        pants_shade=p.FLOOR_L,
        shoe=p.METAL_H,
        eye=p.INK,
        outline=p.INK,
        accessory_base=p.METAL_H,
        accessory_accent=p.LED_C,
    )
    prefabs.avatar_character(
        a,
        12,
        30,
        pal,
        state="idle",
        frame=a.frame,
        frames=a.frames,
        facing="front",
        hair_style="short",
        accessory="glasses",
        seed=a.seed,
    )


def render(a: Asset[Homelab16bitPalette]) -> None:
    """Render shared crew silhouette with per-state `PaletteLookup.with_overrides` swaps."""
    overrides = _VARIANT_OVERRIDES[a.state]
    with a.palette_override(overrides):
        _draw_shared_crew_rig(a)
