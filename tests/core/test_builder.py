"""Unit tests for compositional `Asset` and `Layer` context managers."""

from __future__ import annotations

import numpy as np
import pytest

from pixelforge import Asset, AssetSpec, PaletteColor, StylePack
from pixelforge.core.types import TRANSPARENT_INDEX, AnchorPoint, HitboxRect


def _make_test_style() -> StylePack:
    return StylePack(
        id="test-homelab",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#0d0e15", flags=("outline",)),
            PaletteColor(index=1, name="SHADOW", hex="#181c28", flags=("shadow",)),
            PaletteColor(index=2, name="SLATE_DARK", hex="#252c3f", flags=("surface",)),
            PaletteColor(index=3, name="SLATE_MID", hex="#3b455e", flags=("surface",)),
            PaletteColor(index=4, name="SLATE_LIGHT", hex="#5e6b8c", flags=("surface",)),
            PaletteColor(index=5, name="METAL_LIGHT", hex="#9aa6bf", flags=("metal",)),
            PaletteColor(index=6, name="FAULT_RED", hex="#f85149", flags=("emissive", "accent")),
            PaletteColor(index=7, name="CYAN_GLOW", hex="#56d4dd", flags=("emissive", "bright")),
            PaletteColor(index=8, name="DUST_LIGHT", hex="#a89984", flags=("surface",)),
            PaletteColor(index=9, name="DUST_DARK", hex="#7c6f64", flags=("surface",)),
            PaletteColor(index=10, name="SHIRT_A", hex="#39669f", flags=("accent",)),
            PaletteColor(index=11, name="SHIRT_B", hex="#3fb950", flags=("accent",)),
            PaletteColor(index=12, name="HAIR_A", hex="#4d3b32", flags=("accent",)),
            PaletteColor(index=13, name="HAIR_B", hex="#e3b341", flags=("accent",)),
        ),
        variants={
            "alt": {"SHIRT_A": "#cc4444"},
        },
    )


def test_compositional_thinkpad_like_asset_and_determinism() -> None:
    """Verify nested layers, planes, bevels, masked scatter, 1px escape hatch, and determinism."""
    style = _make_test_style()
    spec = AssetSpec(
        id="thinkpad_r51_iso",
        style_id="test-homelab",
        width=64,
        height=64,
        perspective="iso-2:1",
        states=("healthy", "dusty"),
        frames=2,
        fps=2,
        seed=510,
    )

    def render_sample(a: Asset) -> None:
        pal = a.pal
        with (
            a.layer("lid", outline=pal.OUTLINE),
            a.plane(p0=(22, 4), p1=(57, 13), p2=(17, 30)) as lid,
        ):
            lid.rect(
                0.0,
                0.0,
                1.0,
                1.0,
                fill=pal.SLATE_DARK,
                bevel=(pal.SLATE_LIGHT, pal.SHADOW),
            )
            lid.rect(0.08, 0.11, 0.84, 0.76, fill=pal.METAL_LIGHT)
            lid.anchor("screen", 0.5, 0.5)

        with (
            a.layer("deck", outline=pal.OUTLINE),
            a.plane(p0=(17, 32), p1=(52, 41), p2=(5, 49)) as deck,
        ):
            deck.rect(0.0, 0.0, 1.0, 1.0, fill=pal.SLATE_MID, extrude_y=3, side=pal.SHADOW)
            deck.grid(0.07, 0.08, 0.83, 0.46, cols=13, rows=4, color=pal.SLATE_DARK)
            deck.dot(0.45, 0.29, pal.FAULT_RED, anchor="trackpoint")

        if a.state == "dusty":
            placed = a.scatter(count=16, colors=(pal.DUST_LIGHT, pal.DUST_DARK), mask="opaque")
            assert placed == 16

        if a.state == "healthy" and a.frame == 0:
            a.put(31, 14, pal.CYAN_GLOW)

        a.hitbox("body", 4, 3, 55, 58)

    a1 = Asset(spec, style, state="dusty", frame=1)
    a2 = Asset(spec, style, state="dusty", frame=1)
    render_sample(a1)
    render_sample(a2)

    assert np.array_equal(a1.root_surface.data, a2.root_surface.data)
    assert a1.anchors == a2.anchors
    assert a1.hitboxes == (HitboxRect(name="body", x=4, y=3, w=55, h=58),)
    assert {pt.name for pt in a1.anchors} == {"screen", "trackpoint"}
    # Dust must only appear on opaque pixels (never on transparent background corner)
    assert a1.get(0, 0) == TRANSPARENT_INDEX

    healthy = Asset(spec, style, state="healthy", frame=0)
    render_sample(healthy)
    assert healthy.get(31, 14) == style.palette[7].index


def test_nested_layers_offset_mirror_sel_out_and_bevel() -> None:
    """Verify nested layer offset stacking, mirror_x, sel_out, bevel, and metadata offsets."""
    style = _make_test_style()
    spec = AssetSpec(
        id="nested_test",
        style_id="test-homelab",
        width=32,
        height=32,
        perspective="front-2.5d",
    )
    a = Asset(spec, style)
    pal = a.pal

    with a.layer("parent", offset=(6, 4)) as parent:
        with a.layer(
            "sym_badge",
            offset=(2, 2),
            size=(8, 6),
            mirror_x="left",
            outline=pal.OUTLINE,
        ) as badge:
            badge.rect(1, 1, 3, 4, pal.METAL_LIGHT)
            badge.anchor("badge_center", 4, 3)
        assert parent.get(3, 3) == pal.METAL_LIGHT
        # Mirrored across x=4 inside 8x6 surface -> x=6 gets METAL_LIGHT, x=7 gets outline
        assert parent.get(8, 3) == pal.METAL_LIGHT
        assert parent.get(9, 3) == pal.OUTLINE

    # Global surface includes parent offset (6, 4) + badge offset (2, 2) = (8, 6)
    assert a.get(9, 7) == pal.METAL_LIGHT
    assert a.anchors == (AnchorPoint(name="badge_center", x=12, y=9),)

    # Sel_out + bevel layer
    with a.layer(
        "chip",
        offset=(16, 16),
        size=(8, 8),
        bevel=(pal.SLATE_LIGHT, pal.SHADOW),
        sel_out=(pal.CYAN_GLOW, pal.OUTLINE, pal.SLATE_DARK),
    ) as chip:
        chip.rect(2, 2, 4, 4, pal.SLATE_MID)
    # Top bevel at (16+2, 16+2) = (18, 18), sel_out top at (18, 17)
    assert a.get(18, 18) == pal.SLATE_LIGHT
    assert a.get(18, 21) == pal.SHADOW
    assert a.get(18, 17) == pal.CYAN_GLOW
    assert a.get(18, 22) == pal.OUTLINE
    assert a.get(17, 19) == pal.SLATE_DARK


def test_avatar_token_overrides_and_atomic_recolor() -> None:
    """Verify palette_override scoping and collision-free recolor for shared-silhouette avatars."""
    style = _make_test_style()
    spec = AssetSpec(
        id="avatar_shared",
        style_id="test-homelab",
        width=16,
        height=16,
        perspective="front-2.5d",
    )

    def draw_avatar(a: Asset) -> None:
        a.rect(4, 2, 8, 4, a.pal.HAIR_A)
        a.rect(4, 6, 8, 6, a.pal.SHIRT_A)

    base = Asset(style=style, spec=spec)
    draw_avatar(base)
    assert base.get(5, 3) == style.palette[12].index  # HAIR_A
    assert base.get(5, 7) == style.palette[10].index  # SHIRT_A

    # Scope-based token override
    swapped = Asset(spec, style)
    with swapped.palette_override({"HAIR_A": "HAIR_B", "SHIRT_A": "SHIRT_B"}):
        draw_avatar(swapped)
    # Outside scope, swapped.pal is restored
    assert swapped.pal["SHIRT_A"] == style.palette[10].index
    assert swapped.get(5, 3) == style.palette[13].index  # HAIR_B
    assert swapped.get(5, 7) == style.palette[11].index  # SHIRT_B

    # Atomic simultaneous swap (A <-> B must not clobber)
    swapped.recolor({"HAIR_B": "HAIR_A", "HAIR_A": "HAIR_B", "SHIRT_B": "SHIRT_A"})
    assert swapped.get(5, 3) == style.palette[12].index  # HAIR_A
    assert swapped.get(5, 7) == style.palette[10].index  # SHIRT_A

    # Keyword override syntax works identically to mapping syntax
    kw_swapped = Asset(spec, style)
    with kw_swapped.palette_override(HAIR_A="HAIR_B", SHIRT_A="SHIRT_B"):
        draw_avatar(kw_swapped)
    assert kw_swapped.get(5, 3) == style.palette[13].index  # HAIR_B
    assert kw_swapped.get(5, 7) == style.palette[11].index  # SHIRT_B


def test_multi_anchor_scene_and_coupled_hitboxes() -> None:
    """Verify scene slot anchors (`hw_slot_*`, `window`, `solar`, `breaker`) and `anchor_hitbox`."""
    style = _make_test_style()
    spec = AssetSpec(
        id="bedroom_desk_iso",
        style_id="test-homelab",
        width=320,
        height=200,
        perspective="iso-2:1",
    )

    with Asset(spec, style) as a:
        pal = a.pal
        a.iso_tile(160, 120, 64, pal.SLATE_DARK)
        a.iso_box(
            220,
            40,
            16,
            12,
            24,
            top=pal.SLATE_LIGHT,
            left=pal.SLATE_MID,
            right=pal.SHADOW,
            outline=pal.OUTLINE,
        )
        a.anchor_slots("hw_slot_", [(80, 110), (120, 120), (160, 130)])
        a.anchor("window", 50, 30)
        a.anchor("solar", 260, 24)
        a.anchor("breaker", 290, 90)
        pt, hb = a.anchor_hitbox("desk", 100, 100, 40, 20, anchor_at="bottom-center")

    assert pt == AnchorPoint(name="desk", x=120, y=120)
    assert hb == HitboxRect(name="desk", x=100, y=100, w=40, h=20)
    names = [anchor.name for anchor in a.anchors]
    assert names == ["hw_slot_0", "hw_slot_1", "hw_slot_2", "window", "solar", "breaker", "desk"]


def test_anchor_and_hitbox_metadata_kind_and_dir() -> None:
    """Verify `kind` and `dir` propagate through Asset, Layer, anchor_slots, and anchor_hitbox."""
    style = _make_test_style()
    spec = AssetSpec(
        id="switch_meta",
        style_id="test-homelab",
        width=32,
        height=32,
        perspective="iso-2:1",
    )

    with Asset(spec, style) as a:
        a.anchor("uplink", 4, 8, kind="sfp", dir=(1, -1))
        a.anchor_slots("port_", [(6, 10), (10, 12)], kind="rj45", dir=(-1, 1))
        a.hitbox("chassis", 2, 2, 20, 12, kind="solid")
        pt, hb = a.anchor_hitbox(
            "psu",
            20,
            4,
            6,
            8,
            anchor_at="center",
            kind="power",
            dir=(0, 1),
        )
        with a.layer("daughter", offset=(2, 3)) as layer:
            layer.anchor("aux", 1, 1, kind="gpio", dir=(0, -1))
            layer.hitbox("aux_box", 0, 0, 4, 4, kind="pin")

    assert pt == AnchorPoint(name="psu", x=23, y=8, kind="power", dir=(0, 1))
    assert hb == HitboxRect(name="psu", x=20, y=4, w=6, h=8, kind="power")
    assert a.anchors == (
        AnchorPoint(name="uplink", x=4, y=8, kind="sfp", dir=(1, -1)),
        AnchorPoint(name="port_0", x=6, y=10, kind="rj45", dir=(-1, 1)),
        AnchorPoint(name="port_1", x=10, y=12, kind="rj45", dir=(-1, 1)),
        AnchorPoint(name="psu", x=23, y=8, kind="power", dir=(0, 1)),
        AnchorPoint(name="aux", x=3, y=4, kind="gpio", dir=(0, -1)),
    )
    assert a.hitboxes == (
        HitboxRect(name="chassis", x=2, y=2, w=20, h=12, kind="solid"),
        HitboxRect(name="psu", x=20, y=4, w=6, h=8, kind="power"),
        HitboxRect(name="aux_box", x=2, y=3, w=4, h=4, kind="pin"),
    )


def test_builder_validation_errors() -> None:
    """Verify fail-loud errors on invalid states, frames, variants, and layer names."""
    style = _make_test_style()
    spec = AssetSpec(
        id="err_test",
        style_id="test-homelab",
        width=8,
        height=8,
        perspective="side",
        states=("idle",),
        frames=2,
    )

    with pytest.raises(ValueError, match="Invalid state"):
        Asset(spec, style, state="missing")
    with pytest.raises(ValueError, match="out of range"):
        Asset(spec, style, frame=2)
    with pytest.raises(ValueError, match="Unknown variant"):
        Asset(spec, style, variant="nope")

    a = Asset(spec, style)
    with pytest.raises(ValueError, match="non-empty"):
        a.layer("")
    # Unentered layer must not corrupt _layer_stack or active surface
    _unused = a.layer("unused")
    assert a.surface is a.root_surface
    a.put(1, 1, 1)
    assert a.root_surface.get(1, 1) == 1

    with pytest.raises(RuntimeError, match="Out-of-order"):
        outer = a.layer("outer")
        with outer:
            inner = a.layer("inner")
            inner.__enter__()
            outer.__exit__(None, None, None)
