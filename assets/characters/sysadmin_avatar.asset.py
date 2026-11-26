"""Modular front-2.5d sysadmin avatar showcasing all 4 deterministic animation cycles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec, prefabs

if TYPE_CHECKING:
    from styles.homelab_16bit_palette import Homelab16bitPalette

SPEC = AssetSpec(
    id="sysadmin_avatar",
    style_id="homelab-16bit",
    width=24,
    height=32,
    perspective="front-2.5d",
    states=("idle", "walk", "typing", "alert"),
    frames=4,
    fps=6,
    seed=601,
)

_CYCLE_STATES: dict[str, prefabs.CharacterCycleState] = {
    "idle": "idle",
    "walk": "walk",
    "typing": "typing",
    "alert": "alert",
}


def render(a: Asset[Homelab16bitPalette]) -> None:
    """Render `sysadmin_avatar` across `idle`, `walk`, `typing`, and `alert` cycles."""
    p = a.pal
    cycle_state = _CYCLE_STATES[a.state]
    is_alert = a.state == "alert"
    is_typing = a.state == "typing"

    if not is_typing:
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
        accessory_base=p.METAL_L,
        accessory_accent=p.LED_R if is_alert else p.LED_C,
    )
    prefabs.avatar_character(
        a,
        12,
        30,
        pal,
        state=cycle_state,
        frame=a.frame,
        frames=a.frames,
        facing="front",
        hair_style="parted",
        accessory="headphones",
        seated=is_typing,
        seed=a.seed,
    )
