"""CLI `new` scaffolders for zero-reference assets, scenes, and styles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pixelforge.cli.output import OutputFn, OutputFormat
from pixelforge.cli.scaffold import pick_starter_tokens, starter_style_source
from pixelforge.cli.settings import PixelforgeSettings, resolve_project_style_id
from pixelforge.core.palette_stub import palette_stub_class_name
from pixelforge.core.types import StylePack
from pixelforge.guard.runner import (
    check_ast_file,
    discover_style_files,
    load_all_styles,
    load_style_module,
    sync_palette_stubs,
)
from pixelforge.presets import (
    DEFAULT_INIT_PRESET,
    PRESET_IDS,
    is_builtin_preset,
    read_preset_source,
)

AssetKind = Literal[
    "iso-prop",
    "front-prop",
    "character",
    "tile-blob47",
    "9slice",
    "font",
]
ASSET_KINDS: tuple[AssetKind, ...] = (
    "iso-prop",
    "front-prop",
    "character",
    "tile-blob47",
    "9slice",
    "font",
)

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_STYLE_ID_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")
_STYLE_ID_ASSIGN_RE = re.compile(r'(\bid\s*=\s*)(["\'])[^"\']*\2')


@dataclass(frozen=True)
class NewScaffoldResult:
    """Structured outcome of a `pixelforge new` invocation."""

    target: Literal["asset", "scene", "style"]
    entity_id: str
    path: Path
    style_id: str | None
    kind: AssetKind | None
    parent_id: str | None
    from_preset: str | None
    synced_stubs: tuple[Path, ...]
    next_commands: tuple[str, ...]


def _normalize_entity_id(raw_name: str, *, suffix: str) -> str:
    cleaned = raw_name.strip().removesuffix(suffix).removesuffix(".py").replace("-", "_")
    if not _IDENTIFIER_RE.fullmatch(cleaned):
        msg = f"Invalid identifier {raw_name!r}; expected [a-zA-Z_][a-zA-Z0-9_]*"
        raise ValueError(msg)
    return cleaned


def _normalize_style_id(raw_name: str) -> str:
    cleaned = raw_name.strip().removesuffix(".style.py").removesuffix(".py")
    if not _STYLE_ID_RE.fullmatch(cleaned):
        msg = f"Invalid style id {raw_name!r}; expected [a-zA-Z_][a-zA-Z0-9_-]*"
        raise ValueError(msg)
    return cleaned


def _resolve_output_path(
    root: Path,
    default_dir: str,
    filename: str,
    out: str | None,
) -> Path:
    if out is None:
        return root / default_dir / filename
    candidate = Path(out)
    resolved = candidate if candidate.is_absolute() else root / candidate
    if out.endswith(("/", "\\")) or resolved.is_dir() or resolved.suffix != ".py":
        return resolved / filename
    return resolved


def _write_scaffold(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        msg = f"Refusing to overwrite existing file {path} (pass --force to overwrite)"
        raise FileExistsError(msg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _find_style_path_for_id(root: Path, style_id: str) -> Path | None:
    for style_path in discover_style_files(root / "styles"):
        if check_ast_file(style_path, scope="style"):
            continue
        pack = load_style_module(style_path)
        if pack.id == style_id:
            return style_path
    return None


def _render_asset_skeleton(
    *,
    asset_id: str,
    kind: AssetKind,
    pack: StylePack,
    stub_module: str,
    stub_class: str,
) -> str:
    outline_tok, light_tok, mid_tok, dark_tok, accent_tok = pick_starter_tokens(pack)
    header = (
        f'"""Starter {kind} asset `{asset_id}`."""\n\n'
        "from __future__ import annotations\n\n"
        "from typing import TYPE_CHECKING\n\n"
    )
    stub_import = f"if TYPE_CHECKING:\n    from {stub_module} import {stub_class}\n\n"

    if kind == "iso-prop":
        accent_lines = ""
        if accent_tok is not None:
            accent_lines = f"    a.put(12, 11, p.{accent_tok})\n    a.put(13, 11, p.{accent_tok})\n"
        return (
            header
            + "from pixelforge.core import Asset, AssetSpec\n\n"
            + stub_import
            + "SPEC = AssetSpec(\n"
            + f"    id={asset_id!r},\n"
            + f"    style_id={pack.id!r},\n"
            + '    perspective="iso-2:1",\n'
            + "    width=24,\n"
            + "    height=24,\n"
            + '    states=("idle",),\n'
            + "    frames=1,\n"
            + "    fps=4,\n"
            + ")\n\n\n"
            + f"def render(a: Asset[{stub_class}]) -> None:\n"
            + f'    """Render starter isometric prop `{asset_id}`."""\n'
            + "    p = a.pal\n"
            + f'    with a.layer("body", outline=p.{outline_tok}):\n'
            + "        a.iso_box(\n"
            + "            x=12,\n"
            + "            y=10,\n"
            + "            w=8,\n"
            + "            d=8,\n"
            + "            h=6,\n"
            + f"            top=p.{light_tok},\n"
            + f"            left=p.{mid_tok},\n"
            + f"            right=p.{dark_tok},\n"
            + "        )\n"
            + accent_lines
            + '    a.anchor("foot", 12, 20, kind="ground")\n'
            + '    a.hitbox("solid", 4, 8, 16, 13, kind="solid")\n'
        )

    if kind == "front-prop":
        accent_line = f"    a.rect(11, 11, 2, 2, p.{accent_tok})\n" if accent_tok else ""
        return (
            header
            + "from pixelforge.core import Asset, AssetSpec\n\n"
            + stub_import
            + "SPEC = AssetSpec(\n"
            + f"    id={asset_id!r},\n"
            + f"    style_id={pack.id!r},\n"
            + '    perspective="front-2.5d",\n'
            + "    width=24,\n"
            + "    height=24,\n"
            + '    states=("idle",),\n'
            + "    frames=1,\n"
            + "    fps=4,\n"
            + ")\n\n\n"
            + f"def render(a: Asset[{stub_class}]) -> None:\n"
            + f'    """Render starter front-2.5d prop `{asset_id}`."""\n'
            + "    p = a.pal\n"
            + f'    with a.layer("body", outline=p.{outline_tok}):\n'
            + f"        a.rect(6, 6, 12, 14, p.{mid_tok})\n"
            + f"        a.rect(6, 6, 12, 3, p.{light_tok})\n"
            + f"        a.rect(6, 17, 12, 3, p.{dark_tok})\n"
            + accent_line
            + '    a.anchor("foot", 12, 20, kind="ground")\n'
            + '    a.hitbox("solid", 6, 6, 12, 14, kind="solid")\n'
        )

    if kind == "character":
        return (
            header
            + "from pixelforge.core import Asset, AssetSpec\n\n"
            + stub_import
            + "SPEC = AssetSpec(\n"
            + f"    id={asset_id!r},\n"
            + f"    style_id={pack.id!r},\n"
            + '    perspective="front-2.5d",\n'
            + "    width=24,\n"
            + "    height=32,\n"
            + '    states=("idle", "walk"),\n'
            + "    frames=2,\n"
            + "    fps=6,\n"
            + ")\n\n\n"
            + f"def render(a: Asset[{stub_class}]) -> None:\n"
            + f'    """Render starter animated character `{asset_id}`."""\n'
            + "    p = a.pal\n"
            + '    bob = -1 if (a.state == "walk" and a.frame == 1) else 0\n'
            + f'    with a.layer("body", outline=p.{outline_tok}):\n'
            + f"        a.rect(9, 6 + bob, 6, 6, p.{light_tok})\n"
            + f"        a.rect(8, 12 + bob, 8, 9, p.{mid_tok})\n"
            + f"        a.rect(8, 21, 3, 7, p.{dark_tok})\n"
            + f"        a.rect(13, 21, 3, 7, p.{dark_tok})\n"
            + '    a.anchor("foot", 12, 28, kind="ground")\n'
            + '    a.hitbox("body", 8, 6, 8, 22, kind="body")\n'
        )

    if kind == "tile-blob47":
        return (
            header
            + "from pixelforge.core import (\n"
            + "    BLOB47_MASKS,\n"
            + "    Asset,\n"
            + "    AssetSpec,\n"
            + "    AutotileStyle,\n"
            + "    TilemapSpec,\n"
            + "    autotile_walls,\n"
            + ")\n\n"
            + stub_import
            + "SPEC = AssetSpec(\n"
            + f"    id={asset_id!r},\n"
            + f"    style_id={pack.id!r},\n"
            + '    perspective="top-down",\n'
            + "    width=146,\n"
            + "    height=110,\n"
            + "    tilemap=TilemapSpec(\n"
            + '        mode="blob47",\n'
            + "        tile_width=16,\n"
            + "        tile_height=16,\n"
            + "        columns=8,\n"
            + "        rows=6,\n"
            + "        bitmasks=BLOB47_MASKS,\n"
            + f"        terrain_name={asset_id!r},\n"
            + "        margin=2,\n"
            + "        spacing=2,\n"
            + "    ),\n"
            + ")\n\n\n"
            + f"def render(a: Asset[{stub_class}]) -> None:\n"
            + f'    """Render 47-tile blob autotile sheet `{asset_id}`."""\n'
            + "    p = a.pal\n"
            + '    with a.layer("tiles"):\n'
            + "        autotile_walls(\n"
            + "            a,\n"
            + "            AutotileStyle(\n"
            + f"                fill=p.{mid_tok},\n"
            + f"                edge=p.{outline_tok},\n"
            + f"                highlight=p.{light_tok},\n"
            + f"                shadow=p.{dark_tok},\n"
            + f"                detail=p.{dark_tok},\n"
            + f"                inner_corner=p.{outline_tok},\n"
            + "            ),\n"
            + "            tile_w=16,\n"
            + "            tile_h=16,\n"
            + '            mode="blob47",\n'
            + "            columns=8,\n"
            + "            margin=2,\n"
            + "            spacing=2,\n"
            + "            seed=a.seed,\n"
            + "        )\n"
            + '    a.anchor("origin", 0, 0, kind="tilemap")\n'
            + '    a.hitbox("tile_bounds", 2, 2, 16, 16, kind="tile")\n'
        )

    if kind == "9slice":
        return (
            header
            + "from pixelforge.core import Asset, AssetSpec, NineSliceMargins\n\n"
            + stub_import
            + "SPEC = AssetSpec(\n"
            + f"    id={asset_id!r},\n"
            + f"    style_id={pack.id!r},\n"
            + '    perspective="front-2.5d",\n'
            + "    width=28,\n"
            + "    height=28,\n"
            + '    states=("default",),\n'
            + "    frames=1,\n"
            + "    nine_slice=NineSliceMargins(left=8, right=8, top=8, bottom=8),\n"
            + ")\n\n\n"
            + f"def render(a: Asset[{stub_class}]) -> None:\n"
            + f'    """Render starter 9-slice UI panel `{asset_id}`."""\n'
            + "    p = a.pal\n"
            + f'    with a.layer("panel", outline=p.{outline_tok}):\n'
            + f"        a.rect(2, 2, 24, 24, p.{mid_tok})\n"
            + f"        a.rect(3, 3, 22, 2, p.{light_tok})\n"
            + f"        a.rect(3, 23, 22, 2, p.{dark_tok})\n"
            + '    a.anchor("origin", 0, 0, kind="ui")\n'
            + '    a.hitbox("content", 8, 8, 12, 12, kind="ui_content")\n'
        )

    # kind == "font"
    return (
        header
        + "from pixelforge.core import (\n"
        + "    Asset,\n"
        + "    AssetSpec,\n"
        + "    compute_font_atlas_size,\n"
        + "    make_bitmap_font_spec,\n"
        + "    render_font_atlas,\n"
        + ")\n\n"
        + stub_import
        + '_FONT_SPEC = make_bitmap_font_spec("4x6", columns=16, margin=0, spacing=1)\n'
        + "_ATLAS_W, _ATLAS_H = compute_font_atlas_size(_FONT_SPEC)\n\n"
        + "SPEC = AssetSpec(\n"
        + f"    id={asset_id!r},\n"
        + f"    style_id={pack.id!r},\n"
        + '    perspective="front-2.5d",\n'
        + "    width=_ATLAS_W,\n"
        + "    height=_ATLAS_H,\n"
        + '    states=("default",),\n'
        + "    frames=1,\n"
        + "    font=_FONT_SPEC,\n"
        + ")\n\n\n"
        + f"def render(a: Asset[{stub_class}]) -> None:\n"
        + f'    """Render starter 4x6 bitmap font atlas `{asset_id}`."""\n'
        + "    p = a.pal\n"
        + f"    render_font_atlas(a, _FONT_SPEC, p.{light_tok})\n"
        + '    a.anchor("origin", 0, 0, kind="font_atlas")\n'
        + "    a.hitbox(\n"
        + '        "glyph_cell",\n'
        + "        0,\n"
        + "        0,\n"
        + "        _FONT_SPEC.glyph_width,\n"
        + "        _FONT_SPEC.glyph_height,\n"
        + '        kind="glyph",\n'
        + "    )\n"
    )


def _render_scene_skeleton(
    *,
    scene_id: str,
    parent_id: str,
    style_id: str,
) -> str:
    return (
        f'"""Declarative scene `{scene_id}`."""\n\n'
        "from __future__ import annotations\n\n"
        "from pixelforge import SceneSpec\n\n"
        "# Add SceneMountSpec / ScenePortalSpec entries as you populate mounts and portals.\n"
        "SCENE = SceneSpec(\n"
        f"    id={scene_id!r},\n"
        f"    parent_id={parent_id!r},\n"
        f"    style_id={style_id!r},\n"
        '    depth_sort="iso_y",\n'
        "    strict_bounds=True,\n"
        "    strict_perspective=True,\n"
        "    portals=(),\n"
        "    mounts=(),\n"
        ")\n"
    )


def scaffold_new_asset(
    root: Path,
    *,
    name: str,
    kind: AssetKind,
    style: str | None,
    out: str | None,
    force: bool,
    settings: PixelforgeSettings,
) -> NewScaffoldResult:
    """Create a typed `.asset.py` skeleton and sync palette stubs."""
    asset_id = _normalize_entity_id(name, suffix=".asset.py")
    styles = load_all_styles(root / "styles")
    style_id = resolve_project_style_id(
        explicit_style=style,
        default_style=settings.default_style,
        styles=styles,
        styles_dir=root / "styles",
    )
    pack = styles[style_id]
    synced_stubs = tuple(sync_palette_stubs(root))

    style_path = _find_style_path_for_id(root, style_id)
    stub_stem = (
        style_path.name.removesuffix(".style.py")
        if style_path is not None
        else style_id.replace("-", "_")
    )
    stub_module = f"styles.{stub_stem}_palette"
    stub_class = palette_stub_class_name(style_id)

    out_path = _resolve_output_path(root, "assets", f"{asset_id}.asset.py", out)
    source = _render_asset_skeleton(
        asset_id=asset_id,
        kind=kind,
        pack=pack,
        stub_module=stub_module,
        stub_class=stub_class,
    )
    _write_scaffold(out_path, source, force=force)
    return NewScaffoldResult(
        target="asset",
        entity_id=asset_id,
        path=out_path,
        style_id=style_id,
        kind=kind,
        parent_id=None,
        from_preset=None,
        synced_stubs=synced_stubs,
        next_commands=(
            f"pixelforge check {asset_id}",
            f"pixelforge render {asset_id} --sheet",
        ),
    )


def scaffold_new_scene(
    root: Path,
    *,
    name: str,
    parent: str | None,
    style: str | None,
    out: str | None,
    force: bool,
    settings: PixelforgeSettings,
) -> NewScaffoldResult:
    """Create a `.scene.py` skeleton bound to an optional parent asset."""
    scene_id = _normalize_entity_id(name, suffix=".scene.py")
    parent_id = (
        _normalize_entity_id(parent, suffix=".asset.py")
        if parent is not None
        else f"{scene_id}_base"
    )
    styles = load_all_styles(root / "styles")
    if styles:
        style_id = resolve_project_style_id(
            explicit_style=style,
            default_style=settings.default_style,
            styles=styles,
            styles_dir=root / "styles",
        )
    else:
        style_id = style or settings.default_style or DEFAULT_INIT_PRESET

    out_path = _resolve_output_path(root, "assets", f"{scene_id}.scene.py", out)
    source = _render_scene_skeleton(
        scene_id=scene_id,
        parent_id=parent_id,
        style_id=style_id,
    )
    _write_scaffold(out_path, source, force=force)
    return NewScaffoldResult(
        target="scene",
        entity_id=scene_id,
        path=out_path,
        style_id=style_id,
        kind=None,
        parent_id=parent_id,
        from_preset=None,
        synced_stubs=(),
        next_commands=(
            "pixelforge check",
            f"pixelforge inspect scenes {scene_id}",
        ),
    )


def scaffold_new_style(
    root: Path,
    *,
    name: str,
    from_preset: str | None,
    out: str | None,
    force: bool,
) -> NewScaffoldResult:
    """Create a `.style.py` skeleton (optionally cloned from a built-in preset) and sync stubs."""
    style_id = _normalize_style_id(name)
    slug = style_id.replace("-", "_")

    if from_preset is not None:
        if not is_builtin_preset(from_preset):
            available = ", ".join(PRESET_IDS)
            msg = f"Unknown built-in preset {from_preset!r}; available: {available}"
            raise ValueError(msg)
        raw_source = read_preset_source(from_preset)
        source, count = _STYLE_ID_ASSIGN_RE.subn(
            rf"\g<1>{style_id!r}",
            raw_source,
            count=1,
        )
        if count == 0:
            source = starter_style_source(style_id)
    else:
        source = starter_style_source(style_id)

    out_path = _resolve_output_path(root, "styles", f"{slug}.style.py", out)
    _write_scaffold(out_path, source, force=force)
    synced_stubs = tuple(sync_palette_stubs(root))
    return NewScaffoldResult(
        target="style",
        entity_id=style_id,
        path=out_path,
        style_id=style_id,
        kind=None,
        parent_id=None,
        from_preset=from_preset,
        synced_stubs=synced_stubs,
        next_commands=(
            f"pixelforge inspect style {style_id}",
            f"pixelforge new asset my_prop --style {style_id}",
        ),
    )


def emit_new_result(
    result: NewScaffoldResult,
    *,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    """Emit a `pixelforge new` result in `llm`, `json`, or `human` format."""
    if output_format == "json":
        payload: dict[str, object] = {
            "command": "new",
            "target": result.target,
            "id": result.entity_id,
            "path": str(result.path),
            "style_id": result.style_id,
            "kind": result.kind,
            "parent_id": result.parent_id,
            "from_preset": result.from_preset,
            "synced_stubs": [str(p) for p in result.synced_stubs],
            "next": list(result.next_commands),
        }
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        extras: list[str] = []
        if result.kind is not None:
            extras.append(f"kind: {result.kind}")
        if result.style_id is not None:
            extras.append(f"style: {result.style_id}")
        if result.parent_id is not None:
            extras.append(f"parent: {result.parent_id}")
        if result.from_preset is not None:
            extras.append(f"preset: {result.from_preset}")
        suffix = f" ({', '.join(extras)})" if extras else ""
        out(f"Created {result.target} '{result.entity_id}' at {result.path}{suffix}")
        for stub in result.synced_stubs:
            out(f"Synced palette stub: {stub}")
        if result.next_commands:
            out(f"Next: {' | '.join(result.next_commands)}")
        return

    # output_format == "llm"
    parts = [f"NEW {result.target} {result.entity_id}", f"path={result.path}"]
    if result.kind is not None:
        parts.append(f"kind={result.kind}")
    if result.style_id is not None:
        parts.append(f"style={result.style_id}")
    if result.parent_id is not None:
        parts.append(f"parent={result.parent_id}")
    if result.from_preset is not None:
        parts.append(f"preset={result.from_preset}")
    out(" ".join(parts))
    for stub in result.synced_stubs:
        out(f"STUB_SYNCED {stub}")
    if result.next_commands:
        out(f"NEXT {' | '.join(result.next_commands)}")
