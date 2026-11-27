"""Pixel cursor sprites with exact hotspot anchor emission."""

from __future__ import annotations

from typing import Final, Literal

from pixelforge.core.prefabs.ui.palette import UiPalette, UiTarget

UiCursorKind = Literal["pointer", "hand", "crosshair", "resize_h", "resize_v", "text"]

_CURSOR_GRIDS: Final[dict[UiCursorKind, tuple[str, ...]]] = {
    "pointer": (
        "oo..........",
        "o#o.........",
        "o##o........",
        "o###o.......",
        "o####o......",
        "o#####o.....",
        "o######o....",
        "o#######o...",
        "o########o..",
        "o#####oooo..",
        "o##o##o.....",
        "o#o.o##o....",
        "oo..o##o....",
        ".....o##o...",
        ".....o##o...",
        "......oo....",
    ),
    "hand": (
        "....oo........",
        "...o##o.......",
        "...o##o.......",
        "...o##o.......",
        "...o##oooo....",
        ".ooo##o##ooo..",
        "o##o##o##o##o.",
        "o##o########o.",
        "o###########o.",
        ".o##########o.",
        ".o##########o.",
        "..o########o..",
        "..o########o..",
        "...o######o...",
        "...oooooooo...",
        "..............",
    ),
    "crosshair": (
        "......ooo......",
        "......o#o......",
        "......o#o......",
        "......o#o......",
        "......o#o......",
        "......ooo......",
        "ooooo..+..ooooo",
        "o###o.+o+.o###o",
        "ooooo..+..ooooo",
        "......ooo......",
        "......o#o......",
        "......o#o......",
        "......o#o......",
        "......o#o......",
        "......ooo......",
    ),
    "resize_h": (
        "...............",
        "...oo.....oo...",
        "..o#o.....o#o..",
        ".o##ooooooo##o.",
        "o#############o",
        ".o##ooooooo##o.",
        "..o#o.....o#o..",
        "...oo.....oo...",
        "...............",
    ),
    "resize_v": (
        "....o....",
        "...o#o...",
        "..o###o..",
        ".o#####o.",
        "ooo#o#ooo",
        "..o###o..",
        "..o###o..",
        "..o###o..",
        "..o###o..",
        "..o###o..",
        "ooo#o#ooo",
        ".o#####o.",
        "..o###o..",
        "...o#o...",
        "....o....",
    ),
    "text": (
        "oooooo.",
        "o####o.",
        "oo##oo.",
        ".o##o..",
        ".o##o..",
        ".o##o..",
        ".o##o..",
        ".o##o..",
        ".o##o..",
        ".o##o..",
        "oo##oo.",
        "o####o.",
        "oooooo.",
    ),
}

_CURSOR_HOTSPOTS: Final[dict[UiCursorKind, tuple[int, int]]] = {
    "pointer": (0, 0),
    "hand": (4, 0),
    "crosshair": (7, 7),
    "resize_h": (7, 4),
    "resize_v": (4, 7),
    "text": (2, 6),
}


def ui_cursor(
    a: UiTarget,
    x: int,
    y: int,
    kind: UiCursorKind,
    pal: UiPalette,
    *,
    fg: int | None = None,
    outline: int | None = None,
    accent: int | None = None,
    emit_hotspot_anchor: bool = True,
    anchor_name: str = "hotspot",
) -> tuple[int, int]:
    """Draw a pixel UI cursor and optionally emit its exact `hotspot` anchor."""
    grid = _CURSOR_GRIDS[kind]
    fill_color = pal.text if fg is None else fg
    outline_color = pal.border_outer if outline is None else outline
    accent_color = pal.accent_bright if accent is None else accent
    color_map: dict[str, int] = {
        "#": fill_color,
        "o": outline_color,
        "+": accent_color,
    }
    a.spr(grid, x, y, color_map)
    hx, hy = _CURSOR_HOTSPOTS[kind]
    abs_x = x + hx
    abs_y = y + hy
    if emit_hotspot_anchor:
        a.anchor(anchor_name, abs_x, abs_y, kind="ui_hotspot")
    return (abs_x, abs_y)
