"""StylePack-agnostic UI pixel art primitives (panels, buttons, bars, badges, 16x16 icons)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields
from typing import Final, Literal

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.palette import PaletteLookup, hex_to_rgb
from pixelforge.core.types import MAX_PALETTE_INDEX, PaletteColor, StylePack

UiTarget = Asset[object] | Layer
UiStyleTarget = StylePack | Asset[object] | Layer

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

    @classmethod
    def from_style(
        cls,
        target: UiStyleTarget,
        **overrides: int | str,
    ) -> UiPalette:
        """Derive a deterministic `UiPalette` from a `StylePack`, `Asset`, or `Layer`."""
        style, lookup = _unpack_style_target(target)
        derived = _derive_ui_palette(style, lookup)
        if not overrides:
            return derived
        return _apply_ui_palette_overrides(derived, style, lookup, overrides)


_UI_PALETTE_FIELDS: Final[frozenset[str]] = frozenset(f.name for f in fields(UiPalette))


def _unpack_style_target(target: UiStyleTarget) -> tuple[StylePack, PaletteLookup]:
    if isinstance(target, StylePack):
        return target, PaletteLookup(target)
    if isinstance(target, Asset):
        pal = target.pal
        if not isinstance(pal, PaletteLookup):
            msg = f"Asset palette must be a PaletteLookup (got {type(pal).__name__})"
            raise TypeError(msg)
        return target.style, pal
    if target.style is None:
        msg = "Layer has no bound StylePack; pass Asset or StylePack to UiPalette.from_style()"
        raise ValueError(msg)
    return target.style, PaletteLookup(target.style)


def _hex_luminance(hex_color: str) -> float:
    r, g, b = hex_to_rgb(hex_color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _color_saturation(entry: PaletteColor) -> int:
    r, g, b = hex_to_rgb(entry.hex)
    return max(r, g, b) - min(r, g, b)


def _derive_surface_trio(
    style: StylePack,
    lookup: PaletteLookup,
    by_name: dict[str, PaletteColor],
    non_outline: list[PaletteColor],
) -> tuple[int, int, int]:
    """Resolve `(bg_dark, bg, bg_light)` from aliases, ramps, or luminance order."""
    if "SURFACE_D" in lookup and "SURFACE_M" in lookup and "SURFACE_L" in lookup:
        return lookup["SURFACE_D"], lookup["SURFACE_M"], lookup["SURFACE_L"]

    # Prefer neutral/surface/metal ramps with >= 3 non-outline, non-emissive steps.
    best_ramp: tuple[tuple[int, float, int], list[int]] | None = None
    for ramp_tokens in style.ramps.values():
        filtered = [
            by_name[tok]
            for tok in ramp_tokens
            if tok in by_name
            and by_name[tok].index != style.outline_index
            and "outline" not in by_name[tok].flags
            and "emissive" not in by_name[tok].flags
        ]
        if len(filtered) < 3:
            continue
        neutral_hits = sum(1 for e in filtered if "surface" in e.flags or "metal" in e.flags)
        mean_sat = sum(_color_saturation(e) for e in filtered) / len(filtered)
        score = (neutral_hits, -mean_sat, len(filtered))
        if best_ramp is None or score > best_ramp[0]:
            best_ramp = (score, [e.index for e in filtered[:3]])

    if best_ramp is not None:
        idxs = best_ramp[1]
        return idxs[0], idxs[1], idxs[2]

    pool = [e for e in non_outline if "emissive" not in e.flags]
    surface_pool = [e for e in pool if "surface" in e.flags]
    ordered = sorted(
        surface_pool if len(surface_pool) >= 3 else (pool or list(style.palette)),
        key=lambda e: (_hex_luminance(e.hex), e.index),
    )
    if len(ordered) == 1:
        idx = ordered[0].index
        return idx, idx, idx
    if len(ordered) == 2:
        return ordered[0].index, ordered[1].index, ordered[1].index
    return ordered[0].index, ordered[len(ordered) // 2].index, ordered[-1].index


def _derive_ui_palette(style: StylePack, lookup: PaletteLookup) -> UiPalette:
    """Derive all 13 `UiPalette` semantic indices deterministically from `StylePack`."""
    entries = sorted(style.palette, key=lambda e: e.index)
    by_index = {e.index: e for e in entries}
    by_name = {e.name: e for e in entries}
    non_outline = [
        e for e in entries if e.index != style.outline_index and "outline" not in e.flags
    ]
    non_emissive = [e for e in non_outline if "emissive" not in e.flags]

    indices_map = lookup.to_dict()
    border_outer = indices_map.get("INK", style.outline_index)
    bg_dark, bg, bg_light = _derive_surface_trio(style, lookup, by_name, non_outline)

    shadow_cands = sorted(
        (e for e in non_outline if "shadow" in e.flags),
        key=lambda e: (_hex_luminance(e.hex), e.index),
    )
    if shadow_cands:
        border_shadow = shadow_cands[0].index
    elif "BG_D" in lookup:
        border_shadow = lookup["BG_D"]
    else:
        border_shadow = border_outer

    bg_light_lum = _hex_luminance(by_index[bg_light].hex)
    hi_cands = [
        e
        for e in non_emissive
        if _hex_luminance(e.hex) > bg_light_lum + 1e-6
        and ("metal" in e.flags or "surface" in e.flags or "bright" in e.flags)
    ]
    if hi_cands:
        hi_cands.sort(
            key=lambda e: (
                0 if "metal" in e.flags else (1 if "surface" in e.flags else 2),
                _hex_luminance(e.hex),
                e.index,
            )
        )
        border_highlight = hi_cands[0].index
    else:
        border_highlight = bg_light

    bg_lum = _hex_luminance(by_index[bg].hex)
    text_pool = non_emissive or entries
    text_entry = max(
        text_pool,
        key=lambda e: (
            abs(_hex_luminance(e.hex) - bg_lum),
            1 if "bright" in e.flags else 0,
            _hex_luminance(e.hex),
            -e.index,
        ),
    )
    if abs(_hex_luminance(text_entry.hex) - bg_lum) < 40.0 and text_pool is not entries:
        text_entry = max(
            entries,
            key=lambda e: (
                abs(_hex_luminance(e.hex) - bg_lum),
                1 if "bright" in e.flags else 0,
                -e.index,
            ),
        )
    text = text_entry.index
    text_lum = _hex_luminance(text_entry.hex)

    mid_lum = 0.5 * (bg_lum + text_lum)
    muted_cands = [e for e in text_pool if e.index not in (bg, text)]
    if muted_cands:
        text_muted = min(
            muted_cands,
            key=lambda e: (
                abs(_hex_luminance(e.hex) - mid_lum) + 0.25 * _color_saturation(e),
                e.index,
            ),
        ).index
    else:
        text_muted = bg_light

    accent = _pick_accent(lookup, non_emissive, non_outline, bg, entries)
    accent_bright = _pick_accent_bright(
        lookup, by_index, non_emissive, non_outline, entries, accent, text
    )
    success, warning, danger = _pick_status_colors(
        non_emissive or non_outline or entries,
        fallback_pool=non_outline or entries,
        accent=accent,
        accent_bright=accent_bright,
    )

    return UiPalette(
        bg=bg,
        bg_dark=bg_dark,
        bg_light=bg_light,
        border_outer=border_outer,
        border_highlight=border_highlight,
        border_shadow=border_shadow,
        accent=accent,
        accent_bright=accent_bright,
        text=text,
        text_muted=text_muted,
        success=success,
        warning=warning,
        danger=danger,
    )


def _pick_accent(
    lookup: PaletteLookup,
    non_emissive: list[PaletteColor],
    non_outline: list[PaletteColor],
    bg: int,
    entries: list[PaletteColor],
) -> int:
    if "ACCENT_1" in lookup:
        return lookup["ACCENT_1"]
    accent_cands = [e for e in non_emissive if "accent" in e.flags and e.index != bg]
    if accent_cands:
        return max(
            accent_cands,
            key=lambda e: (_color_saturation(e), _hex_luminance(e.hex), -e.index),
        ).index
    pool = [e for e in (non_emissive or non_outline or entries) if e.index != bg] or entries
    return max(pool, key=lambda e: (_color_saturation(e), _hex_luminance(e.hex), -e.index)).index


def _pick_accent_bright(
    lookup: PaletteLookup,
    by_index: dict[int, PaletteColor],
    non_emissive: list[PaletteColor],
    non_outline: list[PaletteColor],
    entries: list[PaletteColor],
    accent: int,
    text: int,
) -> int:
    # INVARIANT: Prefer non-emissive bright accents for `accent_bright` (used as button hover
    # fills) so UI buttons do not bleed into WebGL2 emissive bloom masks.
    accent_lum = _hex_luminance(by_index[accent].hex)
    if (
        "ACCENT_2" in lookup
        and "emissive" not in by_index[lookup["ACCENT_2"]].flags
        and _hex_luminance(by_index[lookup["ACCENT_2"]].hex) >= accent_lum
    ):
        return lookup["ACCENT_2"]
    bright_non_emissive = [
        e for e in non_emissive if "accent" in e.flags and _hex_luminance(e.hex) > accent_lum + 1e-6
    ]
    if bright_non_emissive:
        return min(bright_non_emissive, key=lambda e: (_hex_luminance(e.hex), e.index)).index
    if "EMISSIVE_1" in lookup:
        return lookup["EMISSIVE_1"]
    emissive_cands = [e for e in non_outline if "emissive" in e.flags]
    if emissive_cands:
        return max(emissive_cands, key=lambda e: (_hex_luminance(e.hex), -e.index)).index
    bright_accent = [
        e for e in (non_outline or entries) if "bright" in e.flags and "accent" in e.flags
    ]
    if bright_accent:
        return max(bright_accent, key=lambda e: (_hex_luminance(e.hex), -e.index)).index
    return text


def _pick_status_colors(
    pool: list[PaletteColor],
    *,
    fallback_pool: list[PaletteColor],
    accent: int,
    accent_bright: int,
) -> tuple[int, int, int]:
    """Pick `(success, warning, danger)` by RGB channel dominance with safe fallbacks."""
    # INVARIANT: Prefer non-emissive semantic status colors and enforce a minimum
    # channel-dominance threshold so UI badges/icons avoid emissive bloom bleed.
    min_chroma = 12

    def _best_channel(
        candidates: list[PaletteColor],
        score_fn: Callable[[tuple[int, int, int]], int],
    ) -> tuple[PaletteColor, int]:
        best = max(
            candidates,
            key=lambda e: (score_fn(hex_to_rgb(e.hex)), _hex_luminance(e.hex), -e.index),
        )
        return best, score_fn(hex_to_rgb(best.hex))

    def _pick_one(
        score_fn: Callable[[tuple[int, int, int]], int],
        default_idx: int,
    ) -> int:
        best, score = _best_channel(pool, score_fn)
        if score > min_chroma:
            return best.index
        fb_best, fb_score = _best_channel(fallback_pool, score_fn)
        return fb_best.index if fb_score > min_chroma else default_idx

    success = _pick_one(lambda rgb: rgb[1] - max(rgb[0], rgb[2]), accent_bright)
    warning = _pick_one(lambda rgb: min(rgb[0], rgb[1]) - rgb[2], accent_bright)
    danger = _pick_one(lambda rgb: rgb[0] - max(rgb[1], rgb[2]), accent)
    return success, warning, danger


def _apply_ui_palette_overrides(
    base: UiPalette,
    style: StylePack,
    lookup: PaletteLookup,
    overrides: dict[str, int | str],
) -> UiPalette:
    unknown = sorted(set(overrides) - _UI_PALETTE_FIELDS)
    if unknown:
        msg = f"Unknown UiPalette field(s): {', '.join(unknown)}"
        raise TypeError(msg)

    valid_indices = {e.index for e in style.palette}
    resolved: dict[str, int] = {name: getattr(base, name) for name in _UI_PALETTE_FIELDS}
    for key, val in overrides.items():
        if isinstance(val, bool):
            msg = f"UiPalette override {key!r} must be int or str (got {type(val).__name__})"
            raise TypeError(msg)
        if isinstance(val, str):
            resolved[key] = lookup[val]
        else:
            if val < 0 or val > MAX_PALETTE_INDEX or val not in valid_indices:
                msg = f"UiPalette override {key!r} index {val} is not in style {style.id!r}"
                raise ValueError(msg)
            resolved[key] = val
    return UiPalette(**resolved)


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
