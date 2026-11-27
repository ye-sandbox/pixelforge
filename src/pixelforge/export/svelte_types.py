"""TypeScript declaration (`manifest.d.ts`) codegen for Svelte 5 consumers."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pixelforge.export.bundle import ExportedAssetManifestEntry

_NON_IDENT = re.compile(r"[^a-zA-Z0-9_]")


def _ts_literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=True)


def _ts_union(values: Sequence[str]) -> str:
    unique = list(dict.fromkeys(values))
    if not unique:
        return "never"
    return " | ".join(_ts_literal(v) for v in unique)


def _pascal_ident(asset_id: str) -> str:
    cleaned = _NON_IDENT.sub("_", asset_id).strip("_")
    parts = [part for part in cleaned.split("_") if part]
    if not parts:
        return "Asset"
    ident = "".join(part[0].upper() + part[1:] for part in parts)
    if ident[0].isdigit():
        return f"Asset{ident}"
    return ident


def _collect_anchor_names(entry: ExportedAssetManifestEntry) -> list[str]:
    names = [a.name for a in entry.anchors]
    if entry.frameMetadata:
        for frame_list in entry.frameMetadata.values():
            for frame_meta in frame_list:
                names.extend(a.name for a in frame_meta.anchors)
    return list(dict.fromkeys(names))


def _collect_hitbox_names(entry: ExportedAssetManifestEntry) -> list[str]:
    names = [h.name for h in entry.hitboxes]
    if entry.frameMetadata:
        for frame_list in entry.frameMetadata.values():
            for frame_meta in frame_list:
                names.extend(h.name for h in frame_meta.hitboxes)
    return list(dict.fromkeys(names))


def _collect_event_names(entry: ExportedAssetManifestEntry) -> list[str]:
    names: list[str] = []
    if entry.frameMetadata:
        for frame_list in entry.frameMetadata.values():
            for frame_meta in frame_list:
                if frame_meta.events:
                    names.extend(frame_meta.events)
    return list(dict.fromkeys(names))


def _render_asset_interface(entry: ExportedAssetManifestEntry, type_name: str) -> list[str]:
    state_union = _ts_union(entry.states)
    anchor_union = _ts_union(_collect_anchor_names(entry))
    hitbox_union = _ts_union(_collect_hitbox_names(entry))
    event_union = _ts_union(_collect_event_names(entry))

    state_field_lines = [f"    readonly {_ts_literal(state)}: string;" for state in entry.states]
    lines: list[str] = [
        f"export type {type_name}State = {state_union};",
        f"export type {type_name}AnchorName = {anchor_union};",
        f"export type {type_name}HitboxName = {hitbox_union};",
        f"export type {type_name}EventName = {event_union};",
        "",
        f"export interface {type_name}ManifestEntry {{",
        f"  readonly id: {_ts_literal(entry.id)};",
        f"  readonly styleId: {_ts_literal(entry.styleId)};",
        f"  readonly perspective: {_ts_literal(entry.perspective)};",
        f"  readonly width: {entry.width};",
        f"  readonly height: {entry.height};",
        f"  readonly states: readonly {type_name}State[];",
        f"  readonly frames: {entry.frames};",
        f"  readonly fps: {entry.fps};",
        "  readonly files: {",
        "    readonly states: {",
        *state_field_lines,
        "    };",
    ]
    if entry.files.sheet is not None:
        lines.append("    readonly sheet: string;")
    if entry.files.emissive is not None:
        emissive_lines = [f"      readonly {_ts_literal(state)}: string;" for state in entry.states]
        lines.extend(["    readonly emissive: {", *emissive_lines, "    };"])
    if entry.files.sheetEmissive is not None:
        lines.append("    readonly sheetEmissive: string;")
    if entry.files.indexed is not None:
        indexed_lines = [f"      readonly {_ts_literal(state)}: string;" for state in entry.states]
        lines.extend(["    readonly indexed: {", *indexed_lines, "    };"])
    if entry.files.lut is not None:
        lines.append("    readonly lut: string;")
    if entry.files.normals is not None:
        normal_lines = [f"      readonly {_ts_literal(state)}: string;" for state in entry.states]
        lines.extend(["    readonly normals: {", *normal_lines, "    };"])
    if entry.files.sheetNormal is not None:
        lines.append("    readonly sheetNormal: string;")
    if entry.files.height is not None:
        height_lines = [f"      readonly {_ts_literal(state)}: string;" for state in entry.states]
        lines.extend(["    readonly height: {", *height_lines, "    };"])
    if entry.files.sheetHeight is not None:
        lines.append("    readonly sheetHeight: string;")
    lines.append("  };")

    lines.extend(
        [
            f"  readonly anchors: readonly PixelForgeAnchor<{type_name}AnchorName>[];",
            f"  readonly hitboxes: readonly PixelForgeHitbox<{type_name}HitboxName>[];",
        ]
    )
    if entry.nineSlice is not None:
        lines.append("  readonly nineSlice: PixelForgeNineSlice;")
    if entry.tilemap is not None:
        lines.append("  readonly tilemap: PixelForgeTilemap;")
    if entry.font is not None:
        lines.append("  readonly font: PixelForgeBitmapFont;")
    if entry.semantics is not None:
        lines.append("  readonly semantics: PixelForgeGameplaySemantics;")
    if entry.frameMetadata is not None:
        lines.append(
            f"  readonly frameMetadata?: Readonly<Record<{type_name}State, "
            f"readonly PixelForgeFrameMetadata<{type_name}AnchorName, "
            f"{type_name}HitboxName, {type_name}EventName>[]>>;"
        )
    lines.extend(
        [
            "  readonly sha256: string;",
            "}",
        ]
    )
    return lines


def generate_svelte_manifest_dts(
    entries: Sequence[ExportedAssetManifestEntry] | Mapping[str, ExportedAssetManifestEntry],
) -> str:
    """Emit strict `manifest.d.ts` TypeScript declarations for Svelte 5 consumers."""
    ordered = (
        [entries[k] for k in sorted(entries.keys())]
        if isinstance(entries, Mapping)
        else sorted(entries, key=lambda item: item.id)
    )

    lines: list[str] = [
        "// Auto-generated by pixelforge — do not edit manually.",
        "",
        "export interface PixelForgeAnchor<TName extends string = string> {",
        "  readonly name: TName;",
        "  readonly x: number;",
        "  readonly y: number;",
        "  readonly kind?: string;",
        "  readonly dir?: readonly [number, number];",
        "}",
        "",
        "export interface PixelForgeHitbox<TName extends string = string> {",
        "  readonly name: TName;",
        "  readonly x: number;",
        "  readonly y: number;",
        "  readonly w: number;",
        "  readonly h: number;",
        "  readonly kind?: string;",
        "}",
        "",
        "export interface PixelForgeNineSlice {",
        "  readonly left: number;",
        "  readonly right: number;",
        "  readonly top: number;",
        "  readonly bottom: number;",
        "}",
        "",
        "export interface PixelForgeTilemap {",
        "  readonly mode: 'cardinal16' | 'blob47';",
        "  readonly tile_width: number;",
        "  readonly tile_height: number;",
        "  readonly columns: number;",
        "  readonly rows: number;",
        "  readonly bitmasks: readonly number[];",
        "  readonly terrain_name: string;",
        "  readonly margin: number;",
        "  readonly spacing: number;",
        "}",
        "",
        "export interface PixelForgeBitmapGlyph {",
        "  readonly char: string;",
        "  readonly x: number;",
        "  readonly y: number;",
        "  readonly width: number;",
        "  readonly height: number;",
        "  readonly x_advance: number;",
        "  readonly x_offset: number;",
        "  readonly y_offset: number;",
        "}",
        "",
        "export interface PixelForgeBitmapFont {",
        "  readonly preset: '4x6' | '5x7' | '6x8' | '8x10';",
        "  readonly glyph_width: number;",
        "  readonly glyph_height: number;",
        "  readonly line_height: number;",
        "  readonly letter_spacing: number;",
        "  readonly space_advance: number;",
        "  readonly columns: number;",
        "  readonly rows: number;",
        "  readonly margin: number;",
        "  readonly spacing: number;",
        "  readonly charset: string;",
        "  readonly glyphs: readonly PixelForgeBitmapGlyph[];",
        "}",
        "",
        "export interface PixelForgePoint {",
        "  readonly x: number;",
        "  readonly y: number;",
        "}",
        "",
        "export interface PixelForgeSemanticGrid {",
        "  readonly cell_width: number;",
        "  readonly cell_height: number;",
        "  readonly columns: number;",
        "  readonly rows: number;",
        "  readonly cells: readonly (0 | 1)[];",
        "}",
        "",
        "export interface PixelForgeSemanticZone {",
        "  readonly name: string;",
        "  readonly x: number;",
        "  readonly y: number;",
        "  readonly w: number;",
        "  readonly h: number;",
        "  readonly kind: string;",
        "}",
        "",
        "export interface PixelForgeGameplaySemantics {",
        "  readonly y_sort_pivot: PixelForgePoint;",
        "  readonly collision_grid: PixelForgeSemanticGrid;",
        "  readonly walkable_mask: PixelForgeSemanticGrid;",
        "  readonly occlusion_zones: readonly PixelForgeSemanticZone[];",
        "  readonly interact_zones: readonly PixelForgeSemanticZone[];",
        "}",
        "",
        "export interface PixelForgeFrameMetadata<",
        "  TAnchor extends string = string,",
        "  THitbox extends string = string,",
        "  TEvent extends string = string,",
        "> {",
        "  readonly frame: number;",
        "  readonly anchors: readonly PixelForgeAnchor<TAnchor>[];",
        "  readonly hitboxes: readonly PixelForgeHitbox<THitbox>[];",
        "  readonly events?: readonly TEvent[];",
        "}",
        "",
    ]

    used_names: dict[str, int] = {}
    asset_type_map: list[tuple[str, str]] = []
    for entry in ordered:
        base_name = _pascal_ident(entry.id)
        count = used_names.get(base_name, 0) + 1
        used_names[base_name] = count
        type_name = base_name if count == 1 else f"{base_name}_{count}"
        asset_type_map.append((entry.id, type_name))
        lines.extend(_render_asset_interface(entry, type_name))
        lines.append("")

    asset_id_union = _ts_union([asset_id for asset_id, _ in asset_type_map])
    lines.append(f"export type PixelForgeAssetId = {asset_id_union};")
    lines.append("")
    lines.append("export interface PixelForgeManifestMap {")
    for asset_id, type_name in asset_type_map:
        lines.append(f"  readonly {_ts_literal(asset_id)}: {type_name}ManifestEntry;")
    lines.append("}")
    lines.append("")
    lines.extend(
        [
            "export type PixelForgeManifest = {",
            "  readonly [K in PixelForgeAssetId]: PixelForgeManifestMap[K];",
            "};",
            "",
            "export type PixelForgeManifestEntry<",
            "  K extends PixelForgeAssetId = PixelForgeAssetId,",
            "> = PixelForgeManifestMap[K];",
            "",
            "export type PixelForgeAssetState<K extends PixelForgeAssetId> =",
            "  PixelForgeManifestMap[K]['states'][number];",
            "",
            "export type PixelForgeAssetAnchor<K extends PixelForgeAssetId> =",
            "  PixelForgeManifestMap[K]['anchors'][number]['name'];",
            "",
            "export type PixelForgeAssetHitbox<K extends PixelForgeAssetId> =",
            "  PixelForgeManifestMap[K]['hitboxes'][number]['name'];",
            "",
            "export type PixelForgeAssetEvent<K extends PixelForgeAssetId> =",
            "  PixelForgeManifestMap[K] extends {",
            "    readonly frameMetadata?: Readonly<",
            "      Record<string, readonly { readonly events?: readonly (infer E)[] }[]>",
            "    >;",
            "  }",
            "    ? E",
            "    : never;",
            "",
        ]
    )
    return "\n".join(lines)
