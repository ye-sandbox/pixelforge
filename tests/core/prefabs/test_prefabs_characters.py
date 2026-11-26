"""Hermetic tests for StylePack-agnostic modular character and animation prefabs."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from pixelforge import Asset, PaletteLookup, prefabs
from pixelforge.core.surface import orphan_pixel_mask
from pixelforge.core.types import TRANSPARENT_INDEX


def _make_char_palette(pal: PaletteLookup) -> prefabs.CharacterPalette:
    return prefabs.CharacterPalette.from_lookup(
        pal,
        skin_light="CLOUD",
        skin_mid="SUN",
        skin_dark="WOOD_L",
        hair_base="WOOD_M",
        hair_highlight="SUN",
        hair_shadow="WOOD_D",
        shirt_base="SKY",
        shirt_shade="SKY_DARK",
        shirt_highlight="METAL_H",
        pants_base="FLOOR",
        pants_shade="FLOOR_D",
        shoe="METAL_D",
        eye="INK",
        outline="INK",
        accessory_base="METAL_M",
        accessory_accent="LED",
    )


def test_individual_character_parts_and_variants(make_asset: Callable[..., Asset]) -> None:
    """Verify `head`, `torso`, `legs`, `hair`, and `accessory` primitives render cleanly."""
    asset = make_asset(160, 120)
    p = asset.pal

    legs = prefabs.avatar_legs(
        asset,
        24,
        40,
        pants_base=p.FLOOR,
        pants_shade=p.FLOOR_D,
        shoe=p.METAL_D,
        outline=p.INK,
        facing="front",
        stride=-1,
    )
    assert legs.ground == (24, 40)

    torso = prefabs.avatar_torso(
        asset,
        legs.waist[0],
        legs.waist[1],
        shirt_base=p.SKY,
        shirt_shade=p.SKY_DARK,
        shirt_highlight=p.METAL_H,
        skin_light=p.CLOUD,
        skin_mid=p.SUN,
        outline=p.INK,
        arm_left_dy=-1,
        arm_right_dy=1,
    )
    assert torso.neck[1] < legs.waist[1]

    head = prefabs.avatar_head(
        asset,
        torso.neck[0],
        torso.neck[1],
        skin_light=p.CLOUD,
        skin_mid=p.SUN,
        skin_dark=p.WOOD_L,
        eye=p.INK,
        outline=p.INK,
        facing="iso-se",
        blink=False,
    )
    assert head.hair_top[1] < head.neck[1]

    hair_styles: tuple[prefabs.HairStyle, ...] = (
        "short",
        "parted",
        "spiky",
        "bob",
        "ponytail",
        "buzz",
    )
    for idx, hstyle in enumerate(hair_styles):
        hx = 20 + idx * 22
        h_anchor = prefabs.avatar_head(
            asset,
            hx,
            70,
            skin_light=p.CLOUD,
            skin_mid=p.SUN,
            skin_dark=p.WOOD_L,
            eye=p.INK,
            outline=p.INK,
        )
        prefabs.avatar_hair(
            asset,
            hx,
            h_anchor.hair_top[1],
            hair_base=p.WOOD_M,
            hair_highlight=p.SUN,
            hair_shadow=p.WOOD_D,
            style=hstyle,
        )

    accessories: tuple[prefabs.AccessoryKind, ...] = (
        "none",
        "glasses",
        "visor",
        "headphones",
        "headset",
        "cap",
        "badge",
    )
    for idx, acc_kind in enumerate(accessories):
        ax = 16 + idx * 20
        t_anc = prefabs.avatar_torso(
            asset,
            ax,
            110,
            shirt_base=p.SKY,
            shirt_shade=p.SKY_DARK,
            shirt_highlight=p.METAL_H,
            skin_light=p.CLOUD,
            skin_mid=p.SUN,
        )
        h_anc = prefabs.avatar_head(
            asset,
            ax,
            t_anc.neck[1],
            skin_light=p.CLOUD,
            skin_mid=p.SUN,
            skin_dark=p.WOOD_L,
            eye=p.INK,
        )
        prefabs.avatar_accessory(
            asset,
            h_anc,
            t_anc,
            kind=acc_kind,
            primary=p.METAL_H,
            accent=p.LED,
            shade=p.METAL_D,
            alert_indicator=(acc_kind == "visor"),
        )

    valid_indices = {c.index for c in asset.style.palette} | {TRANSPARENT_INDEX}
    assert set(np.unique(asset.root_surface.data).tolist()).issubset(valid_indices)
    assert not np.any(orphan_pixel_mask(asset.root_surface))


def test_character_animation_cycles_determinism_and_poses() -> None:
    """Verify deterministic poses across `idle`, `walk`, `typing`, and `alert`."""
    idle_poses = [prefabs.eval_character_cycle("idle", f, 4, seed=42) for f in range(4)]
    assert idle_poses == [prefabs.eval_character_cycle("idle", f, 4, seed=42) for f in range(4)]
    assert any(pose.blink for pose in idle_poses)
    assert any(pose.bob_y != 0 for pose in idle_poses)

    walk_poses = [prefabs.eval_character_cycle("walk", f, 4, seed=42) for f in range(4)]
    assert [pose.leg_stride for pose in walk_poses] == [-1, 0, 1, 0]
    assert walk_poses[0].arm_left_dy == -walk_poses[0].arm_right_dy

    typing_poses = [
        prefabs.eval_character_cycle("typing", f, 4, seed=42, seated=True) for f in range(4)
    ]
    assert all(pose.seated for pose in typing_poses)
    assert typing_poses[0].arm_left_dy != typing_poses[1].arm_left_dy
    assert typing_poses[0].typing_pulse != typing_poses[1].typing_pulse

    alert_poses = [prefabs.eval_character_cycle("alert", f, 4, seed=42) for f in range(4)]
    assert alert_poses[0].alert_indicator is True
    assert alert_poses[0].arm_right_dy <= -2

    with pytest.raises(ValueError, match="Unsupported character cycle state"):
        prefabs.eval_character_cycle("dance", 0, 4)  # type: ignore[arg-type]


def test_avatar_character_facings_overrides_and_anchors(
    make_asset: Callable[..., Asset],
) -> None:
    """Verify `avatar_character` across facings, `with_overrides` swaps, and metadata."""
    base_asset = make_asset(32, 40)
    base_pal = _make_char_palette(base_asset.pal)
    anc = prefabs.avatar_character(
        base_asset,
        16,
        36,
        base_pal,
        state="walk",
        frame=0,
        frames=4,
        facing="iso-sw",
        hair_style="bob",
        accessory="headset",
    )
    assert anc.foot == (16, 36)
    assert {a.name for a in base_asset.anchors} >= {
        "foot",
        "head_top",
        "hand_left",
        "hand_right",
        "accessory",
    }
    assert len(base_asset.hitboxes) == 1
    assert base_asset.hitboxes[0].name == "body"
    assert not np.any(orphan_pixel_mask(base_asset.root_surface))

    # Skin/hair/shirt swap via PaletteLookup.with_overrides preserves silhouette but swaps indices.
    swapped_asset = make_asset(32, 40)
    swapped_lookup = swapped_asset.pal.with_overrides(
        SUN="WOOD_L",
        WOOD_M="METAL_D",
        SKY="WOOD_M",
    )
    swapped_pal = _make_char_palette(swapped_lookup)
    prefabs.avatar_character(
        swapped_asset,
        16,
        36,
        swapped_pal,
        state="walk",
        frame=0,
        frames=4,
        facing="iso-sw",
        hair_style="bob",
        accessory="headset",
    )
    base_mask = base_asset.root_surface.data != TRANSPARENT_INDEX
    swapped_mask = swapped_asset.root_surface.data != TRANSPARENT_INDEX
    assert np.array_equal(base_mask, swapped_mask)
    assert not np.array_equal(base_asset.root_surface.data, swapped_asset.root_surface.data)
