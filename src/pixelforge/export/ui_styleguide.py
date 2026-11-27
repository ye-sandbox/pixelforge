"""Comparative UI Styleguide `.contact.png` generator for cohesive UI theme kits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.builder import Asset
from pixelforge.core.font import BitmapFontPreset
from pixelforge.core.prefabs.ui import (
    UiBadgeTone,
    UiButtonState,
    UiCursorKind,
    UiPalette,
    UiSlotState,
    UiThemeConfig,
    UiThemeName,
    get_ui_theme_config,
    list_icons,
    ui_badge,
    ui_button,
    ui_checkbox,
    ui_cursor,
    ui_dialogue_box,
    ui_icon,
    ui_panel,
    ui_progress_bar,
    ui_slider,
    ui_slot,
    ui_toggle,
)
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import AssetSpec, StylePack
from pixelforge.export._canvas import Rgb, composite_rgba, draw_checkerboard
from pixelforge.export._font import draw_bitmap_text, fill_rgba_rect
from pixelforge.export.png import rgba_to_png, surface_to_rgba

_BG_MAIN: Final[Rgb] = (18, 22, 29)
_BG_HEADER: Final[Rgb] = (28, 34, 45)
_BG_CELL: Final[Rgb] = (22, 27, 36)
_BORDER_SUBTLE: Final[Rgb] = (48, 56, 70)
_TEXT_LIGHT: Final[Rgb] = (230, 237, 243)
_TEXT_MUTED: Final[Rgb] = (139, 148, 158)
_HOTSPOT_COLOR: Final[Rgb] = (255, 123, 114)
_CHECK_DARK_A: Final[Rgb] = (13, 17, 23)
_CHECK_DARK_B: Final[Rgb] = (24, 30, 40)

UI_STYLEGUIDE_SECTIONS: Final[tuple[str, ...]] = (
    "panels",
    "buttons",
    "bars",
    "slots",
    "badges",
    "cursors",
    "icons",
    "fonts",
)


@dataclass(frozen=True)
class UiStyleguideOptions:
    """Configuration options for `generate_ui_styleguide_sheet`."""

    theme: UiThemeName = "pixel_chamfer"
    zoom: int = 2
    variant: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class UiStyleguideResult:
    """Generated UI Styleguide RGBA buffer, PNG bytes, and metadata."""

    width: int
    height: int
    rgba: NDArray[np.uint8]
    png: bytes
    theme: UiThemeName
    style_id: str
    sections: tuple[str, ...]


def _make_asset(style: StylePack, w: int, h: int, name: str) -> Asset[object]:
    spec = AssetSpec(
        id=f"_styleguide_{name}",
        style_id=style.id,
        perspective="top-down",
        width=w,
        height=h,
        states=("idle",),
    )
    return Asset(spec, style)


def _render_panels_section(style: StylePack, pal: UiPalette, cfg: UiThemeConfig) -> IndexedSurface:
    a = _make_asset(style, 156, 44, "panels")
    ui_panel(
        a,
        2,
        2,
        46,
        38,
        pal,
        beveled=cfg.beveled,
        corner_cut=cfg.corner_cut,
        recessed=cfg.recessed_panel,
    )
    ui_panel(
        a,
        52,
        2,
        48,
        38,
        pal,
        title_bar_h=cfg.title_bar_h,
        beveled=cfg.beveled,
        corner_cut=cfg.corner_cut,
        recessed=cfg.recessed_panel,
    )
    ui_dialogue_box(
        a,
        104,
        2,
        48,
        36,
        pal,
        tail="bottom_left",
        corner_cut=cfg.corner_cut,
    )
    return a.surface


def _render_buttons_section(style: StylePack, pal: UiPalette, cfg: UiThemeConfig) -> IndexedSurface:
    a = _make_asset(style, 196, 20, "buttons")
    states: tuple[UiButtonState, ...] = ("normal", "hover", "pressed", "disabled")
    for idx, st in enumerate(states):
        bx = 2 + idx * 38
        ui_button(a, bx, 3, 34, 14, pal, state=st, corner_cut=cfg.corner_cut)
        label = st[:4].upper()
        fg = pal.text_muted if st == "disabled" else pal.text
        a.text(label, bx + 5, 7, fg, font="4x6")
    ui_button(a, 154, 3, 38, 14, pal, state="normal", accent=True, corner_cut=cfg.corner_cut)
    a.text("ACT", 164, 7, pal.text, font="4x6")
    return a.surface


def _render_bars_section(style: StylePack, pal: UiPalette, cfg: UiThemeConfig) -> IndexedSurface:
    a = _make_asset(style, 176, 26, "bars")
    ui_progress_bar(
        a,
        2,
        2,
        64,
        9,
        pal,
        value=0.72,
        segments=cfg.bar_segments,
        show_specular=cfg.bar_specular,
    )
    ui_progress_bar(
        a,
        2,
        14,
        64,
        9,
        pal,
        value=0.40,
        fill_color=pal.success,
        segments=max(4, cfg.bar_segments),
        show_specular=cfg.bar_specular,
    )
    ui_slider(a, 72, 2, 52, 9, pal, value=0.65)
    ui_toggle(a, 72, 14, 20, 9, pal, checked=False)
    ui_toggle(a, 96, 14, 20, 9, pal, checked=True)
    ui_checkbox(a, 130, 3, 9, pal, checked=False)
    ui_checkbox(a, 144, 3, 9, pal, checked=True)
    ui_checkbox(a, 158, 3, 9, pal, checked=True, disabled=True)
    return a.surface


def _render_slots_section(style: StylePack, pal: UiPalette, cfg: UiThemeConfig) -> IndexedSurface:
    a = _make_asset(style, 100, 24, "slots")
    states: tuple[UiSlotState, ...] = ("empty", "hover", "selected", "locked")
    for idx, st in enumerate(states):
        ui_slot(a, 2 + idx * 24, 2, 20, 20, pal, state=st, corner_cut=cfg.corner_cut)
    return a.surface


def _render_badges_section(style: StylePack, pal: UiPalette, cfg: UiThemeConfig) -> IndexedSurface:
    a = _make_asset(style, 140, 16, "badges")
    tones: tuple[UiBadgeTone, ...] = ("neutral", "info", "success", "warning", "danger")
    for idx, tone in enumerate(tones):
        ui_badge(a, 2 + idx * 27, 3, 24, 10, pal, tone=tone, pill=cfg.badge_pill)
    return a.surface


def _render_cursors_section(
    style: StylePack,
    pal: UiPalette,
) -> tuple[IndexedSurface, list[tuple[int, int]]]:
    a = _make_asset(style, 126, 20, "cursors")
    kinds: tuple[UiCursorKind, ...] = (
        "pointer",
        "hand",
        "crosshair",
        "resize_h",
        "resize_v",
        "text",
    )
    hotspots: list[tuple[int, int]] = []
    for idx, kind in enumerate(kinds):
        hx, hy = ui_cursor(a, 2 + idx * 20, 2, kind, pal, emit_hotspot_anchor=False)
        hotspots.append((hx, hy))
    return a.surface, hotspots


def _render_icons_section(style: StylePack, pal: UiPalette, cfg: UiThemeConfig) -> IndexedSurface:
    a = _make_asset(style, 172, 22, "icons")
    cx = 2
    for size in (8, 12, 16):
        names = list_icons(pack=cfg.icon_pack, size=size)[:3]
        for icon_name in names:
            ui_icon(
                a,
                cx,
                2 + (16 - size) // 2,
                icon_name,
                pal.text,
                size=size,
                pack=cfg.icon_pack,
                accent=pal.accent_bright,
                outline=pal.border_outer,
            )
            cx += size + 4
        cx += 4
    return a.surface


def _render_fonts_section(style: StylePack, pal: UiPalette, cfg: UiThemeConfig) -> IndexedSurface:
    a = _make_asset(style, 210, 52, "fonts")
    ui_panel(
        a,
        0,
        0,
        210,
        52,
        pal,
        beveled=cfg.beveled,
        corner_cut=cfg.corner_cut,
        recessed=cfg.recessed_panel,
    )
    samples: tuple[tuple[BitmapFontPreset, str, int], ...] = (
        ("4x6", "4x6: Olá! Ação 0123", 4),
        ("5x7", "5x7: Olá! Ação 0123", 13),
        ("6x8", "6x8: Olá! Ação 0123", 23),
        ("8x10", "8x10: Olá! Ação", 35),
    )
    for preset, text, sy in samples:
        fg = pal.accent_bright if preset == cfg.font_preset else pal.text
        a.text(text, 6, sy, fg, font=preset)
    return a.surface


def _upscale_rgba(rgba: NDArray[np.uint8], zoom: int) -> NDArray[np.uint8]:
    if zoom <= 1:
        return rgba
    return np.repeat(np.repeat(rgba, zoom, axis=0), zoom, axis=1)


def generate_ui_styleguide_sheet(
    style: StylePack,
    options: UiStyleguideOptions | None = None,
) -> UiStyleguideResult:
    """Render a comparative UI Styleguide `.contact.png` for a theme and `StylePack`."""
    opts = options or UiStyleguideOptions()
    if opts.zoom < 1:
        msg = f"Styleguide zoom must be >= 1 (got {opts.zoom})"
        raise ValueError(msg)
    cfg = get_ui_theme_config(opts.theme)
    pal = UiPalette.from_style(style)

    cursors_surf, hotspots = _render_cursors_section(style, pal)
    cards: list[tuple[str, IndexedSurface, list[tuple[int, int]]]] = [
        ("PANELS & DIALOGUE", _render_panels_section(style, pal, cfg), []),
        ("BUTTON STATES", _render_buttons_section(style, pal, cfg), []),
        ("BARS, SLIDERS & TOGGLES", _render_bars_section(style, pal, cfg), []),
        ("SLOTS", _render_slots_section(style, pal, cfg), []),
        ("BADGES", _render_badges_section(style, pal, cfg), []),
        ("CURSORS (HOTSPOTS)", cursors_surf, hotspots),
        (f"ICONS ({cfg.icon_pack.upper()} 8/12/16)", _render_icons_section(style, pal, cfg), []),
        (f"BITMAP FONTS (DEFAULT {cfg.font_preset})", _render_fonts_section(style, pal, cfg), []),
    ]

    pad = 12
    header_h = 28
    cell_pad = 8
    label_h = 12
    gap = 10
    col_w = max(surf.width * opts.zoom + cell_pad * 2 for _, surf, _ in cards)
    # Two-column grid layout for compact visual comparison.
    rows: list[tuple[int, int]] = [(0, 1), (2, 3), (4, 5), (6, 7)]
    row_heights = [
        max(cards[i][1].height, cards[j][1].height) * opts.zoom + label_h + cell_pad * 2
        for i, j in rows
    ]
    canvas_w = pad * 2 + col_w * 2 + gap
    canvas_h = header_h + pad + sum(row_heights) + gap * (len(rows) - 1) + pad

    canvas = np.empty((canvas_h, canvas_w, 4), dtype=np.uint8)
    canvas[:, :] = (*_BG_MAIN, 255)
    fill_rgba_rect(canvas, 0, 0, canvas_w, header_h, _BG_HEADER)
    fill_rgba_rect(canvas, 0, header_h - 1, canvas_w, 1, _BORDER_SUBTLE)

    title_text = opts.title or f"UI STYLEGUIDE | THEME={cfg.name} | STYLE={style.id}"
    draw_bitmap_text(canvas, title_text, pad, 7, _TEXT_LIGHT, scale=1)
    draw_bitmap_text(
        canvas,
        f"ZOOM={opts.zoom}X | FONT={cfg.font_preset} | ICONS={cfg.icon_pack}",
        pad,
        16,
        _TEXT_MUTED,
        scale=1,
    )

    y_cursor = header_h + pad
    for row_idx, (left_idx, right_idx) in enumerate(rows):
        row_h = row_heights[row_idx]
        for col_pos, card_idx in enumerate((left_idx, right_idx)):
            label, surf, card_hotspots = cards[card_idx]
            cx = pad + col_pos * (col_w + gap)
            fill_rgba_rect(canvas, cx, y_cursor, col_w, row_h, _BORDER_SUBTLE)
            fill_rgba_rect(canvas, cx + 1, y_cursor + 1, col_w - 2, row_h - 2, _BG_CELL)
            draw_bitmap_text(canvas, label, cx + cell_pad, y_cursor + 5, _TEXT_LIGHT, scale=1)

            draw_x = cx + cell_pad
            draw_y = y_cursor + label_h + cell_pad
            sw_z = surf.width * opts.zoom
            sh_z = surf.height * opts.zoom
            draw_checkerboard(canvas, draw_x, draw_y, sw_z, sh_z, _CHECK_DARK_A, _CHECK_DARK_B)
            rgba = surface_to_rgba(surf, style, variant=opts.variant)
            composite_rgba(canvas, _upscale_rgba(rgba, opts.zoom), draw_x, draw_y)
            for hx, hy in card_hotspots:
                px = draw_x + hx * opts.zoom
                py = draw_y + hy * opts.zoom
                fill_rgba_rect(canvas, px, py, opts.zoom, opts.zoom, _HOTSPOT_COLOR)
        y_cursor += row_h + gap

    return UiStyleguideResult(
        width=canvas_w,
        height=canvas_h,
        rgba=canvas,
        png=rgba_to_png(canvas),
        theme=cfg.name,
        style_id=style.id,
        sections=UI_STYLEGUIDE_SECTIONS,
    )
