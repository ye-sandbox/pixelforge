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

from pydantic import BaseModel, ConfigDict, TypeAdapter

from pixelforge.core.builder import Asset
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import AnchorPoint, AssetSpec, HitboxRect, StylePack
from pixelforge.export.png import (
    frames_to_apng,
    frames_to_gif,
    rgba_to_png,
    style_to_lut_png,
    surface_to_indexed_png,
    surface_to_png,
    surface_to_rgba,
)
from pixelforge.export.svelte_types import generate_svelte_manifest_dts


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
    frameMetadata: dict[str, tuple[FrameMetadataEntry, ...]] | None = None
    sha256: str


class ExportBundleOptions(BaseModel):
    """Configuration flags for `export_asset_bundle`."""

    model_config = ConfigDict(frozen=True)

    variant: str | None = None
    scale: int = 1
    emissive: bool | None = None
    lut: bool = False
    animate: bool = False
    animate_format: Literal["gif", "apng"] = "gif"
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
            )
            asset.render(builder)
            results.append(
                RenderedFrame(
                    state=state,
                    frame=frame,
                    surface=builder.root_surface,
                    anchors=builder.anchors,
                    hitboxes=builder.hitboxes,
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


@dataclass(frozen=True)
class _StateExportOutputs:
    files: dict[str, bytes]
    preview_files: dict[str, bytes]
    state_files: dict[str, str]
    emissive_files: dict[str, str]
    indexed_files: dict[str, str]


def _export_state_outputs(
    spec: AssetSpec,
    style: StylePack,
    by_key: Mapping[tuple[str, int], RenderedFrame],
    opts: ExportBundleOptions,
    *,
    include_emissive: bool,
) -> _StateExportOutputs:
    files: dict[str, bytes] = {}
    preview_files: dict[str, bytes] = {}
    state_files: dict[str, str] = {}
    emissive_files: dict[str, str] = {}
    indexed_files: dict[str, str] = {}

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
    )


def _export_spritesheet_outputs(
    spec: AssetSpec,
    style: StylePack,
    rendered_frames: Sequence[RenderedFrame],
    opts: ExportBundleOptions,
    *,
    include_emissive: bool,
) -> tuple[dict[str, bytes], str | None, str | None]:
    if spec.frames <= 1:
        return ({}, None, None)

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
    return (files, sheet_name, sheet_emissive_name)


def export_asset_bundle(
    asset: AssetModule,
    style: StylePack,
    options: ExportBundleOptions | None = None,
) -> ExportBundleResult:
    """Compile an asset into PNGs, spritesheets, emissive masks, LUTs, previews, and manifest."""
    opts = options or ExportBundleOptions()
    spec = asset.SPEC
    rendered_frames = render_asset_frames(
        asset,
        style,
        variant=opts.variant,
        token_overrides=opts.token_overrides,
    )

    include_emissive = _has_emissive_colors(style) if opts.emissive is None else opts.emissive
    by_key = {(item.state, item.frame): item for item in rendered_frames}

    state_out = _export_state_outputs(
        spec,
        style,
        by_key,
        opts,
        include_emissive=include_emissive,
    )
    sheet_files, sheet_name, sheet_emissive_name = _export_spritesheet_outputs(
        spec,
        style,
        rendered_frames,
        opts,
        include_emissive=include_emissive,
    )
    files = {**state_out.files, **sheet_files}

    lut_name: str | None = None
    if opts.lut:
        lut_name = f"{style.id}_lut.png"
        files[lut_name] = style_to_lut_png(style)

    baseline = rendered_frames[0]
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
    )

    export_files = ExportedAssetFiles(
        states=state_out.state_files,
        sheet=sheet_name,
        emissive=state_out.emissive_files if include_emissive else None,
        sheetEmissive=sheet_emissive_name,
        indexed=state_out.indexed_files if opts.lut else None,
        lut=lut_name,
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
        frameMetadata=frame_metadata,
        sha256=sha256,
    )

    return ExportBundleResult(
        manifest=manifest,
        files=files,
        preview_files=state_out.preview_files,
        rendered_frames=rendered_frames,
    )


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
