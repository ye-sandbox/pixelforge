"""Compositional `build123d`-style Asset and Layer context-manager authoring API."""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Self

import numpy as np

from pixelforge.core.iso import IsoAnchor, iso_box, iso_tile
from pixelforge.core.palette import PaletteLookup
from pixelforge.core.plane import Plane, Point2D
from pixelforge.core.prng import hashf, mulberry32
from pixelforge.core.surface import (
    DitherMask,
    DitherPattern,
    IndexedSurface,
    MirrorSource,
)
from pixelforge.core.types import (
    TRANSPARENT_INDEX,
    AnchorPoint,
    AssetSpec,
    HitboxRect,
    StylePack,
)

ScatterMask = Literal["all", "opaque", "transparent"]
SelOutSpec = int | tuple[int, int] | tuple[int, int, int]
AnchorAlign = Literal["center", "bottom-center", "top-left"]


def _derive_seed(base_seed: int, state: str, frame: int) -> int:
    """Compute a deterministic uint32 seed via FNV-1a (immune to PYTHONHASHSEED)."""
    h = 2166136261
    payload = f"{base_seed}:{state}:{frame}".encode()
    for byte in payload:
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return h


@dataclass
class _LayerFrame:
    name: str
    surface: IndexedSurface
    offset: tuple[int, int]
    outline: int | None
    sel_out: SelOutSpec | None
    bevel: tuple[int, int] | None
    mirror_x: bool | MirrorSource
    layer: Layer


def _apply_palette_overrides(
    base: PaletteLookup,
    style: StylePack,
    overrides: Mapping[str, str | int],
) -> PaletteLookup:
    """Return a new `PaletteLookup` with selected semantic token names remapped."""
    resolved = base.to_dict()
    for src_token, dst_value in overrides.items():
        if src_token not in resolved:
            msg = f"Unknown source token {src_token!r} for palette override"
            raise KeyError(msg)
        if isinstance(dst_value, str):
            resolved[src_token] = base[dst_value]
        else:
            idx = int(dst_value)
            if idx < 0 or idx >= TRANSPARENT_INDEX:
                msg = (
                    f"Override index {idx} out of valid palette range [0..{TRANSPARENT_INDEX - 1}]"
                )
                raise ValueError(msg)
            resolved[src_token] = idx

    # Build a synthetic PaletteLookup bound to the same style id with remapped indices.
    remapped = PaletteLookup(style)
    object.__setattr__(remapped, "_indices", resolved)
    return remapped


class _DrawingMixin:
    """Shared drawing, scatter, recolor, and metadata helpers for `Asset` and `Layer`."""

    @property
    def surface(self) -> IndexedSurface:
        raise NotImplementedError

    def _next_rng(self) -> float:
        raise NotImplementedError

    def _emit_anchor(self, name: str, x: int | float, y: int | float) -> AnchorPoint:
        raise NotImplementedError

    def _emit_hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
    ) -> HitboxRect:
        raise NotImplementedError

    def _resolve_pal_index(self, token_or_idx: str | int) -> int:
        raise NotImplementedError

    def _make_plane(self, p0: Point2D, p1: Point2D, p2: Point2D) -> Plane:
        return Plane(self.surface, p0, p1, p2, self._emit_anchor)

    def plane(self, p0: Point2D, p1: Point2D, p2: Point2D) -> Plane:
        """Open a normalized `(u, v)` affine `Plane` context onto the active surface."""
        return self._make_plane(p0, p1, p2)

    def put(self, x: int | float, y: int | float, color: int) -> None:
        """Write a single integer-grid pixel (1px surgical escape hatch)."""
        self.surface.put(x, y, color)

    def erase(self, x: int | float, y: int | float) -> None:
        """Erase a single integer-grid pixel back to `TRANSPARENT_INDEX`."""
        self.surface.erase(x, y)

    def get(self, x: int | float, y: int | float) -> int:
        """Read palette index at `(x, y)` or `TRANSPARENT_INDEX` when out of bounds."""
        return self.surface.get(x, y)

    def clear(self, color: int = TRANSPARENT_INDEX) -> None:
        """Fill the active surface with `color`."""
        self.surface.clear(color)

    def rect(
        self,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw an axis-aligned rectangle onto the active surface."""
        self.surface.rect(x, y, w, h, color, fill=fill)

    def rounded_rect(
        self,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        radius: int,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw a pixel-crisp rounded rectangle onto the active surface."""
        self.surface.rounded_rect(x, y, w, h, radius, color, fill=fill)

    def line(
        self,
        x0: int | float,
        y0: int | float,
        x1: int | float,
        y1: int | float,
        color: int,
    ) -> None:
        """Draw an integer Bresenham line onto the active surface."""
        self.surface.line(x0, y0, x1, y1, color)

    def circle(
        self,
        cx: int | float,
        cy: int | float,
        radius: int,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw an integer midpoint circle onto the active surface."""
        self.surface.circle(cx, cy, radius, color, fill=fill)

    def ellipse(
        self,
        cx: int | float,
        cy: int | float,
        rx: int,
        ry: int,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw an integer midpoint ellipse onto the active surface."""
        self.surface.ellipse(cx, cy, rx, ry, color, fill=fill)

    def polygon(
        self,
        points: Sequence[Point2D],
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw a polygon onto the active surface."""
        self.surface.polygon(points, color, fill=fill)

    def quad(
        self,
        p0: Point2D,
        p1: Point2D,
        p2: Point2D,
        p3: Point2D,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw a quadrilateral onto the active surface."""
        self.surface.quad(p0, p1, p2, p3, color, fill=fill)

    def fill(self, x: int | float, y: int | float, color: int) -> None:
        """Scanline 4-connected flood fill on the active surface."""
        self.surface.fill(x, y, color)

    def dither(
        self,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        color_a: int | None,
        color_b: int | None,
        *,
        pattern: DitherPattern = "bayer4",
        ratio: float = 0.5,
        mask: DitherMask = "all",
    ) -> None:
        """Apply ordered Bayer 2x2/4x4 or checker dithering onto the active surface."""
        self.surface.dither(x, y, w, h, color_a, color_b, pattern=pattern, ratio=ratio, mask=mask)

    def spr(
        self,
        grid: Sequence[str],
        x: int | float,
        y: int | float,
        color_map: Mapping[str, int],
    ) -> None:
        """Stamp an ASCII sprite grid onto the active surface."""
        self.surface.spr(grid, x, y, color_map)

    def mirror_x(self, source: MirrorSource = "left") -> None:
        """Mirror one horizontal half of the active surface onto the other."""
        self.surface.mirror_x(source)

    def flip_x(self) -> None:
        """Flip the active surface horizontally."""
        self.surface.flip_x()

    def flip_y(self) -> None:
        """Flip the active surface vertically."""
        self.surface.flip_y()

    def auto_outline(self, outline_color: int) -> None:
        """Add a 1px 4-connected outline onto transparent border pixels."""
        self.surface.auto_outline(outline_color)

    def sel_out(
        self,
        top_color: int,
        bottom_color: int | None = None,
        *,
        side_color: int | None = None,
    ) -> None:
        """Apply directional selective outlining around opaque pixels."""
        self.surface.sel_out(top_color, bottom_color, side_color=side_color)

    def edge_mask(
        self,
        top_color: int | None = None,
        bottom_color: int | None = None,
    ) -> None:
        """Recolor top/bottom exposed opaque edge pixels for bevels and rims."""
        self.surface.edge_mask(top_color, bottom_color)

    def iso_tile(
        self,
        cx: int | float,
        cy: int | float,
        width: int,
        color: int,
        *,
        height: int | None = None,
        fill: bool = True,
        outline: int | None = None,
    ) -> None:
        """Draw a 2:1 isometric diamond tile onto the active surface."""
        iso_tile(self.surface, cx, cy, width, color, height=height, fill=fill, outline=outline)

    def iso_box(
        self,
        x: int | float,
        y: int | float,
        w: int,
        d: int,
        h: int,
        *,
        top: int,
        left: int,
        right: int,
        outline: int | None = None,
        highlight: int | None = None,
        anchor: IsoAnchor = "top",
    ) -> None:
        """Draw a 2:1 isometric 3-face box onto the active surface."""
        iso_box(
            self.surface,
            x,
            y,
            w,
            d,
            h,
            top=top,
            left=left,
            right=right,
            outline=outline,
            highlight=highlight,
            anchor=anchor,
        )

    def scatter(
        self,
        count: int,
        colors: Sequence[int] | int,
        *,
        mask: ScatterMask = "opaque",
        bounds: tuple[int, int, int, int] | None = None,
        only_colors: Sequence[int] | None = None,
    ) -> int:
        """Deterministically place `count` pixels onto masked coordinates using `rng`."""
        if count <= 0:
            return 0
        palette_choices = (
            (int(colors),) if isinstance(colors, int) else tuple(int(c) for c in colors)
        )
        if not palette_choices:
            msg = "scatter requires at least one color"
            raise ValueError(msg)

        surf = self.surface
        if bounds is None:
            x0, y0, x1, y1 = 0, 0, surf.width, surf.height
        else:
            bx, by, bw, bh = bounds
            x0 = max(0, int(bx))
            y0 = max(0, int(by))
            x1 = min(surf.width, int(bx) + int(bw))
            y1 = min(surf.height, int(by) + int(bh))
        if x0 >= x1 or y0 >= y1:
            return 0

        patch = surf.data[y0:y1, x0:x1]
        if mask == "opaque":
            eligible = patch != TRANSPARENT_INDEX
        elif mask == "transparent":
            eligible = patch == TRANSPARENT_INDEX
        elif mask == "all":
            eligible = np.ones_like(patch, dtype=bool)
        else:
            msg = f"Unsupported scatter mask: {mask!r}"
            raise ValueError(msg)

        if only_colors is not None:
            allowed = np.isin(patch, np.array([int(c) for c in only_colors], dtype=np.uint8))
            eligible &= allowed

        coords = np.argwhere(eligible)
        total = len(coords)
        if total == 0:
            return 0

        picks = min(int(count), total)
        indices = list(range(total))
        # INVARIANT: Partial Fisher-Yates driven solely by the asset's mulberry32 stream
        # guarantees exact `count` placement and bit-determinism without numpy.random.
        for i in range(picks):
            j = i + int(self._next_rng() * (total - i))
            indices[i], indices[j] = indices[j], indices[i]
            ry, rx = int(coords[indices[i], 0]), int(coords[indices[i], 1])
            color = palette_choices[int(self._next_rng() * len(palette_choices))]
            surf.put(x0 + rx, y0 + ry, color)
        return picks

    def recolor(self, mapping: Mapping[str | int, str | int]) -> None:
        """Atomically remap palette indices on the active surface without swap collisions."""
        if not mapping:
            return
        surf = self.surface
        resolved_pairs = [
            (self._resolve_pal_index(src), self._resolve_pal_index(dst))
            for src, dst in mapping.items()
        ]
        snapshot = surf.data.copy()
        for src_idx, dst_idx in resolved_pairs:
            surf.data[snapshot == src_idx] = dst_idx

    def anchor(self, name: str, x: int | float, y: int | float) -> AnchorPoint:
        """Register a named `AnchorPoint` automatically shifted by active layer offsets."""
        return self._emit_anchor(name, x, y)

    def anchor_slots(
        self,
        prefix: str,
        points: Sequence[Point2D],
        *,
        start: int = 0,
    ) -> tuple[AnchorPoint, ...]:
        """Register sequential scene slot anchors (e.g. `hw_slot_0..N`)."""
        return tuple(
            self._emit_anchor(f"{prefix}{start + idx}", pt[0], pt[1])
            for idx, pt in enumerate(points)
        )

    def hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
    ) -> HitboxRect:
        """Register a named `HitboxRect` automatically shifted by active layer offsets."""
        return self._emit_hitbox(name, x, y, w, h)

    def anchor_hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        *,
        anchor_at: AnchorAlign = "bottom-center",
    ) -> tuple[AnchorPoint, HitboxRect]:
        """Register a coupled `HitboxRect` and `AnchorPoint` from one geometry block."""
        hb = self._emit_hitbox(name, x, y, w, h)
        ix = round(x)
        iy = round(y)
        iw = round(w)
        ih = round(h)
        if anchor_at == "bottom-center":
            ax, ay = ix + (iw // 2), iy + ih
        elif anchor_at == "center":
            ax, ay = ix + (iw // 2), iy + (ih // 2)
        elif anchor_at == "top-left":
            ax, ay = ix, iy
        else:
            msg = f"Unsupported anchor_at alignment: {anchor_at!r}"
            raise ValueError(msg)
        pt = self._emit_anchor(name, ax, ay)
        return (pt, hb)


class Layer(_DrawingMixin):
    """Isolated compositional drawing layer composited onto its parent on exit."""

    name: str
    offset: tuple[int, int]
    _surface: IndexedSurface
    _rng: Callable[[], float]
    _resolve_color: Callable[[str | int], int]
    _emit_anchor_cb: Callable[[Layer, str, int | float, int | float], AnchorPoint]
    _emit_hitbox_cb: Callable[
        [Layer, str, int | float, int | float, int | float, int | float],
        HitboxRect,
    ]
    _on_exit: Callable[[Layer, bool], None]

    def __init__(
        self,
        name: str,
        surface: IndexedSurface,
        offset: tuple[int, int],
        *,
        rng: Callable[[], float],
        resolve_color: Callable[[str | int], int],
        emit_anchor: Callable[[Layer, str, int | float, int | float], AnchorPoint],
        emit_hitbox: Callable[
            [Layer, str, int | float, int | float, int | float, int | float],
            HitboxRect,
        ],
        on_exit: Callable[[Layer, bool], None],
    ) -> None:
        self.name = name
        self.offset = offset
        self._surface = surface
        self._rng = rng
        self._resolve_color = resolve_color
        self._emit_anchor_cb = emit_anchor
        self._emit_hitbox_cb = emit_hitbox
        self._on_exit = on_exit

    @property
    def surface(self) -> IndexedSurface:
        return self._surface

    def _next_rng(self) -> float:
        return self._rng()

    def _resolve_pal_index(self, token_or_idx: str | int) -> int:
        return self._resolve_color(token_or_idx)

    def _emit_anchor(self, name: str, x: int | float, y: int | float) -> AnchorPoint:
        return self._emit_anchor_cb(self, name, x, y)

    def _emit_hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
    ) -> HitboxRect:
        return self._emit_hitbox_cb(self, name, x, y, w, h)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._on_exit(self, exc_type is None)


class Asset(_DrawingMixin):
    """Compositional pixel art asset builder managing framebuffer, layers, planes, and metadata."""

    spec: AssetSpec
    style: StylePack
    state: str
    frame: int
    variant: str | None
    rng: Callable[[], float]
    _pal: PaletteLookup
    _root_surface: IndexedSurface
    _layer_stack: list[_LayerFrame]
    _anchors: list[AnchorPoint]
    _hitboxes: list[HitboxRect]

    def __init__(
        self,
        spec: AssetSpec,
        style: StylePack,
        *,
        state: str | None = None,
        frame: int = 0,
        variant: str | None = None,
        token_overrides: Mapping[str, str | int] | None = None,
    ) -> None:
        active_state = spec.states[0] if state is None else state
        if active_state not in spec.states:
            msg = f"Invalid state {active_state!r} for asset {spec.id!r} (expected {spec.states})"
            raise ValueError(msg)
        if frame < 0 or frame >= spec.frames:
            msg = f"Frame {frame} out of range [0..{spec.frames - 1}] for asset {spec.id!r}"
            raise ValueError(msg)
        if variant is not None and variant not in style.variants:
            msg = f"Unknown variant {variant!r} for style {style.id!r}"
            raise ValueError(msg)

        self.spec = spec
        self.style = style
        self.state = active_state
        self.frame = int(frame)
        self.variant = variant
        self.rng = mulberry32(_derive_seed(spec.seed, active_state, self.frame))

        base_pal = PaletteLookup(style)
        if token_overrides:
            base_pal = _apply_palette_overrides(base_pal, style, token_overrides)
        self._pal = base_pal

        self._root_surface = IndexedSurface(spec.width, spec.height)
        self._layer_stack = []
        self._anchors = []
        self._hitboxes = []

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return None

    @property
    def id(self) -> str:
        return self.spec.id

    @property
    def width(self) -> int:
        return self.spec.width

    @property
    def height(self) -> int:
        return self.spec.height

    @property
    def frames(self) -> int:
        return self.spec.frames

    @property
    def fps(self) -> int:
        return self.spec.fps

    @property
    def seed(self) -> int:
        return self.spec.seed

    @property
    def pal(self) -> PaletteLookup:
        """Active fail-loud semantic palette lookup."""
        return self._pal

    @property
    def root_surface(self) -> IndexedSurface:
        """Top-level `width x height` indexed framebuffer."""
        return self._root_surface

    @property
    def surface(self) -> IndexedSurface:
        """Active surface (top-of-stack layer if open, otherwise `root_surface`)."""
        if self._layer_stack:
            return self._layer_stack[-1].surface
        return self._root_surface

    @property
    def anchors(self) -> tuple[AnchorPoint, ...]:
        """Snapshot of recorded global anchors."""
        return tuple(self._anchors)

    @property
    def hitboxes(self) -> tuple[HitboxRect, ...]:
        """Snapshot of recorded global hitboxes."""
        return tuple(self._hitboxes)

    def hashf(self, x: int, y: int, salt: int = 0) -> float:
        """Stateless deterministic `[0, 1)` coordinate hash salted by asset seed."""
        return hashf(x, y, (self.spec.seed + self.frame + salt) & 0xFFFFFFFF)

    @contextmanager
    def palette_override(self, overrides: Mapping[str, str | int]) -> Generator[PaletteLookup]:
        """Temporarily remap palette token names inside a `with` scope (e.g., avatar swaps)."""
        prev_pal = self._pal
        self._pal = _apply_palette_overrides(prev_pal, self.style, overrides)
        try:
            yield self._pal
        finally:
            self._pal = prev_pal

    def layer(
        self,
        name: str,
        *,
        offset: tuple[int, int] = (0, 0),
        size: tuple[int, int] | None = None,
        outline: int | None = None,
        sel_out: SelOutSpec | None = None,
        bevel: tuple[int, int] | None = None,
        mirror_x: bool | MirrorSource = False,
    ) -> Layer:
        """Push an isolated compositional layer composited onto its parent on exit."""
        if not name:
            msg = "Layer name must be non-empty"
            raise ValueError(msg)
        parent = self.surface
        lw, lh = size if size is not None else (parent.width, parent.height)
        layer_surf = IndexedSurface(lw, lh)
        ox, oy = int(offset[0]), int(offset[1])
        layer_obj = Layer(
            name,
            layer_surf,
            (ox, oy),
            rng=self.rng,
            resolve_color=self._resolve_pal_index,
            emit_anchor=self._emit_anchor_for_layer,
            emit_hitbox=self._emit_hitbox_for_layer,
            on_exit=self._exit_layer_callback,
        )
        self._layer_stack.append(
            _LayerFrame(
                name=name,
                surface=layer_surf,
                offset=(ox, oy),
                outline=outline,
                sel_out=sel_out,
                bevel=bevel,
                mirror_x=mirror_x,
                layer=layer_obj,
            )
        )
        return layer_obj

    def _emit_anchor_for_layer(
        self,
        layer_obj: Layer,
        name: str,
        x: int | float,
        y: int | float,
    ) -> AnchorPoint:
        ox, oy = self._offset_through(layer_obj)
        return self._record_global_anchor(name, round(x) + ox, round(y) + oy)

    def _emit_hitbox_for_layer(
        self,
        layer_obj: Layer,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
    ) -> HitboxRect:
        ox, oy = self._offset_through(layer_obj)
        return self._record_global_hitbox(name, round(x) + ox, round(y) + oy, round(w), round(h))

    def _exit_layer_callback(self, layer_obj: Layer, apply_effects: bool) -> None:
        self._exit_layer(layer_obj, apply_effects=apply_effects)

    def _exit_layer(self, layer_obj: Layer, *, apply_effects: bool) -> None:
        if not self._layer_stack or self._layer_stack[-1].layer is not layer_obj:
            msg = f"Out-of-order exit for layer {layer_obj.name!r}"
            raise RuntimeError(msg)
        frame = self._layer_stack.pop()
        if not apply_effects:
            return

        surf = frame.surface
        if frame.mirror_x:
            source: MirrorSource = "left" if frame.mirror_x is True else frame.mirror_x
            surf.mirror_x(source)
        if frame.bevel is not None:
            surf.edge_mask(top_color=frame.bevel[0], bottom_color=frame.bevel[1])
        if frame.outline is not None:
            surf.auto_outline(frame.outline)
        if frame.sel_out is not None:
            _apply_sel_out(surf, frame.sel_out)

        parent = self.surface
        parent.blit_layer(surf, frame.offset[0], frame.offset[1])

    def _current_offset(self) -> tuple[int, int]:
        ox = sum(frame.offset[0] for frame in self._layer_stack)
        oy = sum(frame.offset[1] for frame in self._layer_stack)
        return (ox, oy)

    def _offset_through(self, layer_obj: Layer) -> tuple[int, int]:
        ox = 0
        oy = 0
        for frame in self._layer_stack:
            ox += frame.offset[0]
            oy += frame.offset[1]
            if frame.layer is layer_obj:
                return (ox, oy)
        return self._current_offset()

    def _next_rng(self) -> float:
        return self.rng()

    def _resolve_pal_index(self, token_or_idx: str | int) -> int:
        if isinstance(token_or_idx, str):
            return self._pal[token_or_idx]
        idx = int(token_or_idx)
        if idx < 0 or idx > TRANSPARENT_INDEX:
            msg = f"Palette index {idx} out of range [0..{TRANSPARENT_INDEX}]"
            raise ValueError(msg)
        return idx

    def _record_global_anchor(self, name: str, gx: int, gy: int) -> AnchorPoint:
        pt = AnchorPoint(name=name, x=gx, y=gy)
        self._anchors.append(pt)
        return pt

    def _record_global_hitbox(self, name: str, gx: int, gy: int, gw: int, gh: int) -> HitboxRect:
        hb = HitboxRect(name=name, x=gx, y=gy, w=gw, h=gh)
        self._hitboxes.append(hb)
        return hb

    def _emit_anchor(self, name: str, x: int | float, y: int | float) -> AnchorPoint:
        ox, oy = self._current_offset()
        return self._record_global_anchor(name, round(x) + ox, round(y) + oy)

    def _emit_hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
    ) -> HitboxRect:
        ox, oy = self._current_offset()
        return self._record_global_hitbox(name, round(x) + ox, round(y) + oy, round(w), round(h))


def _apply_sel_out(surf: IndexedSurface, spec: SelOutSpec) -> None:
    if isinstance(spec, int):
        surf.sel_out(spec)
    elif len(spec) == 2:
        surf.sel_out(spec[0], spec[1])
    else:
        surf.sel_out(spec[0], spec[1], side_color=spec[2])
