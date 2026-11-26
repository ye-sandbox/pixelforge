"""Tile-metadata atlas exporters for Tiled, Godot, and Phaser."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pixelforge._version import __version__
from pixelforge.core.tilemap import (
    BLOB_E,
    BLOB_N,
    BLOB_NE,
    BLOB_NW,
    BLOB_S,
    BLOB_SE,
    BLOB_SW,
    BLOB_W,
    CARDINAL_E,
    CARDINAL_N,
    CARDINAL_S,
    CARDINAL_W,
    reduce_blob_mask,
)
from pixelforge.core.types import AssetSpec, AutotileMode, TilemapSpec
from pixelforge.export.atlas import resolve_atlas_image_name

TileAtlasFormat = Literal["tiled", "godot", "phaser", "all"]


@dataclass(frozen=True)
class TileEntry:
    """Normalized tile entry within a compiled autotile sheet."""

    index: int
    bitmask: int
    col: int
    row: int
    x: int
    y: int
    w: int
    h: int
    peering_bits: dict[str, int]


def _peering_bits(mask: int, mode: AutotileMode) -> dict[str, int]:
    if mode == "cardinal16":
        return {
            "top": int(bool(mask & CARDINAL_N)),
            "right": int(bool(mask & CARDINAL_E)),
            "bottom": int(bool(mask & CARDINAL_S)),
            "left": int(bool(mask & CARDINAL_W)),
        }
    reduced = reduce_blob_mask(mask)
    return {
        "top": int(bool(reduced & BLOB_N)),
        "top_right": int(bool(reduced & BLOB_NE)),
        "right": int(bool(reduced & BLOB_E)),
        "bottom_right": int(bool(reduced & BLOB_SE)),
        "bottom": int(bool(reduced & BLOB_S)),
        "bottom_left": int(bool(reduced & BLOB_SW)),
        "left": int(bool(reduced & BLOB_W)),
        "top_left": int(bool(reduced & BLOB_NW)),
    }


def _require_tilemap(spec: AssetSpec) -> TilemapSpec:
    if spec.tilemap is None:
        msg = f"AssetSpec {spec.id!r} does not define tilemap metadata"
        raise ValueError(msg)
    return spec.tilemap


def build_tile_entries(spec: AssetSpec, *, scale: int = 1) -> list[TileEntry]:
    """Compute scaled tile coordinates and peering-bit metadata for `spec.tilemap`."""
    if scale < 1:
        msg = f"scale must be >= 1, got {scale}"
        raise ValueError(msg)
    tm = _require_tilemap(spec)
    entries: list[TileEntry] = []
    for idx, mask in enumerate(tm.bitmasks):
        col = idx % tm.columns
        row = idx // tm.columns
        x = (tm.margin + col * (tm.tile_width + tm.spacing)) * scale
        y = (tm.margin + row * (tm.tile_height + tm.spacing)) * scale
        entries.append(
            TileEntry(
                index=idx,
                bitmask=mask,
                col=col,
                row=row,
                x=x,
                y=y,
                w=tm.tile_width * scale,
                h=tm.tile_height * scale,
                peering_bits=_peering_bits(mask, tm.mode),
            )
        )
    return entries


def _tiled_wangid(peering: Mapping[str, int]) -> list[int]:
    # Tiled WangID order: [top, top-right, right, bottom-right, bottom, bottom-left, left, top-left]
    return [
        peering.get("top", 0),
        peering.get("top_right", 0),
        peering.get("right", 0),
        peering.get("bottom_right", 0),
        peering.get("bottom", 0),
        peering.get("bottom_left", 0),
        peering.get("left", 0),
        peering.get("top_left", 0),
    ]


def build_tiled_tileset(
    spec: AssetSpec,
    *,
    scale: int = 1,
    image_name: str | None = None,
) -> dict[str, object]:
    """Build a Tiled `.tsj` JSON tileset document with Wang terrain metadata."""
    tm = _require_tilemap(spec)
    entries = build_tile_entries(spec, scale=scale)
    wang_type = "edge" if tm.mode == "cardinal16" else "mixed"

    tiles: list[dict[str, object]] = []
    wang_tiles: list[dict[str, object]] = []
    for entry in entries:
        tiles.append(
            {
                "id": entry.index,
                "properties": [
                    {"name": "bitmask", "type": "int", "value": entry.bitmask},
                    {"name": "mode", "type": "string", "value": tm.mode},
                    {"name": "col", "type": "int", "value": entry.col},
                    {"name": "row", "type": "int", "value": entry.row},
                ],
            }
        )
        wang_tiles.append(
            {
                "tileid": entry.index,
                "wangid": _tiled_wangid(entry.peering_bits),
            }
        )

    return {
        "type": "tileset",
        "version": "1.10",
        "tiledversion": "1.10.2",
        "name": spec.id,
        "image": image_name or resolve_atlas_image_name(spec),
        "imagewidth": spec.width * scale,
        "imageheight": spec.height * scale,
        "tilewidth": tm.tile_width * scale,
        "tileheight": tm.tile_height * scale,
        "margin": tm.margin * scale,
        "spacing": tm.spacing * scale,
        "columns": tm.columns,
        "tilecount": len(entries),
        "tiles": tiles,
        "wangsets": [
            {
                "name": tm.terrain_name,
                "type": wang_type,
                "tile": entries[0].index if entries else -1,
                "colors": [
                    {
                        "name": tm.terrain_name,
                        "color": "#ff00ff00",
                        "tile": entries[0].index if entries else -1,
                        "probability": 1,
                    }
                ],
                "wangtiles": wang_tiles,
            }
        ],
    }


def build_godot_tileset(
    spec: AssetSpec,
    *,
    scale: int = 1,
    image_name: str | None = None,
) -> dict[str, object]:
    """Build a Godot 4 `TileSetAtlasSource` peering-bit metadata document."""
    tm = _require_tilemap(spec)
    entries = build_tile_entries(spec, scale=scale)
    terrain_mode = "match_sides" if tm.mode == "cardinal16" else "match_corners_and_sides"

    return {
        "format": "godot-tileset-v1",
        "app": "pixelforge",
        "version": __version__,
        "name": spec.id,
        "texture": image_name or resolve_atlas_image_name(spec),
        "texture_region_size": {"x": tm.tile_width * scale, "y": tm.tile_height * scale},
        "margins": {"x": tm.margin * scale, "y": tm.margin * scale},
        "separation": {"x": tm.spacing * scale, "y": tm.spacing * scale},
        "columns": tm.columns,
        "rows": tm.rows,
        "terrain_set_mode": terrain_mode,
        "terrain_name": tm.terrain_name,
        "tiles": [
            {
                "index": entry.index,
                "atlas_coords": [entry.col, entry.row],
                "bitmask": entry.bitmask,
                "terrain_set": 0,
                "terrain": 0,
                "peering_bits": entry.peering_bits,
            }
            for entry in entries
        ],
    }


def build_phaser_tilemap_atlas(
    spec: AssetSpec,
    *,
    scale: int = 1,
    image_name: str | None = None,
) -> dict[str, object]:
    """Build a Phaser 3 compatible tileset and bitmask lookup document."""
    tm = _require_tilemap(spec)
    entries = build_tile_entries(spec, scale=scale)

    return {
        "format": "phaser-tileset-v1",
        "app": "pixelforge",
        "version": __version__,
        "name": spec.id,
        "image": image_name or resolve_atlas_image_name(spec),
        "mode": tm.mode,
        "terrainName": tm.terrain_name,
        "tileWidth": tm.tile_width * scale,
        "tileHeight": tm.tile_height * scale,
        "tileMargin": tm.margin * scale,
        "tileSpacing": tm.spacing * scale,
        "columns": tm.columns,
        "rows": tm.rows,
        "tileCount": len(entries),
        "bitmaskToTileIndex": {str(entry.bitmask): entry.index for entry in entries},
        "tiles": [
            {
                "index": entry.index,
                "bitmask": entry.bitmask,
                "x": entry.x,
                "y": entry.y,
                "w": entry.w,
                "h": entry.h,
                "col": entry.col,
                "row": entry.row,
            }
            for entry in entries
        ],
    }


def serialize_tilemap_json(document: Mapping[str, object]) -> bytes:
    """Serialize a tilemap/tileset metadata document into deterministic UTF-8 JSON bytes."""
    return f"{json.dumps(document, indent=2)}\n".encode()
