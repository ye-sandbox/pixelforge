"""Asset rendering orchestrator and deterministic bundle/manifest exporter."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, TypeAdapter

from pixelforge.core.builder import Asset, LayerSemanticSpan
from pixelforge.core.semantics import derive_gameplay_semantics
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import (
    AnchorPoint,
    AssetSpec,
    BitmapFontSpec,
    GameplaySemantics,
    HitboxRect,
    NineSliceMargins,
    StylePack,
    TilemapSpec,
)
from pixelforge.export.atlas import (
    AtlasFormat,
    build_aseprite_atlas,
    build_texturepacker_atlas,
    resolve_atlas_image_name,
    serialize_atlas_json,
)
from pixelforge.export.png import (
    frames_to_apng,
    frames_to_gif,
    height_map_to_png,
    normal_map_to_png,
    rgba_to_png,
    style_to_lut_png,
    surface_to_indexed_png,
    surface_to_png,
    surface_to_rgba,
)
from pixelforge.export.svelte_types import generate_svelte_manifest_dts
from pixelforge.export.tilemap import (
    TileAtlasFormat,
    build_godot_tileset,
    build_phaser_tilemap_atlas,
    build_tiled_tileset,
    serialize_tilemap_json,
)


@runtime_checkable
class AssetModule(Protocol):
    """Protocol satisfied by any `.asset.py` module or wrapper object."""

    @property
    def SPEC(self) -> AssetSpec: ...

    @property
    def render(self) -> Callable[[Asset], None]: ...


@dataclass(frozen=True)
class LoadedAsset:
    """In-memory `AssetModule` container pairing `SPEC` with `render(a)`."""

    SPEC: AssetSpec
    render: Callable[[Asset], None]


@dataclass(frozen=True)
class RenderedFrame:
    """Single deterministic `(state, frame)` output from an asset render."""

    state: str
    frame: int
    surface: IndexedSurface
    anchors: tuple[AnchorPoint, ...]
    hitboxes: tuple[HitboxRect, ...]
    layer_spans: tuple[LayerSemanticSpan, ...] = ()
    normal_map: NDArray[np.float32] | None = None
    height_map: NDArray[np.float32] | None = None


class FrameMetadataEntry(BaseModel):
    """Per-frame anchors and hitboxes recorded when coordinates vary across states/frames."""

    model_config = ConfigDict(frozen=True)

    frame: int
    anchors: tuple[AnchorPoint, ...]
    hitboxes: tuple[HitboxRect, ...]


class ExportedAssetFiles(BaseModel):
    """Relative sprite file references inside `dist/sprites/`."""

    model_config = ConfigDict(frozen=True)

    states: dict[str, str]
    sheet: str | None = None
    emissive: dict[str, str] | None = None
    sheetEmissive: str | None = None
    indexed: dict[str, str] | None = None
    lut: str | None = None
    normals: dict[str, str] | None = None
    sheetNormal: str | None = None
    height: dict[str, str] | None = None
    sheetHeight: str | None = None


class ExportedAssetManifestEntry(BaseModel):
    """Deterministic JSON manifest entry emitted per exported asset."""

    model_config = ConfigDict(frozen=True)

    id: str
    styleId: str
    perspective: str
    width: int
    height: int
    states: tuple[str, ...]
    frames: int
    fps: int
    files: ExportedAssetFiles
    anchors: tuple[AnchorPoint, ...]
    hitboxes: tuple[HitboxRect, ...]
    nineSlice: NineSliceMargins | None = None
    tilemap: TilemapSpec | None = None
    font: BitmapFontSpec | None = None
    frameMetadata: dict[str, tuple[FrameMetadataEntry, ...]] | None = None
    semantics: GameplaySemantics | None = None
    sha256: str


class ExportBundleOptions(BaseModel):
    """Configuration flags for `export_asset_bundle`."""

    model_config = ConfigDict(frozen=True)

    variant: str | None = None
    scale: int = 1
    emissive: bool | None = None
    lut: bool = False
    normals: bool = False
    height: bool = False
    animate: bool = False
    animate_format: Literal["gif", "apng"] = "gif"
    atlas: AtlasFormat | None = None
    tilemap_atlas: TileAtlasFormat | None = None
    token_overrides: dict[str, str | int] | None = None


@dataclass(frozen=True)
class ExportBundleResult:
    """Complete compiled output bundle for one asset."""

    manifest: ExportedAssetManifestEntry
    files: dict[str, bytes]
    preview_files: dict[str, bytes]
    rendered_frames: tuple[RenderedFrame, ...]


def render_asset_frames(
    asset: AssetModule,
    style: StylePack,
    *,
    variant: str | None = None,
    token_overrides: Mapping[str, str | int] | None = None,
    track_maps: bool = False,
) -> tuple[RenderedFrame, ...]:
    """Deterministically execute `asset.render` for every `(state, frame)`."""
    spec = asset.SPEC
    results: list[RenderedFrame] = []

    for state in spec.states:
        for frame in range(spec.frames):
            builder = Asset(
                spec,
                style,
                state=state,
                frame=frame,
                variant=variant,
                token_overrides=token_overrides,
                track_maps=track_maps,
            )
            asset.render(builder)
            results.append(
                RenderedFrame(
                    state=state,
                    frame=frame,
                    surface=builder.root_surface,
                    anchors=builder.anchors,
                    hitboxes=builder.hitboxes,
                    layer_spans=builder.layer_spans,
                    normal_map=builder.normal_map,
                    height_map=builder.height_map,
                )
            )

    return tuple(results)


def build_spritesheet_surface(
    spec: AssetSpec,
    rendered_frames: Sequence[RenderedFrame],
) -> IndexedSurface:
    """Pack rendered frames into a `(frames * width) x (states * height)` indexed sheet."""
    sheet_w = spec.width * spec.frames
    sheet_h = spec.height * len(spec.states)
    sheet = IndexedSurface(sheet_w, sheet_h)
    by_key = {(item.state, item.frame): item for item in rendered_frames}

    for state_idx, state in enumerate(spec.states):
        for frame in range(spec.frames):
            item = by_key.get((state, frame))
            if item is not None:
                sheet.blit_layer(item.surface, frame * spec.width, state_idx * spec.height)
    return sheet


def _has_emissive_colors(style: StylePack) -> bool:
    return any("emissive" in entry.flags for entry in style.palette)


def _build_frame_metadata(
    spec: AssetSpec,
    rendered_frames: Sequence[RenderedFrame],
    baseline_anchors: tuple[AnchorPoint, ...],
    baseline_hitboxes: tuple[HitboxRect, ...],
) -> dict[str, tuple[FrameMetadataEntry, ...]] | None:
    varies = any(
        item.anchors != baseline_anchors or item.hitboxes != baseline_hitboxes
        for item in rendered_frames
    )
    if not varies:
        return None

    by_state: dict[str, list[FrameMetadataEntry]] = {state: [] for state in spec.states}
    for item in rendered_frames:
        by_state[item.state].append(
            FrameMetadataEntry(
                frame=item.frame,
                anchors=item.anchors,
                hitboxes=item.hitboxes,
            )
        )
    return {state: tuple(entries) for state, entries in by_state.items()}


def _compute_bundle_digest(
    spec: AssetSpec,
    rendered_frames: Sequence[RenderedFrame],
    anchors: tuple[AnchorPoint, ...],
    hitboxes: tuple[HitboxRect, ...],
    frame_metadata: dict[str, tuple[FrameMetadataEntry, ...]] | None,
    semantics: GameplaySemantics | None = None,
) -> str:
    hasher = hashlib.sha256()
    header_payload = {
        "id": spec.id,
        "styleId": spec.style_id,
        "perspective": spec.perspective,
        "width": spec.width,
        "height": spec.height,
        "states": spec.states,
        "frames": spec.frames,
        "fps": spec.fps,
        "anchors": [a.model_dump() for a in anchors],
        "hitboxes": [h.model_dump() for h in hitboxes],
        **({"nineSlice": spec.nine_slice.model_dump()} if spec.nine_slice is not None else {}),
        **({"tilemap": spec.tilemap.model_dump()} if spec.tilemap is not None else {}),
        **({"font": spec.font.model_dump()} if spec.font is not None else {}),
        **({"semantics": semantics.model_dump()} if semantics is not None else {}),
        "frameMetadata": (
            {
                state: [entry.model_dump() for entry in entries]
                for state, entries in frame_metadata.items()
            }
            if frame_metadata is not None
            else None
        ),
    }
    hasher.update(json.dumps(header_payload, sort_keys=True, separators=(",", ":")).encode())
    for item in rendered_frames:
        hasher.update(item.state.encode())
        hasher.update(item.frame.to_bytes(4, "little"))
        hasher.update(item.surface.data.tobytes())
    return hasher.hexdigest()


def build_spritesheet_normal_map(
    spec: AssetSpec,
    rendered_frames: Sequence[RenderedFrame],
) -> NDArray[np.float32]:
    """Pack rendered frame normal maps into a `(states * H, frames * W, 3)` float32 array."""
    sheet_w = spec.width * spec.frames
    sheet_h = spec.height * len(spec.states)
    sheet = np.zeros((sheet_h, sheet_w, 3), dtype=np.float32)
    sheet[..., 2] = 1.0
    by_key = {(item.state, item.frame): item for item in rendered_frames}

    for state_idx, state in enumerate(spec.states):
        for frame in range(spec.frames):
            item = by_key.get((state, frame))
            if item is not None and item.normal_map is not None:
                x0 = frame * spec.width
                y0 = state_idx * spec.height
                sheet[y0 : y0 + spec.height, x0 : x0 + spec.width, :] = item.normal_map
    return sheet


def build_spritesheet_height_map(
    spec: AssetSpec,
    rendered_frames: Sequence[RenderedFrame],
) -> NDArray[np.float32]:
    """Pack rendered frame height maps into a `(states * H, frames * W)` float32 array."""
    sheet_w = spec.width * spec.frames
    sheet_h = spec.height * len(spec.states)
    sheet = np.zeros((sheet_h, sheet_w), dtype=np.float32)
    by_key = {(item.state, item.frame): item for item in rendered_frames}

    for state_idx, state in enumerate(spec.states):
        for frame in range(spec.frames):
            item = by_key.get((state, frame))
            if item is not None and item.height_map is not None:
                x0 = frame * spec.width
                y0 = state_idx * spec.height
                sheet[y0 : y0 + spec.height, x0 : x0 + spec.width] = item.height_map
    return sheet


def _max_height_across_frames(rendered_frames: Sequence[RenderedFrame]) -> float:
    max_h = 0.0
    for item in rendered_frames:
        if item.height_map is not None:
            opaque = item.surface.data != 255
            if np.any(opaque):
                frame_max = float(np.max(item.height_map[opaque]))
                if frame_max > max_h:
                    max_h = frame_max
    return max_h


@dataclass(frozen=True)
class _StateExportOutputs:
    files: dict[str, bytes]
    preview_files: dict[str, bytes]
    state_files: dict[str, str]
    emissive_files: dict[str, str]
    indexed_files: dict[str, str]
    normal_files: dict[str, str]
    height_files: dict[str, str]


def _export_state_outputs(
    spec: AssetSpec,
    style: StylePack,
    by_key: Mapping[tuple[str, int], RenderedFrame],
    opts: ExportBundleOptions,
    *,
    include_emissive: bool,
    max_height: float,
) -> _StateExportOutputs:
    files: dict[str, bytes] = {}
    preview_files: dict[str, bytes] = {}
    state_files: dict[str, str] = {}
    emissive_files: dict[str, str] = {}
    indexed_files: dict[str, str] = {}
    normal_files: dict[str, str] = {}
    height_files: dict[str, str] = {}

    for state in spec.states:
        primary = by_key[(state, 0)]
        state_name = f"{spec.id}_{state}.png"
        state_files[state] = state_name
        files[state_name] = surface_to_png(
            primary.surface,
            style,
            variant=opts.variant,
            scale=opts.scale,
        )

        if include_emissive:
            emissive_name = f"{spec.id}_{state}_emissive.png"
            emissive_files[state] = emissive_name
            files[emissive_name] = surface_to_png(
                primary.surface,
                style,
                variant=opts.variant,
                scale=opts.scale,
                emissive_only=True,
            )

        if opts.lut:
            indexed_name = f"{spec.id}_{state}_idx.png"
            indexed_files[state] = indexed_name
            files[indexed_name] = surface_to_indexed_png(primary.surface, scale=opts.scale)

        if opts.normals and primary.normal_map is not None:
            normal_name = f"{spec.id}_{state}_normal.png"
            normal_files[state] = normal_name
            files[normal_name] = normal_map_to_png(
                primary.normal_map,
                primary.surface,
                scale=opts.scale,
            )

        if opts.height and primary.height_map is not None:
            height_name = f"{spec.id}_{state}_height.png"
            height_files[state] = height_name
            files[height_name] = height_map_to_png(
                primary.height_map,
                primary.surface,
                max_height=max_height,
                scale=opts.scale,
            )

        if opts.animate and spec.frames > 1:
            rgba_seq = [
                surface_to_rgba(
                    by_key[(state, f)].surface,
                    style,
                    variant=opts.variant,
                    scale=opts.scale,
                )
                for f in range(spec.frames)
            ]
            ext = opts.animate_format
            preview_name = f"{spec.id}_{state}.{ext}"
            preview_files[preview_name] = (
                frames_to_apng(rgba_seq, fps=spec.fps)
                if ext == "apng"
                else frames_to_gif(rgba_seq, fps=spec.fps)
            )

    return _StateExportOutputs(
        files=files,
        preview_files=preview_files,
        state_files=state_files,
        emissive_files=emissive_files,
        indexed_files=indexed_files,
        normal_files=normal_files,
        height_files=height_files,
    )


def _export_spritesheet_outputs(
    spec: AssetSpec,
    style: StylePack,
    rendered_frames: Sequence[RenderedFrame],
    opts: ExportBundleOptions,
    *,
    include_emissive: bool,
    max_height: float,
) -> tuple[dict[str, bytes], str | None, str | None, str | None, str | None]:
    if spec.frames <= 1:
        return ({}, None, None, None, None)

    files: dict[str, bytes] = {}
    sheet_surface = build_spritesheet_surface(spec, rendered_frames)
    sheet_name = f"{spec.id}_sheet.png"
    files[sheet_name] = rgba_to_png(
        surface_to_rgba(sheet_surface, style, variant=opts.variant, scale=opts.scale)
    )

    sheet_emissive_name: str | None = None
    if include_emissive:
        sheet_emissive_name = f"{spec.id}_sheet_emissive.png"
        files[sheet_emissive_name] = rgba_to_png(
            surface_to_rgba(
                sheet_surface,
                style,
                variant=opts.variant,
                scale=opts.scale,
                emissive_only=True,
            )
        )

    sheet_normal_name: str | None = None
    if opts.normals and any(item.normal_map is not None for item in rendered_frames):
        sheet_normal_name = f"{spec.id}_sheet_normal.png"
        sheet_normals = build_spritesheet_normal_map(spec, rendered_frames)
        files[sheet_normal_name] = normal_map_to_png(sheet_normals, sheet_surface, scale=opts.scale)

    sheet_height_name: str | None = None
    if opts.height and any(item.height_map is not None for item in rendered_frames):
        sheet_height_name = f"{spec.id}_sheet_height.png"
        sheet_heights = build_spritesheet_height_map(spec, rendered_frames)
        files[sheet_height_name] = height_map_to_png(
            sheet_heights,
            sheet_surface,
            max_height=max_height,
            scale=opts.scale,
        )

    return (files, sheet_name, sheet_emissive_name, sheet_normal_name, sheet_height_name)


def _export_atlas_outputs(
    spec: AssetSpec,
    style: StylePack,
    rendered_frames: Sequence[RenderedFrame],
    opts: ExportBundleOptions,
    *,
    has_sheet_png: bool,
    semantics: GameplaySemantics | None = None,
) -> dict[str, bytes]:
    if opts.atlas is None:
        return {}

    files: dict[str, bytes] = {}
    image_name = resolve_atlas_image_name(spec)
    # INVARIANT: Multi-state single-frame assets do not emit `<id>_sheet.png` by default;
    # emit the sheet PNG alongside the atlas metadata without altering `manifest.json`.
    if not has_sheet_png and image_name == f"{spec.id}_sheet.png":
        sheet_surface = build_spritesheet_surface(spec, rendered_frames)
        files[image_name] = rgba_to_png(
            surface_to_rgba(sheet_surface, style, variant=opts.variant, scale=opts.scale)
        )

    if opts.atlas in ("aseprite", "all"):
        aseprite_doc = build_aseprite_atlas(
            spec, rendered_frames, scale=opts.scale, image_name=image_name
        )
        files[f"{spec.id}.aseprite.json"] = serialize_atlas_json(aseprite_doc)

    if opts.atlas in ("texturepacker", "all"):
        tp_doc = build_texturepacker_atlas(
            spec, rendered_frames, scale=opts.scale, image_name=image_name
        )
        files[f"{spec.id}.texturepacker.json"] = serialize_atlas_json(tp_doc)

    tile_fmt: TileAtlasFormat | None = opts.tilemap_atlas
    if tile_fmt is None and opts.atlas == "all" and spec.tilemap is not None:
        tile_fmt = "all"
    if tile_fmt is not None and spec.tilemap is not None:
        if tile_fmt in ("tiled", "all"):
            files[f"{spec.id}.tiled.json"] = serialize_tilemap_json(
                build_tiled_tileset(
                    spec, scale=opts.scale, image_name=image_name, semantics=semantics
                )
            )
        if tile_fmt in ("godot", "all"):
            files[f"{spec.id}.godot.json"] = serialize_tilemap_json(
                build_godot_tileset(
                    spec, scale=opts.scale, image_name=image_name, semantics=semantics
                )
            )
        if tile_fmt in ("phaser", "all"):
            files[f"{spec.id}.phaser.json"] = serialize_tilemap_json(
                build_phaser_tilemap_atlas(spec, scale=opts.scale, image_name=image_name)
            )

    return files


def export_rendered_frames_bundle(
    spec: AssetSpec,
    rendered_frames: tuple[RenderedFrame, ...],
    style: StylePack,
    options: ExportBundleOptions | None = None,
    *,
    semantics: GameplaySemantics | None = None,
) -> ExportBundleResult:
    """Package pre-rendered frames into PNGs, spritesheets, masks, LUTs, and manifest."""
    opts = options or ExportBundleOptions()
    include_emissive = _has_emissive_colors(style) if opts.emissive is None else opts.emissive
    by_key = {(item.state, item.frame): item for item in rendered_frames}

    baseline = rendered_frames[0]
    resolved_semantics = (
        semantics
        if semantics is not None
        else derive_gameplay_semantics(
            spec,
            baseline.surface,
            anchors=baseline.anchors,
            hitboxes=baseline.hitboxes,
            layer_spans=baseline.layer_spans,
        )
    )

    max_height = _max_height_across_frames(rendered_frames) if opts.height else 0.0
    state_out = _export_state_outputs(
        spec,
        style,
        by_key,
        opts,
        include_emissive=include_emissive,
        max_height=max_height,
    )
    sheet_files, sheet_name, sheet_emissive_name, sheet_normal_name, sheet_height_name = (
        _export_spritesheet_outputs(
            spec,
            style,
            rendered_frames,
            opts,
            include_emissive=include_emissive,
            max_height=max_height,
        )
    )
    atlas_files = _export_atlas_outputs(
        spec,
        style,
        rendered_frames,
        opts,
        has_sheet_png=sheet_name is not None,
        semantics=resolved_semantics,
    )
    files = {**state_out.files, **sheet_files, **atlas_files}

    lut_name: str | None = None
    if opts.lut:
        lut_name = f"{style.id}_lut.png"
        files[lut_name] = style_to_lut_png(style)

    frame_metadata = _build_frame_metadata(
        spec,
        rendered_frames,
        baseline.anchors,
        baseline.hitboxes,
    )
    sha256 = _compute_bundle_digest(
        spec,
        rendered_frames,
        baseline.anchors,
        baseline.hitboxes,
        frame_metadata,
        resolved_semantics,
    )

    export_files = ExportedAssetFiles(
        states=state_out.state_files,
        sheet=sheet_name,
        emissive=state_out.emissive_files if include_emissive else None,
        sheetEmissive=sheet_emissive_name,
        indexed=state_out.indexed_files if opts.lut else None,
        lut=lut_name,
        normals=state_out.normal_files if opts.normals and state_out.normal_files else None,
        sheetNormal=sheet_normal_name,
        height=state_out.height_files if opts.height and state_out.height_files else None,
        sheetHeight=sheet_height_name,
    )

    manifest = ExportedAssetManifestEntry(
        id=spec.id,
        styleId=spec.style_id,
        perspective=spec.perspective,
        width=spec.width,
        height=spec.height,
        states=spec.states,
        frames=spec.frames,
        fps=spec.fps,
        files=export_files,
        anchors=baseline.anchors,
        hitboxes=baseline.hitboxes,
        nineSlice=spec.nine_slice,
        tilemap=spec.tilemap,
        font=spec.font,
        frameMetadata=frame_metadata,
        semantics=resolved_semantics,
        sha256=sha256,
    )

    return ExportBundleResult(
        manifest=manifest,
        files=files,
        preview_files=state_out.preview_files,
        rendered_frames=rendered_frames,
    )


def export_asset_bundle(
    asset: AssetModule,
    style: StylePack,
    options: ExportBundleOptions | None = None,
) -> ExportBundleResult:
    """Compile an asset into PNGs, spritesheets, emissive masks, LUTs, previews, and manifest."""
    opts = options or ExportBundleOptions()
    rendered_frames = render_asset_frames(
        asset,
        style,
        variant=opts.variant,
        token_overrides=opts.token_overrides,
        track_maps=(opts.normals or opts.height),
    )
    return export_rendered_frames_bundle(asset.SPEC, rendered_frames, style, opts)


def build_manifest_document(
    entries: Mapping[str, ExportedAssetManifestEntry],
) -> dict[str, object]:
    """Serialize manifest entries sorted deterministically by asset ID."""
    return {
        asset_id: entries[asset_id].model_dump(exclude_none=True, mode="json")
        for asset_id in sorted(entries.keys())
    }


def _atomic_write_text(target_path: Path, content: str) -> None:
    fd, tmp_name = tempfile.mkstemp(
        dir=target_path.parent,
        prefix=f".{target_path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, target_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def write_manifest(
    entries: Mapping[str, ExportedAssetManifestEntry],
    out_dir: Path,
) -> tuple[Path, Path]:
    """Atomically write `manifest.json` and `manifest.d.ts` into `out_dir`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_json_path = out_dir / "manifest.json"
    manifest_dts_path = out_dir / "manifest.d.ts"

    doc = build_manifest_document(entries)
    _atomic_write_text(manifest_json_path, f"{json.dumps(doc, indent=2)}\n")
    _atomic_write_text(manifest_dts_path, generate_svelte_manifest_dts(entries))
    return (manifest_json_path, manifest_dts_path)


_MANIFEST_ADAPTER = TypeAdapter(dict[str, ExportedAssetManifestEntry])


def write_export_bundle(
    bundle: ExportBundleResult,
    out_dir: Path,
    *,
    previews_dir: Path | None = None,
    update_manifest: bool = True,
) -> Path:
    """Write compiled sprite PNGs, optionally merge manifest files, and save previews."""
    sprites_dir = out_dir / "sprites"
    sprites_dir.mkdir(parents=True, exist_ok=True)

    for filename, payload in bundle.files.items():
        (sprites_dir / filename).write_bytes(payload)

    if previews_dir is not None and bundle.preview_files:
        previews_dir.mkdir(parents=True, exist_ok=True)
        for filename, payload in bundle.preview_files.items():
            (previews_dir / filename).write_bytes(payload)

    manifest_path = out_dir / "manifest.json"
    if not update_manifest:
        return manifest_path

    existing: dict[str, ExportedAssetManifestEntry] = (
        _MANIFEST_ADAPTER.validate_json(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {}
    )

    existing[bundle.manifest.id] = bundle.manifest
    write_manifest(existing, out_dir)
    return manifest_path
