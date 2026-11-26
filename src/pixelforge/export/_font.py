"""Crisp deterministic 4x6 pixel bitmap font for diagnostic contact sheets."""

from __future__ import annotations

from typing import Final

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.font import get_font_definition, measure_bitmap_text, resolve_glyph

_FONT_4X6 = get_font_definition("4x6")

CELL_ADVANCE: Final[int] = _FONT_4X6.glyph_width + _FONT_4X6.default_letter_spacing
GLYPH_HEIGHT: Final[int] = _FONT_4X6.glyph_height


def measure_text(text: str, *, scale: int = 1) -> tuple[int, int]:
    """Return `(width, height)` in pixels for `text` rendered at integer `scale`."""
    return measure_bitmap_text(text, font="4x6", scale=scale)


def fill_rgba_rect(
    canvas: NDArray[np.uint8],
    x: int,
    y: int,
    w: int,
    h: int,
    rgb: tuple[int, int, int],
) -> None:
    """Fill a clipped opaque rectangle on an `(H, W, 4)` uint8 RGBA canvas."""
    ch, cw, _ = canvas.shape
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(cw, x + w)
    y1 = min(ch, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    canvas[y0:y1, x0:x1] = (rgb[0], rgb[1], rgb[2], 255)


def draw_bitmap_text(
    canvas: NDArray[np.uint8],
    text: str,
    x: int,
    y: int,
    rgb: tuple[int, int, int],
    *,
    scale: int = 1,
) -> None:
    """Render deterministic crisp bitmap text onto an `(H, W, 4)` uint8 RGBA canvas."""
    cx = x
    for ch in text:
        glyph = resolve_glyph(_FONT_4X6, ch)
        for row_idx, row_bits in enumerate(glyph):
            if row_bits == 0:
                continue
            for col_idx in range(_FONT_4X6.glyph_width):
                if (row_bits >> (3 - col_idx)) & 1:
                    fill_rgba_rect(
                        canvas,
                        cx + col_idx * scale,
                        y + row_idx * scale,
                        scale,
                        scale,
                        rgb,
                    )
        cx += CELL_ADVANCE * scale
