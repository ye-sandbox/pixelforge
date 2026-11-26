"""Deterministic bitmap pixel fonts, text measurement, indexed drawing, and glyph atlases."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import (
    BitmapFontPreset,
    BitmapFontSpec,
    BitmapGlyphMetrics,
)

DEFAULT_ASCII_CHARSET: Final[str] = "".join(chr(c) for c in range(32, 127))


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


# Each glyph is 6 rows of 4-bit bitmasks (MSB = leftmost pixel of the 4px cell).
_GLYPHS_4X6: Final[dict[str, tuple[int, int, int, int, int, int]]] = {
    " ": (0, 0, 0, 0, 0, 0),
    "!": (0b0100, 0b0100, 0b0100, 0b0100, 0b0000, 0b0100),
    '"': (0b1010, 0b1010, 0b0000, 0b0000, 0b0000, 0b0000),
    "#": (0b1010, 0b1111, 0b1010, 0b1111, 0b1010, 0b0000),
    "$": (0b0111, 0b1100, 0b0110, 0b0011, 0b1110, 0b0100),
    "%": (0b1001, 0b0010, 0b0100, 0b1001, 0b0000, 0b0000),
    "&": (0b0110, 0b1001, 0b0110, 0b1010, 0b0101, 0b0000),
    "'": (0b0100, 0b0100, 0b0000, 0b0000, 0b0000, 0b0000),
    "(": (0b0010, 0b0100, 0b0100, 0b0100, 0b0010, 0b0000),
    ")": (0b0100, 0b0010, 0b0010, 0b0010, 0b0100, 0b0000),
    "*": (0b0000, 0b1010, 0b0100, 0b1010, 0b0000, 0b0000),
    "+": (0b0000, 0b0100, 0b1110, 0b0100, 0b0000, 0b0000),
    ",": (0b0000, 0b0000, 0b0000, 0b0100, 0b0100, 0b1000),
    "-": (0b0000, 0b0000, 0b1110, 0b0000, 0b0000, 0b0000),
    ".": (0b0000, 0b0000, 0b0000, 0b0000, 0b0100, 0b0000),
    "/": (0b0001, 0b0010, 0b0100, 0b1000, 0b0000, 0b0000),
    "0": (0b0110, 0b1001, 0b1001, 0b1001, 0b0110, 0b0000),
    "1": (0b0100, 0b1100, 0b0100, 0b0100, 0b1110, 0b0000),
    "2": (0b1110, 0b0001, 0b0110, 0b1000, 0b1111, 0b0000),
    "3": (0b1110, 0b0001, 0b0110, 0b0001, 0b1110, 0b0000),
    "4": (0b1001, 0b1001, 0b1111, 0b0001, 0b0001, 0b0000),
    "5": (0b1111, 0b1000, 0b1110, 0b0001, 0b1110, 0b0000),
    "6": (0b0111, 0b1000, 0b1110, 0b1001, 0b0110, 0b0000),
    "7": (0b1111, 0b0001, 0b0010, 0b0100, 0b0100, 0b0000),
    "8": (0b0110, 0b1001, 0b0110, 0b1001, 0b0110, 0b0000),
    "9": (0b0110, 0b1001, 0b0111, 0b0001, 0b1110, 0b0000),
    ":": (0b0000, 0b0100, 0b0000, 0b0100, 0b0000, 0b0000),
    ";": (0b0000, 0b0100, 0b0000, 0b0100, 0b0100, 0b1000),
    "<": (0b0010, 0b0100, 0b1000, 0b0100, 0b0010, 0b0000),
    "=": (0b0000, 0b1110, 0b0000, 0b1110, 0b0000, 0b0000),
    ">": (0b1000, 0b0100, 0b0010, 0b0100, 0b1000, 0b0000),
    "?": (0b0110, 0b1001, 0b0010, 0b0000, 0b0010, 0b0000),
    "@": (0b0110, 0b1011, 0b1011, 0b1000, 0b0111, 0b0000),
    "A": (0b0110, 0b1001, 0b1111, 0b1001, 0b1001, 0b0000),
    "B": (0b1110, 0b1001, 0b1110, 0b1001, 0b1110, 0b0000),
    "C": (0b0111, 0b1000, 0b1000, 0b1000, 0b0111, 0b0000),
    "D": (0b1110, 0b1001, 0b1001, 0b1001, 0b1110, 0b0000),
    "E": (0b1111, 0b1000, 0b1110, 0b1000, 0b1111, 0b0000),
    "F": (0b1111, 0b1000, 0b1110, 0b1000, 0b1000, 0b0000),
    "G": (0b0111, 0b1000, 0b1011, 0b1001, 0b0111, 0b0000),
    "H": (0b1001, 0b1001, 0b1111, 0b1001, 0b1001, 0b0000),
    "I": (0b1110, 0b0100, 0b0100, 0b0100, 0b1110, 0b0000),
    "J": (0b0001, 0b0001, 0b0001, 0b1001, 0b0110, 0b0000),
    "K": (0b1001, 0b1010, 0b1100, 0b1010, 0b1001, 0b0000),
    "L": (0b1000, 0b1000, 0b1000, 0b1000, 0b1111, 0b0000),
    "M": (0b1001, 0b1111, 0b1111, 0b1001, 0b1001, 0b0000),
    "N": (0b1001, 0b1101, 0b1011, 0b1001, 0b1001, 0b0000),
    "O": (0b0110, 0b1001, 0b1001, 0b1001, 0b0110, 0b0000),
    "P": (0b1110, 0b1001, 0b1110, 0b1000, 0b1000, 0b0000),
    "Q": (0b0110, 0b1001, 0b1001, 0b1011, 0b0111, 0b0000),
    "R": (0b1110, 0b1001, 0b1110, 0b1010, 0b1001, 0b0000),
    "S": (0b0111, 0b1000, 0b0110, 0b0001, 0b1110, 0b0000),
    "T": (0b1111, 0b0100, 0b0100, 0b0100, 0b0100, 0b0000),
    "U": (0b1001, 0b1001, 0b1001, 0b1001, 0b0110, 0b0000),
    "V": (0b1001, 0b1001, 0b1001, 0b0110, 0b0110, 0b0000),
    "W": (0b1001, 0b1001, 0b1111, 0b1111, 0b1001, 0b0000),
    "X": (0b1001, 0b0110, 0b0110, 0b0110, 0b1001, 0b0000),
    "Y": (0b1001, 0b1001, 0b0110, 0b0100, 0b0100, 0b0000),
    "Z": (0b1111, 0b0010, 0b0100, 0b1000, 0b1111, 0b0000),
    "[": (0b1100, 0b1000, 0b1000, 0b1000, 0b1100, 0b0000),
    "\\": (0b1000, 0b0100, 0b0010, 0b0001, 0b0000, 0b0000),
    "]": (0b0110, 0b0010, 0b0010, 0b0010, 0b0110, 0b0000),
    "^": (0b0100, 0b1010, 0b0000, 0b0000, 0b0000, 0b0000),
    "_": (0b0000, 0b0000, 0b0000, 0b0000, 0b1111, 0b0000),
    "`": (0b1000, 0b0100, 0b0000, 0b0000, 0b0000, 0b0000),
    "a": (0b0000, 0b0110, 0b0001, 0b0111, 0b0111, 0b0000),
    "b": (0b1000, 0b1110, 0b1001, 0b1001, 0b1110, 0b0000),
    "c": (0b0000, 0b0111, 0b1000, 0b1000, 0b0111, 0b0000),
    "d": (0b0001, 0b0111, 0b1001, 0b1001, 0b0111, 0b0000),
    "e": (0b0000, 0b0110, 0b1111, 0b1000, 0b0111, 0b0000),
    "f": (0b0011, 0b0100, 0b1110, 0b0100, 0b0100, 0b0000),
    "g": (0b0000, 0b0111, 0b1001, 0b0111, 0b0001, 0b1110),
    "h": (0b1000, 0b1110, 0b1001, 0b1001, 0b1001, 0b0000),
    "i": (0b0100, 0b0000, 0b0100, 0b0100, 0b0100, 0b0000),
    "j": (0b0010, 0b0000, 0b0010, 0b0010, 0b1010, 0b0100),
    "k": (0b1000, 0b1010, 0b1100, 0b1010, 0b1001, 0b0000),
    "l": (0b1100, 0b0100, 0b0100, 0b0100, 0b1110, 0b0000),
    "m": (0b0000, 0b1110, 0b1111, 0b1011, 0b1001, 0b0000),
    "n": (0b0000, 0b1110, 0b1001, 0b1001, 0b1001, 0b0000),
    "o": (0b0000, 0b0110, 0b1001, 0b1001, 0b0110, 0b0000),
    "p": (0b0000, 0b1110, 0b1001, 0b1110, 0b1000, 0b1000),
    "q": (0b0000, 0b0111, 0b1001, 0b0111, 0b0001, 0b0001),
    "r": (0b0000, 0b1011, 0b1100, 0b1000, 0b1000, 0b0000),
    "s": (0b0000, 0b0111, 0b1100, 0b0011, 0b1110, 0b0000),
    "t": (0b0100, 0b1110, 0b0100, 0b0100, 0b0011, 0b0000),
    "u": (0b0000, 0b1001, 0b1001, 0b1001, 0b0111, 0b0000),
    "v": (0b0000, 0b1001, 0b1001, 0b0110, 0b0110, 0b0000),
    "w": (0b0000, 0b1001, 0b1011, 0b1111, 0b0110, 0b0000),
    "x": (0b0000, 0b1001, 0b0110, 0b0110, 0b1001, 0b0000),
    "y": (0b0000, 0b1001, 0b1001, 0b0111, 0b0001, 0b1110),
    "z": (0b0000, 0b1111, 0b0010, 0b0100, 0b1111, 0b0000),
    "{": (0b0010, 0b0100, 0b1100, 0b0100, 0b0010, 0b0000),
    "|": (0b0100, 0b0100, 0b0100, 0b0100, 0b0100, 0b0000),
    "}": (0b1000, 0b0100, 0b0110, 0b0100, 0b1000, 0b0000),
    "~": (0b0000, 0b0101, 0b1010, 0b0000, 0b0000, 0b0000),
}

# Each glyph is 7 rows of 5-bit bitmasks (MSB = leftmost pixel of the 5px cell).
_GLYPHS_5X7: Final[dict[str, tuple[int, int, int, int, int, int, int]]] = {
    " ": (0, 0, 0, 0, 0, 0, 0),
    "!": (0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00000, 0b00100),
    '"': (0b01010, 0b01010, 0b01010, 0b00000, 0b00000, 0b00000, 0b00000),
    "#": (0b01010, 0b01010, 0b11111, 0b01010, 0b11111, 0b01010, 0b01010),
    "$": (0b00100, 0b01111, 0b10100, 0b01110, 0b00101, 0b11110, 0b00100),
    "%": (0b11000, 0b11001, 0b00010, 0b00100, 0b01000, 0b10011, 0b00011),
    "&": (0b01100, 0b10010, 0b10100, 0b01000, 0b10101, 0b10010, 0b01101),
    "'": (0b00100, 0b00100, 0b01000, 0b00000, 0b00000, 0b00000, 0b00000),
    "(": (0b00010, 0b00100, 0b01000, 0b01000, 0b01000, 0b00100, 0b00010),
    ")": (0b01000, 0b00100, 0b00010, 0b00010, 0b00010, 0b00100, 0b01000),
    "*": (0b00000, 0b00100, 0b10101, 0b01110, 0b10101, 0b00100, 0b00000),
    "+": (0b00000, 0b00100, 0b00100, 0b11111, 0b00100, 0b00100, 0b00000),
    ",": (0b00000, 0b00000, 0b00000, 0b00000, 0b00100, 0b00100, 0b01000),
    "-": (0b00000, 0b00000, 0b00000, 0b11111, 0b00000, 0b00000, 0b00000),
    ".": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00100, 0b00000),
    "/": (0b00001, 0b00010, 0b00010, 0b00100, 0b01000, 0b01000, 0b10000),
    "0": (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110),
    "1": (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "2": (0b01110, 0b10001, 0b00001, 0b00110, 0b01000, 0b10000, 0b11111),
    "3": (0b11111, 0b00010, 0b00100, 0b00110, 0b00001, 0b10001, 0b01110),
    "4": (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010),
    "5": (0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110),
    "6": (0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110),
    "7": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000),
    "8": (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110),
    "9": (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100),
    ":": (0b00000, 0b00100, 0b00100, 0b00000, 0b00100, 0b00100, 0b00000),
    ";": (0b00000, 0b00100, 0b00100, 0b00000, 0b00100, 0b00100, 0b01000),
    "<": (0b00010, 0b00100, 0b01000, 0b10000, 0b01000, 0b00100, 0b00010),
    "=": (0b00000, 0b00000, 0b11111, 0b00000, 0b11111, 0b00000, 0b00000),
    ">": (0b01000, 0b00100, 0b00010, 0b00001, 0b00010, 0b00100, 0b01000),
    "?": (0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b00000, 0b00100),
    "@": (0b01110, 0b10001, 0b10111, 0b10101, 0b10111, 0b10000, 0b01110),
    "A": (0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "B": (0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110),
    "C": (0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110),
    "D": (0b11100, 0b10010, 0b10001, 0b10001, 0b10001, 0b10010, 0b11100),
    "E": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111),
    "F": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000),
    "G": (0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110),
    "H": (0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "I": (0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "J": (0b00111, 0b00010, 0b00010, 0b00010, 0b10010, 0b10010, 0b01100),
    "K": (0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001),
    "L": (0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111),
    "M": (0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001),
    "N": (0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001),
    "O": (0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "P": (0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000),
    "Q": (0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101),
    "R": (0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001),
    "S": (0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110),
    "T": (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    "U": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "V": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    "W": (0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b11011, 0b10001),
    "X": (0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001),
    "Y": (0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100),
    "Z": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111),
    "[": (0b01110, 0b01000, 0b01000, 0b01000, 0b01000, 0b01000, 0b01110),
    "\\": (0b10000, 0b01000, 0b01000, 0b00100, 0b00010, 0b00010, 0b00001),
    "]": (0b01110, 0b00010, 0b00010, 0b00010, 0b00010, 0b00010, 0b01110),
    "^": (0b00100, 0b01010, 0b10001, 0b00000, 0b00000, 0b00000, 0b00000),
    "_": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b11111),
    "`": (0b01000, 0b00100, 0b00010, 0b00000, 0b00000, 0b00000, 0b00000),
    "a": (0b00000, 0b00000, 0b01110, 0b00001, 0b01111, 0b10001, 0b01111),
    "b": (0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b10001, 0b11110),
    "c": (0b00000, 0b00000, 0b01110, 0b10000, 0b10000, 0b10001, 0b01110),
    "d": (0b00001, 0b00001, 0b01111, 0b10001, 0b10001, 0b10001, 0b01111),
    "e": (0b00000, 0b00000, 0b01110, 0b10001, 0b11111, 0b10000, 0b01110),
    "f": (0b00110, 0b01001, 0b01000, 0b11100, 0b01000, 0b01000, 0b01000),
    "g": (0b00000, 0b01111, 0b10001, 0b01111, 0b00001, 0b10001, 0b01110),
    "h": (0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b10001, 0b10001),
    "i": (0b00100, 0b00000, 0b01100, 0b00100, 0b00100, 0b00100, 0b01110),
    "j": (0b00010, 0b00000, 0b00110, 0b00010, 0b00010, 0b10010, 0b01100),
    "k": (0b10000, 0b10000, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010),
    "l": (0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "m": (0b00000, 0b00000, 0b11010, 0b10101, 0b10101, 0b10101, 0b10001),
    "n": (0b00000, 0b00000, 0b11110, 0b10001, 0b10001, 0b10001, 0b10001),
    "o": (0b00000, 0b00000, 0b01110, 0b10001, 0b10001, 0b10001, 0b01110),
    "p": (0b00000, 0b11110, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000),
    "q": (0b00000, 0b01111, 0b10001, 0b01111, 0b00001, 0b00001, 0b00001),
    "r": (0b00000, 0b00000, 0b10110, 0b11001, 0b10000, 0b10000, 0b10000),
    "s": (0b00000, 0b00000, 0b01111, 0b10000, 0b01110, 0b00001, 0b11110),
    "t": (0b01000, 0b01000, 0b11100, 0b01000, 0b01000, 0b01001, 0b00110),
    "u": (0b00000, 0b00000, 0b10001, 0b10001, 0b10001, 0b10011, 0b01101),
    "v": (0b00000, 0b00000, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    "w": (0b00000, 0b00000, 0b10001, 0b10001, 0b10101, 0b10101, 0b01010),
    "x": (0b00000, 0b00000, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001),
    "y": (0b00000, 0b10001, 0b10001, 0b01111, 0b00001, 0b10001, 0b01110),
    "z": (0b00000, 0b00000, 0b11111, 0b00010, 0b00100, 0b01000, 0b11111),
    "{": (0b00010, 0b00100, 0b00100, 0b01000, 0b00100, 0b00100, 0b00010),
    "|": (0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    "}": (0b01000, 0b00100, 0b00100, 0b00010, 0b00100, 0b00100, 0b01000),
    "~": (0b00000, 0b01001, 0b10110, 0b00000, 0b00000, 0b00000, 0b00000),
}

_FONT_DEFINITIONS: Final[dict[BitmapFontPreset, BitmapFontDefinition]] = {
    "4x6": BitmapFontDefinition(
        preset="4x6",
        glyph_width=4,
        glyph_height=6,
        default_line_height=7,
        default_letter_spacing=1,
        default_space_advance=5,
        glyphs=_GLYPHS_4X6,
    ),
    "5x7": BitmapFontDefinition(
        preset="5x7",
        glyph_width=5,
        glyph_height=7,
        default_line_height=9,
        default_letter_spacing=1,
        default_space_advance=5,
        glyphs=_GLYPHS_5X7,
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
    rows = math.ceil(len(charset) / columns)
    glyphs: list[BitmapGlyphMetrics] = []
    for idx, ch in enumerate(charset):
        col = idx % columns
        row = idx // columns
        gx = margin + col * (definition.glyph_width + spacing)
        gy = margin + row * (definition.glyph_height + spacing)
        x_adv = (
            resolved_space_advance
            if ch == " "
            else definition.glyph_width + resolved_letter_spacing
        )
        glyphs.append(
            BitmapGlyphMetrics(
                char=ch,
                x=gx,
                y=gy,
                width=definition.glyph_width,
                height=definition.glyph_height,
                x_advance=x_adv,
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

    lines = text.split("\n")
    max_w = 0
    for line in lines:
        if not line:
            continue
        line_w = len(line) * (definition.glyph_width + spacing) - spacing
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
) -> None:
    msb_shift = glyph_width - 1
    for row_idx, row_bits in enumerate(glyph_rows):
        if row_bits == 0:
            continue
        for col_idx in range(glyph_width):
            if (row_bits >> (msb_shift - col_idx)) & 1:
                if scale == 1:
                    surface.put(x + col_idx, y + row_idx, color)
                else:
                    surface.rect(
                        x + col_idx * scale,
                        y + row_idx * scale,
                        scale,
                        scale,
                        color,
                    )


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
    letter_spacing: int | None = None,
    line_height: int | None = None,
) -> None:
    """Render deterministic crisp bitmap text onto an `IndexedSurface`, `Asset`, or `Layer`."""
    if scale <= 0:
        msg = f"scale must be > 0, got {scale}"
        raise ValueError(msg)
    surface = _resolve_surface(target)
    definition = get_font_definition(font)
    spacing = definition.default_letter_spacing if letter_spacing is None else letter_spacing
    line_h = definition.default_line_height if line_height is None else line_height
    advance = (definition.glyph_width + spacing) * scale

    passes: list[tuple[int, int, int]] = []
    if shadow is not None:
        passes.append((x + scale, y + scale, shadow))
    passes.append((x, y, color))

    for start_x, start_y, pass_color in passes:
        cx = start_x
        cy = start_y
        for ch in text:
            if ch == "\n":
                cx = start_x
                cy += line_h * scale
                continue
            glyph_rows = resolve_glyph(definition, ch)
            _draw_glyph_to_surface(
                surface,
                glyph_rows,
                definition.glyph_width,
                cx,
                cy,
                pass_color,
                scale=scale,
            )
            cx += advance


def render_font_atlas(
    target: SurfaceTarget | IndexedSurface,
    spec: BitmapFontSpec,
    color: int,
    *,
    shadow: int | None = None,
) -> None:
    """Render all glyphs defined in `spec` into their exact atlas cell coordinates."""
    surface = _resolve_surface(target)
    definition = get_font_definition(spec.preset)
    for glyph in spec.glyphs:
        if glyph.char == " ":
            continue
        glyph_rows = resolve_glyph(definition, glyph.char)
        gx = glyph.x + glyph.x_offset
        gy = glyph.y + glyph.y_offset
        if shadow is not None:
            _draw_glyph_to_surface(
                surface,
                glyph_rows,
                definition.glyph_width,
                gx + 1,
                gy + 1,
                shadow,
            )
        _draw_glyph_to_surface(
            surface,
            glyph_rows,
            definition.glyph_width,
            gx,
            gy,
            color,
        )
