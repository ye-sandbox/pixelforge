"""Compositional `build123d`-style Asset and Layer context-manager authoring API."""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Self, cast

import numpy as np
from numpy.typing import NDArray

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
from pixelforge.core.surface_maps import Normal3D
from pixelforge.core.types import (
    TRANSPARENT_INDEX,
    AnchorPoint,
    AssetSpec,
    HitboxRect,
    LayerRole,
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


@dataclass(frozen=True)
class LayerSemanticSpan:
    """Global opaque bounding box and mask captured from a semantic `Layer`."""

    name: str
    role: LayerRole
    x: int
    y: int
    w: int
    h: int
    mask: NDArray[np.bool_]


def _infer_layer_role(name: str) -> LayerRole:
    lower = name.lower()
    if lower in {"collision", "solid", "wall", "walls", "blocker", "colliders"} or lower.startswith(
        "collision_"
    ):
        return "collision"
    if lower in {"walkable", "floor", "floors", "ground", "path"} or lower.startswith("walkable_"):
        return "walkable"
    if lower in {"occlusion", "occluder", "roof", "canopy", "foreground"} or lower.startswith(
        "occlusion_"
    ):
        return "occlusion"
    if lower in {"interact", "trigger", "portal", "switch", "terminal"} or lower.startswith(
        "interact_"
    ):
        return "interact"
    return "visual"


@dataclass
class _LayerFrame:
    name: str
    role: LayerRole
    surface: IndexedSurface
    offset: tuple[int, int]
    outline: int | None
    sel_out: SelOutSpec | None
    bevel: tuple[int, int] | None
    mirror_x: bool | MirrorSource
    layer: Layer
    z: float | None = None


class _DrawingMixin:
    """Shared drawing, scatter, recolor, and metadata helpers for `Asset` and `Layer`."""

    @property
    def surface(self) -> IndexedSurface:
        raise NotImplementedError

    def _next_rng(self) -> float:
        raise NotImplementedError

    def _emit_anchor(
        self,
        name: str,
        x: int | float,
        y: int | float,
        *,
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> AnchorPoint:
        raise NotImplementedError

    def _emit_hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        *,
        kind: str | None = None,
    ) -> HitboxRect:
        raise NotImplementedError

    def _resolve_pal_index(self, token_or_idx: str | int) -> int:
        raise NotImplementedError

    def _make_plane(
        self,
        p0: Point2D,
        p1: Point2D,
        p2: Point2D,
        *,
        normal: Normal3D | None = None,
    ) -> Plane:
        return Plane(self.surface, p0, p1, p2, self._emit_anchor, normal=normal)

    def plane(
        self,
        p0: Point2D,
        p1: Point2D,
        p2: Point2D,
        *,
        normal: Normal3D | None = None,
    ) -> Plane:
        """Open a normalized `(u, v)` affine `Plane` context onto the active surface."""
        return self._make_plane(p0, p1, p2, normal=normal)

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

    def anchor(
        self,
        name: str,
        x: int | float,
        y: int | float,
        *,
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> AnchorPoint:
        """Register a named `AnchorPoint` automatically shifted by active layer offsets."""
        return self._emit_anchor(name, x, y, kind=kind, dir=dir)

    def anchor_slots(
        self,
        prefix: str,
        points: Sequence[Point2D],
        *,
        start: int = 0,
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> tuple[AnchorPoint, ...]:
        """Register sequential scene slot anchors (e.g. `hw_slot_0..N`)."""
        return tuple(
            self._emit_anchor(f"{prefix}{start + idx}", pt[0], pt[1], kind=kind, dir=dir)
            for idx, pt in enumerate(points)
        )

    def hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        *,
        kind: str | None = None,
    ) -> HitboxRect:
        """Register a named `HitboxRect` automatically shifted by active layer offsets."""
        return self._emit_hitbox(name, x, y, w, h, kind=kind)

    def anchor_hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        *,
        anchor_at: AnchorAlign = "bottom-center",
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> tuple[AnchorPoint, HitboxRect]:
        """Register a coupled `HitboxRect` and `AnchorPoint` from one geometry block."""
        hb = self._emit_hitbox(name, x, y, w, h, kind=kind)
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
        pt = self._emit_anchor(name, ax, ay, kind=kind, dir=dir)
        return (pt, hb)


class Layer(_DrawingMixin):
    """Isolated compositional drawing layer composited onto its parent on exit."""

    name: str
    offset: tuple[int, int]
    _surface: IndexedSurface
    _rng: Callable[[], float]
    _resolve_color: Callable[[str | int], int]
    _emit_anchor_cb: Callable[
        [Layer, str, int | float, int | float, str | None, tuple[int, int] | None],
        AnchorPoint,
    ]
    _emit_hitbox_cb: Callable[
        [Layer, str, int | float, int | float, int | float, int | float, str | None],
        HitboxRect,
    ]
    _on_enter: Callable[[Layer], None]
    _on_exit: Callable[[Layer, bool], None]

    def __init__(
        self,
        name: str,
        surface: IndexedSurface,
        offset: tuple[int, int],
        *,
        rng: Callable[[], float],
        resolve_color: Callable[[str | int], int],
        emit_anchor: Callable[
            [Layer, str, int | float, int | float, str | None, tuple[int, int] | None],
            AnchorPoint,
        ],
        emit_hitbox: Callable[
            [Layer, str, int | float, int | float, int | float, int | float, str | None],
            HitboxRect,
        ],
        on_enter: Callable[[Layer], None],
        on_exit: Callable[[Layer, bool], None],
    ) -> None:
        self.name = name
        self.offset = offset
        self._surface = surface
        self._rng = rng
        self._resolve_color = resolve_color
        self._emit_anchor_cb = emit_anchor
        self._emit_hitbox_cb = emit_hitbox
        self._on_enter = on_enter
        self._on_exit = on_exit

    @property
    def surface(self) -> IndexedSurface:
        return self._surface

    def _next_rng(self) -> float:
        return self._rng()

    def _resolve_pal_index(self, token_or_idx: str | int) -> int:
        return self._resolve_color(token_or_idx)

    def _emit_anchor(
        self,
        name: str,
        x: int | float,
        y: int | float,
        *,
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> AnchorPoint:
        return self._emit_anchor_cb(self, name, x, y, kind, dir)

    def _emit_hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        *,
        kind: str | None = None,
    ) -> HitboxRect:
        return self._emit_hitbox_cb(self, name, x, y, w, h, kind)

    def __enter__(self) -> Self:
        self._on_enter(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._on_exit(self, exc_type is None)


class Asset[PalT = PaletteLookup](_DrawingMixin):
    """Compositional pixel art asset builder managing framebuffer, layers, planes, and metadata."""

    spec: AssetSpec
    style: StylePack
    state: str
    frame: int
    variant: str | None
    rng: Callable[[], float]
    _pal: PalT
    _root_surface: IndexedSurface
    _layer_stack: list[_LayerFrame]
    _anchors: list[AnchorPoint]
    _hitboxes: list[HitboxRect]
    _layer_spans: list[LayerSemanticSpan]

    def __init__(
        self,
        spec: AssetSpec,
        style: StylePack,
        *,
        state: str | None = None,
        frame: int = 0,
        variant: str | None = None,
        token_overrides: Mapping[str, str | int] | None = None,
        track_maps: bool = False,
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
            base_pal = base_pal.with_overrides(token_overrides)
        self._pal = cast(PalT, base_pal)

        self._root_surface = IndexedSurface(spec.width, spec.height, track_maps=track_maps)
        self._layer_stack = []
        self._anchors = []
        self._hitboxes = []
        self._layer_spans = []

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
    def pal(self) -> PalT:
        """Active fail-loud semantic palette lookup."""
        return self._pal

    @property
    def root_surface(self) -> IndexedSurface:
        """Top-level `width x height` indexed framebuffer."""
        return self._root_surface

    @property
    def normal_map(self) -> NDArray[np.float32] | None:
        """Derived `(H, W, 3)` camera-space normal map when `track_maps=True`."""
        maps = self._root_surface.maps
        return maps.normals if maps is not None else None

    @property
    def height_map(self) -> NDArray[np.float32] | None:
        """Derived `(H, W)` surface height map when `track_maps=True`."""
        maps = self._root_surface.maps
        return maps.height_data if maps is not None else None

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

    @property
    def layer_spans(self) -> tuple[LayerSemanticSpan, ...]:
        """Snapshot of recorded semantic layer spans."""
        return tuple(self._layer_spans)

    def hashf(self, x: int, y: int, salt: int = 0) -> float:
        """Stateless deterministic `[0, 1)` coordinate hash salted by asset seed."""
        return hashf(x, y, (self.spec.seed + self.frame + salt) & 0xFFFFFFFF)

    @contextmanager
    def palette_override(
        self,
        overrides: Mapping[str, str | int] | None = None,
        /,
        **kw_overrides: str | int,
    ) -> Generator[PalT]:
        """Temporarily remap palette token names inside a `with` scope (e.g., avatar swaps)."""
        prev_pal = self._pal
        self._pal = cast(
            PalT,
            cast(PaletteLookup, prev_pal).with_overrides(overrides, **kw_overrides),
        )
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
        role: LayerRole | None = None,
        z: float | None = None,
    ) -> Layer:
        """Push an isolated compositional layer composited onto its parent on exit."""
        if not name:
            msg = "Layer name must be non-empty"
            raise ValueError(msg)
        resolved_role = role if role is not None else _infer_layer_role(name)
        parent = self.surface
        lw, lh = size if size is not None else (parent.width, parent.height)
        layer_surf = IndexedSurface(lw, lh, track_maps=self._root_surface.has_maps)
        ox, oy = int(offset[0]), int(offset[1])
        layer_frame: list[_LayerFrame] = []

        def _enter_layer(_layer: Layer) -> None:
            self._layer_stack.append(layer_frame[0])

        layer_obj = Layer(
            name,
            layer_surf,
            (ox, oy),
            rng=self.rng,
            resolve_color=self._resolve_pal_index,
            emit_anchor=self._emit_anchor_for_layer,
            emit_hitbox=self._emit_hitbox_for_layer,
            on_enter=_enter_layer,
            on_exit=self._exit_layer_callback,
        )
        # INVARIANT: Push onto `_layer_stack` only inside `Layer.__enter__` so unentered
        # `a.layer(...)` handles cannot leak onto the stack and corrupt subsequent draws.
        layer_frame.append(
            _LayerFrame(
                name=name,
                role=resolved_role,
                surface=layer_surf,
                offset=(ox, oy),
                outline=outline,
                sel_out=sel_out,
                bevel=bevel,
                mirror_x=mirror_x,
                layer=layer_obj,
                z=z,
            )
        )
        return layer_obj

    def _emit_anchor_for_layer(
        self,
        layer_obj: Layer,
        name: str,
        x: int | float,
        y: int | float,
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> AnchorPoint:
        ox, oy = self._offset_through(layer_obj)
        return self._record_global_anchor(name, round(x) + ox, round(y) + oy, kind=kind, dir=dir)

    def _emit_hitbox_for_layer(
        self,
        layer_obj: Layer,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        kind: str | None = None,
    ) -> HitboxRect:
        ox, oy = self._offset_through(layer_obj)
        return self._record_global_hitbox(
            name,
            round(x) + ox,
            round(y) + oy,
            round(w),
            round(h),
            kind=kind,
        )

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

        if frame.role != "visual":
            self._record_layer_span(frame, surf)

        parent = self.surface
        z_offset = 0.0
        if parent.maps is not None and surf.maps is not None:
            z_offset = _compute_layer_z_offset(
                parent,
                surf,
                frame.offset[0],
                frame.offset[1],
                explicit_z=frame.z,
            )
        parent.blit_layer(surf, frame.offset[0], frame.offset[1], z_offset=z_offset)

    def _record_layer_span(self, frame: _LayerFrame, surf: IndexedSurface) -> None:
        ys, xs = np.nonzero(surf.data != TRANSPARENT_INDEX)
        if len(xs) == 0:
            return
        parent_ox, parent_oy = self._current_offset()
        gx_off = parent_ox + frame.offset[0]
        gy_off = parent_oy + frame.offset[1]
        min_x = int(xs.min())
        max_x = int(xs.max())
        min_y = int(ys.min())
        max_y = int(ys.max())
        patch = (surf.data[min_y : max_y + 1, min_x : max_x + 1] != TRANSPARENT_INDEX).copy()
        self._layer_spans.append(
            LayerSemanticSpan(
                name=frame.name,
                role=frame.role,
                x=gx_off + min_x,
                y=gy_off + min_y,
                w=max_x - min_x + 1,
                h=max_y - min_y + 1,
                mask=patch,
            )
        )

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
            return cast(PaletteLookup, self._pal)[token_or_idx]
        idx = int(token_or_idx)
        if idx < 0 or idx > TRANSPARENT_INDEX:
            msg = f"Palette index {idx} out of range [0..{TRANSPARENT_INDEX}]"
            raise ValueError(msg)
        return idx

    def _record_global_anchor(
        self,
        name: str,
        gx: int,
        gy: int,
        *,
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> AnchorPoint:
        pt = AnchorPoint(name=name, x=gx, y=gy, kind=kind, dir=dir)
        self._anchors.append(pt)
        return pt

    def _record_global_hitbox(
        self,
        name: str,
        gx: int,
        gy: int,
        gw: int,
        gh: int,
        *,
        kind: str | None = None,
    ) -> HitboxRect:
        hb = HitboxRect(name=name, x=gx, y=gy, w=gw, h=gh, kind=kind)
        self._hitboxes.append(hb)
        return hb

    def _emit_anchor(
        self,
        name: str,
        x: int | float,
        y: int | float,
        *,
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> AnchorPoint:
        ox, oy = self._current_offset()
        return self._record_global_anchor(name, round(x) + ox, round(y) + oy, kind=kind, dir=dir)

    def _emit_hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        *,
        kind: str | None = None,
    ) -> HitboxRect:
        ox, oy = self._current_offset()
        return self._record_global_hitbox(
            name,
            round(x) + ox,
            round(y) + oy,
            round(w),
            round(h),
            kind=kind,
        )


def _compute_layer_z_offset(
    parent: IndexedSurface,
    child: IndexedSurface,
    ox: int,
    oy: int,
    *,
    explicit_z: float | None,
) -> float:
    if explicit_z is not None:
        return float(explicit_z)
    if parent.maps is None or child.maps is None:
        return 0.0
    sx0 = max(0, -ox)
    sy0 = max(0, -oy)
    tx0 = max(0, ox)
    ty0 = max(0, oy)
    copy_w = min(child.width - sx0, parent.width - tx0)
    copy_h = min(child.height - sy0, parent.height - ty0)
    if copy_w > 0 and copy_h > 0:
        src_opaque = child.data[sy0 : sy0 + copy_h, sx0 : sx0 + copy_w] != TRANSPARENT_INDEX
        dst_opaque = parent.data[ty0 : ty0 + copy_h, tx0 : tx0 + copy_w] != TRANSPARENT_INDEX
        overlap = src_opaque & dst_opaque
        if np.any(overlap):
            parent_h = parent.maps.height_data[ty0 : ty0 + copy_h, tx0 : tx0 + copy_w]
            return float(np.max(parent_h[overlap])) + 1.0
    child_opaque = child.data != TRANSPARENT_INDEX
    if np.any(child_opaque) and float(np.max(child.maps.height_data[child_opaque])) == 0.0:
        return 1.0
    return 0.0


def _apply_sel_out(surf: IndexedSurface, spec: SelOutSpec) -> None:
    if isinstance(spec, int):
        surf.sel_out(spec)
    elif len(spec) == 2:
        surf.sel_out(spec[0], spec[1])
    else:
        surf.sel_out(spec[0], spec[1], side_color=spec[2])
