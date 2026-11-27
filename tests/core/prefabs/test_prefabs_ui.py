"""Unit tests for UI pixel art primitives and 9-slice showcase assets."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast, get_args

import numpy as np
import pytest

from pixelforge import TRANSPARENT_INDEX, Asset, AssetSpec, StylePack, prefabs
from pixelforge.core.palette import PaletteLookupError
from pixelforge.guard.runner import load_all_styles, load_asset_module

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _ui_palette(a: Asset) -> prefabs.UiPalette:
    return prefabs.UiPalette(
        bg=a.pal.WALL_L,
        bg_dark=a.pal.FLOOR_D,
        bg_light=a.pal.WALL_R,
        border_outer=a.pal.INK,
        border_highlight=a.pal.METAL_H,
        border_shadow=a.pal.FLOOR_D,
        accent=a.pal.METAL_M,
        accent_bright=a.pal.SKY,
        text=a.pal.CLOUD,
        text_muted=a.pal.METAL_D,
        success=a.pal.LED,
        warning=a.pal.SUN,
        danger=a.pal.WOOD_M,
    )


def test_ui_panel_chamfer_and_title_bar(make_asset: Callable[[int, int], Asset]) -> None:
    a = make_asset(32, 24)
    pal = _ui_palette(a)
    prefabs.ui_panel(a, 2, 2, 24, 20, pal, title_bar_h=3, beveled=True, corner_cut=1)

    assert a.surface.get(2, 2) == TRANSPARENT_INDEX
    assert a.surface.get(25, 2) == TRANSPARENT_INDEX
    assert a.surface.get(2, 21) == TRANSPARENT_INDEX
    assert a.surface.get(25, 21) == TRANSPARENT_INDEX
    assert a.surface.get(3, 3) == pal.border_outer
    assert a.surface.get(5, 5) == pal.accent
    assert int(np.count_nonzero(a.surface.data != TRANSPARENT_INDEX)) > 300


@pytest.mark.parametrize("state", ["normal", "hover", "pressed", "disabled"])
def test_ui_button_states_render_distinctly(
    make_asset: Callable[[int, int], Asset],
    state: prefabs.UiButtonState,
) -> None:
    a = make_asset(32, 20)
    pal = _ui_palette(a)
    prefabs.ui_button(a, 2, 2, 24, 14, pal, state=state, accent=True, corner_cut=1)
    assert a.surface.get(2, 2) == TRANSPARENT_INDEX
    assert a.surface.get(3, 3) == (pal.border_shadow if state == "disabled" else pal.border_outer)
    assert int(np.count_nonzero(a.surface.data != TRANSPARENT_INDEX)) > 200


def test_ui_progress_bar_clamps_and_segments(make_asset: Callable[[int, int], Asset]) -> None:
    a_empty = make_asset(32, 12)
    a_full = make_asset(32, 12)
    a_seg = make_asset(32, 12)
    pal = _ui_palette(a_empty)

    prefabs.ui_progress_bar(a_empty, 2, 2, 24, 8, pal, value=-0.5)
    prefabs.ui_progress_bar(a_full, 2, 2, 24, 8, pal, value=1.5)
    prefabs.ui_progress_bar(a_seg, 2, 2, 24, 8, pal, value=1.0, segments=4)

    assert int(np.count_nonzero(a_empty.surface.data == pal.accent)) == 0
    assert int(np.count_nonzero(a_full.surface.data == pal.accent)) > 0
    assert a_seg.surface.get(8, 5) == pal.border_outer


@pytest.mark.parametrize("tone", ["neutral", "info", "success", "warning", "danger"])
def test_ui_badge_tones(
    make_asset: Callable[[int, int], Asset],
    tone: prefabs.UiBadgeTone,
) -> None:
    a = make_asset(24, 12)
    pal = _ui_palette(a)
    prefabs.ui_badge(a, 2, 2, 18, 7, pal, tone=tone, pill=True)
    assert a.surface.get(2, 2) == TRANSPARENT_INDEX
    assert int(np.count_nonzero(a.surface.data != TRANSPARENT_INDEX)) > 80


@pytest.mark.parametrize("kind", list(get_args(prefabs.UiIconKind)))
def test_ui_icon_16_all_kinds(
    make_asset: Callable[[int, int], Asset],
    kind: prefabs.UiIconKind,
) -> None:
    a = make_asset(16, 16)
    prefabs.ui_icon_16(a, 0, 0, kind, a.pal.METAL_H, accent=a.pal.LED, outline=a.pal.INK)
    opaque = int(np.count_nonzero(a.surface.data != TRANSPARENT_INDEX))
    assert opaque >= 32


@pytest.mark.parametrize(
    "rel_path",
    [
        "assets/ui/hud_panel_9slice.asset.py",
        "assets/ui/hud_button_9slice.asset.py",
        "assets/ui/hud_icons_16.asset.py",
    ],
)
def test_showcase_ui_assets_render_cleanly(rel_path: str) -> None:
    styles = load_all_styles(_REPO_ROOT / "styles")
    asset_mod = load_asset_module(_REPO_ROOT / rel_path)
    style = styles[asset_mod.SPEC.style_id]
    for state in asset_mod.SPEC.states:
        a = Asset(asset_mod.SPEC, style, state=state, frame=0)
        asset_mod.render(a)
        assert int(np.count_nonzero(a.surface.data != TRANSPARENT_INDEX)) > 0


def test_ui_palette_from_style_all_builtin_presets() -> None:
    """Verify `UiPalette.from_style()` derives valid, deterministic palettes for all presets."""
    styles = load_all_styles(_REPO_ROOT / "styles")
    assert len(styles) >= 8

    for style_id, style in sorted(styles.items()):
        pal_a = prefabs.UiPalette.from_style(style)
        pal_b = prefabs.UiPalette.from_style(style)
        assert pal_a == pal_b

        valid_indices = {entry.index for entry in style.palette}
        for field_name in (
            "bg",
            "bg_dark",
            "bg_light",
            "border_outer",
            "border_highlight",
            "border_shadow",
            "accent",
            "accent_bright",
            "text",
            "text_muted",
            "success",
            "warning",
            "danger",
        ):
            idx = getattr(pal_a, field_name)
            assert idx in valid_indices, f"{style_id}.{field_name}={idx} not in palette"
            assert idx != TRANSPARENT_INDEX

        if len(style.palette) >= 2:
            assert pal_a.text != pal_a.bg, f"{style_id} text must contrast with bg"

        spec = AssetSpec(
            id=f"ui_probe_{style_id}",
            style_id=style_id,
            width=64,
            height=48,
            perspective=style.perspective,
            states=("default",),
            seed=1,
        )
        asset = Asset(spec, style)
        asset_pal = prefabs.UiPalette.from_style(asset)
        assert asset_pal == pal_a
        with asset.layer("ui") as layer:
            assert prefabs.UiPalette.from_style(layer) == pal_a
            prefabs.ui_panel(layer, 2, 2, 28, 22, asset_pal, title_bar_h=3)
            prefabs.ui_button(layer, 34, 2, 26, 14, asset_pal, state="hover", accent=True)
            prefabs.ui_progress_bar(layer, 34, 18, 26, 6, asset_pal, value=0.75)
            prefabs.ui_badge(layer, 2, 28, 18, 7, asset_pal, tone="success")
        assert int(np.count_nonzero(asset.surface.data != TRANSPARENT_INDEX)) > 400


def test_ui_palette_from_style_overrides_and_errors(
    make_asset: Callable[[int, int], Asset],
) -> None:
    """Verify `UiPalette.from_style()` supports int/str overrides and fails loudly on bad input."""
    a = make_asset(32, 32)
    pal = prefabs.UiPalette.from_style(a, accent="LED", border_highlight=a.pal.SUN)
    assert pal.accent == a.pal.LED
    assert pal.border_highlight == a.pal.SUN

    with pytest.raises(TypeError, match="Unknown UiPalette field"):
        prefabs.UiPalette.from_style(a, unknown_token=1)

    with pytest.raises(PaletteLookupError, match="Missing palette token"):
        prefabs.UiPalette.from_style(a, accent="NONEXISTENT_TOKEN")

    with pytest.raises(ValueError, match="not in style"):
        prefabs.UiPalette.from_style(a, bg=TRANSPARENT_INDEX)

    with pytest.raises(AttributeError):
        prefabs.UiPalette.from_style(cast(StylePack, cast(object, "not_a_style")))
