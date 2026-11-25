"""Core domain contracts, constants, and Pydantic models for pixelforge v2."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# INVARIANT: Index 255 is permanently reserved as binary transparent alpha (0);
# indices 0..254 map strictly to active StylePack colors.
TRANSPARENT_INDEX: Final[int] = 255
MAX_PALETTE_INDEX: Final[int] = 254

PerspectiveMode = Literal["front-2.5d", "iso-2:1", "top-down", "side"]
LightingAngle = Literal["top-left", "top-right", "top"]
PaletteFlag = Literal[
    "outline",
    "emissive",
    "bright",
    "shadow",
    "metal",
    "accent",
    "surface",
]

_HEX_PATTERN: Final[str] = r"^#[0-9a-fA-F]{6}$"


class PaletteColor(BaseModel):
    """Single indexed color entry inside a StylePack."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0, le=MAX_PALETTE_INDEX)
    name: str = Field(min_length=1)
    hex: str = Field(pattern=_HEX_PATTERN)
    flags: tuple[PaletteFlag, ...] = ()


class StylePack(BaseModel):
    """Canonical palette, lighting, reflection, and variant contract."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    perspective: PerspectiveMode
    lighting_angle: LightingAngle
    outline_index: int = Field(ge=0, le=MAX_PALETTE_INDEX)
    palette: tuple[PaletteColor, ...] = Field(min_length=1)
    reflections: dict[str, str] = Field(default_factory=dict)
    variants: dict[str, dict[str, str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_integrity(self) -> StylePack:
        indices: set[int] = set()
        names: set[str] = set()
        for entry in self.palette:
            if entry.index in indices:
                msg = f"Duplicate palette index {entry.index} in style {self.id!r}"
                raise ValueError(msg)
            if entry.name in names:
                msg = f"Duplicate palette token {entry.name!r} in style {self.id!r}"
                raise ValueError(msg)
            indices.add(entry.index)
            names.add(entry.name)

        if self.outline_index not in indices:
            msg = f"outline_index {self.outline_index} is not defined in style {self.id!r}"
            raise ValueError(msg)

        for src, dst in self.reflections.items():
            if src not in names:
                msg = f"Reflection source token {src!r} missing from style {self.id!r}"
                raise ValueError(msg)
            if dst not in names:
                msg = f"Reflection target token {dst!r} missing from style {self.id!r}"
                raise ValueError(msg)

        for variant_name, overrides in self.variants.items():
            for token, hex_val in overrides.items():
                if token not in names:
                    msg = (
                        f"Variant {variant_name!r} references unknown token "
                        f"{token!r} in style {self.id!r}"
                    )
                    raise ValueError(msg)
                if len(hex_val) != 7 or not hex_val.startswith("#"):
                    msg = f"Variant {variant_name!r} token {token!r} has invalid hex {hex_val!r}"
                    raise ValueError(msg)
                int(hex_val[1:], 16)

        return self


class AnchorPoint(BaseModel):
    """Named integer-coordinate anchor emitted during asset rendering."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    x: int
    y: int


class HitboxRect(BaseModel):
    """Named integer-coordinate bounding rectangle emitted during asset rendering."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    x: int
    y: int
    w: int = Field(gt=0)
    h: int = Field(gt=0)


class AssetSpec(BaseModel):
    """Static metadata specification declared by each `.asset.py` module."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    style_id: str = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    perspective: PerspectiveMode
    states: tuple[str, ...] = Field(default=("default",), min_length=1)
    frames: int = Field(default=1, ge=1)
    fps: int = Field(default=6, ge=1)
    seed: int = 0

    @model_validator(mode="after")
    def _validate_states(self) -> AssetSpec:
        seen: set[str] = set()
        for state in self.states:
            if not state:
                msg = f"AssetSpec {self.id!r} contains an empty state name"
                raise ValueError(msg)
            if state in seen:
                msg = f"AssetSpec {self.id!r} contains duplicate state {state!r}"
                raise ValueError(msg)
            seen.add(state)
        return self
