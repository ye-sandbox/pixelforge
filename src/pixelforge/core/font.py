"""Deterministic bitmap pixel fonts, text measurement, indexed drawing, and glyph atlases."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from pixelforge.core._font_glyphs import GLYPHS_4X6, GLYPHS_5X7, GLYPHS_6X8, GLYPHS_8X10
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import (
    BitmapFontPreset,
    BitmapFontSpec,
    BitmapGlyphMetrics,
)

DEFAULT_ASCII_CHARSET: Final[str] = "".join(chr(c) for c in range(32, 127))
PTBR_DIACRITICS_CHARSET: Final[str] = "áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ¡¿°ªº"
HUD_SYMBOLS_CHARSET: Final[str] = "♥★→←↑↓\u00d7•"
PTBR_HUD_CHARSET: Final[str] = DEFAULT_ASCII_CHARSET + PTBR_DIACRITICS_CHARSET + HUD_SYMBOLS_CHARSET

_DIGITS: Final[str] = "0123456789"
_OUTLINE_OFFSETS: Final[tuple[tuple[int, int], ...]] = ((-1, 0), (1, 0), (0, -1), (0, 1))


class SurfaceTarget(Protocol):
    """Structural protocol satisfied by `IndexedSurface`, `Asset`, and `Layer`."""

    @property
    def surface(self) -> IndexedSurface: ...


@dataclass(frozen=True)
class BitmapFontDefinition:
    """Immutable pixel-mask glyph set and default metrics for a built-in font preset."""

    preset: BitmapFontPreset
    glyph_width: int
    glyph_height: int
    default_line_height: int
    default_letter_spacing: int
    default_space_advance: int
    glyphs: Mapping[str, tuple[int, ...]]


_FONT_DEFINITIONS: Final[dict[BitmapFontPreset, BitmapFontDefinition]] = {
    "4x6": BitmapFontDefinition(
        preset="4x6",
        glyph_width=4,
        glyph_height=6,
        default_line_height=7,
        default_letter_spacing=1,
        default_space_advance=5,
        glyphs=GLYPHS_4X6,
    ),
    "5x7": BitmapFontDefinition(
        preset="5x7",
        glyph_width=5,
        glyph_height=7,
        default_line_height=9,
        default_letter_spacing=1,
        default_space_advance=5,
        glyphs=GLYPHS_5X7,
    ),
    "6x8": BitmapFontDefinition(
        preset="6x8",
        glyph_width=6,
        glyph_height=8,
        default_line_height=10,
        default_letter_spacing=1,
        default_space_advance=5,
        glyphs=GLYPHS_6X8,
    ),
    "8x10": BitmapFontDefinition(
        preset="8x10",
        glyph_width=8,
        glyph_height=10,
        default_line_height=12,
        default_letter_spacing=1,
        default_space_advance=6,
        glyphs=GLYPHS_8X10,
    ),
}


def get_font_definition(preset: BitmapFontPreset = "4x6") -> BitmapFontDefinition:
    """Return the built-in `BitmapFontDefinition` for `preset`."""
    definition = _FONT_DEFINITIONS.get(preset)
    if definition is None:
        msg = f"Unknown bitmap font preset {preset!r}"
        raise ValueError(msg)
    return definition


def resolve_glyph(definition: BitmapFontDefinition, ch: str) -> tuple[int, ...]:
    """Resolve a character's bitmask rows, falling back to uppercase or `'?'`."""
    glyph = definition.glyphs.get(ch)
    if glyph is not None:
        return glyph
    upper = definition.glyphs.get(ch.upper())
    if upper is not None:
        return upper
    return definition.glyphs["?"]


def _glyph_ink_bounds(glyph_rows: tuple[int, ...], glyph_width: int) -> tuple[int, int]:
    """Return `(min_col, ink_width)` for non-empty bitmask rows, or `(0, 0)`."""
    ink_mask = 0
    for row_bits in glyph_rows:
        ink_mask |= row_bits
    if ink_mask == 0:
        return (0, 0)

    msb_shift = glyph_width - 1
    min_col = glyph_width
    max_col = -1
    for col in range(glyph_width):
        if (ink_mask >> (msb_shift - col)) & 1:
            if col < min_col:
                min_col = col
            if col > max_col:
                max_col = col
    return (min_col, max_col - min_col + 1)


def _tabular_digit_width(definition: BitmapFontDefinition) -> int:
    """Return the uniform ink width shared by all decimal digits in `definition`."""
    return max(_glyph_ink_bounds(definition.glyphs[d], definition.glyph_width)[1] for d in _DIGITS)


def _resolve_glyph_layout(
    definition: BitmapFontDefinition,
    ch: str,
    *,
    letter_spacing: int,
    space_advance: int,
    proportional: bool,
    tabular_digits: bool,
    tabular_digit_width: int | None = None,
) -> tuple[tuple[int, ...], int, int, int, int]:
    """Return `(glyph_rows, trim_left, draw_width, x_offset, x_advance)` for `ch`."""
    glyph_rows = resolve_glyph(definition, ch)
    if not proportional:
        x_adv = space_advance if ch == " " else definition.glyph_width + letter_spacing
        return (glyph_rows, 0, definition.glyph_width, 0, x_adv)

    if ch == " ":
        return (glyph_rows, 0, 1, 0, space_advance)

    min_col, ink_width = _glyph_ink_bounds(glyph_rows, definition.glyph_width)
    if ink_width == 0:
        return (glyph_rows, 0, definition.glyph_width, 0, definition.glyph_width + letter_spacing)

    if tabular_digits and ch in _DIGITS:
        digit_w = (
            _tabular_digit_width(definition) if tabular_digit_width is None else tabular_digit_width
        )
        x_off = (digit_w - ink_width) // 2
        return (glyph_rows, min_col, ink_width, x_off, digit_w + letter_spacing)

    return (glyph_rows, min_col, ink_width, 0, ink_width + letter_spacing)


def make_bitmap_font_spec(
    preset: BitmapFontPreset = "4x6",
    *,
    charset: str = DEFAULT_ASCII_CHARSET,
    columns: int = 16,
    margin: int = 0,
    spacing: int = 1,
    letter_spacing: int | None = None,
    line_height: int | None = None,
    space_advance: int | None = None,
    proportional: bool = False,
    tabular_digits: bool = True,
) -> BitmapFontSpec:
    """Construct a deterministic `BitmapFontSpec` grid layout for `charset`."""
    if columns <= 0:
        msg = f"columns must be > 0, got {columns}"
        raise ValueError(msg)
    if not charset:
        msg = "charset must be non-empty"
        raise ValueError(msg)
    definition = get_font_definition(preset)
    resolved_letter_spacing = (
        definition.default_letter_spacing if letter_spacing is None else letter_spacing
    )
    resolved_line_height = definition.default_line_height if line_height is None else line_height
    resolved_space_advance = (
        definition.default_space_advance if space_advance is None else space_advance
    )
    tab_w = _tabular_digit_width(definition) if (proportional and tabular_digits) else None
    rows = math.ceil(len(charset) / columns)
    glyphs: list[BitmapGlyphMetrics] = []
    for idx, ch in enumerate(charset):
        col = idx % columns
        row = idx // columns
        gx = margin + col * (definition.glyph_width + spacing)
        gy = margin + row * (definition.glyph_height + spacing)
        _, _, draw_w, x_off, x_adv = _resolve_glyph_layout(
            definition,
            ch,
            letter_spacing=resolved_letter_spacing,
            space_advance=resolved_space_advance,
            proportional=proportional,
            tabular_digits=tabular_digits,
            tabular_digit_width=tab_w,
        )
        glyphs.append(
            BitmapGlyphMetrics(
                char=ch,
                x=gx,
                y=gy,
                width=draw_w,
                height=definition.glyph_height,
                x_advance=x_adv,
                x_offset=x_off,
            )
        )
    return BitmapFontSpec(
        preset=preset,
        glyph_width=definition.glyph_width,
        glyph_height=definition.glyph_height,
        line_height=resolved_line_height,
        letter_spacing=resolved_letter_spacing,
        space_advance=resolved_space_advance,
        columns=columns,
        rows=rows,
        margin=margin,
        spacing=spacing,
        charset=charset,
        glyphs=tuple(glyphs),
    )


def compute_font_atlas_size(spec: BitmapFontSpec) -> tuple[int, int]:
    """Return minimum `(width, height)` in 1x pixels required to fit `spec`."""
    width = 2 * spec.margin + spec.columns * spec.glyph_width + (spec.columns - 1) * spec.spacing
    height = 2 * spec.margin + spec.rows * spec.glyph_height + (spec.rows - 1) * spec.spacing
    return (width, height)


def measure_bitmap_text(
    text: str,
    *,
    font: BitmapFontPreset = "4x6",
    scale: int = 1,
    letter_spacing: int | None = None,
    line_height: int | None = None,
    proportional: bool = False,
    tabular_digits: bool = True,
) -> tuple[int, int]:
    """Return `(width, height)` in pixels for single- or multi-line `text`."""
    if scale <= 0:
        msg = f"scale must be > 0, got {scale}"
        raise ValueError(msg)
    definition = get_font_definition(font)
    spacing = definition.default_letter_spacing if letter_spacing is None else letter_spacing
    line_h = definition.default_line_height if line_height is None else line_height
    if not text:
        return (0, definition.glyph_height * scale)

    tab_w = _tabular_digit_width(definition) if (proportional and tabular_digits) else None
    lines = text.split("\n")
    max_w = 0
    for line in lines:
        if not line:
            continue
        if not proportional:
            line_w = len(line) * (definition.glyph_width + spacing) - spacing
        else:
            line_w = 0
            for idx, ch in enumerate(line):
                _, _, draw_w, x_off, x_adv = _resolve_glyph_layout(
                    definition,
                    ch,
                    letter_spacing=spacing,
                    space_advance=definition.default_space_advance,
                    proportional=True,
                    tabular_digits=tabular_digits,
                    tabular_digit_width=tab_w,
                )
                if idx < len(line) - 1 or ch == " ":
                    line_w += x_adv
                else:
                    line_w += max(x_off + draw_w, x_adv - spacing)
        if line_w > max_w:
            max_w = line_w
    total_h = (
        definition.glyph_height + (len(lines) - 1) * line_h
        if len(lines) > 1
        else definition.glyph_height
    )
    return (max_w * scale, total_h * scale)


def _draw_glyph_to_surface(
    surface: IndexedSurface,
    glyph_rows: tuple[int, ...],
    glyph_width: int,
    x: int,
    y: int,
    color: int,
    *,
    scale: int = 1,
    trim_left: int = 0,
    draw_width: int | None = None,
) -> None:
    msb_shift = glyph_width - 1
    end_col = glyph_width if draw_width is None else min(glyph_width, trim_left + draw_width)
    for row_idx, row_bits in enumerate(glyph_rows):
        if row_bits == 0:
            continue
        for col_idx in range(trim_left, end_col):
            if (row_bits >> (msb_shift - col_idx)) & 1:
                px = x + (col_idx - trim_left) * scale
                py = y + row_idx * scale
                if scale == 1:
                    surface.put(px, py, color)
                else:
                    surface.rect(px, py, scale, scale, color)


def _resolve_surface(target: SurfaceTarget | IndexedSurface) -> IndexedSurface:
    if isinstance(target, IndexedSurface):
        return target
    return target.surface


def draw_indexed_text(
    target: SurfaceTarget | IndexedSurface,
    text: str,
    x: int,
    y: int,
    color: int,
    *,
    font: BitmapFontPreset = "4x6",
    scale: int = 1,
    shadow: int | None = None,
    outline: int | None = None,
    letter_spacing: int | None = None,
    line_height: int | None = None,
    proportional: bool = False,
    tabular_digits: bool = True,
) -> None:
    """Render deterministic crisp bitmap text onto an `IndexedSurface`, `Asset`, or `Layer`."""
    if scale <= 0:
        msg = f"scale must be > 0, got {scale}"
        raise ValueError(msg)
    surface = _resolve_surface(target)
    definition = get_font_definition(font)
    spacing = definition.default_letter_spacing if letter_spacing is None else letter_spacing
    line_h = definition.default_line_height if line_height is None else line_height
    tab_w = _tabular_digit_width(definition) if (proportional and tabular_digits) else None

    passes: list[tuple[int, int, int]] = []
    if shadow is not None:
        passes.append((x + scale, y + scale, shadow))
    if outline is not None:
        for ox, oy in _OUTLINE_OFFSETS:
            passes.append((x + ox * scale, y + oy * scale, outline))
    passes.append((x, y, color))

    for start_x, start_y, pass_color in passes:
        cx = start_x
        cy = start_y
        for ch in text:
            if ch == "\n":
                cx = start_x
                cy += line_h * scale
                continue
            glyph_rows, trim_left, draw_w, x_off, x_adv = _resolve_glyph_layout(
                definition,
                ch,
                letter_spacing=spacing,
                space_advance=definition.default_space_advance,
                proportional=proportional,
                tabular_digits=tabular_digits,
                tabular_digit_width=tab_w,
            )
            if ch != " ":
                _draw_glyph_to_surface(
                    surface,
                    glyph_rows,
                    definition.glyph_width,
                    cx + x_off * scale,
                    cy,
                    pass_color,
                    scale=scale,
                    trim_left=trim_left,
                    draw_width=draw_w,
                )
            cx += x_adv * scale


def render_font_atlas(
    target: SurfaceTarget | IndexedSurface,
    spec: BitmapFontSpec,
    color: int,
    *,
    shadow: int | None = None,
    outline: int | None = None,
) -> None:
    """Render all glyphs defined in `spec` into their exact atlas cell coordinates."""
    surface = _resolve_surface(target)
    definition = get_font_definition(spec.preset)
    for glyph in spec.glyphs:
        if glyph.char == " ":
            continue
        glyph_rows = resolve_glyph(definition, glyph.char)
        is_trimmed = glyph.width < definition.glyph_width
        if is_trimmed:
            trim_left, _ = _glyph_ink_bounds(glyph_rows, definition.glyph_width)
            gx = glyph.x
            gy = glyph.y + glyph.y_offset
            draw_w: int | None = glyph.width
        else:
            trim_left = 0
            gx = glyph.x + glyph.x_offset
            gy = glyph.y + glyph.y_offset
            draw_w = None

        passes: list[tuple[int, int, int]] = []
        if shadow is not None:
            passes.append((gx + 1, gy + 1, shadow))
        if outline is not None:
            for ox, oy in _OUTLINE_OFFSETS:
                passes.append((gx + ox, gy + oy, outline))
        passes.append((gx, gy, color))

        for px, py, pass_color in passes:
            _draw_glyph_to_surface(
                surface,
                glyph_rows,
                definition.glyph_width,
                px,
                py,
                pass_color,
                trim_left=trim_left,
                draw_width=draw_w,
            )


def format_bmfont_fnt(
    spec: BitmapFontSpec,
    *,
    page_file: str,
    face: str | None = None,
    atlas_width: int | None = None,
    atlas_height: int | None = None,
    scale: int = 1,
) -> str:
    """Serialize `spec` into AngelCode BMFont text (`.fnt`) format."""
    if scale <= 0:
        msg = f"scale must be > 0, got {scale}"
        raise ValueError(msg)
    base_w, base_h = compute_font_atlas_size(spec)
    scale_w = (atlas_width if atlas_width is not None else base_w) * scale
    scale_h = (atlas_height if atlas_height is not None else base_h) * scale
    font_face = face or f"pixelforge-{spec.preset}"
    is_bold = 1 if spec.preset in ("6x8", "8x10") else 0
    lines = [
        (
            f'info face="{font_face}" size={spec.glyph_height * scale} bold={is_bold} '
            f'italic=0 charset="" unicode=1 stretchH=100 smooth=0 aa=0 '
            f"padding=0,0,0,0 spacing={spec.spacing * scale},{spec.spacing * scale}"
        ),
        (
            f"common lineHeight={spec.line_height * scale} base={spec.glyph_height * scale} "
            f"scaleW={scale_w} scaleH={scale_h} pages=1 packed=0"
        ),
        f'page id=0 file="{page_file}"',
        f"chars count={len(spec.glyphs)}",
    ]
    for g in spec.glyphs:
        lines.append(
            f"char id={ord(g.char)} x={g.x * scale} y={g.y * scale} "
            f"width={g.width * scale} height={g.height * scale} "
            f"xoffset={g.x_offset * scale} yoffset={g.y_offset * scale} "
            f"xadvance={g.x_advance * scale} page=0 chnl=15"
        )
    return "\n".join(lines) + "\n"
