"""Core indexed framebuffer, PRNG, palette, isometric, plane, and compositional builder APIs."""

from pixelforge.core import prefabs
from pixelforge.core.builder import (
    AnchorAlign,
    Asset,
    Layer,
    ScatterMask,
    SelOutSpec,
)
from pixelforge.core.iso import IsoAnchor, iso_box, iso_project, iso_tile
from pixelforge.core.palette import (
    PaletteLookup,
    PaletteLookupError,
    build_reflection_lut,
    build_rgba_lut,
    hex_to_rgb,
    resolve_reflections,
    resolve_variant_colors,
)
from pixelforge.core.plane import GridMode, Plane, Point2D
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
    "AnchorAlign",
    "AnchorPoint",
    "Asset",
    "AssetSpec",
    "DitherMask",
    "DitherPattern",
    "GridMode",
    "HitboxRect",
    "IndexedSurface",
    "IsoAnchor",
    "Layer",
    "LightingAngle",
    "MirrorSource",
    "PaletteColor",
    "PaletteFlag",
    "PaletteLookup",
    "PaletteLookupError",
    "PerspectiveMode",
    "Plane",
    "Point2D",
    "ScatterMask",
    "SelOutSpec",
    "StylePack",
    "build_reflection_lut",
    "build_rgba_lut",
    "hashf",
    "hex_to_rgb",
    "iso_box",
    "iso_project",
    "iso_tile",
    "mulberry32",
    "prefabs",
    "resolve_reflections",
    "resolve_variant_colors",
    "xorshift32",
]
