"""Starter project scaffolding helpers for `pixelforge init`."""

from __future__ import annotations

from pathlib import Path

from pixelforge.core.palette_stub import generate_palette_stub, palette_stub_path
from pixelforge.core.types import PaletteColor, StylePack
from pixelforge.presets import (
    DEFAULT_INIT_PRESET,
    is_builtin_preset,
    load_preset_style,
    read_preset_source,
)


def starter_style_source(style_id: str) -> str:
    """Return the starter `.style.py` module source for `style_id`."""
    return f'''"""Starter StylePack for {style_id}."""

from __future__ import annotations

from pixelforge.core.types import PaletteColor, StylePack

STYLE = StylePack(
    id={style_id!r},
    perspective="iso-2:1",
    lighting_angle="top-left",
    outline_index=0,
    palette=(
        PaletteColor(index=0, name="OUTLINE", hex="#0d1117", flags=("outline",)),
        PaletteColor(index=1, name="CHASSIS_DARK", hex="#1f2937", flags=("surface",)),
        PaletteColor(index=2, name="CHASSIS_MID", hex="#374151", flags=("surface",)),
        PaletteColor(index=3, name="CHASSIS_LIGHT", hex="#6b7280", flags=("bright",)),
        PaletteColor(index=4, name="ACCENT_CYAN", hex="#38bdf8", flags=("emissive",)),
    ),
)
'''


def starter_palette_stub_source(style_id: str) -> str:
    """Return the starter typed palette stub source for `style_id`."""
    pack = StylePack(
        id=style_id,
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="CHASSIS_DARK", hex="#1f2937", flags=("surface",)),
            PaletteColor(index=2, name="CHASSIS_MID", hex="#374151", flags=("surface",)),
            PaletteColor(index=3, name="CHASSIS_LIGHT", hex="#6b7280", flags=("bright",)),
            PaletteColor(index=4, name="ACCENT_CYAN", hex="#38bdf8", flags=("emissive",)),
        ),
    )
    return generate_palette_stub(pack)


def starter_asset_source(style_id: str) -> str:
    """Return the starter `.asset.py` module source bound to `style_id`."""
    return f'''"""Starter compositional pixel asset."""

from __future__ import annotations

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec

SPEC = AssetSpec(
    id="example_crate",
    style_id={style_id!r},
    perspective="iso-2:1",
    width=24,
    height=24,
    states=("idle",),
    frames=1,
    fps=4,
)


def render(a: Asset) -> None:
    """Render a minimal isometric crate."""
    p = a.pal
    with a.layer("body", outline=p.OUTLINE):
        a.iso_box(
            x=12,
            y=10,
            w=8,
            d=8,
            h=6,
            top=p.CHASSIS_LIGHT,
            left=p.CHASSIS_MID,
            right=p.CHASSIS_DARK,
        )
    a.put(12, 11, p.ACCENT_CYAN)
    a.put(13, 11, p.ACCENT_CYAN)
    a.anchor("foot", 12, 20)
'''


def _hex_luma(hex_color: str) -> float:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _pick_starter_tokens(pack: StylePack) -> tuple[str, str, str, str, str | None]:
    outline_entry = next(
        (c for c in pack.palette if c.index == pack.outline_index),
        pack.palette[0],
    )
    non_outline = [
        c for c in pack.palette if c.index != outline_entry.index and "emissive" not in c.flags
    ]
    if not non_outline:
        non_outline = [c for c in pack.palette if c.index != outline_entry.index]
    if not non_outline:
        non_outline = [outline_entry]

    by_luma = sorted(non_outline, key=lambda c: (_hex_luma(c.hex), c.index))
    dark_tok = by_luma[0].name
    mid_tok = by_luma[len(by_luma) // 2].name
    light_tok = by_luma[-1].name

    emissive = [c for c in pack.palette if "emissive" in c.flags]
    if emissive:
        accent_tok: str | None = emissive[0].name
    else:
        accents = [
            c
            for c in non_outline
            if ("accent" in c.flags or "bright" in c.flags) and c.name != light_tok
        ]
        accent_tok = accents[0].name if accents else None

    return outline_entry.name, light_tok, mid_tok, dark_tok, accent_tok


def starter_asset_source_for_style(pack: StylePack) -> str:
    """Return a starter `.asset.py` module tailored to `pack`'s tokens and perspective."""
    outline_tok, light_tok, mid_tok, dark_tok, accent_tok = _pick_starter_tokens(pack)
    accent_lines = ""
    if accent_tok is not None:
        accent_lines = f"    a.put(12, 11, p.{accent_tok})\n    a.put(13, 11, p.{accent_tok})\n"
    return f'''"""Starter compositional pixel asset."""

from __future__ import annotations

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec

SPEC = AssetSpec(
    id="example_crate",
    style_id={pack.id!r},
    perspective={pack.perspective!r},
    width=24,
    height=24,
    states=("idle",),
    frames=1,
    fps=4,
)


def render(a: Asset) -> None:
    """Render a minimal isometric crate."""
    p = a.pal
    with a.layer("body", outline=p.{outline_tok}):
        a.iso_box(
            x=12,
            y=10,
            w=8,
            d=8,
            h=6,
            top=p.{light_tok},
            left=p.{mid_tok},
            right=p.{dark_tok},
        )
{accent_lines}    a.anchor("foot", 12, 20)
'''


def _write_if_allowed(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def scaffold_project(
    root: Path,
    *,
    style_id: str = DEFAULT_INIT_PRESET,
    force: bool = False,
) -> list[Path]:
    """Create starter `styles/`, `assets/`, `.pixelforge/`, and `.env.example` under `root`."""
    slug = style_id.replace("-", "_")
    for directory in ("styles", "assets", ".pixelforge"):
        (root / directory).mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    style_path = root / "styles" / f"{slug}.style.py"
    stub_path = palette_stub_path(style_path)
    asset_path = root / "assets" / "example_crate.asset.py"
    env_example = root / ".env.example"

    if is_builtin_preset(style_id):
        style_src = read_preset_source(style_id)
        preset_pack = load_preset_style(style_id)
        stub_src = generate_palette_stub(preset_pack)
        asset_src = starter_asset_source_for_style(preset_pack)
    else:
        style_src = starter_style_source(style_id)
        stub_src = starter_palette_stub_source(style_id)
        asset_src = starter_asset_source(style_id)

    if _write_if_allowed(style_path, style_src, force=force):
        created.append(style_path)
    if _write_if_allowed(stub_path, stub_src, force=force):
        created.append(stub_path)
    if _write_if_allowed(asset_path, asset_src, force=force):
        created.append(asset_path)

    env_content = (
        "PIXELFORGE_OUT_DIR=dist\n"
        "PIXELFORGE_SHEETS_DIR=.pixelforge/sheets\n"
        "PIXELFORGE_PREVIEWS_DIR=.pixelforge/previews\n"
        "PIXELFORGE_DIFFS_DIR=.pixelforge/diffs\n"
        f"PIXELFORGE_DEFAULT_STYLE={style_id}\n"
    )
    if _write_if_allowed(env_example, env_content, force=force):
        created.append(env_example)

    return created
