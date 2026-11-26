"""Aseprite JSON and TexturePacker atlas metadata exporters for third-party game engines."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Literal, Protocol

from pixelforge._version import __version__
from pixelforge.core.types import AnchorPoint, AssetSpec, HitboxRect

AtlasFormat = Literal["aseprite", "texturepacker", "all"]


class AtlasFrameProtocol(Protocol):
    """Structural frame protocol satisfied by `RenderedFrame` without circular imports."""

    @property
    def state(self) -> str: ...

    @property
    def frame(self) -> int: ...

    @property
    def anchors(self) -> tuple[AnchorPoint, ...]: ...

    @property
    def hitboxes(self) -> tuple[HitboxRect, ...]: ...


def resolve_atlas_image_name(spec: AssetSpec) -> str:
    """Return the PNG filename referenced by `meta.image` for an asset's atlas."""
    if spec.frames == 1 and len(spec.states) == 1:
        return f"{spec.id}_{spec.states[0]}.png"
    return f"{spec.id}_sheet.png"


def _atlas_sheet_dimensions(spec: AssetSpec, scale: int) -> tuple[int, int]:
    return (spec.width * spec.frames * scale, spec.height * len(spec.states) * scale)


def _index_frames(
    rendered_frames: Sequence[AtlasFrameProtocol],
) -> dict[tuple[str, int], AtlasFrameProtocol]:
    return {(item.state, item.frame): item for item in rendered_frames}


def _build_aseprite_slices(
    spec: AssetSpec,
    by_key: Mapping[tuple[str, int], AtlasFrameProtocol],
    scale: int,
) -> list[dict[str, object]]:
    slice_keys: dict[tuple[str, str], list[dict[str, object]]] = {}

    for state_idx, state in enumerate(spec.states):
        for frame in range(spec.frames):
            flat_idx = state_idx * spec.frames + frame
            item = by_key.get((state, frame))
            if item is None:
                continue
            for anchor in item.anchors:
                key = ("anchor", anchor.name)
                slice_keys.setdefault(key, []).append(
                    {
                        "frame": flat_idx,
                        "bounds": {
                            "x": anchor.x * scale,
                            "y": anchor.y * scale,
                            "w": scale,
                            "h": scale,
                        },
                    }
                )
            for hitbox in item.hitboxes:
                key = ("hitbox", hitbox.name)
                slice_keys.setdefault(key, []).append(
                    {
                        "frame": flat_idx,
                        "bounds": {
                            "x": hitbox.x * scale,
                            "y": hitbox.y * scale,
                            "w": hitbox.w * scale,
                            "h": hitbox.h * scale,
                        },
                    }
                )

    slices: list[dict[str, object]] = []
    for (kind, name), keys in sorted(slice_keys.items()):
        slices.append(
            {
                "name": f"{kind}:{name}",
                "color": "#0000ffff" if kind == "anchor" else "#ff0000ff",
                "keys": keys,
            }
        )
    return slices


def build_aseprite_atlas(
    spec: AssetSpec,
    rendered_frames: Sequence[AtlasFrameProtocol],
    *,
    scale: int = 1,
    image_name: str | None = None,
) -> dict[str, object]:
    """Build an Aseprite JSON-hash atlas document (`frames`, `meta.frameTags`, `meta.slices`)."""
    if scale < 1:
        msg = f"scale must be >= 1, got {scale}"
        raise ValueError(msg)

    by_key = _index_frames(rendered_frames)
    duration_ms = max(1, round(1000 / spec.fps))
    frame_w = spec.width * scale
    frame_h = spec.height * scale
    sheet_w, sheet_h = _atlas_sheet_dimensions(spec, scale)

    frames: dict[str, dict[str, object]] = {}
    frame_tags: list[dict[str, object]] = []

    for state_idx, state in enumerate(spec.states):
        from_idx = state_idx * spec.frames
        to_idx = from_idx + spec.frames - 1
        frame_tags.append({"name": state, "from": from_idx, "to": to_idx, "direction": "forward"})

        for frame in range(spec.frames):
            frame_key = f"{spec.id}_{state}_{frame}"
            frames[frame_key] = {
                "frame": {
                    "x": frame * frame_w,
                    "y": state_idx * frame_h,
                    "w": frame_w,
                    "h": frame_h,
                },
                "rotated": False,
                "trimmed": False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": frame_w, "h": frame_h},
                "sourceSize": {"w": frame_w, "h": frame_h},
                "duration": duration_ms,
            }

    slices = _build_aseprite_slices(spec, by_key, scale)
    meta: dict[str, object] = {
        "app": "pixelforge",
        "version": __version__,
        "image": image_name or resolve_atlas_image_name(spec),
        "format": "RGBA8888",
        "size": {"w": sheet_w, "h": sheet_h},
        "scale": str(scale),
        "frameTags": frame_tags,
    }
    if slices:
        meta["slices"] = slices

    return {"frames": frames, "meta": meta}


def _resolve_pivot(spec: AssetSpec, item: AtlasFrameProtocol | None) -> dict[str, float]:
    if item is not None:
        for anchor in item.anchors:
            if anchor.name == "pivot":
                return {
                    "x": round(anchor.x / spec.width, 6),
                    "y": round(anchor.y / spec.height, 6),
                }
    return {"x": 0.5, "y": 0.5}


def build_texturepacker_atlas(
    spec: AssetSpec,
    rendered_frames: Sequence[AtlasFrameProtocol],
    *,
    scale: int = 1,
    image_name: str | None = None,
) -> dict[str, object]:
    """Build a TexturePacker JSON-hash atlas document (`frames`, `animations`, `meta`)."""
    if scale < 1:
        msg = f"scale must be >= 1, got {scale}"
        raise ValueError(msg)

    by_key = _index_frames(rendered_frames)
    frame_w = spec.width * scale
    frame_h = spec.height * scale
    sheet_w, sheet_h = _atlas_sheet_dimensions(spec, scale)

    frames: dict[str, dict[str, object]] = {}
    animations: dict[str, list[str]] = {}

    for state_idx, state in enumerate(spec.states):
        state_keys: list[str] = []
        for frame in range(spec.frames):
            frame_key = f"{spec.id}/{state}/{frame}"
            state_keys.append(frame_key)
            frames[frame_key] = {
                "frame": {
                    "x": frame * frame_w,
                    "y": state_idx * frame_h,
                    "w": frame_w,
                    "h": frame_h,
                },
                "rotated": False,
                "trimmed": False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": frame_w, "h": frame_h},
                "sourceSize": {"w": frame_w, "h": frame_h},
                "pivot": _resolve_pivot(spec, by_key.get((state, frame))),
            }
        animations[state] = state_keys

    return {
        "frames": frames,
        "animations": animations,
        "meta": {
            "app": "pixelforge",
            "version": __version__,
            "image": image_name or resolve_atlas_image_name(spec),
            "format": "RGBA8888",
            "size": {"w": sheet_w, "h": sheet_h},
            "scale": str(scale),
        },
    }


def serialize_atlas_json(document: Mapping[str, object]) -> bytes:
    """Serialize an atlas document to deterministic UTF-8 JSON bytes."""
    return f"{json.dumps(document, indent=2)}\n".encode()
