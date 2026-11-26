"""Data models and protocols for declarative `.scene.py` composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from pixelforge.core.builder import LayerSemanticSpan
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import AnchorPoint, HitboxRect

DepthSortMode = Literal["z_index", "iso_y"]


class SceneCompositionError(ValueError):
    """Raised when scene composition fails style, anchor, state, or strict bounds checks."""


class SceneMountSpec(BaseModel):
    """Single child prop mount directive targeting a parent scene anchor."""

    model_config = ConfigDict(frozen=True)

    prop_id: str = Field(min_length=1)
    anchor: str = Field(min_length=1)
    prop_anchor: str | None = None
    state: str | None = None
    state_map: dict[str, str] | None = None
    frame: int | None = Field(default=None, ge=0)
    offset_x: int = 0
    offset_y: int = 0
    z_index: int = 0


class ScenePortalSpec(BaseModel):
    """Portal or transition edge linking this scene to another scene."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    target_scene_id: str = Field(min_length=1)
    anchor: str | None = None
    target_portal_id: str | None = None
    bidirectional: bool = False
    transition: str = Field(default="interact", min_length=1)


class SceneCompositionSpec(BaseModel):
    """Complete deterministic scene composition specification."""

    model_config = ConfigDict(frozen=True)

    parent_id: str = Field(min_length=1)
    parent_state: str | None = None
    parent_frame: int = Field(default=0, ge=0)
    mounts: tuple[SceneMountSpec, ...] = ()
    variant: str | None = None
    depth_sort: DepthSortMode = "z_index"


class SceneSpec(BaseModel):
    """Declarative `.scene.py` module specification compiled alongside `.asset.py`."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    parent_id: str = Field(min_length=1)
    style_id: str | None = None
    states: tuple[str, ...] | None = None
    frames: int | None = Field(default=None, ge=1)
    fps: int | None = Field(default=None, ge=1, le=60)
    mounts: tuple[SceneMountSpec, ...] = ()
    portals: tuple[ScenePortalSpec, ...] = ()
    depth_sort: DepthSortMode = "iso_y"
    variant: str | None = None
    strict_bounds: bool = False
    strict_perspective: bool = False


@runtime_checkable
class SceneModule(Protocol):
    """Protocol satisfied by any `.scene.py` module or wrapper object."""

    @property
    def SCENE(self) -> SceneSpec: ...


@dataclass(frozen=True)
class LoadedScene:
    """In-memory `SceneModule` container holding `SCENE`."""

    SCENE: SceneSpec


class MountedPropPlacement(BaseModel):
    """Resolved placement, bounds, and occlusion diagnostics for one mounted prop."""

    model_config = ConfigDict(frozen=True)

    prop_id: str
    anchor: str
    prop_anchor: str | None
    perspective: str
    perspective_match: bool
    state: str
    frame: int
    z_index: int
    dest_x: int
    dest_y: int
    width: int
    height: int
    opaque_bbox: tuple[int, int, int, int] | None
    in_bounds: bool
    clipped_pixels: int
    occluded_by: tuple[str, ...]
    occluded_pixels: int
    opaque_pixels: int = 0


@dataclass(frozen=True)
class SceneCompositionResult:
    """Compiled composite surface alongside anchor, bounds, and occlusion diagnostics."""

    parent_id: str
    style_id: str
    parent_state: str
    parent_frame: int
    surface: IndexedSurface
    parent_anchors: tuple[AnchorPoint, ...]
    placements: tuple[MountedPropPlacement, ...]
    warnings: tuple[str, ...]
    parent_hitboxes: tuple[HitboxRect, ...] = ()
    semantic_anchors: tuple[AnchorPoint, ...] = ()
    semantic_hitboxes: tuple[HitboxRect, ...] = ()
    layer_spans: tuple[LayerSemanticSpan, ...] = ()


@dataclass(frozen=True)
class SceneSheetResult:
    """Generated composite scene contact sheet RGBA buffer and PNG bytes."""

    width: int
    height: int
    rgba: NDArray[np.uint8]
    png: bytes


__all__ = [
    "DepthSortMode",
    "LoadedScene",
    "MountedPropPlacement",
    "SceneCompositionError",
    "SceneCompositionResult",
    "SceneCompositionSpec",
    "SceneModule",
    "SceneMountSpec",
    "ScenePortalSpec",
    "SceneSheetResult",
    "SceneSpec",
]
