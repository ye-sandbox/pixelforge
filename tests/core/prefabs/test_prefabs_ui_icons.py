"""Hermetic unit tests for multi-genre UI pixel icon packs and registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import get_args

import numpy as np
import pytest

from pixelforge.core import TRANSPARENT_INDEX, Asset, prefabs


@pytest.mark.parametrize(
    ("pack_name", "pack"),
    [
        ("core", prefabs.ui_icons_core),
        ("rpg", prefabs.ui_icons_rpg),
        ("tech", prefabs.ui_icons_tech),
    ],
)
@pytest.mark.parametrize("size", [8, 12, 16])
def test_builtin_packs_have_valid_dimensions_and_render(
    make_asset: Callable[[int, int], Asset],
    pack_name: str,
    pack: prefabs.UiIconPack,
    size: prefabs.UiIconSize,
) -> None:
    icons = pack.list_icons(size=size)
    assert len(icons) >= 10
    for icon_name in icons:
        grid = prefabs.get_icon_grid(icon_name, size=size, pack=pack_name)
        assert len(grid) == size
        assert all(len(row) == size for row in grid)

        a = make_asset(size, size)
        prefabs.ui_icon(
            a,
            0,
            0,
            icon_name,
            a.pal.METAL_H,
            size=size,
            pack=pack_name,
            accent=a.pal.LED,
            outline=a.pal.INK,
        )
        opaque = int(np.count_nonzero(a.surface.data != TRANSPARENT_INDEX))
        assert opaque >= 12


@pytest.mark.parametrize("size", [8, 12, 16])
def test_size_helpers_and_bg_fill(
    make_asset: Callable[[int, int], Asset],
    size: prefabs.UiIconSize,
) -> None:
    a = make_asset(size, size)
    if size == 8:
        prefabs.ui_icon_8(
            a,
            0,
            0,
            "heart",
            a.pal.METAL_H,
            pack="rpg",
            bg=a.pal.WALL_L,
            accent=a.pal.LED,
            outline=a.pal.INK,
        )
    elif size == 12:
        prefabs.ui_icon_12(
            a,
            0,
            0,
            "heart",
            a.pal.METAL_H,
            pack="rpg",
            bg=a.pal.WALL_L,
            accent=a.pal.LED,
            outline=a.pal.INK,
        )
    else:
        prefabs.ui_icon_16(
            a,
            0,
            0,
            "heart",
            a.pal.METAL_H,
            pack="rpg",
            bg=a.pal.WALL_L,
            accent=a.pal.LED,
            outline=a.pal.INK,
        )

    assert int(np.count_nonzero(a.surface.data == TRANSPARENT_INDEX)) == 0
    assert int(np.count_nonzero(a.surface.data == a.pal.WALL_L)) > 0


def test_ui_icon_16_backwards_compatibility(make_asset: Callable[[int, int], Asset]) -> None:
    kinds = get_args(prefabs.UiIconKind)
    assert set(kinds) == {
        "cpu",
        "ram",
        "disk",
        "network",
        "power",
        "alert",
        "bolt",
        "terminal",
        "check",
        "lock",
    }
    for kind in kinds:
        a = make_asset(16, 16)
        prefabs.ui_icon_16(a, 0, 0, kind, a.pal.METAL_H, accent=a.pal.LED, outline=a.pal.INK)
        assert int(np.count_nonzero(a.surface.data != TRANSPARENT_INDEX)) >= 32


def test_list_icons_and_packs() -> None:
    packs = prefabs.list_icon_packs()
    assert packs[:3] == ["tech", "core", "rpg"]
    assert "sword" in prefabs.list_icons(pack="rpg", size=16)
    assert "gear" in prefabs.list_icons(pack="core", size=8)
    assert "server" in prefabs.list_icons(pack="tech", size=12)
    assert "sword" in prefabs.list_icons()


def test_custom_icon_registration_and_validation(
    make_asset: Callable[[int, int], Asset],
) -> None:
    custom_pack_name = "test_custom_pack"
    custom_grid = (
        "..oooo..",
        ".o####o.",
        "o##++##o",
        "o#++++#o",
        "o#++++#o",
        "o##++##o",
        ".o####o.",
        "..oooo..",
    )
    try:
        prefabs.register_icon("orb", custom_grid, pack=custom_pack_name)
        assert "orb" in prefabs.list_icons(pack=custom_pack_name, size=8)

        a = make_asset(8, 8)
        prefabs.ui_icon_8(
            a,
            0,
            0,
            "orb",
            a.pal.METAL_H,
            pack=custom_pack_name,
            accent=a.pal.LED,
            outline=a.pal.INK,
        )
        assert int(np.count_nonzero(a.surface.data == a.pal.LED)) == 12

        with pytest.raises(ValueError, match="already exists"):
            prefabs.register_icon("orb", custom_grid, pack=custom_pack_name)

        prefabs.register_icon("orb", custom_grid, pack=custom_pack_name, overwrite=True)

        with pytest.raises(ValueError, match="unsupported size"):
            prefabs.register_icon(
                "bad_size",
                ("....", "....", "....", "...."),
                pack=custom_pack_name,
            )

        with pytest.raises(ValueError, match="invalid chars"):
            prefabs.register_icon(
                "bad_char",
                (
                    "........",
                    "..xxxx..",
                    "........",
                    "........",
                    "........",
                    "........",
                    "........",
                    "........",
                ),
                pack=custom_pack_name,
            )

        with pytest.raises(KeyError, match="Unknown icon pack"):
            prefabs.get_icon_grid("orb", size=8, pack="nonexistent_pack")

        with pytest.raises(KeyError, match="not found"):
            prefabs.get_icon_grid("nonexistent_icon", size=16)
    finally:
        prefabs.unregister_icon_pack(custom_pack_name)
