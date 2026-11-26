"""Isometric cyber-operator avatar (`iso-2:1`) with emissive visor and ponytail."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelforge import Asset, AssetSpec, prefabs

if TYPE_CHECKING:
    from styles.homelab_16bit_palette import Homelab16bitPalette

SPEC = AssetSpec(
    id="cyber_operator_iso",
    style_id="homelab-16bit",
    width=24,
    height=32,
    perspective="iso-2:1",
    states=("idle", "walk", "typing", "alert"),
    frames=4,
    fps=6,
    seed=602,
)

_CYCLE_STATES: dict[str, prefabs.CharacterCycleState] = {
    "idle": "idle",
    "walk": "walk",
    "typing": "typing",
    "alert": "alert",
}


def render(a: Asset[Homelab16bitPalette]) -> None:
    """Render `cyber_operator_iso` with `iso-se` facing and `mount_bottom` scene anchor."""
    p = a.pal
    cycle_state = _CYCLE_STATES[a.state]
    is_alert = a.state == "alert"
    is_typing = a.state == "typing"

    if not is_typing:
        prefabs.contact_shadow(a, 12, 30, 5, 2, color=p.VOID, dither_ratio=0.5)

    pal = prefabs.CharacterPalette(
        skin_light=p.SKIN_M,
        skin_mid=p.SKIN_D,
        skin_dark=p.WOOD_D,
        hair_base=p.WALL_M,
        hair_highlight=p.HAIR_S,
        hair_shadow=p.HAIR_K,
        shirt_base=p.SHIRT_IND,
        shirt_shade=p.SOLAR_B,
        shirt_highlight=p.SHIRT_PURP,
        pants_base=p.METAL_M,
        pants_shade=p.FLOOR_L,
        shoe=p.METAL_H,
        eye=p.INK,
        outline=p.INK,
        accessory_base=p.METAL_D,
        accessory_accent=p.LED_R if is_alert else p.VISOR_C,
    )
    prefabs.avatar_character(
        a,
        12,
        30,
        pal,
        state=cycle_state,
        frame=a.frame,
        frames=a.frames,
        facing="iso-se",
        hair_style="ponytail",
        accessory="visor",
        seated=is_typing,
        seed=a.seed,
    )
    a.anchor("mount_bottom", 12, 30, kind="ground")
