"""CLI `new ui-kit` scaffolder generating cohesive themed UI component kits."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pixelforge.cli.output import OutputFn, OutputFormat
from pixelforge.cli.settings import PixelforgeSettings, resolve_project_style_id
from pixelforge.core.palette_stub import palette_stub_class_name
from pixelforge.core.prefabs.ui import (
    UiThemeConfig,
    UiThemeName,
    get_ui_theme_config,
    list_icons,
)
from pixelforge.core.types import StylePack
from pixelforge.export.ui_styleguide import (
    UiStyleguideOptions,
    generate_ui_styleguide_sheet,
)
from pixelforge.guard.runner import load_all_styles, sync_palette_stubs

_KIT_ID_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass(frozen=True)
class UiKitScaffoldResult:
    """Structured outcome of a `pixelforge new ui-kit` invocation."""

    kit_id: str
    theme: UiThemeName
    style_id: str
    out_dir: Path
    files: tuple[Path, ...]
    synced_stubs: tuple[Path, ...]
    styleguide_path: Path | None
    next_commands: tuple[str, ...]


def _normalize_kit_id(raw_name: str) -> str:
    cleaned = raw_name.strip().replace("-", "_")
    if not _KIT_ID_RE.fullmatch(cleaned):
        msg = f"Invalid ui-kit id {raw_name!r}; expected [a-zA-Z_][a-zA-Z0-9_]*"
        raise ValueError(msg)
    return cleaned


def _resolve_kit_dir(root: Path, kit_id: str, out: str | None) -> Path:
    if out is None:
        return root / "assets" / kit_id
    candidate = Path(out)
    return candidate if candidate.is_absolute() else root / candidate


def _asset_header(
    doc: str,
    asset_id: str,
    stub_module: str,
    stub_class: str,
    extra_imports: str,
) -> str:
    return (
        f'"""{doc}"""\n\n'
        "from __future__ import annotations\n\n"
        "from typing import TYPE_CHECKING\n\n"
        "from pixelforge.core import Asset, AssetSpec\n"
        f"{extra_imports}\n"
        f"if TYPE_CHECKING:\n    from {stub_module} import {stub_class}\n\n"
    )


def _render_panel_source(
    kit_id: str,
    pack: StylePack,
    cfg: UiThemeConfig,
    stub_module: str,
    stub_class: str,
) -> str:
    asset_id = f"{kit_id}_panel"
    head = _asset_header(
        f"UI panel component for `{kit_id}` ({cfg.name}).",
        asset_id,
        stub_module,
        stub_class,
        "from pixelforge.core.prefabs.ui import UiPalette, ui_panel, ui_panel_margins\n",
    )
    return (
        head
        + "SPEC = AssetSpec(\n"
        + f"    id={asset_id!r},\n"
        + f"    style_id={pack.id!r},\n"
        + '    perspective="top-down",\n'
        + "    width=48,\n"
        + "    height=36,\n"
        + '    states=("default", "titled", "recessed"),\n'
        + f"    nine_slice=ui_panel_margins(0, 0, 48, 36, beveled={cfg.beveled!r}, "
        + f"corner_cut={cfg.corner_cut}),\n"
        + ")\n\n\n"
        + f"def render(a: Asset[{stub_class}]) -> None:\n"
        + f'    """Render `{asset_id}` across default, titled, and recessed states."""\n'
        + "    pal = UiPalette.from_style(a)\n"
        + '    title_h = 0 if a.state != "titled" else '
        + f"{cfg.title_bar_h}\n"
        + f'    recessed = {cfg.recessed_panel!r} or a.state == "recessed"\n'
        + "    ui_panel(\n"
        + "        a,\n"
        + "        0,\n"
        + "        0,\n"
        + "        48,\n"
        + "        36,\n"
        + "        pal,\n"
        + "        title_bar_h=title_h,\n"
        + f"        beveled={cfg.beveled!r},\n"
        + f"        corner_cut={cfg.corner_cut},\n"
        + "        recessed=recessed,\n"
        + "        emit_content_hitbox=True,\n"
        + "    )\n"
    )


def _render_button_source(
    kit_id: str,
    pack: StylePack,
    cfg: UiThemeConfig,
    stub_module: str,
    stub_class: str,
) -> str:
    asset_id = f"{kit_id}_button"
    head = _asset_header(
        f"UI button component for `{kit_id}` ({cfg.name}).",
        asset_id,
        stub_module,
        stub_class,
        "from pixelforge.core.prefabs.ui import (\n"
        "    UiButtonState,\n"
        "    UiPalette,\n"
        "    ui_button,\n"
        "    ui_button_margins,\n"
        ")\n",
    )
    return (
        head
        + "SPEC = AssetSpec(\n"
        + f"    id={asset_id!r},\n"
        + f"    style_id={pack.id!r},\n"
        + '    perspective="top-down",\n'
        + "    width=40,\n"
        + "    height=14,\n"
        + '    states=("normal", "hover", "pressed", "disabled"),\n'
        + f"    nine_slice=ui_button_margins(0, 0, 40, 14, corner_cut={cfg.corner_cut}),\n"
        + ")\n\n\n"
        + f"def render(a: Asset[{stub_class}]) -> None:\n"
        + f'    """Render `{asset_id}` across interactive button states."""\n'
        + "    pal = UiPalette.from_style(a)\n"
        + "    state_map: dict[str, UiButtonState] = {\n"
        + '        "normal": "normal",\n'
        + '        "hover": "hover",\n'
        + '        "pressed": "pressed",\n'
        + '        "disabled": "disabled",\n'
        + "    }\n"
        + "    ui_button(\n"
        + "        a,\n"
        + "        0,\n"
        + "        0,\n"
        + "        40,\n"
        + "        14,\n"
        + "        pal,\n"
        + "        state=state_map[a.state],\n"
        + f"        corner_cut={cfg.corner_cut},\n"
        + "        emit_content_hitbox=True,\n"
        + "    )\n"
    )


def _render_bar_source(
    kit_id: str,
    pack: StylePack,
    cfg: UiThemeConfig,
    stub_module: str,
    stub_class: str,
) -> str:
    asset_id = f"{kit_id}_bar"
    head = _asset_header(
        f"UI progress bar component for `{kit_id}` ({cfg.name}).",
        asset_id,
        stub_module,
        stub_class,
        "from pixelforge.core.prefabs.ui import (\n"
        "    UiPalette,\n"
        "    ui_progress_bar,\n"
        "    ui_progress_bar_margins,\n"
        ")\n",
    )
    return (
        head
        + "SPEC = AssetSpec(\n"
        + f"    id={asset_id!r},\n"
        + f"    style_id={pack.id!r},\n"
        + '    perspective="top-down",\n'
        + "    width=48,\n"
        + "    height=8,\n"
        + '    states=("empty", "half", "full"),\n'
        + "    nine_slice=ui_progress_bar_margins(0, 0, 48, 8),\n"
        + ")\n\n\n"
        + f"def render(a: Asset[{stub_class}]) -> None:\n"
        + f'    """Render `{asset_id}` across empty, half, and full states."""\n'
        + "    pal = UiPalette.from_style(a)\n"
        + '    values = {"empty": 0.0, "half": 0.5, "full": 1.0}\n'
        + "    ui_progress_bar(\n"
        + "        a,\n"
        + "        0,\n"
        + "        0,\n"
        + "        48,\n"
        + "        8,\n"
        + "        pal,\n"
        + "        value=values[a.state],\n"
        + f"        segments={cfg.bar_segments},\n"
        + f"        show_specular={cfg.bar_specular!r},\n"
        + "        emit_content_hitbox=True,\n"
        + "    )\n"
    )


def _render_slot_source(
    kit_id: str,
    pack: StylePack,
    cfg: UiThemeConfig,
    stub_module: str,
    stub_class: str,
) -> str:
    asset_id = f"{kit_id}_slot"
    head = _asset_header(
        f"UI inventory slot component for `{kit_id}` ({cfg.name}).",
        asset_id,
        stub_module,
        stub_class,
        "from pixelforge.core.prefabs.ui import (\n"
        "    UiPalette,\n"
        "    UiSlotState,\n"
        "    ui_slot,\n"
        "    ui_slot_margins,\n"
        ")\n",
    )
    return (
        head
        + "SPEC = AssetSpec(\n"
        + f"    id={asset_id!r},\n"
        + f"    style_id={pack.id!r},\n"
        + '    perspective="top-down",\n'
        + "    width=20,\n"
        + "    height=20,\n"
        + '    states=("empty", "hover", "selected", "locked"),\n'
        + f"    nine_slice=ui_slot_margins(0, 0, 20, 20, corner_cut={cfg.corner_cut}),\n"
        + ")\n\n\n"
        + f"def render(a: Asset[{stub_class}]) -> None:\n"
        + f'    """Render `{asset_id}` across slot states."""\n'
        + "    pal = UiPalette.from_style(a)\n"
        + "    state_map: dict[str, UiSlotState] = {\n"
        + '        "empty": "empty",\n'
        + '        "hover": "hover",\n'
        + '        "selected": "selected",\n'
        + '        "locked": "locked",\n'
        + "    }\n"
        + "    ui_slot(\n"
        + "        a,\n"
        + "        0,\n"
        + "        0,\n"
        + "        20,\n"
        + "        20,\n"
        + "        pal,\n"
        + "        state=state_map[a.state],\n"
        + f"        corner_cut={cfg.corner_cut},\n"
        + "        emit_content_hitbox=True,\n"
        + "    )\n"
    )


def _render_badge_source(
    kit_id: str,
    pack: StylePack,
    cfg: UiThemeConfig,
    stub_module: str,
    stub_class: str,
) -> str:
    asset_id = f"{kit_id}_badge"
    head = _asset_header(
        f"UI status badge component for `{kit_id}` ({cfg.name}).",
        asset_id,
        stub_module,
        stub_class,
        "from pixelforge.core.prefabs.ui import (\n"
        "    UiBadgeTone,\n"
        "    UiPalette,\n"
        "    ui_badge,\n"
        "    ui_badge_margins,\n"
        ")\n",
    )
    return (
        head
        + "SPEC = AssetSpec(\n"
        + f"    id={asset_id!r},\n"
        + f"    style_id={pack.id!r},\n"
        + '    perspective="top-down",\n'
        + "    width=24,\n"
        + "    height=10,\n"
        + '    states=("neutral", "info", "success", "warning", "danger"),\n'
        + f"    nine_slice=ui_badge_margins(0, 0, 24, 10, pill={cfg.badge_pill!r}),\n"
        + ")\n\n\n"
        + f"def render(a: Asset[{stub_class}]) -> None:\n"
        + f'    """Render `{asset_id}` across semantic badge tones."""\n'
        + "    pal = UiPalette.from_style(a)\n"
        + "    tone_map: dict[str, UiBadgeTone] = {\n"
        + '        "neutral": "neutral",\n'
        + '        "info": "info",\n'
        + '        "success": "success",\n'
        + '        "warning": "warning",\n'
        + '        "danger": "danger",\n'
        + "    }\n"
        + "    ui_badge(\n"
        + "        a,\n"
        + "        0,\n"
        + "        0,\n"
        + "        24,\n"
        + "        10,\n"
        + "        pal,\n"
        + "        tone=tone_map[a.state],\n"
        + f"        pill={cfg.badge_pill!r},\n"
        + "        emit_content_hitbox=True,\n"
        + "    )\n"
    )


def _render_cursor_source(
    kit_id: str,
    pack: StylePack,
    cfg: UiThemeConfig,
    stub_module: str,
    stub_class: str,
) -> str:
    asset_id = f"{kit_id}_cursor"
    head = _asset_header(
        f"UI cursor sprites for `{kit_id}` ({cfg.name}).",
        asset_id,
        stub_module,
        stub_class,
        "from pixelforge.core.prefabs.ui import UiCursorKind, UiPalette, ui_cursor\n",
    )
    return (
        head
        + "SPEC = AssetSpec(\n"
        + f"    id={asset_id!r},\n"
        + f"    style_id={pack.id!r},\n"
        + '    perspective="top-down",\n'
        + "    width=16,\n"
        + "    height=16,\n"
        + '    states=("pointer", "hand", "crosshair", "resize_h", "resize_v", "text"),\n'
        + ")\n\n\n"
        + f"def render(a: Asset[{stub_class}]) -> None:\n"
        + f'    """Render `{asset_id}` with exact `hotspot` anchor."""\n'
        + "    pal = UiPalette.from_style(a)\n"
        + "    kind_map: dict[str, UiCursorKind] = {\n"
        + '        "pointer": "pointer",\n'
        + '        "hand": "hand",\n'
        + '        "crosshair": "crosshair",\n'
        + '        "resize_h": "resize_h",\n'
        + '        "resize_v": "resize_v",\n'
        + '        "text": "text",\n'
        + "    }\n"
        + "    ui_cursor(a, 0, 0, kind_map[a.state], pal, emit_hotspot_anchor=True)\n"
    )


def _render_icons_source(
    kit_id: str,
    pack: StylePack,
    cfg: UiThemeConfig,
    stub_module: str,
    stub_class: str,
) -> str:
    asset_id = f"{kit_id}_icons"
    icons_16 = tuple(list_icons(pack=cfg.icon_pack, size=16)[:3])
    head = _asset_header(
        f"UI thematic icon strip for `{kit_id}` ({cfg.name}).",
        asset_id,
        stub_module,
        stub_class,
        "from pixelforge.core.prefabs.ui import UiPalette, ui_icon_16\n",
    )
    return (
        head
        + "SPEC = AssetSpec(\n"
        + f"    id={asset_id!r},\n"
        + f"    style_id={pack.id!r},\n"
        + '    perspective="top-down",\n'
        + "    width=56,\n"
        + "    height=20,\n"
        + '    states=("idle",),\n'
        + ")\n\n\n"
        + f"def render(a: Asset[{stub_class}]) -> None:\n"
        + f'    """Render representative 16x16 icons from `{cfg.icon_pack}` pack."""\n'
        + "    pal = UiPalette.from_style(a)\n"
        + f"    icons = {icons_16!r}\n"
        + "    for idx, name in enumerate(icons):\n"
        + "        ui_icon_16(\n"
        + "            a,\n"
        + "            2 + idx * 18,\n"
        + "            2,\n"
        + "            name,\n"
        + "            pal.text,\n"
        + f"            pack={cfg.icon_pack!r},\n"
        + "            accent=pal.accent_bright,\n"
        + "            outline=pal.border_outer,\n"
        + "        )\n"
        + '    a.anchor("center", 28, 10, kind="origin")\n'
    )


def scaffold_new_ui_kit(
    root: Path,
    *,
    name: str,
    theme: str,
    style: str | None,
    out: str | None,
    sheet: bool,
    force: bool,
    settings: PixelforgeSettings,
) -> UiKitScaffoldResult:
    """Scaffold a cohesive themed UI component kit and optional styleguide `.contact.png`."""
    kit_id = _normalize_kit_id(name)
    cfg = get_ui_theme_config(theme)

    styles = load_all_styles(root / "styles")
    if not styles:
        msg = f"No valid .style.py files found in {root / 'styles'}. Run `pixelforge init` first."
        raise FileNotFoundError(msg)

    style_id = resolve_project_style_id(
        explicit_style=style,
        default_style=settings.default_style,
        styles=styles,
        styles_dir=root / "styles",
    )
    pack = styles[style_id]
    synced_stubs = tuple(sync_palette_stubs(root))
    style_slug = style_id.replace("-", "_")
    stub_module = f"styles.{style_slug}_palette"
    stub_class = palette_stub_class_name(style_id)

    out_dir = _resolve_kit_dir(root, kit_id, out)
    specs: tuple[tuple[str, str], ...] = (
        (
            f"{kit_id}_panel.asset.py",
            _render_panel_source(kit_id, pack, cfg, stub_module, stub_class),
        ),
        (
            f"{kit_id}_button.asset.py",
            _render_button_source(kit_id, pack, cfg, stub_module, stub_class),
        ),
        (
            f"{kit_id}_bar.asset.py",
            _render_bar_source(kit_id, pack, cfg, stub_module, stub_class),
        ),
        (
            f"{kit_id}_slot.asset.py",
            _render_slot_source(kit_id, pack, cfg, stub_module, stub_class),
        ),
        (
            f"{kit_id}_badge.asset.py",
            _render_badge_source(kit_id, pack, cfg, stub_module, stub_class),
        ),
        (
            f"{kit_id}_cursor.asset.py",
            _render_cursor_source(kit_id, pack, cfg, stub_module, stub_class),
        ),
        (
            f"{kit_id}_icons.asset.py",
            _render_icons_source(kit_id, pack, cfg, stub_module, stub_class),
        ),
    )

    if not force:
        for filename, _ in specs:
            target_path = out_dir / filename
            if target_path.exists():
                msg = (
                    f"Refusing to overwrite existing file {target_path} (pass --force to overwrite)"
                )
                raise FileExistsError(msg)

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, source in specs:
        target_path = out_dir / filename
        target_path.write_text(source, encoding="utf-8")
        written.append(target_path)

    styleguide_path: Path | None = None
    if sheet:
        result = generate_ui_styleguide_sheet(
            pack,
            UiStyleguideOptions(theme=cfg.name, title=f"{kit_id.upper()} | {cfg.name} | {pack.id}"),
        )
        styleguide_path = root / ".pixelforge" / "sheets" / f"{kit_id}_styleguide.contact.png"
        styleguide_path.parent.mkdir(parents=True, exist_ok=True)
        styleguide_path.write_bytes(result.png)

    return UiKitScaffoldResult(
        kit_id=kit_id,
        theme=cfg.name,
        style_id=pack.id,
        out_dir=out_dir,
        files=tuple(written),
        synced_stubs=synced_stubs,
        styleguide_path=styleguide_path,
        next_commands=(
            "pixelforge check",
            f"pixelforge render {kit_id}_panel --sheet",
        ),
    )


def emit_ui_kit_result(
    result: UiKitScaffoldResult,
    *,
    output_format: OutputFormat,
    out: OutputFn,
) -> None:
    """Emit a `pixelforge new ui-kit` result in `llm`, `json`, or `human` format."""
    if output_format == "json":
        payload: dict[str, object] = {
            "command": "new",
            "target": "ui-kit",
            "id": result.kit_id,
            "theme": result.theme,
            "style_id": result.style_id,
            "out_dir": str(result.out_dir),
            "files": [str(p) for p in result.files],
            "synced_stubs": [str(p) for p in result.synced_stubs],
            "styleguide_path": (
                str(result.styleguide_path) if result.styleguide_path is not None else None
            ),
            "next": list(result.next_commands),
        }
        out(json.dumps(payload, indent=2))
        return

    if output_format == "human":
        out(
            f"Created ui-kit '{result.kit_id}' at {result.out_dir} "
            f"(theme: {result.theme}, style: {result.style_id}, {len(result.files)} assets)"
        )
        if result.styleguide_path is not None:
            out(f"Styleguide sheet: {result.styleguide_path}")
        if result.next_commands:
            out(f"Next: {' | '.join(result.next_commands)}")
        return

    out(
        f"NEW ui-kit {result.kit_id} theme={result.theme} style={result.style_id} "
        f"dir={result.out_dir} files={len(result.files)}"
    )
    if result.styleguide_path is not None:
        out(f"STYLEGUIDE {result.styleguide_path}")
    for stub in result.synced_stubs:
        out(f"STUB_SYNCED {stub}")
    if result.next_commands:
        out(f"NEXT {' | '.join(result.next_commands)}")
