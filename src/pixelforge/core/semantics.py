"""Deterministic gameplay semantics derivation from Asset, Layer, Hitbox, and Tilemap geometry."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.builder import LayerSemanticSpan
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import (
    TRANSPARENT_INDEX,
    AnchorPoint,
    AssetSpec,
    GameplaySemantics,
    HitboxRect,
    SemanticGrid,
    SemanticPoint,
    SemanticZone,
    TilemapSpec,
)

_COLLISION_KINDS = frozenset({"collision", "solid", "wall", "walls", "blocker"})
_WALKABLE_KINDS = frozenset({"walkable", "floor", "floors", "ground", "path"})
_OCCLUSION_KINDS = frozenset({"occlusion", "occluder", "roof", "canopy"})
_INTERACT_KINDS = frozenset({"interact", "trigger", "portal", "switch", "terminal"})
_PIVOT_NAMES = frozenset({"y_sort_pivot", "pivot", "base", "origin"})


def _opaque_bbox(surface: IndexedSurface) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(surface.data != TRANSPARENT_INDEX)
    if len(xs) == 0:
        return None
    x0 = int(xs.min())
    y0 = int(ys.min())
    x1 = int(xs.max())
    y1 = int(ys.max())
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def _derive_y_sort_pivot(
    spec: AssetSpec,
    anchors: Sequence[AnchorPoint],
    bbox: tuple[int, int, int, int] | None,
) -> SemanticPoint:
    for anchor in anchors:
        if anchor.kind == "pivot" or anchor.name.lower() in _PIVOT_NAMES:
            return SemanticPoint(x=anchor.x, y=anchor.y)
    if bbox is not None:
        bx, by, bw, bh = bbox
        return SemanticPoint(x=bx + (bw // 2), y=by + bh)
    return SemanticPoint(x=spec.width // 2, y=spec.height)


def _fill_rect(mask: NDArray[np.bool_], x: int, y: int, w: int, h: int) -> None:
    mh, mw = mask.shape
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(mw, x + w)
    y1 = min(mh, y + h)
    if x0 < x1 and y0 < y1:
        mask[y0:y1, x0:x1] = True


def _stamp_span(mask: NDArray[np.bool_], span: LayerSemanticSpan) -> None:
    mh, mw = mask.shape
    x0 = max(0, span.x)
    y0 = max(0, span.y)
    x1 = min(mw, span.x + span.w)
    y1 = min(mh, span.y + span.h)
    if x0 >= x1 or y0 >= y1:
        return
    sx0 = x0 - span.x
    sy0 = y0 - span.y
    sx1 = sx0 + (x1 - x0)
    sy1 = sy0 + (y1 - y0)
    mask[y0:y1, x0:x1] |= span.mask[sy0:sy1, sx0:sx1]


def _apply_tilemap_masks(
    tm: TilemapSpec,
    surface: IndexedSurface,
    collision_px: NDArray[np.bool_],
    walkable_px: NDArray[np.bool_],
) -> None:
    terrain = tm.terrain_name.lower()
    target = (
        collision_px
        if terrain in _COLLISION_KINDS
        else (walkable_px if terrain in _WALKABLE_KINDS else None)
    )
    if target is None:
        return

    opaque = surface.data != TRANSPARENT_INDEX
    for idx, _bitmask in enumerate(tm.bitmasks):
        col = idx % tm.columns
        row = idx // tm.columns
        tx = tm.margin + col * (tm.tile_width + tm.spacing)
        ty = tm.margin + row * (tm.tile_height + tm.spacing)
        x0 = max(0, tx)
        y0 = max(0, ty)
        x1 = min(surface.width, tx + tm.tile_width)
        y1 = min(surface.height, ty + tm.tile_height)
        if x0 < x1 and y0 < y1 and bool(opaque[y0:y1, x0:x1].any()):
            target[y0:y1, x0:x1] |= opaque[y0:y1, x0:x1]


def _downsample_grid(
    mask: NDArray[np.bool_],
    cell_w: int,
    cell_h: int,
    cols: int,
    rows: int,
) -> SemanticGrid:
    cells: list[int] = []
    mh, mw = mask.shape
    for r in range(rows):
        y0 = r * cell_h
        y1 = min(mh, y0 + cell_h)
        for c in range(cols):
            x0 = c * cell_w
            x1 = min(mw, x0 + cell_w)
            occupied = y0 < y1 and x0 < x1 and bool(mask[y0:y1, x0:x1].any())
            cells.append(1 if occupied else 0)
    return SemanticGrid(
        cell_width=cell_w,
        cell_height=cell_h,
        columns=cols,
        rows=rows,
        cells=tuple(cells),
    )


def _derive_occlusion_zones(
    hitboxes: Sequence[HitboxRect],
    layer_spans: Sequence[LayerSemanticSpan],
    bbox: tuple[int, int, int, int] | None,
    pivot: SemanticPoint,
    cell_h: int,
) -> tuple[SemanticZone, ...]:
    zones: list[SemanticZone] = []
    for span in layer_spans:
        if span.role == "occlusion":
            zones.append(
                SemanticZone(
                    name=span.name,
                    x=span.x,
                    y=span.y,
                    w=span.w,
                    h=span.h,
                    kind="occlusion",
                )
            )
    for hb in hitboxes:
        if hb.kind in _OCCLUSION_KINDS:
            zones.append(
                SemanticZone(
                    name=hb.name,
                    x=hb.x,
                    y=hb.y,
                    w=hb.w,
                    h=hb.h,
                    kind=hb.kind,
                )
            )

    if not zones and bbox is not None:
        bx, by, bw, _bh = bbox
        overhead_h = pivot.y - by - cell_h
        if overhead_h >= 4:
            zones.append(
                SemanticZone(
                    name="upper_silhouette",
                    x=bx,
                    y=by,
                    w=bw,
                    h=overhead_h,
                    kind="occlusion",
                )
            )
    return tuple(zones)


def _derive_interact_zones(
    spec: AssetSpec,
    anchors: Sequence[AnchorPoint],
    hitboxes: Sequence[HitboxRect],
    layer_spans: Sequence[LayerSemanticSpan],
) -> tuple[SemanticZone, ...]:
    zones: list[SemanticZone] = []
    seen_names: set[str] = set()

    for span in layer_spans:
        if span.role == "interact":
            zones.append(
                SemanticZone(
                    name=span.name,
                    x=span.x,
                    y=span.y,
                    w=span.w,
                    h=span.h,
                    kind="interact",
                )
            )
            seen_names.add(span.name)

    for hb in hitboxes:
        if hb.kind in _INTERACT_KINDS:
            zones.append(
                SemanticZone(
                    name=hb.name,
                    x=hb.x,
                    y=hb.y,
                    w=hb.w,
                    h=hb.h,
                    kind=hb.kind,
                )
            )
            seen_names.add(hb.name)

    box_w = min(16, spec.width)
    box_h = min(16, spec.height)
    for anchor in anchors:
        if anchor.kind in _INTERACT_KINDS and anchor.name not in seen_names:
            zx = max(0, min(spec.width - box_w, anchor.x - box_w // 2))
            zy = max(0, min(spec.height - box_h, anchor.y - box_h // 2))
            zones.append(
                SemanticZone(
                    name=anchor.name,
                    x=zx,
                    y=zy,
                    w=box_w,
                    h=box_h,
                    kind=anchor.kind,
                )
            )
            seen_names.add(anchor.name)

    return tuple(zones)


def derive_gameplay_semantics(
    spec: AssetSpec,
    surface: IndexedSurface,
    *,
    anchors: Sequence[AnchorPoint] = (),
    hitboxes: Sequence[HitboxRect] = (),
    layer_spans: Sequence[LayerSemanticSpan] = (),
    cell_size: int | None = None,
) -> GameplaySemantics:
    """Derive deterministic collision, walkability, y-sort pivot, and zones from geometry."""
    if spec.tilemap is not None:
        cell_w = spec.tilemap.tile_width
        cell_h = spec.tilemap.tile_height
    elif cell_size is not None:
        if cell_size <= 0:
            msg = f"cell_size must be > 0, got {cell_size}"
            raise ValueError(msg)
        cell_w = min(cell_size, spec.width)
        cell_h = min(cell_size, spec.height)
    else:
        cell_w = min(8, spec.width)
        cell_h = min(8, spec.height)

    cols = max(1, (spec.width + cell_w - 1) // cell_w)
    rows = max(1, (spec.height + cell_h - 1) // cell_h)

    bbox = _opaque_bbox(surface)
    pivot = _derive_y_sort_pivot(spec, anchors, bbox)

    collision_px = np.zeros((spec.height, spec.width), dtype=bool)
    walkable_px = np.zeros((spec.height, spec.width), dtype=bool)

    if spec.tilemap is not None:
        _apply_tilemap_masks(spec.tilemap, surface, collision_px, walkable_px)

    for span in layer_spans:
        if span.role == "collision":
            _stamp_span(collision_px, span)
        elif span.role == "walkable":
            _stamp_span(walkable_px, span)

    for hb in hitboxes:
        if hb.kind in _COLLISION_KINDS or (
            hb.kind is None and hb.name.lower().startswith(("collision", "solid"))
        ):
            _fill_rect(collision_px, hb.x, hb.y, hb.w, hb.h)
        elif hb.kind in _WALKABLE_KINDS:
            _fill_rect(walkable_px, hb.x, hb.y, hb.w, hb.h)

    # INVARIANT: When no explicit collision/walkable layer or hitbox is declared,
    # fall back to the ground-plane footprint around `y_sort_pivot` for solid props.
    if not bool(collision_px.any()) and not bool(walkable_px.any()) and bbox is not None:
        bx, by, bw, bh = bbox
        foot_h = min(cell_h, max(1, bh // 3))
        foot_y = max(by, min(spec.height - 1, pivot.y - foot_h))
        _fill_rect(collision_px, bx, foot_y, bw, foot_h)

    if not bool(walkable_px.any()):
        walkable_px = ~collision_px

    collision_grid = _downsample_grid(collision_px, cell_w, cell_h, cols, rows)
    # INVARIANT: Collision cells always block walkability at the cell resolution.
    walkable_raw = _downsample_grid(walkable_px, cell_w, cell_h, cols, rows)
    walkable_cells = tuple(
        0 if c == 1 else w for c, w in zip(collision_grid.cells, walkable_raw.cells, strict=True)
    )
    walkable_mask = SemanticGrid(
        cell_width=cell_w,
        cell_height=cell_h,
        columns=cols,
        rows=rows,
        cells=walkable_cells,
    )

    occlusion_zones = _derive_occlusion_zones(hitboxes, layer_spans, bbox, pivot, cell_h)
    interact_zones = _derive_interact_zones(spec, anchors, hitboxes, layer_spans)

    return GameplaySemantics(
        y_sort_pivot=pivot,
        collision_grid=collision_grid,
        walkable_mask=walkable_mask,
        occlusion_zones=occlusion_zones,
        interact_zones=interact_zones,
    )
