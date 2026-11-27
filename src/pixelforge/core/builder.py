"""Compositional `build123d`-style Asset and Layer context-manager authoring API."""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Self, cast

import numpy as np
from numpy.typing import NDArray

from pixelforge.core._drawing_mixin import (
    AnchorAlign,
    DrawingMixin,
    ScatterMask,
    SelOutSpec,
)
from pixelforge.core.palette import PaletteLookup
from pixelforge.core.prng import hashf, mulberry32
from pixelforge.core.surface import IndexedSurface, MirrorSource
from pixelforge.core.types import (
    TRANSPARENT_INDEX,
    AnchorPoint,
    AssetSpec,
    HitboxRect,
    LayerRole,
    LightingAngle,
    StylePack,
)


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


@dataclass(frozen=True)
class LayerDiagnostic:
    """Per-layer bounding box and pixel count captured when `track_layers=True`."""

    name: str
    role: LayerRole
    depth: int
    offset: tuple[int, int]
    size: tuple[int, int]
    opaque_bbox: tuple[int, int, int, int] | None
    pixel_count: int


@dataclass(frozen=True)
class CapturedLayer:
    """Isolated full-canvas surface for a single `with a.layer(...)` block."""

    name: str
    role: LayerRole
    depth: int
    offset: tuple[int, int]
    opaque_bbox: tuple[int, int, int, int] | None
    pixel_count: int
    surface: IndexedSurface


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


LayerClip = Literal["none", "opaque"]


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
    clip: LayerClip = "none"


class Layer(DrawingMixin):
    """Isolated compositional drawing layer composited onto its parent on exit."""

    name: str
    offset: tuple[int, int]
    _surface: IndexedSurface
    _rng: Callable[[], float]
    _resolve_color: Callable[[str | int], int]
    _resolve_ramp_cb: Callable[[str | Sequence[int]], tuple[int, ...]] | None
    _lighting_angle: LightingAngle
    _outline_index: int | None
    _style: StylePack | None
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
        resolve_ramp: Callable[[str | Sequence[int]], tuple[int, ...]] | None = None,
        lighting_angle: LightingAngle = "top-left",
        outline_index: int | None = None,
        style: StylePack | None = None,
    ) -> None:
        self.name = name
        self.offset = offset
        self._surface = surface
        self._rng = rng
        self._resolve_color = resolve_color
        self._resolve_ramp_cb = resolve_ramp
        self._lighting_angle = lighting_angle
        self._outline_index = outline_index
        self._style = style
        self._emit_anchor_cb = emit_anchor
        self._emit_hitbox_cb = emit_hitbox
        self._on_enter = on_enter
        self._on_exit = on_exit

    @property
    def surface(self) -> IndexedSurface:
        return self._surface

    @property
    def style(self) -> StylePack | None:
        """Bound `StylePack` for this layer when created from an `Asset`."""
        return self._style

    def _next_rng(self) -> float:
        return self._rng()

    def _resolve_pal_index(self, token_or_idx: str | int) -> int:
        return self._resolve_color(token_or_idx)

    def _resolve_pal_ramp(self, ramp: str | Sequence[int]) -> tuple[int, ...]:
        if self._resolve_ramp_cb is not None:
            return self._resolve_ramp_cb(ramp)
        if isinstance(ramp, str):
            msg = f"Layer {self.name!r} has no bound StylePack to resolve ramp {ramp!r}"
            raise ValueError(msg)
        return tuple(int(c) for c in ramp)

    def _default_lighting_angle(self) -> LightingAngle:
        return self._lighting_angle

    def _default_outline_index(self) -> int | None:
        return self._outline_index

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


class Asset[PalT = PaletteLookup](DrawingMixin):
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
    _events: list[str]
    _layer_spans: list[LayerSemanticSpan]
    _track_layers: bool
    _layer_diagnostics: list[LayerDiagnostic]
    _capture_layers: bool
    _captured_layers: list[CapturedLayer]

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
        track_layers: bool = False,
        capture_layers: bool = False,
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
        self._events = []
        self._layer_spans = []
        self._track_layers = track_layers
        self._layer_diagnostics = []
        self._capture_layers = capture_layers
        self._captured_layers = []

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
    def events(self) -> tuple[str, ...]:
        """Snapshot of recorded per-frame event tags."""
        return tuple(self._events)

    def event(self, name: str) -> str:
        """Emit a deterministic per-(state, frame) event tag (e.g. `footstep`, `spark`)."""
        if not name or not name.strip():
            msg = f"Event tag for asset {self.spec.id!r} must be a non-empty string"
            raise ValueError(msg)
        if name not in self._events:
            self._events.append(name)
        return name

    @property
    def layer_spans(self) -> tuple[LayerSemanticSpan, ...]:
        """Snapshot of recorded semantic layer spans."""
        return tuple(self._layer_spans)

    @property
    def layer_diagnostics(self) -> tuple[LayerDiagnostic, ...]:
        """Snapshot of per-layer bounding boxes and pixel counts (`track_layers=True`)."""
        return tuple(self._layer_diagnostics)

    @property
    def captured_layers(self) -> tuple[CapturedLayer, ...]:
        """Snapshot of isolated per-layer surfaces (`capture_layers=True`)."""
        return tuple(self._captured_layers)

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
        clip: LayerClip = "none",
    ) -> Layer:
        """Push an isolated compositional layer composited onto its parent on exit."""
        if not name:
            msg = "Layer name must be non-empty"
            raise ValueError(msg)
        if clip not in ("none", "opaque"):
            msg = f"Unsupported layer clip mode: {clip!r}"
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
            resolve_ramp=self._resolve_pal_ramp,
            lighting_angle=self.style.lighting_angle,
            outline_index=self.style.outline_index,
            style=self.style,
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
                clip=clip,
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

        parent = self.surface
        if frame.clip == "opaque":
            _clip_surface_to_parent(surf, parent, frame.offset[0], frame.offset[1])

        if frame.role != "visual":
            self._record_layer_span(frame, surf)
        if self._track_layers:
            self._record_layer_diagnostic(frame, surf, depth=len(self._layer_stack))
        if self._capture_layers:
            self._record_captured_layer(frame, surf, depth=len(self._layer_stack))

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

    def _record_layer_diagnostic(
        self,
        frame: _LayerFrame,
        surf: IndexedSurface,
        *,
        depth: int,
    ) -> None:
        ys, xs = np.nonzero(surf.data != TRANSPARENT_INDEX)
        parent_ox, parent_oy = self._current_offset()
        gx_off = parent_ox + frame.offset[0]
        gy_off = parent_oy + frame.offset[1]
        if len(xs) == 0:
            bbox: tuple[int, int, int, int] | None = None
            pixel_count = 0
        else:
            min_x = int(xs.min())
            max_x = int(xs.max())
            min_y = int(ys.min())
            max_y = int(ys.max())
            bbox = (gx_off + min_x, gy_off + min_y, max_x - min_x + 1, max_y - min_y + 1)
            pixel_count = len(xs)
        self._layer_diagnostics.append(
            LayerDiagnostic(
                name=frame.name,
                role=frame.role,
                depth=depth,
                offset=frame.offset,
                size=(surf.width, surf.height),
                opaque_bbox=bbox,
                pixel_count=pixel_count,
            )
        )

    def _record_captured_layer(
        self,
        frame: _LayerFrame,
        surf: IndexedSurface,
        *,
        depth: int,
    ) -> None:
        parent_ox, parent_oy = self._current_offset()
        gx_off = parent_ox + frame.offset[0]
        gy_off = parent_oy + frame.offset[1]
        isolated = IndexedSurface(self._root_surface.width, self._root_surface.height)
        isolated.blit_layer(surf, gx_off, gy_off)
        ys, xs = np.nonzero(isolated.data != TRANSPARENT_INDEX)
        if len(xs) == 0:
            bbox: tuple[int, int, int, int] | None = None
            pixel_count = 0
        else:
            min_x = int(xs.min())
            max_x = int(xs.max())
            min_y = int(ys.min())
            max_y = int(ys.max())
            bbox = (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
            pixel_count = len(xs)
        self._captured_layers.append(
            CapturedLayer(
                name=frame.name,
                role=frame.role,
                depth=depth,
                offset=(gx_off, gy_off),
                opaque_bbox=bbox,
                pixel_count=pixel_count,
                surface=isolated,
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

    def _resolve_pal_ramp(self, ramp: str | Sequence[int]) -> tuple[int, ...]:
        if isinstance(ramp, str):
            return cast(PaletteLookup, self._pal).ramp(ramp)
        return tuple(self._resolve_pal_index(c) for c in ramp)

    def _default_lighting_angle(self) -> LightingAngle:
        return self.style.lighting_angle

    def _default_outline_index(self) -> int | None:
        return self.style.outline_index

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


def _clip_surface_to_parent(
    surf: IndexedSurface,
    parent: IndexedSurface,
    ox: int,
    oy: int,
) -> None:
    """Alpha-lock `surf` so only pixels overlapping opaque pixels of `parent` survive."""
    keep = np.zeros((surf.height, surf.width), dtype=bool)
    sx0 = max(0, -ox)
    sy0 = max(0, -oy)
    tx0 = max(0, ox)
    ty0 = max(0, oy)
    copy_w = min(surf.width - sx0, parent.width - tx0)
    copy_h = min(surf.height - sy0, parent.height - ty0)
    if copy_w > 0 and copy_h > 0:
        parent_opaque = parent.data[ty0 : ty0 + copy_h, tx0 : tx0 + copy_w] != TRANSPARENT_INDEX
        keep[sy0 : sy0 + copy_h, sx0 : sx0 + copy_w] = parent_opaque
    erase_mask = (surf.data != TRANSPARENT_INDEX) & (~keep)
    if not np.any(erase_mask):
        return
    surf.data[erase_mask] = TRANSPARENT_INDEX
    if surf.maps is not None:
        surf.maps.write_global_mask(erase_mask, erase=True)


def _apply_sel_out(surf: IndexedSurface, spec: SelOutSpec) -> None:
    if isinstance(spec, int):
        surf.sel_out(spec)
    elif len(spec) == 2:
        surf.sel_out(spec[0], spec[1])
    else:
        surf.sel_out(spec[0], spec[1], side_color=spec[2])


__all__ = [
    "AnchorAlign",
    "Asset",
    "Layer",
    "LayerClip",
    "LayerSemanticSpan",
    "ScatterMask",
    "SelOutSpec",
]
