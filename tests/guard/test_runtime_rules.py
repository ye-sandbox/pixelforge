"""Hermetic unit tests for runtime invariant checks and orphan diagnostics."""

from __future__ import annotations

import numpy as np

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack
from pixelforge.export.bundle import LoadedAsset
from pixelforge.guard.runtime_rules import check_asset_runtime


def _sample_style() -> StylePack:
    return StylePack(
        id="test-style",
        perspective="front-2.5d",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="FILL", hex="#3b82f6", flags=("surface",)),
        ),
    )


def _sample_spec() -> AssetSpec:
    return AssetSpec(
        id="box",
        style_id="test-style",
        perspective="front-2.5d",
        width=8,
        height=8,
        states=("idle",),
        frames=1,
        fps=4,
    )


def test_clean_asset_passes_runtime_guards() -> None:
    """Verify a well-formed connected asset produces zero violations."""

    def render(a: Asset) -> None:
        p = a.pal
        with a.layer("box", outline=p.OUTLINE):
            a.rect(1, 1, 4, 4, p.FILL)
        a.anchor("foot", 4, 5)
        a.hitbox("body", 1, 1, 4, 4)

    violations = check_asset_runtime(
        LoadedAsset(SPEC=_sample_spec(), render=render), _sample_style()
    )
    assert violations == []


def test_closed_palette_violation() -> None:
    """Report undeclared palette indices written to the surface."""

    def render(a: Asset) -> None:
        a.root_surface.data[2, 2] = 99
        a.root_surface.data[2, 3] = 99

    violations = check_asset_runtime(
        LoadedAsset(SPEC=_sample_spec(), render=render), _sample_style()
    )
    assert any(v.rule == "closed-palette" for v in violations)


def test_exact_dimensions_violation() -> None:
    """Report surface shape mismatch against AssetSpec dimensions."""

    def render(a: Asset) -> None:
        a.root_surface.data = np.full((4, 4), 1, dtype=np.uint8)

    violations = check_asset_runtime(
        LoadedAsset(SPEC=_sample_spec(), render=render), _sample_style()
    )
    assert any(v.rule == "exact-dimensions" for v in violations)


def test_bit_determinism_violation() -> None:
    """Detect non-deterministic renders across repeated executions."""
    counter = [0]

    def render(a: Asset) -> None:
        counter[0] += 1
        a.rect(1, 1, 3, 3, 1 if counter[0] % 2 else 0)

    violations = check_asset_runtime(
        LoadedAsset(SPEC=_sample_spec(), render=render), _sample_style()
    )
    assert any(v.rule == "bit-determinism" for v in violations)


def test_valid_anchors_and_hitboxes() -> None:
    """Detect out-of-bounds and duplicate anchor/hitbox declarations."""

    def render(a: Asset) -> None:
        a.rect(1, 1, 4, 4, 1)
        a.anchor("foot", 20, 2)
        a.anchor("foot", 2, 2)
        a.hitbox("box", 6, 6, 4, 4)
        a.hitbox("box", 1, 1, 2, 2)

    violations = check_asset_runtime(
        LoadedAsset(SPEC=_sample_spec(), render=render), _sample_style()
    )
    anchor_rules = [v for v in violations if v.rule == "valid-anchors"]
    assert len(anchor_rules) == 4


def test_orphan_pixels_advisory_and_strict() -> None:
    """Report isolated 1x1 pixels as warning by default and error under --strict-orphans."""

    def render(a: Asset) -> None:
        a.rect(0, 0, 3, 3, 1)
        a.put(6, 6, 1)

    asset = LoadedAsset(SPEC=_sample_spec(), render=render)
    advisory = check_asset_runtime(asset, _sample_style(), strict_orphans=False)
    assert len(advisory) == 1
    assert advisory[0].rule == "orphan-pixels"
    assert advisory[0].severity == "warning"

    strict = check_asset_runtime(asset, _sample_style(), strict_orphans=True)
    assert len(strict) == 1
    assert strict[0].rule == "orphan-pixels"
    assert strict[0].severity == "error"


def test_advisory_canvas_coverage_diagnostics() -> None:
    """Emit advisory `canvas-coverage` warnings for empty, sparse, and overfilled frames."""
    style = _sample_style()

    def render_empty(_a: Asset) -> None:
        return None

    empty_violations = check_asset_runtime(
        LoadedAsset(SPEC=_sample_spec(), render=render_empty), style
    )
    assert any(
        v.rule == "canvas-coverage" and v.severity == "warning" and "Empty frame" in v.detail
        for v in empty_violations
    )

    def render_sparse(a: Asset) -> None:
        a.rect(0, 0, 2, 1, 1)  # 2 / 64 = 3.125% < 5%

    sparse_violations = check_asset_runtime(
        LoadedAsset(SPEC=_sample_spec(), render=render_sparse), style
    )
    assert any(
        v.rule == "canvas-coverage" and v.severity == "warning" and "Sparse" in v.detail
        for v in sparse_violations
    )

    def render_overfilled(a: Asset) -> None:
        a.rect(0, 0, 8, 8, 1)  # 64 / 64 = 100% > 95%

    full_violations = check_asset_runtime(
        LoadedAsset(SPEC=_sample_spec(), render=render_overfilled), style
    )
    assert any(
        v.rule == "canvas-coverage" and v.severity == "warning" and "Overfilled" in v.detail
        for v in full_violations
    )


def test_advisory_emissive_bleed_diagnostic() -> None:
    """Emit advisory `emissive-bleed` warning when emissive pixels exceed 25% of opaque."""
    style = StylePack(
        id="test-style",
        perspective="front-2.5d",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="FILL", hex="#3b82f6", flags=("surface",)),
            PaletteColor(index=2, name="GLOW", hex="#58a6ff", flags=("emissive",)),
        ),
    )

    def render_bleed(a: Asset) -> None:
        a.rect(1, 1, 6, 6, a.pal.GLOW)

    violations = check_asset_runtime(LoadedAsset(SPEC=_sample_spec(), render=render_bleed), style)
    assert any(v.rule == "emissive-bleed" and v.severity == "warning" for v in violations)
