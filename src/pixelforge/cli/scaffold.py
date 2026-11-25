"""Starter project scaffolding helpers for `pixelforge init`."""

from __future__ import annotations

from pathlib import Path


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


def _write_if_allowed(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def scaffold_project(root: Path, *, style_id: str, force: bool = False) -> list[Path]:
    """Create starter `styles/`, `assets/`, `.pixelforge/`, and `.env.example` under `root`."""
    slug = style_id.replace("-", "_")
    for directory in ("styles", "assets", ".pixelforge"):
        (root / directory).mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    style_path = root / "styles" / f"{slug}.style.py"
    asset_path = root / "assets" / "example_crate.asset.py"
    env_example = root / ".env.example"

    if _write_if_allowed(style_path, starter_style_source(style_id), force=force):
        created.append(style_path)
    if _write_if_allowed(asset_path, starter_asset_source(style_id), force=force):
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
