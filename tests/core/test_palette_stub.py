"""Unit tests for typed StylePack palette stub generation and Pyright compatibility."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from pixelforge.core.builder import Asset
from pixelforge.core.palette_stub import (
    generate_palette_stub,
    palette_stub_class_name,
    palette_stub_path,
    write_palette_stub,
)
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack

if TYPE_CHECKING:
    from styles.homelab_16bit_palette import Homelab16bitPalette


def test_palette_stub_naming_and_paths(tmp_path: Path) -> None:
    """Derive deterministic PascalCase class names and `*_palette.py` paths."""
    assert palette_stub_class_name("homelab-16bit") == "Homelab16bitPalette"
    assert palette_stub_class_name("cyber_hud_32") == "CyberHud32Palette"
    style_path = tmp_path / "styles" / "homelab_16bit.style.py"
    assert palette_stub_path(style_path) == tmp_path / "styles" / "homelab_16bit_palette.py"


def test_generate_and_write_palette_stub(tmp_path: Path) -> None:
    """Generated stub declares every StylePack token as a read-only int property."""
    style = StylePack(
        id="demo-pack",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="INK", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="LED_C", hex="#58a6ff", flags=("emissive",)),
        ),
        aliases={"EMISSIVE_1": "LED_C"},
    )
    source = generate_palette_stub(style)
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    assert cls.name == "DemoPackPalette"

    methods = {node.name for node in cls.body if isinstance(node, ast.FunctionDef)}
    assert {
        "style_id",
        "INK",
        "LED_C",
        "EMISSIVE_1",
        "__getitem__",
        "with_overrides",
        "to_dict",
    } <= methods
    assert "__getattr__" not in methods

    style_path = tmp_path / "demo_pack.style.py"
    written = write_palette_stub(style_path, style)
    assert written == tmp_path / "demo_pack_palette.py"
    assert written.read_text(encoding="utf-8") == source


def test_asset_generic_palette_annotation_runtime_compatibility() -> None:
    """`Asset[Homelab16bitPalette]` works at runtime and resolves declared tokens."""
    from pixelforge.guard.runner import load_style_module

    style = load_style_module(Path("styles/homelab_16bit.style.py"))
    spec = AssetSpec(
        id="typed_probe",
        style_id="homelab-16bit",
        perspective="iso-2:1",
        width=8,
        height=8,
    )

    def render(a: Asset[Homelab16bitPalette]) -> None:
        p = a.pal
        a.put(2, 2, p.INK)
        a.put(3, 2, p.LED_C)
        assert p.ramp("metal")[0] == p.INK

    asset: Asset[Homelab16bitPalette] = Asset(spec, style)
    render(asset)
    assert int(asset.root_surface.data[2, 2]) == asset.pal["INK"]
    assert int(asset.root_surface.data[2, 3]) == asset.pal["LED_C"]
    assert "metal" in asset.pal.ramps
