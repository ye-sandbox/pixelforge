"""pixelforge v2 — Deterministic Python compositional indexed pixel art compiler."""

from pixelforge.core import (
    MAX_PALETTE_INDEX,
    TRANSPARENT_INDEX,
    AnchorPoint,
    AssetSpec,
    HitboxRect,
    IndexedSurface,
    PaletteColor,
    PaletteFlag,
    PaletteLookup,
    PaletteLookupError,
    StylePack,
    hashf,
    mulberry32,
    xorshift32,
)

__all__ = [
    "MAX_PALETTE_INDEX",
    "TRANSPARENT_INDEX",
    "AnchorPoint",
    "AssetSpec",
    "HitboxRect",
    "IndexedSurface",
    "PaletteColor",
    "PaletteFlag",
    "PaletteLookup",
    "PaletteLookupError",
    "StylePack",
    "__version__",
    "hashf",
    "mulberry32",
    "xorshift32",
]

__version__ = "0.2.0"
