"""Modular compositional character/avatar primitives and deterministic animation cycles."""

from pixelforge.core.prefabs.characters.cycles import (
    CharacterCycleState,
    CharacterFacing,
    CharacterPose,
    eval_character_cycle,
)
from pixelforge.core.prefabs.characters.parts import (
    AccessoryKind,
    CharacterAnchors,
    CharacterPalette,
    HairStyle,
    HeadAnchors,
    LegsAnchors,
    TorsoAnchors,
    avatar_accessory,
    avatar_character,
    avatar_hair,
    avatar_head,
    avatar_legs,
    avatar_torso,
)

__all__ = [
    "AccessoryKind",
    "CharacterAnchors",
    "CharacterCycleState",
    "CharacterFacing",
    "CharacterPalette",
    "CharacterPose",
    "HairStyle",
    "HeadAnchors",
    "LegsAnchors",
    "TorsoAnchors",
    "avatar_accessory",
    "avatar_character",
    "avatar_hair",
    "avatar_head",
    "avatar_legs",
    "avatar_torso",
    "eval_character_cycle",
]
