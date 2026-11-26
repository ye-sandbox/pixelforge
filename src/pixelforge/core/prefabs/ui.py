"""StylePack-agnostic UI pixel art primitives (panels, buttons, bars, badges, 16x16 icons)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from pixelforge.core.builder import Asset, Layer

UiTarget = Asset[object] | Layer

UiButtonState = Literal["normal", "hover", "pressed", "disabled"]
UiBadgeTone = Literal["neutral", "info", "success", "warning", "danger"]
UiIconKind = Literal[
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
]


@dataclass(frozen=True)
class UiPalette:
    """Semantic palette mapping for UI primitives without StylePack coupling."""

    bg: int
    bg_dark: int
    bg_light: int
    border_outer: int
    border_highlight: int
    border_shadow: int
    accent: int
    accent_bright: int
    text: int
    text_muted: int
    success: int
    warning: int
    danger: int


_ICON_GRIDS_16: Final[dict[UiIconKind, tuple[str, ...]]] = {
    "cpu": (
        "................",
        "....#.#..#.#....",
        "....#.#..#.#....",
        "..oooooooooooo..",
        "..o##########o..",
        ".##+########+##.",
        "..o#oooooooo#o..",
        ".##o#++++++#o##.",
        "..o#o++++++#o...",
        ".##o#++++++#o##.",
        "..o#oooooooo#o..",
        "..o##########o..",
        "..oooooooooooo..",
        "....#.#..#.#....",
        "....#.#..#.#....",
        "................",
    ),
    "ram": (
        "................",
        "................",
        "..oooooooooooo..",
        ".o############o.",
        ".o#++#++#++#+#o.",
        ".o#++#++#++#+#o.",
        ".o#++#++#++#+#o.",
        ".o############o.",
        ".o###o####o###o.",
        "..ooo......ooo..",
        "..#.#.#..#.#.#..",
        "..#.#.#..#.#.#..",
        "................",
        "................",
        "................",
        "................",
    ),
    "disk": (
        "................",
        "..oooooooooooo..",
        ".o############o.",
        ".o#oooooooooo#o.",
        ".o#o########o#o.",
        ".o#o###++###o#o.",
        ".o#o##+##+##o#o.",
        ".o#o###++###o#o.",
        ".o#o########o#o.",
        ".o#oooooooooo#o.",
        ".o############o.",
        ".o##++####oo##o.",
        ".o############o.",
        "..oooooooooooo..",
        "................",
        "................",
    ),
    "network": (
        "................",
        "......oooo......",
        "....oo++++oo....",
        "...o++oooo++o...",
        "..o+oo....oo+o..",
        ".....oo++oo.....",
        "....o+oooo+o....",
        "......oooo......",
        ".......##.......",
        "......o##o......",
        "....oo####oo....",
        "..oo##oooo##oo..",
        ".o####o..o####o.",
        "..oooo....oooo..",
        "................",
        "................",
    ),
    "power": (
        "................",
        ".......oo.......",
        "......o++o......",
        "....ooo++ooo....",
        "...o##o++o##o...",
        "..o##oo++oo##o..",
        "..o#o..++..o#o..",
        "..o#o..oo..o#o..",
        "..o#o......o#o..",
        "..o##o....o##o..",
        "...o##oooo##o...",
        "....o######o....",
        ".....oooooo.....",
        "................",
        "................",
        "................",
    ),
    "alert": (
        "................",
        ".......oo.......",
        "......o++o......",
        ".....o+##+o.....",
        ".....o+##+o.....",
        "....o+#oo#+o....",
        "....o+#oo#+o....",
        "...o+##oo##+o...",
        "...o+##oo##+o...",
        "..o+###oo###+o..",
        "..o+########+o..",
        ".o+####oo####+o.",
        ".o+####oo####+o.",
        ".o++++++++++++o.",
        "..oooooooooooo..",
        "................",
    ),
    "bolt": (
        "................",
        "........oooo....",
        ".......o+++o....",
        "......o+++o.....",
        ".....o+++o......",
        "....o+++o.......",
        "...o+++++oooo...",
        "..o+++++++++o...",
        "......ooo+++o...",
        ".......o+++o....",
        "......o+++o.....",
        ".....o+++o......",
        "....o+++o.......",
        "....oooo........",
        "................",
        "................",
    ),
    "terminal": (
        "................",
        ".oooooooooooooo.",
        ".o############o.",
        ".o#oooooooooo#o.",
        ".o#o........o#o.",
        ".o#o.++.....o#o.",
        ".o#o...++...o#o.",
        ".o#o.....++.o#o.",
        ".o#o...++...o#o.",
        ".o#o.++.....o#o.",
        ".o#o....++++o#o.",
        ".o#o........o#o.",
        ".o#oooooooooo#o.",
        ".o############o.",
        ".oooooooooooooo.",
        "................",
    ),
    "check": (
        "................",
        "................",
        "............oo..",
        "...........o++o.",
        "..........o+++o.",
        ".........o+++o..",
        "..oo....o+++o...",
        ".o++o..o+++o....",
        ".o+++oo+++o.....",
        "..o++++++o......",
        "...o++++o.......",
        "....o++o........",
        ".....oo.........",
        "................",
        "................",
        "................",
    ),
    "lock": (
        "................",
        ".....oooooo.....",
        "....o######o....",
        "...o##oooo##o...",
        "...o#o....o#o...",
        "...o#o....o#o...",
        "..oooooooooooo..",
        ".o############o.",
        ".o####+##+####o.",
        ".o###++++++###o.",
        ".o####+##+####o.",
        ".o#####++#####o.",
        ".o#####++#####o.",
        ".o############o.",
        "..oooooooooooo..",
        "................",
    ),
}


def _cut_rect_corners(a: UiTarget, x: int, y: int, w: int, h: int, cut: int) -> None:
    """Erase `cut` pixels on each outer corner for chamfered pixel UI frames."""
    if cut <= 0 or w < cut * 2 + 2 or h < cut * 2 + 2:
        return
    for dy in range(cut):
        span = cut - dy
        for dx in range(span):
            a.erase(x + dx, y + dy)
            a.erase(x + w - 1 - dx, y + dy)
            a.erase(x + dx, y + h - 1 - dy)
            a.erase(x + w - 1 - dx, y + h - 1 - dy)


def _draw_chamfer_border(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    color: int,
    cut: int,
) -> None:
    """Draw a 1px outer border respecting optional 1px corner chamfers."""
    if cut <= 0 or w < 4 or h < 4:
        a.rect(x, y, w, 1, color)
        a.rect(x, y + h - 1, w, 1, color)
        a.rect(x, y, 1, h, color)
        a.rect(x + w - 1, y, 1, h, color)
        return

    # INVARIANT: Chamfered 1px corners sit at (x+1, y+1) etc. so diagonal edges
    # stay 45-degree pixel-clean without 2px L-clusters.
    a.rect(x + 1, y, w - 2, 1, color)
    a.rect(x + 1, y + h - 1, w - 2, 1, color)
    a.rect(x, y + 1, 1, h - 2, color)
    a.rect(x + w - 1, y + 1, 1, h - 2, color)
    a.put(x + 1, y + 1, color)
    a.put(x + w - 2, y + 1, color)
    a.put(x + 1, y + h - 2, color)
    a.put(x + w - 2, y + h - 2, color)


def ui_panel(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    title_bar_h: int = 0,
    beveled: bool = True,
    corner_cut: int = 1,
    recessed: bool = False,
) -> None:
    """Draw a 9-slice-ready beveled pixel UI panel with optional title bar."""
    if w < 4 or h < 4:
        return

    fill_color = pal.bg_dark if recessed else pal.bg
    a.rect(x, y, w, h, fill_color)
    _draw_chamfer_border(a, x, y, w, h, pal.border_outer, corner_cut)

    if beveled and w >= 6 and h >= 6:
        top_bevel = pal.border_shadow if recessed else pal.border_highlight
        bot_bevel = pal.border_highlight if recessed else pal.border_shadow
        inset = 2 if corner_cut > 0 else 1
        span_w = max(1, w - inset * 2)
        span_h = max(1, h - inset * 2)
        a.rect(x + inset, y + 1, span_w, 1, top_bevel)
        a.rect(x + 1, y + inset, 1, span_h, top_bevel)
        a.rect(x + inset, y + h - 2, span_w, 1, bot_bevel)
        a.rect(x + w - 2, y + inset, 1, span_h, bot_bevel)

    if title_bar_h > 0 and h > title_bar_h + 4:
        bar_y = y + 2
        bar_h = min(title_bar_h, h - 4)
        a.rect(x + 2, bar_y, w - 4, bar_h, pal.bg_light)
        a.rect(x + 1, bar_y + bar_h, w - 2, 1, pal.border_outer)
        if w >= 12 and bar_h >= 2:
            a.put(x + 3, bar_y + 1, pal.accent)

    _cut_rect_corners(a, x, y, w, h, min(corner_cut, 1))


def ui_button(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    state: UiButtonState = "normal",
    accent: bool = False,
    corner_cut: int = 1,
) -> None:
    """Draw a tactile pixel UI button across normal, hover, pressed, and disabled states."""
    if w < 4 or h < 4:
        return

    if state == "disabled":
        fill = pal.bg_dark
        border = pal.border_shadow
        top_edge = pal.bg
        bot_edge = pal.bg_dark
    elif state == "pressed":
        fill = pal.accent if accent else pal.bg_dark
        border = pal.border_outer
        top_edge = pal.border_shadow
        bot_edge = fill
    elif state == "hover":
        fill = pal.accent_bright if accent else pal.bg_light
        border = pal.border_outer
        top_edge = pal.text if accent else pal.accent_bright
        bot_edge = pal.accent if accent else pal.border_shadow
    else:
        fill = pal.accent if accent else pal.bg_light
        border = pal.border_outer
        top_edge = pal.accent_bright if accent else pal.border_highlight
        bot_edge = pal.border_shadow

    a.rect(x, y, w, h, fill)
    _draw_chamfer_border(a, x, y, w, h, border, corner_cut)

    if w >= 6 and h >= 5:
        inset = 2 if corner_cut > 0 else 1
        span_w = max(1, w - inset * 2)
        a.rect(x + inset, y + 1, span_w, 1, top_edge)
        a.rect(x + inset, y + h - 2, span_w, 1, bot_edge)

    _cut_rect_corners(a, x, y, w, h, min(corner_cut, 1))


def ui_progress_bar(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    value: float = 0.5,
    fill_color: int | None = None,
    segments: int = 0,
    show_specular: bool = True,
) -> None:
    """Draw a recessed pixel progress bar with optional specular strip and segments."""
    if w < 4 or h < 3:
        return

    clamped = max(0.0, min(1.0, value))
    a.rect(x, y, w, h, pal.border_outer)
    inner_x = x + 1
    inner_y = y + 1
    inner_w = w - 2
    inner_h = h - 2
    a.rect(inner_x, inner_y, inner_w, inner_h, pal.bg_dark)

    fill_w = round(inner_w * clamped)
    if fill_w > 0:
        bar_color = pal.accent if fill_color is None else fill_color
        a.rect(inner_x, inner_y, fill_w, inner_h, bar_color)
        if show_specular and inner_h >= 2:
            spec_color = pal.accent_bright if fill_color is None else pal.border_highlight
            a.rect(inner_x, inner_y, fill_w, 1, spec_color)

    if segments > 1 and inner_w >= segments * 2:
        for idx in range(1, segments):
            div_x = inner_x + (inner_w * idx) // segments
            if inner_x < div_x < inner_x + inner_w:
                a.rect(div_x, inner_y, 1, inner_h, pal.border_outer)


def ui_badge(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    tone: UiBadgeTone = "neutral",
    pill: bool = True,
) -> None:
    """Draw a compact status badge or pill tag using semantic tone colors."""
    if w < 4 or h < 3:
        return

    tone_colors: dict[UiBadgeTone, tuple[int, int]] = {
        "neutral": (pal.bg_light, pal.text_muted),
        "info": (pal.bg_dark, pal.accent_bright),
        "success": (pal.bg_dark, pal.success),
        "warning": (pal.bg_dark, pal.warning),
        "danger": (pal.bg_dark, pal.danger),
    }
    fill_color, dot_color = tone_colors[tone]
    cut = 1 if (pill and w >= 6 and h >= 5) else 0

    a.rect(x, y, w, h, fill_color)
    _draw_chamfer_border(a, x, y, w, h, pal.border_outer, cut)
    if w >= 8 and h >= 5:
        a.put(x + 2, y + h // 2, dot_color)
        if w >= 12:
            a.rect(x + 4, y + h // 2, w - 7, 1, dot_color)
    _cut_rect_corners(a, x, y, w, h, cut)


def ui_icon_16(
    a: UiTarget,
    x: int,
    y: int,
    kind: UiIconKind,
    fg: int,
    *,
    bg: int | None = None,
    accent: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a crisp `16x16` pixel icon from the built-in semantic icon set."""
    grid = _ICON_GRIDS_16[kind]
    color_map: dict[str, int] = {
        "#": fg,
        "+": fg if accent is None else accent,
        "o": fg if outline is None else outline,
    }
    if bg is not None:
        color_map["."] = bg
    a.spr(grid, x, y, color_map)
