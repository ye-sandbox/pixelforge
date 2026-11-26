"""Tests proving `core/` and `prefabs/` have zero `homelab-16bit` coupling."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import numpy as np

from pixelforge import Asset, AssetSpec, PaletteColor, StylePack, prefabs
from pixelforge.core.palette_stub import generate_palette_stub, palette_stub_path
from pixelforge.core.types import TRANSPARENT_INDEX
from pixelforge.export.bundle import (
    ExportBundleOptions,
    ExportBundleResult,
    export_asset_bundle,
    render_asset_frames,
    write_manifest,
)
from pixelforge.guard.runner import (
    discover_asset_files,
    load_all_styles,
    load_asset_module,
    run_checks,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = ROOT_DIR / "src" / "pixelforge" / "core"

_FORBIDDEN_HOMELAB_TOKENS = (
    "homelab-16bit",
    "homelab_16bit",
    "homelab16bitpalette",
    "idle-datacenter",
    "homelab",
)


def _foreign_style() -> StylePack:
    """Build a minimal StylePack sharing zero token names with `homelab-16bit`."""
    return StylePack(
        id="foreign-minimal",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="F_OUTLINE", hex="#101014", flags=("outline",)),
            PaletteColor(index=1, name="F_FLOOR", hex="#2a2d38", flags=("surface",)),
            PaletteColor(index=2, name="F_WALL", hex="#3d4252", flags=("surface",)),
            PaletteColor(index=3, name="F_WOOD", hex="#8a5a3c", flags=("surface",)),
            PaletteColor(index=4, name="F_WOOD_D", hex="#543623", flags=("shadow",)),
            PaletteColor(index=5, name="F_METAL", hex="#626c7d", flags=("metal",)),
            PaletteColor(index=6, name="F_METAL_H", hex="#9aa5b8", flags=("bright",)),
            PaletteColor(index=7, name="F_ACCENT", hex="#c94a5a", flags=("accent",)),
            PaletteColor(index=8, name="F_GLOW", hex="#52e5ff", flags=("emissive", "bright")),
            PaletteColor(index=9, name="F_SKIN", hex="#e3b596", flags=("surface",)),
        ),
    )


def test_core_and_prefabs_have_zero_homelab_coupling() -> None:
    """Verify every module under `src/pixelforge/core/` has zero `homelab-16bit` coupling."""
    py_files = sorted(CORE_DIR.rglob("*.py"))
    assert len(py_files) > 0

    for path in py_files:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in _FORBIDDEN_HOMELAB_TOKENS:
            assert forbidden not in lowered, (
                f"{path.relative_to(ROOT_DIR)} references {forbidden!r}"
            )

        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in ("styles", "assets"), (
                        f"{path.relative_to(ROOT_DIR)} imports {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                top = node.module.split(".")[0]
                assert top not in ("styles", "assets"), (
                    f"{path.relative_to(ROOT_DIR)} imports from {node.module!r}"
                )


def test_topdown_rpg_style_pack_and_stub_contract() -> None:
    """Verify `topdown-rpg` StylePack metadata and auto-generated Protocol stub."""
    styles = load_all_styles(ROOT_DIR / "styles")
    assert "topdown-rpg" in styles
    style = styles["topdown-rpg"]

    assert style.perspective == "top-down"
    assert style.lighting_angle == "top-left"
    assert style.outline_index == 1
    assert len(style.palette) == 32
    assert [c.index for c in style.palette] == list(range(32))
    assert "dusk" in style.variants
    assert style.reflections["TORCH_CORE"] == "TORCH_GLOW"

    stub_file = palette_stub_path(ROOT_DIR / "styles" / "topdown_rpg.style.py")
    assert stub_file.is_file()
    assert stub_file.read_text(encoding="utf-8") == generate_palette_stub(style)


def test_topdown_rpg_assets_render_and_export(tmp_path: Path) -> None:
    """Verify all `topdown-rpg` sample assets pass guards and export cleanly."""
    styles = load_all_styles(ROOT_DIR / "styles")
    style = styles["topdown-rpg"]
    rpg_files = sorted((ROOT_DIR / "assets" / "rpg").glob("*.asset.py"))
    assert [p.stem.removesuffix(".asset") for p in rpg_files] == [
        "dungeon_chest",
        "dungeon_path_16",
        "stone_brazier",
    ]

    report = run_checks(ROOT_DIR, strict_orphans=True)
    assert report.passed
    assert report.violations == ()

    bundles: list[ExportBundleResult] = []
    for asset_path in discover_asset_files(ROOT_DIR / "assets" / "rpg"):
        loaded = load_asset_module(asset_path)
        assert loaded.SPEC.style_id == "topdown-rpg"
        first = render_asset_frames(loaded, style)
        second = render_asset_frames(loaded, style)
        assert [hashlib.sha256(f.surface.data.tobytes()).hexdigest() for f in first] == [
            hashlib.sha256(f.surface.data.tobytes()).hexdigest() for f in second
        ]
        for frame in first:
            arr = frame.surface.data
            valid = (arr == TRANSPARENT_INDEX) | (arr < len(style.palette))
            assert bool(np.all(valid))

        bundle = export_asset_bundle(loaded, style, ExportBundleOptions(emissive=True))
        bundles.append(bundle)

    manifest_map = {b.manifest.id: b.manifest for b in bundles}
    manifest_path, dts_path = write_manifest(manifest_map, tmp_path)
    assert manifest_path.is_file()
    assert dts_path.is_file()
    dts_text = dts_path.read_text(encoding="utf-8")
    assert "DungeonChestManifestEntry" in dts_text
    assert "StoneBrazierManifestEntry" in dts_text
    assert "DungeonPath16ManifestEntry" in dts_text


def test_prefabs_work_with_foreign_style_pack() -> None:
    """Verify `prefabs/` render cleanly using an arbitrary non-homelab StylePack."""
    style = _foreign_style()
    spec = AssetSpec(
        id="foreign_probe",
        style_id="foreign-minimal",
        width=128,
        height=96,
        perspective="iso-2:1",
        states=("default",),
        seed=42,
    )
    asset = Asset(spec, style)
    p = asset.pal

    prefabs.sky_backdrop(
        asset,
        bands=(p.F_WALL, p.F_FLOOR),
        region=(0, 0, 128, 32),
    )
    prefabs.iso_room_shell(
        asset,
        64,
        54,
        36,
        36,
        32,
        floor=p.F_FLOOR,
        left_wall=p.F_WALL,
        right_wall=p.F_FLOOR,
        outline=p.F_OUTLINE,
    )
    prefabs.iso_desk(
        asset,
        64,
        66,
        24,
        12,
        top=p.F_WOOD,
        left=p.F_WOOD_D,
        right=p.F_WOOD_D,
        leg_top=p.F_METAL,
        leg_left=p.F_METAL,
        leg_right=p.F_METAL,
        outline=p.F_OUTLINE,
        highlight=p.F_METAL_H,
    )
    prefabs.wall_clock(
        asset,
        (40, 26),
        (52, 26),
        (40, 38),
        frame=p.F_METAL,
        face=p.F_METAL_H,
        hands=p.F_ACCENT,
        outline=p.F_OUTLINE,
    )
    prefabs.avatar_character(
        asset,
        92,
        74,
        prefabs.CharacterPalette(
            skin_light=p.F_SKIN,
            skin_mid=p.F_SKIN,
            skin_dark=p.F_WOOD_D,
            hair_base=p.F_WOOD_D,
            hair_highlight=p.F_WOOD,
            hair_shadow=p.F_OUTLINE,
            shirt_base=p.F_ACCENT,
            shirt_shade=p.F_WOOD_D,
            shirt_highlight=p.F_METAL_H,
            pants_base=p.F_WALL,
            pants_shade=p.F_FLOOR,
            shoe=p.F_OUTLINE,
            eye=p.F_OUTLINE,
            outline=p.F_OUTLINE,
        ),
    )
    prefabs.ui_button(
        asset,
        4,
        68,
        36,
        14,
        prefabs.UiPalette(
            bg=p.F_METAL,
            bg_dark=p.F_WALL,
            bg_light=p.F_METAL_H,
            border_outer=p.F_OUTLINE,
            border_highlight=p.F_METAL_H,
            border_shadow=p.F_FLOOR,
            accent=p.F_ACCENT,
            accent_bright=p.F_GLOW,
            text=p.F_METAL_H,
            text_muted=p.F_FLOOR,
            success=p.F_GLOW,
            warning=p.F_ACCENT,
            danger=p.F_ACCENT,
        ),
    )
    prefabs.ui_icon_16(asset, 108, 4, "bolt", p.F_METAL_H, accent=p.F_GLOW, outline=p.F_OUTLINE)

    arr = asset.surface.data
    assert int(np.count_nonzero(arr != TRANSPARENT_INDEX)) > 200
    assert bool(np.all((arr == TRANSPARENT_INDEX) | (arr < len(style.palette))))
