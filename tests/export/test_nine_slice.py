"""Tests for `NineSliceMargins` validation and export across manifest, d.ts, atlas, and TS."""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import ValidationError

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec, NineSliceMargins, PaletteColor, StylePack
from pixelforge.export.atlas import build_aseprite_atlas
from pixelforge.export.bundle import (
    ExportBundleOptions,
    LoadedAsset,
    build_manifest_document,
    export_asset_bundle,
)
from pixelforge.export.indexed_ts import generate_indexed_manifest_ts
from pixelforge.export.svelte_types import generate_svelte_manifest_dts


def _style() -> StylePack:
    return StylePack(
        id="nine-slice-test",
        perspective="front-2.5d",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="INK", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="BG", hex="#1b2230", flags=("surface",)),
            PaletteColor(index=2, name="ACCENT", hex="#1f4b8e", flags=("accent",)),
        ),
    )


def test_asset_spec_validates_nine_slice_bounds() -> None:
    valid = AssetSpec(
        id="panel",
        style_id="nine-slice-test",
        width=24,
        height=16,
        perspective="front-2.5d",
        nine_slice=NineSliceMargins(left=6, right=6, top=4, bottom=4),
    )
    assert valid.nine_slice == NineSliceMargins(left=6, right=6, top=4, bottom=4)

    with pytest.raises(ValidationError, match="horizontal margins"):
        AssetSpec(
            id="bad_h",
            style_id="nine-slice-test",
            width=10,
            height=10,
            perspective="front-2.5d",
            nine_slice=NineSliceMargins(left=6, right=5, top=2, bottom=2),
        )

    with pytest.raises(ValidationError, match="vertical margins"):
        AssetSpec(
            id="bad_v",
            style_id="nine-slice-test",
            width=10,
            height=10,
            perspective="front-2.5d",
            nine_slice=NineSliceMargins(left=2, right=2, top=6, bottom=5),
        )


def test_nine_slice_exports_to_manifest_dts_indexed_ts_and_aseprite() -> None:
    style = _style()
    ns_spec = AssetSpec(
        id="hud_panel",
        style_id="nine-slice-test",
        width=24,
        height=24,
        perspective="front-2.5d",
        nine_slice=NineSliceMargins(left=6, right=6, top=5, bottom=5),
    )
    plain_spec = AssetSpec(
        id="plain_icon",
        style_id="nine-slice-test",
        width=16,
        height=16,
        perspective="front-2.5d",
    )

    def render_box(a: Asset) -> None:
        a.rect(0, 0, a.width, a.height, a.pal.BG)

    ns_bundle = export_asset_bundle(
        LoadedAsset(SPEC=ns_spec, render=render_box),
        style,
        ExportBundleOptions(emissive=False),
    )
    plain_bundle = export_asset_bundle(
        LoadedAsset(SPEC=plain_spec, render=render_box),
        style,
        ExportBundleOptions(emissive=False),
    )

    doc = build_manifest_document(
        {
            "hud_panel": ns_bundle.manifest,
            "plain_icon": plain_bundle.manifest,
        }
    )
    hud_doc = doc["hud_panel"]
    plain_doc = doc["plain_icon"]
    assert isinstance(hud_doc, dict)
    assert isinstance(plain_doc, dict)
    assert hud_doc["nineSlice"] == {"left": 6, "right": 6, "top": 5, "bottom": 5}
    assert "nineSlice" not in plain_doc

    dts = generate_svelte_manifest_dts([ns_bundle.manifest, plain_bundle.manifest])
    assert "export interface PixelForgeNineSlice {" in dts
    assert "readonly nineSlice: PixelForgeNineSlice;" in dts

    indexed_ts = generate_indexed_manifest_ts([ns_bundle, plain_bundle])
    assert '"nineSlice": {' in indexed_ts

    aseprite = build_aseprite_atlas(ns_spec, ns_bundle.rendered_frames, scale=2)
    meta = cast(dict[str, object], aseprite["meta"])
    slices = cast(list[dict[str, object]], meta["slices"])
    first_slice = slices[0]
    assert first_slice["name"] == "nine_slice"
    keys = cast(list[dict[str, object]], first_slice["keys"])
    assert keys[0]["center"] == {"x": 12, "y": 10, "w": 24, "h": 28}
