"""Pilot pack benchmark and contract tests for `homelab-16bit` and ThinkPad assets."""

from __future__ import annotations

import base64
import re
import time
from pathlib import Path

import numpy as np

from pixelforge.cli.main import main
from pixelforge.export.bundle import (
    ExportBundleOptions,
    ExportBundleResult,
    export_asset_bundle,
    render_asset_frames,
    write_manifest,
)
from pixelforge.export.indexed_ts import (
    decode_rle_bytes,
    export_indexed_ts,
    write_indexed_ts_bundle,
)
from pixelforge.guard.runner import (
    discover_asset_files,
    load_all_styles,
    load_asset_module,
    run_checks,
)

ROOT_DIR = Path(__file__).resolve().parent.parent

EXPECTED_HOMELAB_IDS = (
    "ai_cluster_node",
    "ai_cluster_node_iso",
    "bedroom_desk_iso",
    "old_laptop",
    "old_laptop_iso",
    "used_gpu_rig",
    "used_gpu_rig_iso",
    "window_cycles_iso",
    "window_vistas_front",
)
EXPECTED_THINKPAD_IDS = (
    "thinkpad_r51_front",
    "thinkpad_r51_iso",
    "thinkpad_trackpoint_detail",
)
EXPECTED_PROPS_IDS = (
    "coffee_mug_iso",
    "desk_lamp_iso",
    "monitor_iso",
    "network_switch_iso",
    "potted_plant_iso",
    "storage_crate_iso",
)


def test_homelab_style_pack_64_color_canonical_alignment() -> None:
    """Verify `homelab-16bit` aligns 1:1 with `idle-datacenter` 64-color palette & flags."""
    styles = load_all_styles(ROOT_DIR / "styles")
    style = styles["homelab-16bit"]

    assert style.outline_index == 1
    assert len(style.palette) == 64
    assert [c.index for c in style.palette] == list(range(64))
    assert style.palette[0].name == "VOID"
    assert style.palette[1].name == "INK"
    assert style.palette[36].name == "WINDOW_SKY"
    assert style.palette[63].name == "GLASS_L"

    by_name = {c.name: c for c in style.palette}
    emissive_names = {c.name for c in style.palette if "emissive" in c.flags}
    bright_names = {c.name for c in style.palette if "bright" in c.flags}

    assert emissive_names == {
        "SOLAR_L",
        "LED_G",
        "LED_A",
        "LED_R",
        "LED_C",
        "LED_P",
        "SPARK",
        "NEON_G",
        "STAR",
        "WARM_LAMP",
        "VISOR_C",
        "PINK_RGB",
    }
    assert bright_names == emissive_names | {"SCREEN_L", "WHITE", "GLASS_L"}

    # Non-emissive painted accents MUST stay separated from WebGL2 bloom flags.
    for paint_token in ("WINDOW_SKY", "SOLAR_B", "SHIRT_BLUE", "ORANGE", "SHIRT_EMER"):
        assert "emissive" not in by_name[paint_token].flags

    assert style.reflections["LED_C"] == "REFL_C"
    assert style.reflections["LED_G"] == "REFL_G"
    assert style.reflections["LED_R"] == "REFL_R"
    assert style.reflections["LED_A"] == "REFL_A"
    assert style.reflections["WHITE"] == "TILE_L"


def test_pilot_pack_passes_all_guards_strict_orphans() -> None:
    """Verify AST static, runtime, and strict orphan guards pass across all 7 pilot assets."""
    report = run_checks(ROOT_DIR, strict_orphans=True)
    assert report.violations == ()
    assert report.passed
    assert report.styles_checked == 1
    assert report.assets_checked == len(EXPECTED_HOMELAB_IDS) + len(EXPECTED_THINKPAD_IDS) + len(
        EXPECTED_PROPS_IDS
    )


def test_pilot_pack_render_budget_and_exports(tmp_path: Path) -> None:
    """Verify < 40ms per-asset render budget, Svelte `manifest.d.ts`, and `--indexed-ts`."""
    styles = load_all_styles(ROOT_DIR / "styles")
    style = styles["homelab-16bit"]
    asset_files = discover_asset_files(ROOT_DIR / "assets")
    loaded_by_id = {
        loaded.SPEC.id: loaded for loaded in (load_asset_module(p) for p in asset_files)
    }

    assert tuple(sorted(loaded_by_id.keys())) == tuple(
        sorted((*EXPECTED_HOMELAB_IDS, *EXPECTED_THINKPAD_IDS, *EXPECTED_PROPS_IDS))
    )

    bundles: list[ExportBundleResult] = []
    for asset_id, loaded in sorted(loaded_by_id.items()):
        t0 = time.perf_counter()
        frames = render_asset_frames(loaded, style)
        render_ms = (time.perf_counter() - t0) * 1000.0
        assert render_ms < 40.0, f"{asset_id} exceeded 40ms render budget ({render_ms:.2f}ms)"
        assert len(frames) == len(loaded.SPEC.states) * loaded.SPEC.frames

        bundle = export_asset_bundle(loaded, style, ExportBundleOptions(emissive=True))
        bundles.append(bundle)

    by_bundle = {b.manifest.id: b for b in bundles}

    cluster = by_bundle["ai_cluster_node"]
    assert cluster.manifest.width == 64
    assert cluster.manifest.height == 48
    assert cluster.manifest.frames == 2
    assert cluster.manifest.files.emissive is not None
    assert len(cluster.manifest.files.emissive) == 3
    assert cluster.manifest.files.sheetEmissive == "ai_cluster_node_sheet_emissive.png"

    room = by_bundle["bedroom_desk_iso"]
    assert room.manifest.width == 320
    assert room.manifest.height == 200
    assert room.manifest.states == ("day", "night")
    assert [a.name for a in room.manifest.anchors] == [
        "hardware_0",
        "hardware_1",
        "hardware_2",
        "breaker",
    ]

    # Verify non-emissive painted blue/orange tokens on ThinkPad do not leak into emissive mask.
    tp_iso = by_bundle["thinkpad_r51_iso"]
    tp_healthy_f0 = next(f for f in tp_iso.rendered_frames if f.state == "healthy" and f.frame == 0)
    emissive_indices = {c.index for c in style.palette if "emissive" in c.flags}
    present = set(np.unique(tp_healthy_f0.surface.data).tolist())
    assert 47 in present  # SHIRT_BLUE painted Enter key / taskbar
    assert 33 in present  # ORANGE painted TrackPoint / badge
    assert 47 not in emissive_indices
    assert 33 not in emissive_indices

    # Verify manifest.json + Svelte manifest.d.ts
    manifest_map = {b.manifest.id: b.manifest for b in bundles}
    manifest_json, manifest_dts = write_manifest(manifest_map, tmp_path / "dist")
    assert manifest_json.exists()
    dts_text = manifest_dts.read_text(encoding="utf-8")
    assert "export interface AiClusterNodeManifestEntry" in dts_text
    assert "export interface BedroomDeskIsoManifestEntry" in dts_text
    assert "export interface ThinkpadR51IsoManifestEntry" in dts_text
    assert (
        "export type BedroomDeskIsoAnchorName = "
        '"hardware_0" | "hardware_1" | "hardware_2" | "breaker";' in dts_text
    )

    # Verify --indexed-ts export contract & RLE roundtrip
    ts_res = export_indexed_ts(bundles, style)
    assert "export const OUTLINE_INDEX = 1 as const;" in ts_res.palette_ts
    assert "new Set<number>([21, 22, 24, 25, 26, 27, 30, 34, 37, 38, 54, 55])" in ts_res.palette_ts
    assert (
        "new Set<number>([19, 21, 22, 24, 25, 26, 27, 30, 34, 35, 37, 38, 54, 55, 63])"
        in ts_res.palette_ts
    )

    matches = re.findall(
        r'decodeRleSprite\("([A-Za-z0-9+/=]+)", (\d+), (\d+)\)',
        ts_res.sprites_ts,
    )
    ordered_frames = [
        f
        for b in sorted(bundles, key=lambda item: item.manifest.id)
        for st in b.manifest.states
        for f in (
            next(fr for fr in b.rendered_frames if fr.state == st and fr.frame == idx)
            for idx in range(b.manifest.frames)
        )
    ]
    assert len(matches) == len(ordered_frames)
    for rendered, (b64_payload, w_str, h_str) in zip(ordered_frames, matches, strict=True):
        w, h = int(w_str), int(h_str)
        decoded = decode_rle_bytes(base64.b64decode(b64_payload), w * h).reshape((h, w))
        assert np.array_equal(decoded, rendered.surface.data)

    ts_paths = write_indexed_ts_bundle(ts_res, tmp_path / "dist" / "indexed")
    assert all(p.exists() for p in ts_paths)


def test_cli_render_indexed_ts_pilot_pack(tmp_path: Path) -> None:
    """Verify end-to-end CLI render with `--emissive` and `--indexed-ts` on repo pilot."""
    out_dir = tmp_path / "out"
    code = main(
        [
            "render",
            "--root",
            str(ROOT_DIR),
            "--out",
            str(out_dir),
            "--emissive",
            "--indexed-ts",
        ]
    )
    assert code == 0
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "manifest.d.ts").exists()
    assert (out_dir / "indexed" / "palette.generated.ts").exists()
    assert (out_dir / "indexed" / "sprites.generated.ts").exists()
    assert (out_dir / "indexed" / "manifest.generated.ts").exists()
