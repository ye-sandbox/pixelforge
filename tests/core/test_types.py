"""Unit tests for core Pydantic contracts and constants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pixelforge.core.types import (
    MAX_PALETTE_INDEX,
    TRANSPARENT_INDEX,
    AnchorPoint,
    AssetSpec,
    HitboxRect,
    PaletteColor,
    StylePack,
)


def _sample_style() -> StylePack:
    return StylePack(
        id="test-style",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#090a0d", flags=("outline",)),
            PaletteColor(index=1, name="SLATE", hex="#334155", flags=("surface",)),
            PaletteColor(index=2, name="GLOW", hex="#38bdf8", flags=("emissive", "bright")),
            PaletteColor(index=3, name="GLOW_REFL", hex="#1d4ed8", flags=("surface",)),
        ),
        reflections={"GLOW": "GLOW_REFL"},
        variants={"amber": {"GLOW": "#fbbf24"}},
    )


def test_constants_and_valid_contracts() -> None:
    """Verify reserved index constants and valid StylePack/AssetSpec creation."""
    assert TRANSPARENT_INDEX == 255
    assert MAX_PALETTE_INDEX == 254

    style = _sample_style()
    assert style.reflections == {"GLOW": "GLOW_REFL"}
    assert "bright" in style.palette[2].flags
    assert "emissive" in style.palette[2].flags

    spec = AssetSpec(
        id="thinkpad_r51_iso",
        style_id=style.id,
        width=64,
        height=64,
        perspective="iso-2:1",
        states=("healthy", "dusty"),
        frames=2,
        fps=4,
        seed=510,
    )
    assert spec.width == 64
    assert AnchorPoint(name="screen", x=32, y=16).x == 32
    assert HitboxRect(name="body", x=4, y=3, w=55, h=58).h == 58

    port = AnchorPoint(name="port_0", x=6, y=11, kind="rj45", dir=(-1, 1))
    assert port.kind == "rj45"
    assert port.dir == (-1, 1)
    assert AnchorPoint(name="plain", x=1, y=2).kind is None
    assert AnchorPoint(name="plain", x=1, y=2).dir is None

    port_hb = HitboxRect(name="port_0", x=5, y=10, w=2, h=2, kind="rj45")
    assert port_hb.kind == "rj45"
    assert HitboxRect(name="plain", x=0, y=0, w=2, h=2).kind is None

    with pytest.raises(ValidationError):
        AnchorPoint(name="bad_kind", x=0, y=0, kind="")
    with pytest.raises(ValidationError):
        HitboxRect(name="bad_kind", x=0, y=0, w=2, h=2, kind="")


def test_transparent_index_cannot_be_allocated_in_palette() -> None:
    """Reject palette entries using reserved TRANSPARENT_INDEX (255)."""
    with pytest.raises(ValidationError):
        PaletteColor(index=TRANSPARENT_INDEX, name="BAD", hex="#ffffff")


def test_style_pack_rejects_duplicates_and_bad_references() -> None:
    """Reject duplicate indices/names, missing outline_index, and bad reflections/variants."""
    with pytest.raises(ValidationError, match="Duplicate palette index"):
        StylePack(
            id="dup-idx",
            perspective="front-2.5d",
            lighting_angle="top-left",
            outline_index=0,
            palette=(
                PaletteColor(index=0, name="A", hex="#000000"),
                PaletteColor(index=0, name="B", hex="#111111"),
            ),
        )

    with pytest.raises(ValidationError, match="Duplicate palette token"):
        StylePack(
            id="dup-name",
            perspective="front-2.5d",
            lighting_angle="top-left",
            outline_index=0,
            palette=(
                PaletteColor(index=0, name="SAME", hex="#000000"),
                PaletteColor(index=1, name="SAME", hex="#111111"),
            ),
        )

    with pytest.raises(ValidationError, match="outline_index"):
        StylePack(
            id="bad-outline",
            perspective="front-2.5d",
            lighting_angle="top-left",
            outline_index=9,
            palette=(PaletteColor(index=0, name="A", hex="#000000"),),
        )

    with pytest.raises(ValidationError, match="Reflection target token"):
        StylePack(
            id="bad-refl",
            perspective="front-2.5d",
            lighting_angle="top-left",
            outline_index=0,
            palette=(PaletteColor(index=0, name="A", hex="#000000"),),
            reflections={"A": "MISSING"},
        )

    with pytest.raises(ValidationError, match="unknown token"):
        StylePack(
            id="bad-var",
            perspective="front-2.5d",
            lighting_angle="top-left",
            outline_index=0,
            palette=(PaletteColor(index=0, name="A", hex="#000000"),),
            variants={"alt": {"NOPE": "#123456"}},
        )


def test_asset_spec_frame_events_validation() -> None:
    spec = AssetSpec(
        id="bot",
        style_id="test",
        width=8,
        height=8,
        perspective="front-2.5d",
        states=("walk", "idle"),
        frames=3,
        frame_events={"walk": {0: ("footstep",), 2: ("footstep", "beep")}},
    )
    assert spec.frame_events["walk"][2] == ("footstep", "beep")

    with pytest.raises(ValidationError, match="unknown state"):
        AssetSpec(
            id="bot",
            style_id="test",
            width=8,
            height=8,
            perspective="front-2.5d",
            states=("walk",),
            frames=2,
            frame_events={"run": {0: ("footstep",)}},
        )

    with pytest.raises(ValidationError, match="out of range"):
        AssetSpec(
            id="bot",
            style_id="test",
            width=8,
            height=8,
            perspective="front-2.5d",
            states=("walk",),
            frames=2,
            frame_events={"walk": {2: ("footstep",)}},
        )

    with pytest.raises(ValidationError, match="empty event tag"):
        AssetSpec(
            id="bot",
            style_id="test",
            width=8,
            height=8,
            perspective="front-2.5d",
            states=("walk",),
            frames=2,
            frame_events={"walk": {0: ("   ",)}},
        )
