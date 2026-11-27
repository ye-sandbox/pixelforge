"""Core domain contracts, constants, and Pydantic models for pixelforge v2."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    model_serializer,
    model_validator,
)

# INVARIANT: Index 255 is permanently reserved as binary transparent alpha (0);
# indices 0..254 map strictly to active StylePack colors.
TRANSPARENT_INDEX: Final[int] = 255
MAX_PALETTE_INDEX: Final[int] = 254

PerspectiveMode = Literal["front-2.5d", "iso-2:1", "top-down", "side"]
LightingAngle = Literal["top-left", "top-right", "top"]
AutotileMode = Literal["cardinal16", "blob47"]
BitmapFontPreset = Literal["4x6", "5x7"]
LayerRole = Literal["visual", "collision", "walkable", "occlusion", "interact"]
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


def _hex_luminance(hex_color: str) -> float:
    """Return relative sRGB luminance (0..255 scale) for a validated `#RRGGBB` hex string."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


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
    aliases: dict[str, str] = Field(default_factory=dict)
    reflections: dict[str, str] = Field(default_factory=dict)
    variants: dict[str, dict[str, str]] = Field(default_factory=dict)
    ramps: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_integrity(self) -> StylePack:
        indices: set[int] = set()
        names: set[str] = set()
        hex_by_name: dict[str, str] = {}
        for entry in self.palette:
            if entry.index in indices:
                msg = f"Duplicate palette index {entry.index} in style {self.id!r}"
                raise ValueError(msg)
            if entry.name in names:
                msg = f"Duplicate palette token {entry.name!r} in style {self.id!r}"
                raise ValueError(msg)
            indices.add(entry.index)
            names.add(entry.name)
            hex_by_name[entry.name] = entry.hex

        if self.outline_index not in indices:
            msg = f"outline_index {self.outline_index} is not defined in style {self.id!r}"
            raise ValueError(msg)

        for alias_name, target_token in self.aliases.items():
            if not alias_name:
                msg = f"Alias name must be non-empty in style {self.id!r}"
                raise ValueError(msg)
            if alias_name in names:
                msg = (
                    f"Alias {alias_name!r} collides with existing palette token "
                    f"in style {self.id!r}"
                )
                raise ValueError(msg)
            if target_token not in names:
                msg = (
                    f"Alias {alias_name!r} targets unknown token {target_token!r} "
                    f"in style {self.id!r}"
                )
                raise ValueError(msg)
            hex_by_name[alias_name] = hex_by_name[target_token]

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

        for ramp_name, ramp_tokens in self.ramps.items():
            if not ramp_name:
                msg = f"Ramp name must be non-empty in style {self.id!r}"
                raise ValueError(msg)
            if len(ramp_tokens) < 2:
                msg = f"Ramp {ramp_name!r} in style {self.id!r} must have at least 2 tokens"
                raise ValueError(msg)
            prev_lum = -1.0
            prev_token = ""
            for token in ramp_tokens:
                if token not in hex_by_name:
                    msg = (
                        f"Ramp {ramp_name!r} references unknown token {token!r} "
                        f"in style {self.id!r}"
                    )
                    raise ValueError(msg)
                lum = _hex_luminance(hex_by_name[token])
                if lum < prev_lum - 1e-6:
                    msg = (
                        f"Ramp {ramp_name!r} in style {self.id!r} must be ordered dark-to-light: "
                        f"{prev_token!r} ({prev_lum:.1f}) is brighter than {token!r} ({lum:.1f})"
                    )
                    raise ValueError(msg)
                prev_lum = lum
                prev_token = token

        return self


class AnchorPoint(BaseModel):
    """Named integer-coordinate anchor emitted during asset rendering."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    x: int
    y: int
    kind: str | None = Field(default=None, min_length=1)
    dir: tuple[int, int] | None = None

    @model_serializer
    def _serialize(self, info: SerializationInfo) -> dict[str, object]:
        data: dict[str, object] = {"name": self.name, "x": self.x, "y": self.y}
        if self.kind is not None:
            data["kind"] = self.kind
        if self.dir is not None:
            data["dir"] = list(self.dir) if info.mode == "json" else self.dir
        return data


class HitboxRect(BaseModel):
    """Named integer-coordinate bounding rectangle emitted during asset rendering."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    x: int
    y: int
    w: int = Field(gt=0)
    h: int = Field(gt=0)
    kind: str | None = Field(default=None, min_length=1)

    @model_serializer
    def _serialize(self) -> dict[str, object]:
        data: dict[str, object] = {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
        }
        if self.kind is not None:
            data["kind"] = self.kind
        return data


class NineSliceMargins(BaseModel):
    """9-slice stretchable border margins in 1x source pixels."""

    model_config = ConfigDict(frozen=True)

    left: int = Field(ge=0)
    right: int = Field(ge=0)
    top: int = Field(ge=0)
    bottom: int = Field(ge=0)


class SemanticPoint(BaseModel):
    """Integer 2D coordinate used for derived gameplay pivots (e.g., y-sort)."""

    model_config = ConfigDict(frozen=True)

    x: int
    y: int


class SemanticGrid(BaseModel):
    """Row-major binary occupancy grid (`0` or `1`) for collision or walkability."""

    model_config = ConfigDict(frozen=True)

    cell_width: int = Field(gt=0)
    cell_height: int = Field(gt=0)
    columns: int = Field(gt=0)
    rows: int = Field(gt=0)
    cells: tuple[int, ...]

    @model_validator(mode="after")
    def _validate_cells(self) -> SemanticGrid:
        expected = self.columns * self.rows
        if len(self.cells) != expected:
            msg = (
                f"SemanticGrid cells length {len(self.cells)} does not match "
                f"{self.columns}x{self.rows} ({expected})"
            )
            raise ValueError(msg)
        for idx, val in enumerate(self.cells):
            if val not in (0, 1):
                msg = f"SemanticGrid cell[{idx}] must be 0 or 1, got {val}"
                raise ValueError(msg)
        return self


class SemanticZone(BaseModel):
    """Derived axis-aligned gameplay zone (occlusion or interaction trigger)."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    x: int
    y: int
    w: int = Field(gt=0)
    h: int = Field(gt=0)
    kind: str = Field(min_length=1)


class GameplaySemantics(BaseModel):
    """Derived collision, walkability, y-sort pivot, occlusion, and interaction metadata."""

    model_config = ConfigDict(frozen=True)

    y_sort_pivot: SemanticPoint
    collision_grid: SemanticGrid
    walkable_mask: SemanticGrid
    occlusion_zones: tuple[SemanticZone, ...] = ()
    interact_zones: tuple[SemanticZone, ...] = ()


class TilemapSpec(BaseModel):
    """Deterministic autotile sheet layout and bitmask metadata."""

    model_config = ConfigDict(frozen=True)

    mode: AutotileMode
    tile_width: int = Field(gt=0)
    tile_height: int = Field(gt=0)
    columns: int = Field(gt=0)
    rows: int = Field(gt=0)
    bitmasks: tuple[int, ...] = Field(min_length=1)
    terrain_name: str = Field(default="terrain", min_length=1)
    margin: int = Field(default=0, ge=0)
    spacing: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _validate_tilemap(self) -> TilemapSpec:
        capacity = self.columns * self.rows
        if len(self.bitmasks) > capacity:
            msg = f"TilemapSpec bitmasks ({len(self.bitmasks)}) exceed grid capacity ({capacity})"
            raise ValueError(msg)
        max_mask = 15 if self.mode == "cardinal16" else 255
        seen: set[int] = set()
        for mask in self.bitmasks:
            if mask < 0 or mask > max_mask:
                msg = (
                    f"TilemapSpec bitmask {mask} out of range 0..{max_mask} for mode {self.mode!r}"
                )
                raise ValueError(msg)
            if mask in seen:
                msg = f"TilemapSpec contains duplicate bitmask {mask}"
                raise ValueError(msg)
            seen.add(mask)
        return self


class BitmapGlyphMetrics(BaseModel):
    """Per-glyph atlas coordinates and spacing metrics for a compiled bitmap font."""

    model_config = ConfigDict(frozen=True)

    char: str = Field(min_length=1, max_length=1)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    x_advance: int = Field(gt=0)
    x_offset: int = 0
    y_offset: int = 0


class BitmapFontSpec(BaseModel):
    """Deterministic bitmap font atlas layout and glyph spacing contract."""

    model_config = ConfigDict(frozen=True)

    preset: BitmapFontPreset = "4x6"
    glyph_width: int = Field(gt=0)
    glyph_height: int = Field(gt=0)
    line_height: int = Field(gt=0)
    letter_spacing: int = Field(default=1, ge=0)
    space_advance: int = Field(gt=0)
    columns: int = Field(gt=0)
    rows: int = Field(gt=0)
    margin: int = Field(default=0, ge=0)
    spacing: int = Field(default=0, ge=0)
    charset: str = Field(min_length=1)
    glyphs: tuple[BitmapGlyphMetrics, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_font(self) -> BitmapFontSpec:
        capacity = self.columns * self.rows
        if len(self.glyphs) > capacity:
            msg = f"BitmapFontSpec glyphs ({len(self.glyphs)}) exceed grid capacity ({capacity})"
            raise ValueError(msg)
        if len(set(self.charset)) != len(self.charset):
            msg = "BitmapFontSpec charset contains duplicate characters"
            raise ValueError(msg)
        glyph_chars = "".join(g.char for g in self.glyphs)
        if len(set(glyph_chars)) != len(self.glyphs):
            msg = "BitmapFontSpec glyphs contains duplicate characters"
            raise ValueError(msg)
        if glyph_chars != self.charset:
            msg = "BitmapFontSpec glyphs must match charset order 1:1"
            raise ValueError(msg)
        return self


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
    nine_slice: NineSliceMargins | None = None
    tilemap: TilemapSpec | None = None
    font: BitmapFontSpec | None = None
    frame_events: dict[str, dict[int, tuple[str, ...]]] = Field(default_factory=dict)

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
        if self.nine_slice is not None:
            if self.nine_slice.left + self.nine_slice.right > self.width:
                msg = (
                    f"AssetSpec {self.id!r} nine_slice horizontal margins "
                    f"({self.nine_slice.left} + {self.nine_slice.right}) exceed width {self.width}"
                )
                raise ValueError(msg)
            if self.nine_slice.top + self.nine_slice.bottom > self.height:
                msg = (
                    f"AssetSpec {self.id!r} nine_slice vertical margins "
                    f"({self.nine_slice.top} + {self.nine_slice.bottom}) "
                    f"exceed height {self.height}"
                )
                raise ValueError(msg)
        if self.tilemap is not None:
            tm = self.tilemap
            req_w = 2 * tm.margin + tm.columns * tm.tile_width + (tm.columns - 1) * tm.spacing
            req_h = 2 * tm.margin + tm.rows * tm.tile_height + (tm.rows - 1) * tm.spacing
            if req_w > self.width or req_h > self.height:
                msg = (
                    f"AssetSpec {self.id!r} tilemap dimensions ({req_w}x{req_h}) "
                    f"exceed canvas ({self.width}x{self.height})"
                )
                raise ValueError(msg)
        if self.font is not None:
            f = self.font
            req_w = 2 * f.margin + f.columns * f.glyph_width + (f.columns - 1) * f.spacing
            req_h = 2 * f.margin + f.rows * f.glyph_height + (f.rows - 1) * f.spacing
            if req_w > self.width or req_h > self.height:
                msg = (
                    f"AssetSpec {self.id!r} font atlas dimensions ({req_w}x{req_h}) "
                    f"exceed canvas ({self.width}x{self.height})"
                )
                raise ValueError(msg)
            for glyph in f.glyphs:
                if glyph.x + glyph.width > self.width or glyph.y + glyph.height > self.height:
                    msg = (
                        f"AssetSpec {self.id!r} font glyph {glyph.char!r} "
                        f"({glyph.x},{glyph.y},{glyph.width}x{glyph.height}) "
                        f"exceeds canvas ({self.width}x{self.height})"
                    )
                    raise ValueError(msg)
        for ev_state, frame_map in self.frame_events.items():
            if ev_state not in seen:
                msg = (
                    f"AssetSpec {self.id!r} frame_events references unknown state {ev_state!r} "
                    f"(expected one of {self.states})"
                )
                raise ValueError(msg)
            for ev_frame, tags in frame_map.items():
                if ev_frame < 0 or ev_frame >= self.frames:
                    msg = (
                        f"AssetSpec {self.id!r} frame_events[{ev_state!r}] frame {ev_frame} "
                        f"out of range [0..{self.frames - 1}]"
                    )
                    raise ValueError(msg)
                for tag in tags:
                    if not tag or not tag.strip():
                        msg = (
                            f"AssetSpec {self.id!r} frame_events[{ev_state!r}][{ev_frame}] "
                            "contains an empty event tag"
                        )
                        raise ValueError(msg)
        return self
