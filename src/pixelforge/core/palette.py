"""Fail-loud palette lookup, reflection tables, and variant LUT resolution."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.types import TRANSPARENT_INDEX, PaletteColor, StylePack


class PaletteLookupError(KeyError, AttributeError):
    """Raised when an asset requests an undefined palette token or variant."""


class PaletteLookup:
    """Typed, fail-loud mapping from semantic palette token names to uint8 indices."""

    _style_id: str
    _indices: dict[str, int]

    def __init__(self, style: StylePack, tokens: Sequence[str] | None = None) -> None:
        by_name = {entry.name: entry.index for entry in style.palette}
        if tokens is None:
            resolved = dict(by_name)
        else:
            resolved = {}
            for token in tokens:
                if token not in by_name:
                    msg = f"Missing palette token: {token!r} (style: {style.id!r})"
                    raise PaletteLookupError(msg)
                resolved[token] = by_name[token]

        # INVARIANT: Fail loudly on unknown token reads instead of returning None or 0,
        # which would silently write palette index 0 into the uint8 framebuffer.
        object.__setattr__(self, "_style_id", style.id)
        object.__setattr__(self, "_indices", resolved)

    @property
    def style_id(self) -> str:
        """Return the bound StylePack identifier."""
        return self._style_id

    def __getattr__(self, name: str) -> int:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._indices[name]
        except KeyError as exc:
            msg = f"Missing palette token: {name!r} (style: {self._style_id!r})"
            raise PaletteLookupError(msg) from exc

    def __getitem__(self, name: str) -> int:
        try:
            return self._indices[name]
        except KeyError as exc:
            msg = f"Missing palette token: {name!r} (style: {self._style_id!r})"
            raise PaletteLookupError(msg) from exc

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._indices

    def __len__(self) -> int:
        return len(self._indices)

    def __iter__(self) -> Iterator[str]:
        return iter(self._indices)

    @classmethod
    def _from_resolved(cls, style_id: str, resolved: Mapping[str, int]) -> PaletteLookup:
        instance = cls.__new__(cls)
        object.__setattr__(instance, "_style_id", style_id)
        object.__setattr__(instance, "_indices", dict(resolved))
        return instance

    def with_overrides(self, overrides: Mapping[str, str | int]) -> PaletteLookup:
        """Return a new `PaletteLookup` with selected semantic token names remapped."""
        resolved = dict(self._indices)
        for src_token, dst_value in overrides.items():
            if src_token not in resolved:
                msg = f"Unknown source token {src_token!r} for palette override"
                raise KeyError(msg)
            if isinstance(dst_value, str):
                resolved[src_token] = self[dst_value]
            else:
                idx = int(dst_value)
                if idx < 0 or idx >= TRANSPARENT_INDEX:
                    msg = (
                        f"Override index {idx} out of valid palette range "
                        f"[0..{TRANSPARENT_INDEX - 1}]"
                    )
                    raise ValueError(msg)
                resolved[src_token] = idx
        return PaletteLookup._from_resolved(self._style_id, resolved)

    def to_dict(self) -> dict[str, int]:
        """Return a shallow copy of the resolved token-to-index map."""
        return dict(self._indices)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Parse a `#RRGGBB` string into an integer `(r, g, b)` tuple."""
    if len(hex_color) != 7 or not hex_color.startswith("#"):
        msg = f"Invalid hex color: {hex_color!r}"
        raise ValueError(msg)
    return (
        int(hex_color[1:3], 16),
        int(hex_color[3:5], 16),
        int(hex_color[5:7], 16),
    )


def resolve_reflections(style: StylePack) -> dict[int, int]:
    """Resolve `StylePack.reflections` token pairs into `{src_index: dst_index}`."""
    by_name = {entry.name: entry.index for entry in style.palette}
    return {by_name[src]: by_name[dst] for src, dst in style.reflections.items()}


def build_reflection_lut(style: StylePack, *, fallback_self: bool = False) -> NDArray[np.uint8]:
    """Build a 256-entry uint8 `REFL` lookup table for floor reflections."""
    if fallback_self:
        lut = np.arange(256, dtype=np.uint8)
        lut[TRANSPARENT_INDEX] = TRANSPARENT_INDEX
    else:
        lut = np.full(256, TRANSPARENT_INDEX, dtype=np.uint8)

    for src_idx, dst_idx in resolve_reflections(style).items():
        lut[src_idx] = dst_idx
    return lut


def resolve_variant_colors(
    style: StylePack,
    variant: str | None = None,
) -> tuple[PaletteColor, ...]:
    """Return `style.palette` with optional named variant hex overrides applied."""
    if variant is None:
        return style.palette

    if variant not in style.variants:
        msg = f"Unknown variant {variant!r} for style {style.id!r}"
        raise PaletteLookupError(msg)

    overrides = style.variants[variant]
    return tuple(
        PaletteColor(
            index=entry.index,
            name=entry.name,
            hex=overrides.get(entry.name, entry.hex),
            flags=entry.flags,
        )
        for entry in style.palette
    )


def build_rgba_lut(style: StylePack, variant: str | None = None) -> NDArray[np.uint8]:
    """Build a `(256, 4)` uint8 RGBA LUT enforcing binary alpha (`0` or `255`)."""
    # INVARIANT: Binary alpha — index 255 (and undeclared slots) have alpha 0;
    # declared palette indices 0..254 strictly have alpha 255.
    lut = np.zeros((256, 4), dtype=np.uint8)
    for entry in resolve_variant_colors(style, variant):
        r, g, b = hex_to_rgb(entry.hex)
        lut[entry.index] = (r, g, b, 255)
    return lut
