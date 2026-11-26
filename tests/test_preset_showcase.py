"""Multi-genre preset showcase, emissive bloom isolation, and UniversalPalette tests."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pytest

from pixelforge import Asset, AssetSpec, UniversalPalette
from pixelforge.export.bundle import ExportBundleOptions, LoadedAsset, export_asset_bundle
from pixelforge.export.png import surface_to_rgba
from pixelforge.guard.runner import (
    discover_asset_files,
    load_all_styles,
    load_asset_module,
    run_checks,
)

ROOT_DIR = Path(__file__).resolve().parent.parent

SHOWCASE_STYLE_MAP: dict[str, str] = {
    "ink_1bit_knight": "ink-1bit",
    "retro_pocket_slime": "retro-pocket-4",
    "sweetie_beacon_iso": "sweetie-16",
    "endesga_forge_anvil": "endesga-32",
    "cozy_teahouse_lantern_iso": "cozy-pastel",
    "scifi_neon_terminal": "scifi-neon",
}


def test_showcase_assets_pass_strict_guards() -> None:
    """Verify all 6 multi-genre showcase assets and 8 styles pass `run_checks`."""
    report = run_checks(ROOT_DIR, strict_orphans=True)
    assert report.passed
    assert report.errors == 0
    assert report.warnings == 0
    assert report.styles_checked >= 8

    showcase_files = discover_asset_files(ROOT_DIR / "assets" / "showcase")
    loaded_ids = {load_asset_module(p).SPEC.id for p in showcase_files}
    assert set(SHOWCASE_STYLE_MAP).issubset(loaded_ids)


@pytest.mark.parametrize(("asset_id", "style_id"), sorted(SHOWCASE_STYLE_MAP.items()))
def test_showcase_asset_export_and_emissive_isolation(
    asset_id: str,
    style_id: str,
) -> None:
    """Verify binary alpha, manifest export, and strict emissive bloom isolation."""
    styles = load_all_styles(ROOT_DIR / "styles")
    style = styles[style_id]
    asset_path = ROOT_DIR / "assets" / "showcase" / f"{asset_id}.asset.py"
    loaded = load_asset_module(asset_path)
    assert loaded.SPEC.style_id == style_id

    bundle = export_asset_bundle(
        loaded,
        style,
        ExportBundleOptions(emissive=True),
    )
    assert bundle.manifest.id == asset_id
    assert bundle.manifest.styleId == style_id

    emissive_indices = [c.index for c in style.palette if "emissive" in c.flags]
    has_active_emissive = False

    for rendered in bundle.rendered_frames:
        rgba = surface_to_rgba(rendered.surface, style)
        emissive_rgba = surface_to_rgba(rendered.surface, style, emissive_only=True)
        alpha = rgba[:, :, 3]
        emissive_alpha = emissive_rgba[:, :, 3]

        # Binary alpha invariant on both color and emissive buffers
        assert set(np.unique(alpha).tolist()).issubset({0, 255})
        assert set(np.unique(emissive_alpha).tolist()).issubset({0, 255})

        # Emissive mask must be a strict subset of opaque pixels
        assert bool(np.all((emissive_alpha == 0) | (alpha == 255)))

        # Verify exact pixel-level isolation against StylePack emissive flags
        data = rendered.surface.data
        expected_emissive_mask = np.isin(data, emissive_indices)
        assert np.array_equal(emissive_alpha == 255, expected_emissive_mask)

        if bool(np.any(expected_emissive_mask)):
            has_active_emissive = True

    if emissive_indices:
        assert has_active_emissive, f"Expected emissive pixels in {asset_id} ({style_id})"
    else:
        assert not has_active_emissive


def test_universal_palette_portable_asset_across_showcase_presets() -> None:
    """Verify one `Asset[UniversalPalette]` renders cleanly on all 6 UniversalPalette presets."""
    styles = load_all_styles(ROOT_DIR / "styles")

    def render_portable(a: Asset[UniversalPalette]) -> None:
        p = a.pal
        with a.layer("crate", outline=p.INK):
            a.rect(4, 4, 16, 16, p.SURFACE_M)
            a.rect(5, 5, 14, 4, p.SURFACE_L)
            a.rect(5, 15, 14, 4, p.SURFACE_D)
            a.rect(6, 9, 4, 4, p.ACCENT_1)
            a.rect(14, 9, 4, 4, p.EMISSIVE_1)
        a.anchor("foot", 12, 20, kind="ground")
        a.hitbox("body", 3, 3, 18, 18)

    def _render_wrapper(a: Asset) -> None:
        render_portable(cast("Asset[UniversalPalette]", a))

    for style_id in sorted(SHOWCASE_STYLE_MAP.values()):
        style = styles[style_id]
        spec = AssetSpec(
            id=f"portable_{style_id.replace('-', '_')}",
            style_id=style_id,
            width=24,
            height=24,
            perspective=style.perspective,
            states=("idle",),
            frames=1,
            seed=42,
        )
        loaded = LoadedAsset(SPEC=spec, render=_render_wrapper)
        bundle = export_asset_bundle(loaded, style)
        rgba = surface_to_rgba(bundle.rendered_frames[0].surface, style)
        assert rgba.shape == (24, 24, 4)
        assert bool(np.any(rgba[:, :, 3] == 255))
