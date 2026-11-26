"""CLI `inspect` introspection workflows for styles, prefabs, assets, and scenes."""

from __future__ import annotations

import difflib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pixelforge.cli.output import OutputFn, OutputFormat
from pixelforge.core import font as font_mod
from pixelforge.core import prefabs
from pixelforge.core import tilemap as tilemap_mod
from pixelforge.core.builder import Asset, Layer
from pixelforge.core.plane import Plane
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import AnchorPoint, HitboxRect, PaletteColor, StylePack
from pixelforge.export.bundle import LoadedAsset
from pixelforge.export.scene import SceneSpec
from pixelforge.guard.runner import (
    discover_asset_files,
    discover_scene_files,
    load_all_styles,
    load_asset_module,
    load_scene_module,
)
from pixelforge.presets import DEFAULT_INIT_PRESET, PRESET_IDS, load_all_presets

_PREFAB_CATEGORIES: Final[tuple[str, ...]] = (
    "architecture",
    "furniture",
    "details",
    "atmosphere",
    "characters",
    "ui",
)

_API_SECTIONS: Final[tuple[str, ...]] = (
    "Asset",
    "Layer",
    "Plane",
    "IndexedSurface",
    "tilemap",
    "font",
)


@dataclass(frozen=True)
class ApiMemberInfo:
    """Introspected core drawing API method, property, or function."""

    name: str
    section: str
    kind: str
    signature: str
    summary: str


@dataclass(frozen=True)
class PrefabInfo:
    """Introspected prefab function signature and summary."""

    name: str
    category: str
    signature: str
    summary: str


@dataclass(frozen=True)
class AssetInspection:
    """Introspected asset specification and frame-0 anchors/hitboxes."""

    id: str
    style_id: str
    width: int
    height: int
    perspective: str
    states: tuple[str, ...]
    frames: int
    fps: int | None
    seed: int
    path: str
    anchors: tuple[AnchorPoint, ...]
    hitboxes: tuple[HitboxRect, ...]
    style_missing: bool = False


@dataclass(frozen=True)
class SceneInspection:
    """Introspected declarative `.scene.py` specification and parent metadata."""

    scene: SceneSpec
    path: str
    parent_width: int | None = None
    parent_height: int | None = None
    parent_states: tuple[str, ...] | None = None


def _suggest_close(name: str, candidates: list[str]) -> str:
    matches = difflib.get_close_matches(name, candidates, n=3, cutoff=0.5)
    if not matches:
        return ""
    return f"; did you mean {', '.join(repr(m) for m in matches)}?"


def _rel_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _group_palette(
    style: StylePack,
) -> tuple[list[PaletteColor], list[PaletteColor], list[PaletteColor]]:
    paint = [c for c in style.palette if "emissive" not in c.flags]
    emissive = [c for c in style.palette if "emissive" in c.flags]
    bright = [c for c in style.palette if "bright" in c.flags]
    return paint, emissive, bright


def _format_token_compact(entry: PaletteColor) -> str:
    flags = ",".join(entry.flags)
    return f"{entry.index}:{entry.name}({entry.hex}" + (f",{flags})" if flags else ")")


def _token_to_dict(entry: PaletteColor) -> dict[str, object]:
    return {
        "index": entry.index,
        "name": entry.name,
        "hex": entry.hex,
        "flags": list(entry.flags),
    }


def _emit_styles(
    styles: list[StylePack],
    *,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    if output_format == "json":
        payload = {
            "total": len(styles),
            "styles": [
                {
                    "id": s.id,
                    "perspective": s.perspective,
                    "lighting_angle": s.lighting_angle,
                    "outline_index": s.outline_index,
                    "token_count": len(s.palette),
                    "variants": sorted(s.variants),
                    "groups": {
                        "paint": [_token_to_dict(c) for c in paint],
                        "emissive": [_token_to_dict(c) for c in emissive],
                        "bright": [_token_to_dict(c) for c in bright],
                        "reflections": dict(s.reflections),
                    },
                }
                for s in styles
                for paint, emissive, bright in [_group_palette(s)]
            ],
        }
        out(json.dumps(payload, indent=2))
        return

    for s in styles:
        paint, emissive, bright = _group_palette(s)
        outline_name = next((c.name for c in s.palette if c.index == s.outline_index), "?")
        variants_str = ",".join(sorted(s.variants)) or "none"
        if output_format == "human":
            out(
                f"Style: {s.id} ({s.perspective}, lighting={s.lighting_angle}, "
                f"outline={s.outline_index}:{outline_name}, variants={variants_str})"
            )
            out(f"  Paint ({len(paint)}): " + ", ".join(c.name for c in paint))
            out(f"  Emissive ({len(emissive)}): " + ", ".join(c.name for c in emissive))
            out(f"  Bright ({len(bright)}): " + ", ".join(c.name for c in bright))
            refl_items = [f"{k}->{v}" for k, v in s.reflections.items()]
            out(f"  Reflections ({len(refl_items)}): " + (", ".join(refl_items) or "none"))
            continue

        out(
            f"style={s.id} perspective={s.perspective} lighting={s.lighting_angle} "
            f"outline={s.outline_index}({outline_name}) tokens={len(s.palette)} "
            f"variants={variants_str}"
        )
        out(f"paint({len(paint)}): " + " ".join(_format_token_compact(c) for c in paint))
        out(f"emissive({len(emissive)}): " + " ".join(_format_token_compact(c) for c in emissive))
        out(f"bright({len(bright)}): " + " ".join(_format_token_compact(c) for c in bright))
        refl_items = [f"{k}->{v}" for k, v in s.reflections.items()]
        out(f"reflections({len(refl_items)}): " + (" ".join(refl_items) if refl_items else "none"))


def inspect_style_workflow(
    root: Path,
    *,
    style_id: str | None,
    presets: bool = False,
    output_format: OutputFormat,
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Inspect one or all `StylePack` definitions under `styles/` (or built-in presets)."""
    if presets:
        return inspect_presets_workflow(
            preset_id=style_id,
            output_format=output_format,
            out=out,
            err=err,
        )

    styles = load_all_styles(root / "styles")
    if not styles:
        err(f"No .style.py files found under {root / 'styles'}")
        return 1

    if style_id is not None:
        if style_id not in styles:
            suggestion = _suggest_close(style_id, sorted(styles))
            available = ", ".join(sorted(styles))
            err(f"Unknown style {style_id!r}; available: {available}{suggestion}")
            return 1
        selected = [styles[style_id]]
    else:
        selected = [styles[k] for k in sorted(styles)]

    _emit_styles(selected, output_format=output_format, out=out)
    return 0


def _emit_preset_summary(
    presets: list[StylePack],
    *,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    if output_format == "json":
        payload = {
            "total": len(presets),
            "default": DEFAULT_INIT_PRESET,
            "presets": [
                {
                    "id": s.id,
                    "perspective": s.perspective,
                    "lighting_angle": s.lighting_angle,
                    "token_count": len(s.palette),
                    "emissive_count": sum(1 for c in s.palette if "emissive" in c.flags),
                    "variants": sorted(s.variants),
                }
                for s in presets
            ],
        }
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        out(f"Built-in StylePack presets ({len(presets)}, default: {DEFAULT_INIT_PRESET}):")
        for s in presets:
            emissive_n = sum(1 for c in s.palette if "emissive" in c.flags)
            variants_str = ", ".join(sorted(s.variants)) or "none"
            default_tag = " [default]" if s.id == DEFAULT_INIT_PRESET else ""
            out(
                f"  {s.id}{default_tag} — {len(s.palette)} colors "
                f"({emissive_n} emissive), {s.perspective}, variants={variants_str}"
            )
        return

    out(f"presets={len(presets)} default={DEFAULT_INIT_PRESET}")
    for s in presets:
        emissive_n = sum(1 for c in s.palette if "emissive" in c.flags)
        variants_str = ",".join(sorted(s.variants)) or "none"
        out(
            f"preset={s.id} perspective={s.perspective} colors={len(s.palette)} "
            f"emissive={emissive_n} variants={variants_str}"
        )


def inspect_presets_workflow(
    *,
    preset_id: str | None,
    output_format: OutputFormat,
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Inspect built-in `StylePack` presets available for `pixelforge init --style`."""
    presets = load_all_presets()
    if preset_id is not None:
        if preset_id not in presets:
            suggestion = _suggest_close(preset_id, list(PRESET_IDS))
            available = ", ".join(PRESET_IDS)
            err(f"Unknown preset {preset_id!r}; available: {available}{suggestion}")
            return 1
        _emit_styles([presets[preset_id]], output_format=output_format, out=out)
        return 0

    ordered = [presets[pid] for pid in PRESET_IDS]
    _emit_preset_summary(ordered, output_format=output_format, out=out)
    return 0


def _collect_prefabs() -> list[PrefabInfo]:
    items: list[PrefabInfo] = []
    for name in sorted(prefabs.__all__):
        obj: object = getattr(prefabs, name, None)
        if not callable(obj) or isinstance(obj, type):
            continue
        mod = getattr(obj, "__module__", "")
        category = "other"
        for cat in _PREFAB_CATEGORIES:
            if f"prefabs.{cat}" in mod:
                category = cat
                break
        sig = str(inspect.signature(obj))
        doc = inspect.getdoc(obj) or ""
        summary = doc.splitlines()[0].strip() if doc else ""
        items.append(PrefabInfo(name=name, category=category, signature=sig, summary=summary))
    return items


def _emit_prefabs(
    items: list[PrefabInfo],
    *,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    grouped: dict[str, list[PrefabInfo]] = {cat: [] for cat in _PREFAB_CATEGORIES}
    for item in items:
        grouped.setdefault(item.category, []).append(item)
    non_empty_cats = [cat for cat, group in grouped.items() if group]

    if output_format == "json":
        payload = {
            "total": len(items),
            "categories": {
                cat: [
                    {
                        "name": entry.name,
                        "signature": entry.signature,
                        "summary": entry.summary,
                    }
                    for entry in grouped[cat]
                ]
                for cat in non_empty_cats
            },
        }
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        out(f"Prefabs ({len(items)} total across {len(non_empty_cats)} categories):")
        for cat in non_empty_cats:
            out(f"\n[{cat}] ({len(grouped[cat])})")
            for entry in grouped[cat]:
                out(f"  {entry.name}{entry.signature}")
                if entry.summary:
                    out(f"    {entry.summary}")
        return

    out(f"prefabs={len(items)} categories={','.join(non_empty_cats)}")
    for cat in non_empty_cats:
        out(f"[{cat}]")
        for entry in grouped[cat]:
            summary = f" | {entry.summary}" if entry.summary else ""
            out(f"{entry.name}{entry.signature}{summary}")


def inspect_prefabs_workflow(
    *,
    target: str | None,
    output_format: OutputFormat,
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Inspect available prefab kits, categories, and signatures."""
    all_items = _collect_prefabs()
    if target is None:
        _emit_prefabs(all_items, output_format=output_format, out=out)
        return 0

    needle = target.lower()
    if needle in _PREFAB_CATEGORIES:
        filtered = [item for item in all_items if item.category == needle]
    else:
        exact = [item for item in all_items if item.name.lower() == needle]
        filtered = exact or [item for item in all_items if needle in item.name.lower()]

    if not filtered:
        candidates = [*_PREFAB_CATEGORIES, *(item.name for item in all_items)]
        suggestion = _suggest_close(target, candidates)
        err(
            f"No prefabs matching {target!r}; categories: {', '.join(_PREFAB_CATEGORIES)}"
            f"{suggestion}"
        )
        return 1

    _emit_prefabs(filtered, output_format=output_format, out=out)
    return 0


def _inspect_single_asset(
    path: Path,
    loaded: LoadedAsset,
    styles: dict[str, StylePack],
    root: Path,
) -> AssetInspection:
    spec = loaded.SPEC
    style = styles.get(spec.style_id)
    if style is None:
        return AssetInspection(
            id=spec.id,
            style_id=spec.style_id,
            width=spec.width,
            height=spec.height,
            perspective=spec.perspective,
            states=spec.states,
            frames=spec.frames,
            fps=spec.fps,
            seed=spec.seed,
            path=_rel_path(path, root),
            anchors=(),
            hitboxes=(),
            style_missing=True,
        )

    asset = Asset(spec, style, state=spec.states[0], frame=0)
    loaded.render(asset)
    return AssetInspection(
        id=spec.id,
        style_id=spec.style_id,
        width=spec.width,
        height=spec.height,
        perspective=spec.perspective,
        states=spec.states,
        frames=spec.frames,
        fps=spec.fps,
        seed=spec.seed,
        path=_rel_path(path, root),
        anchors=tuple(asset.anchors),
        hitboxes=tuple(asset.hitboxes),
    )


def _emit_assets(
    items: list[AssetInspection],
    *,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    if output_format == "json":
        payload = {
            "total": len(items),
            "assets": [
                {
                    "id": item.id,
                    "style_id": item.style_id,
                    "width": item.width,
                    "height": item.height,
                    "perspective": item.perspective,
                    "states": list(item.states),
                    "frames": item.frames,
                    "fps": item.fps,
                    "seed": item.seed,
                    "path": item.path,
                    "style_missing": item.style_missing,
                    "anchors": [a.model_dump(mode="json") for a in item.anchors],
                    "hitboxes": [h.model_dump(mode="json") for h in item.hitboxes],
                }
                for item in items
            ],
        }
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        out(f"Assets ({len(items)}):")
        for item in items:
            fps_str = f", fps={item.fps}" if item.fps is not None else ""
            out(
                f"  {item.id} [{item.width}x{item.height}, {item.perspective}, "
                f"style={item.style_id}, frames={item.frames}{fps_str}] ({item.path})"
            )
            out(f"    states: {', '.join(item.states)}")
            anchors_str = ", ".join(f"{a.name}@({a.x},{a.y})" for a in item.anchors) or "none"
            hitboxes_str = (
                ", ".join(f"{h.name}({h.x},{h.y},{h.w}x{h.h})" for h in item.hitboxes) or "none"
            )
            out(f"    anchors: {anchors_str}")
            out(f"    hitboxes: {hitboxes_str}")
        return

    out(f"assets={len(items)}")
    for item in items:
        fps_str = f" fps={item.fps}" if item.fps is not None else ""
        anchors_str = ",".join(f"{a.name}({a.x},{a.y})" for a in item.anchors) or "none"
        hitboxes_str = (
            ",".join(f"{h.name}({h.x},{h.y},{h.w},{h.h})" for h in item.hitboxes) or "none"
        )
        out(
            f"{item.id} {item.width}x{item.height} {item.perspective} style={item.style_id} "
            f"states={','.join(item.states)} frames={item.frames}{fps_str} "
            f"anchors={anchors_str} hitboxes={hitboxes_str} path={item.path}"
        )


def inspect_assets_workflow(
    root: Path,
    *,
    asset_id: str | None,
    output_format: OutputFormat,
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Inspect `.asset.py` dimensions, states, anchors, and hitboxes."""
    asset_files = discover_asset_files(root / "assets")
    if not asset_files:
        err(f"No .asset.py files found under {root / 'assets'}")
        return 1

    loaded_by_id: dict[str, tuple[Path, LoadedAsset]] = {}
    for asset_path in asset_files:
        loaded = load_asset_module(asset_path)
        loaded_by_id[loaded.SPEC.id] = (asset_path, loaded)

    if asset_id is not None:
        if asset_id not in loaded_by_id:
            suggestion = _suggest_close(asset_id, sorted(loaded_by_id))
            err(f"Asset {asset_id!r} not found under {root / 'assets'}{suggestion}")
            return 1
        target_ids = [asset_id]
    else:
        target_ids = sorted(loaded_by_id)

    styles = load_all_styles(root / "styles")
    inspections = [
        _inspect_single_asset(path, loaded, styles, root)
        for aid in target_ids
        for path, loaded in [loaded_by_id[aid]]
    ]
    _emit_assets(inspections, output_format=output_format, out=out)
    return 0


def _emit_scenes(
    items: list[SceneInspection],
    *,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    if output_format == "json":
        payload = {
            "total": len(items),
            "scenes": [
                {
                    "id": item.scene.id,
                    "parent_id": item.scene.parent_id,
                    "style_id": item.scene.style_id,
                    "states": list(item.scene.states)
                    if item.scene.states is not None
                    else (list(item.parent_states) if item.parent_states is not None else None),
                    "frames": item.scene.frames,
                    "fps": item.scene.fps,
                    "depth_sort": item.scene.depth_sort,
                    "variant": item.scene.variant,
                    "strict_bounds": item.scene.strict_bounds,
                    "strict_perspective": item.scene.strict_perspective,
                    "parent_width": item.parent_width,
                    "parent_height": item.parent_height,
                    "path": item.path,
                    "mounts": [m.model_dump(mode="json") for m in item.scene.mounts],
                }
                for item in items
            ],
        }
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        out(f"Scenes ({len(items)}):")
        for item in items:
            s = item.scene
            size_str = (
                f"{item.parent_width}x{item.parent_height}"
                if item.parent_width is not None and item.parent_height is not None
                else "unknown-size"
            )
            states = s.states or item.parent_states or ()
            out(
                f"  {s.id} -> parent={s.parent_id} ({size_str}, depth_sort={s.depth_sort}, "
                f"strict_bounds={s.strict_bounds}, strict_perspective={s.strict_perspective}) "
                f"({item.path})"
            )
            out(f"    states: {', '.join(states) if states else 'inherited'}")
            for m in s.mounts:
                prop_anchor = f":{m.prop_anchor}" if m.prop_anchor else ""
                smap = (
                    " map=" + ",".join(f"{k}->{v}" for k, v in m.state_map.items())
                    if m.state_map
                    else ""
                )
                out(f"    mount: {m.prop_id}@{m.anchor}{prop_anchor}{smap}")
        return

    out(f"scenes={len(items)}")
    for item in items:
        s = item.scene
        states = s.states or item.parent_states or ()
        states_str = ",".join(states) if states else "inherited"
        size_str = (
            f"{item.parent_width}x{item.parent_height}"
            if item.parent_width is not None and item.parent_height is not None
            else "unknown"
        )
        out(
            f"scene={s.id} parent={s.parent_id} size={size_str} style={s.style_id or 'inherited'} "
            f"states={states_str} depth_sort={s.depth_sort} "
            f"strict_bounds={str(s.strict_bounds).lower()} "
            f"strict_perspective={str(s.strict_perspective).lower()} "
            f"mounts={len(s.mounts)} path={item.path}"
        )
        for m in s.mounts:
            prop_anchor = f":{m.prop_anchor}" if m.prop_anchor else ""
            smap = (
                " state_map=" + ",".join(f"{k}->{v}" for k, v in m.state_map.items())
                if m.state_map
                else ""
            )
            offset_str = (
                f" offset=({m.offset_x},{m.offset_y})" if (m.offset_x or m.offset_y) else ""
            )
            z_str = f" z={m.z_index}" if m.z_index else ""
            out(f"  mount={m.prop_id}@{m.anchor}{prop_anchor}{smap}{offset_str}{z_str}")


def inspect_scenes_workflow(
    root: Path,
    *,
    scene_id: str | None,
    output_format: OutputFormat,
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Inspect `.scene.py` composition specs, mounts, and parent metadata."""
    scene_files = discover_scene_files(root / "assets")
    if not scene_files:
        err(f"No .scene.py files found under {root / 'assets'}")
        return 1

    loaded_by_id: dict[str, tuple[Path, SceneSpec]] = {}
    for scene_path in scene_files:
        loaded = load_scene_module(scene_path)
        loaded_by_id[loaded.SCENE.id] = (scene_path, loaded.SCENE)

    if scene_id is not None:
        if scene_id not in loaded_by_id:
            suggestion = _suggest_close(scene_id, sorted(loaded_by_id))
            err(f"Scene {scene_id!r} not found under {root / 'assets'}{suggestion}")
            return 1
        target_ids = [scene_id]
    else:
        target_ids = sorted(loaded_by_id)

    parent_specs: dict[str, LoadedAsset] = {}
    for asset_path in discover_asset_files(root / "assets"):
        loaded_asset = load_asset_module(asset_path)
        parent_specs[loaded_asset.SPEC.id] = loaded_asset

    inspections: list[SceneInspection] = []
    for sid in target_ids:
        path, scene = loaded_by_id[sid]
        parent = parent_specs.get(scene.parent_id)
        inspections.append(
            SceneInspection(
                scene=scene,
                path=_rel_path(path, root),
                parent_width=parent.SPEC.width if parent is not None else None,
                parent_height=parent.SPEC.height if parent is not None else None,
                parent_states=parent.SPEC.states if parent is not None else None,
            )
        )

    _emit_scenes(inspections, output_format=output_format, out=out)
    return 0


def _strip_self_param(sig: inspect.Signature) -> inspect.Signature:
    params = list(sig.parameters.values())
    if params and params[0].name == "self":
        return sig.replace(parameters=params[1:])
    return sig


def _first_doc_line(obj: object) -> str:
    doc = inspect.getdoc(obj) or ""
    return doc.splitlines()[0].strip() if doc else ""


def _collect_class_api(cls: type[object], section: str) -> list[ApiMemberInfo]:
    items: list[ApiMemberInfo] = []
    for name in sorted(dir(cls)):
        if name.startswith("_"):
            continue
        raw = inspect.getattr_static(cls, name)
        if isinstance(raw, property):
            if raw.fget is None:
                continue
            sig = str(_strip_self_param(inspect.signature(raw.fget)))
            summary = _first_doc_line(raw.fget) or _first_doc_line(raw)
            items.append(
                ApiMemberInfo(
                    name=name,
                    section=section,
                    kind="property",
                    signature=sig,
                    summary=summary,
                )
            )
            continue

        attr: object = getattr(cls, name, None)
        if not callable(attr) or isinstance(attr, type):
            continue
        sig = str(_strip_self_param(inspect.signature(attr)))
        summary = _first_doc_line(attr)
        items.append(
            ApiMemberInfo(
                name=name,
                section=section,
                kind="method",
                signature=sig,
                summary=summary,
            )
        )
    return items


def _collect_module_api(module: object, section: str) -> list[ApiMemberInfo]:
    mod_name = getattr(module, "__name__", "")
    items: list[ApiMemberInfo] = []
    for name in sorted(dir(module)):
        if name.startswith("_"):
            continue
        obj: object = getattr(module, name, None)
        if not inspect.isfunction(obj) or getattr(obj, "__module__", "") != mod_name:
            continue
        sig = str(inspect.signature(obj))
        summary = _first_doc_line(obj)
        items.append(
            ApiMemberInfo(
                name=name,
                section=section,
                kind="function",
                signature=sig,
                summary=summary,
            )
        )
    return items


def _collect_api() -> list[ApiMemberInfo]:
    items: list[ApiMemberInfo] = []
    items.extend(_collect_class_api(Asset, "Asset"))
    items.extend(_collect_class_api(Layer, "Layer"))
    items.extend(_collect_class_api(Plane, "Plane"))
    items.extend(_collect_class_api(IndexedSurface, "IndexedSurface"))
    items.extend(_collect_module_api(tilemap_mod, "tilemap"))
    items.extend(_collect_module_api(font_mod, "font"))
    return items


def _emit_api(
    items: list[ApiMemberInfo],
    *,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    grouped: dict[str, list[ApiMemberInfo]] = {sec: [] for sec in _API_SECTIONS}
    for item in items:
        grouped.setdefault(item.section, []).append(item)
    non_empty = [sec for sec in _API_SECTIONS if grouped[sec]]

    if output_format == "json":
        payload = {
            "total": len(items),
            "sections": {
                sec: [
                    {
                        "name": entry.name,
                        "kind": entry.kind,
                        "signature": entry.signature,
                        "summary": entry.summary,
                    }
                    for entry in grouped[sec]
                ]
                for sec in non_empty
            },
        }
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        out(f"Core Drawing API ({len(items)} total across {len(non_empty)} sections):")
        for sec in non_empty:
            out(f"\n[{sec}] ({len(grouped[sec])})")
            for entry in grouped[sec]:
                prefix = "@property " if entry.kind == "property" else ""
                out(f"  {prefix}{entry.name}{entry.signature}")
                if entry.summary:
                    out(f"    {entry.summary}")
        return

    out(f"api={len(items)} sections={','.join(non_empty)}")
    for sec in non_empty:
        out(f"[{sec}]")
        for entry in grouped[sec]:
            prefix = "@property " if entry.kind == "property" else ""
            summary = f" | {entry.summary}" if entry.summary else ""
            out(f"{prefix}{entry.name}{entry.signature}{summary}")


def inspect_api_workflow(
    *,
    target: str | None,
    output_format: OutputFormat,
    out: OutputFn,
    err: OutputFn,
) -> int:
    """Inspect public methods, signatures, and summaries of core drawing APIs."""
    all_items = _collect_api()
    if target is None:
        _emit_api(all_items, output_format=output_format, out=out)
        return 0

    needle = target.lower()
    section_map = {sec.lower(): sec for sec in _API_SECTIONS}
    if needle in section_map:
        matched_section = section_map[needle]
        filtered = [item for item in all_items if item.section == matched_section]
    else:
        exact = [item for item in all_items if item.name.lower() == needle]
        filtered = exact or [item for item in all_items if needle in item.name.lower()]

    if not filtered:
        candidates = [*_API_SECTIONS, *(item.name for item in all_items)]
        suggestion = _suggest_close(target, candidates)
        err(f"No API symbols matching {target!r}; sections: {', '.join(_API_SECTIONS)}{suggestion}")
        return 1

    _emit_api(filtered, output_format=output_format, out=out)
    return 0
