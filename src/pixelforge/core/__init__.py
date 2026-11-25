"""Core indexed framebuffer, PRNG, palette, and pixel primitives."""

from pixelforge.core.palette import (
    PaletteLookup,
    PaletteLookupError,
    build_reflection_lut,
    build_rgba_lut,
    hex_to_rgb,
    resolve_reflections,
    resolve_variant_colors,
)
from pixelforge.core.prng import hashf, mulberry32, xorshift32
from pixelforge.core.surface import (
    DitherMask,
    DitherPattern,
    IndexedSurface,
    MirrorSource,
)
from pixelforge.core.types import (
    MAX_PALETTE_INDEX,
    TRANSPARENT_INDEX,
    AnchorPoint,
    AssetSpec,
    HitboxRect,
    LightingAngle,
    PaletteColor,
    PaletteFlag,
    PerspectiveMode,
    StylePack,
)

__all__ = [
    "MAX_PALETTE_INDEX",
    "TRANSPARENT_INDEX",
    "AnchorPoint",
    "AssetSpec",
    "DitherMask",
    "DitherPattern",
    "HitboxRect",
    "IndexedSurface",
    "LightingAngle",
    "MirrorSource",
    "PaletteColor",
    "PaletteFlag",
    "PaletteLookup",
    "PaletteLookupError",
    "PerspectiveMode",
    "StylePack",
    "build_reflection_lut",
    "build_rgba_lut",
    "hashf",
    "hex_to_rgb",
    "mulberry32",
    "resolve_reflections",
    "resolve_variant_colors",
    "xorshift32",
]
