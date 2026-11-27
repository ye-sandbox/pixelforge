"""Hermetic unit, guard, and CLI tests for deterministic pixel-art craft lints."""

from __future__ import annotations

from pathlib import Path

from pixelforge.cli.main import main
from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack
from pixelforge.export.bundle import LoadedAsset
from pixelforge.guard.runner import run_checks
from pixelforge.guard.runtime_rules import check_asset_runtime


def _craft_style(lighting_angle: str = "top-left") -> StylePack:
    return StylePack(
        id="craft-test",
        perspective="front-2.5d",
        lighting_angle=lighting_angle,  # type: ignore[arg-type]
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="OUTLINE", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="DARK", hex="#1b263b", flags=("shadow",)),
            PaletteColor(index=2, name="MID", hex="#415a77", flags=("surface",)),
            PaletteColor(index=3, name="LIGHT", hex="#778da9", flags=("bright",)),
            PaletteColor(index=4, name="HIGH", hex="#e0e1dd", flags=("bright",)),
            PaletteColor(index=5, name="NEAR_DARK", hex="#10141b", flags=("shadow",)),
            PaletteColor(index=6, name="NEAR_LIGHT", hex="#e5ecf2", flags=("bright",)),
        ),
    )


def _craft_spec(
    *,
    width: int = 16,
    height: int = 16,
    states: tuple[str, ...] = ("idle",),
    frames: int = 1,
) -> AssetSpec:
    return AssetSpec(
        id="craft_prop",
        style_id="craft-test",
        perspective="front-2.5d",
        width=width,
        height=height,
        states=states,
        frames=frames,
        fps=4,
    )


def test_craft_jaggies_detects_staircase_l_corners() -> None:
    """Detect double-pixel L-corner jaggies on outlines while ignoring 90-degree box corners."""

    def render_jaggy(a: Asset) -> None:
        # 5 diagonal staircase L-corners (10+ jaggy pixels on outline)
        for i in range(6):
            x = 2 + i * 2
            y = 2 + i * 2
            a.put(x, y, 0)
            a.put(x + 1, y, 0)
            a.put(x + 1, y + 1, 0)
            a.put(x + 2, y + 1, 0)
        a.rect(1, 1, 2, 2, 3)

    asset = LoadedAsset(SPEC=_craft_spec(width=20, height=20), render=render_jaggy)
    advisory = check_asset_runtime(asset, _craft_style(), strict_craft=False)
    jaggy_warns = [v for v in advisory if v.rule == "craft-jaggies"]
    assert jaggy_warns
    assert all(v.severity == "warning" for v in jaggy_warns)

    strict = check_asset_runtime(asset, _craft_style(), strict_craft=True)
    jaggy_errs = [v for v in strict if v.rule == "craft-jaggies"]
    assert jaggy_errs
    assert all(v.severity == "error" for v in jaggy_errs)


def test_craft_pillow_shading_detected() -> None:
    """Detect concentric edge-following pillow shading."""

    def render_pillow(a: Asset) -> None:
        a.rect(1, 1, 14, 14, 0)
        a.rect(2, 2, 12, 12, 1)
        a.rect(4, 4, 8, 8, 2)
        a.rect(6, 6, 4, 4, 4)

    asset = LoadedAsset(SPEC=_craft_spec(width=16, height=16), render=render_pillow)
    advisory = check_asset_runtime(asset, _craft_style(), strict_craft=False)
    assert any(v.rule == "craft-pillow-shading" and v.severity == "warning" for v in advisory)

    strict = check_asset_runtime(asset, _craft_style(), strict_craft=True)
    assert any(v.rule == "craft-pillow-shading" and v.severity == "error" for v in strict)


def test_craft_directional_lighting_opposes_style() -> None:
    """Detect inverted shading that opposes `style.lighting_angle`."""

    def render_inverted(a: Asset) -> None:
        a.rect(1, 1, 14, 14, 0)
        for y in range(2, 14):
            for x in range(2, 14):
                score = (x - 2) + (y - 2)
                if score < 7:
                    a.put(x, y, 1)
                elif score < 15:
                    a.put(x, y, 2)
                else:
                    a.put(x, y, 4)

    asset = LoadedAsset(SPEC=_craft_spec(width=16, height=16), render=render_inverted)
    advisory = check_asset_runtime(asset, _craft_style("top-left"), strict_craft=False)
    assert any(v.rule == "craft-lighting" and v.severity == "warning" for v in advisory)

    # Same sprite under opposing light angle? Still not top-right, but let's verify clean top-left:
    def render_aligned(a: Asset) -> None:
        a.rect(1, 1, 14, 14, 0)
        for y in range(2, 14):
            for x in range(2, 14):
                score = (x - 2) + (y - 2)
                if score < 7:
                    a.put(x, y, 4)
                elif score < 15:
                    a.put(x, y, 2)
                else:
                    a.put(x, y, 1)

    aligned_asset = LoadedAsset(SPEC=_craft_spec(width=16, height=16), render=render_aligned)
    clean = check_asset_runtime(aligned_asset, _craft_style("top-left"), strict_craft=True)
    assert not any(v.rule == "craft-lighting" for v in clean)


def test_craft_silhouette_contrast_dark_and_light() -> None:
    """Flag silhouettes with low 1x contrast against #0d1117 or #e6edf3."""

    def render_all_dark(a: Asset) -> None:
        a.rect(2, 2, 8, 8, 5)

    def render_all_light(a: Asset) -> None:
        a.rect(2, 2, 8, 8, 6)

    dark_asset = LoadedAsset(SPEC=_craft_spec(), render=render_all_dark)
    dark_v = check_asset_runtime(dark_asset, _craft_style())
    assert any(v.rule == "craft-contrast" and "#0d1117" in v.detail for v in dark_v)

    light_asset = LoadedAsset(SPEC=_craft_spec(), render=render_all_light)
    light_v = check_asset_runtime(light_asset, _craft_style())
    assert any(v.rule == "craft-contrast" and "#e6edf3" in v.detail for v in light_v)


def test_craft_noop_delta_frames_and_states() -> None:
    """Detect no-op animations and duplicate states via SHA-256."""

    def render_noop(a: Asset) -> None:
        a.rect(2, 2, 8, 8, 3)

    asset = LoadedAsset(
        SPEC=_craft_spec(states=("idle", "active"), frames=2),
        render=render_noop,
    )
    violations = check_asset_runtime(asset, _craft_style(), strict_craft=False)
    noop = [v for v in violations if v.rule == "craft-noop-delta"]
    assert len(noop) == 2

    def render_partial_anim(a: Asset) -> None:
        a.rect(2, 2, 8, 8, 3)
        if a.state == "active" and a.frame == 1:
            a.put(4, 4, 4)

    partial = LoadedAsset(
        SPEC=_craft_spec(states=("idle", "active"), frames=2),
        render=render_partial_anim,
    )
    partial_v = check_asset_runtime(partial, _craft_style(), strict_craft=True)
    assert not any(v.rule == "craft-noop-delta" for v in partial_v)


def test_craft_anchor_and_hitbox_fidelity() -> None:
    """Flag anchors outside opaque bbox and empty/sparse non-container hitboxes."""

    def render_bad_anchors(a: Asset) -> None:
        a.rect(2, 2, 4, 4, 3)
        a.anchor("floating", 14, 14)
        a.hitbox("empty_box", 10, 10, 4, 4)
        a.hitbox("door_clearance_front", 10, 10, 4, 4)

    asset = LoadedAsset(SPEC=_craft_spec(), render=render_bad_anchors)
    violations = check_asset_runtime(asset, _craft_style(), strict_craft=False)
    fidelity = [v for v in violations if v.rule == "craft-anchor-fidelity"]
    assert len(fidelity) == 2


def test_cli_strict_craft_flag(tmp_path: Path) -> None:
    """Verify `pixelforge check --strict-craft` promotes craft warnings to exit 1."""
    assert main(["init", "--root", str(tmp_path)]) == 0
    bad_asset = tmp_path / "assets" / "low_contrast.asset.py"
    bad_asset.write_text(
        '''"""Low-contrast test asset."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec

SPEC = AssetSpec(
    id="low_contrast",
    style_id="sweetie-16",
    width=16,
    height=16,
    perspective="front-2.5d",
    states=("idle",),
    frames=1,
    fps=1,
)


def render(a: Asset) -> None:
    a.rect(2, 2, 8, 8, a.pal.WHITE)
''',
        encoding="utf-8",
    )

    advisory_report = run_checks(tmp_path, asset_id="low_contrast", strict_craft=False)
    assert advisory_report.passed
    assert advisory_report.warnings >= 1
    assert main(["check", "low_contrast", "--root", str(tmp_path)]) == 0

    strict_report = run_checks(tmp_path, asset_id="low_contrast", strict_craft=True)
    assert not strict_report.passed
    assert strict_report.errors >= 1
    assert main(["check", "low_contrast", "--strict-craft", "--root", str(tmp_path)]) == 1
