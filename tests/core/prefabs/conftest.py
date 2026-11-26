"""Shared pytest fixtures for `tests/core/prefabs/`."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from pixelforge import Asset, AssetSpec, PaletteColor, StylePack


def _build_style() -> StylePack:
    """Create a deterministic 16-color `StylePack` for prefab unit tests."""
    return StylePack(
        id="prefab-test",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="INK", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="FLOOR", hex="#3b4252", flags=("surface",)),
            PaletteColor(index=2, name="FLOOR_D", hex="#2e3440", flags=("shadow",)),
            PaletteColor(index=3, name="WALL_L", hex="#4c566a", flags=("surface",)),
            PaletteColor(index=4, name="WALL_R", hex="#434c5e", flags=("surface",)),
            PaletteColor(index=5, name="WOOD_L", hex="#d08770", flags=("bright",)),
            PaletteColor(index=6, name="WOOD_M", hex="#bf616a", flags=("surface",)),
            PaletteColor(index=7, name="WOOD_D", hex="#8f434a", flags=("shadow",)),
            PaletteColor(index=8, name="METAL_H", hex="#d8dee9", flags=("bright",)),
            PaletteColor(index=9, name="METAL_M", hex="#81a1c1", flags=("surface",)),
            PaletteColor(index=10, name="METAL_D", hex="#4c566a", flags=("shadow",)),
            PaletteColor(index=11, name="SKY", hex="#88c0d0", flags=("surface",)),
            PaletteColor(index=12, name="LED", hex="#a3be8c", flags=("emissive",)),
            PaletteColor(index=13, name="SKY_DARK", hex="#1b263b", flags=("surface",)),
            PaletteColor(index=14, name="SUN", hex="#ebcb8b", flags=("bright",)),
            PaletteColor(index=15, name="CLOUD", hex="#eceff4", flags=("bright",)),
        ),
    )


def _build_asset(width: int = 160, height: int = 120) -> Asset:
    """Create a fresh `Asset` bound to `_build_style()` for hermetic prefab tests."""
    spec = AssetSpec(
        id="prefab_probe",
        style_id="prefab-test",
        width=width,
        height=height,
        perspective="iso-2:1",
        states=("day",),
        seed=7,
    )
    return Asset(spec, _build_style())


@pytest.fixture
def make_style() -> Callable[[], StylePack]:
    """Return a factory for deterministic 16-color `StylePack` instances."""
    return _build_style


@pytest.fixture
def make_asset() -> Callable[..., Asset]:
    """Return a factory for fresh `Asset` instances."""
    return _build_asset
