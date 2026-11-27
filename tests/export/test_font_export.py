"""Export tests for BitmapFontSpec manifest, manifest.d.ts, and --indexed-ts output."""

from __future__ import annotations

from pixelforge import (
    Asset,
    AssetSpec,
    PaletteColor,
    StylePack,
    compute_font_atlas_size,
    make_bitmap_font_spec,
    render_font_atlas,
)
from pixelforge.export import (
    ExportBundleOptions,
    LoadedAsset,
    build_manifest_document,
    export_asset_bundle,
    generate_indexed_manifest_ts,
    generate_svelte_manifest_dts,
)


def _font_style() -> StylePack:
    return StylePack(
        id="font-export-style",
        perspective="front-2.5d",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="INK", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="WHITE", hex="#ffffff", flags=("bright",)),
            PaletteColor(index=2, name="LED_C", hex="#39c5cf", flags=("emissive",)),
        ),
    )


def test_font_bundle_manifest_dts_and_indexed_ts() -> None:
    style = _font_style()
    font_spec = make_bitmap_font_spec("4x6", charset=" 012AB", columns=4, margin=0, spacing=1)
    w, h = compute_font_atlas_size(font_spec)
    spec = AssetSpec(
        id="hud_font_mini",
        style_id=style.id,
        width=w,
        height=h,
        perspective="front-2.5d",
        states=("default", "emissive"),
        font=font_spec,
    )

    def _render(a: Asset[object]) -> None:
        color = 2 if a.state == "emissive" else 1
        render_font_atlas(a, font_spec, color)

    bundle = export_asset_bundle(
        LoadedAsset(SPEC=spec, render=_render),
        style,
        ExportBundleOptions(),
    )

    assert bundle.manifest.font is not None
    assert bundle.manifest.font.preset == "4x6"
    assert len(bundle.manifest.font.glyphs) == 6

    manifest_doc = build_manifest_document({"hud_font_mini": bundle.manifest})
    assert "hud_font_mini" in manifest_doc
    dumped = bundle.manifest.model_dump(mode="json")
    assert dumped["font"]["glyph_width"] == 4
    assert dumped["font"]["glyphs"][1]["char"] == "0"

    dts = generate_svelte_manifest_dts([bundle.manifest])
    assert "export interface PixelForgeBitmapGlyph" in dts
    assert "export interface PixelForgeBitmapFont" in dts
    assert "readonly font: PixelForgeBitmapFont;" in dts

    indexed_manifest_ts = generate_indexed_manifest_ts([bundle])
    assert '"font": {' in indexed_manifest_ts
    assert '"preset": "4x6"' in indexed_manifest_ts


def test_font_bundle_bmfont_fnt_and_display_preset() -> None:
    style = _font_style()
    font_spec = make_bitmap_font_spec(
        "6x8",
        charset=" AÇÃO♥18",
        columns=4,
        margin=1,
        spacing=1,
        proportional=True,
    )
    w, h = compute_font_atlas_size(font_spec)
    spec = AssetSpec(
        id="hud_font_6x8",
        style_id=style.id,
        width=w,
        height=h,
        perspective="front-2.5d",
        font=font_spec,
    )

    def _render(a: Asset[object]) -> None:
        render_font_atlas(a, font_spec, 1)

    bundle = export_asset_bundle(
        LoadedAsset(SPEC=spec, render=_render),
        style,
        ExportBundleOptions(atlas="all"),
    )
    assert "hud_font_6x8.fnt" in bundle.files
    fnt_text = bundle.files["hud_font_6x8.fnt"].decode("utf-8")
    assert 'info face="hud_font_6x8" size=8 bold=1' in fnt_text
    assert 'page id=0 file="hud_font_6x8_default.png"' in fnt_text
    assert f"char id={ord('Ç')} " in fnt_text

    dts = generate_svelte_manifest_dts([bundle.manifest])
    assert "'6x8' | '8x10'" in dts
