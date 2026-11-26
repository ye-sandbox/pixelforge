"""Unit and protocol tests for `pixelforge.export.studio` Preview Studio."""

from __future__ import annotations

import json
import socket
import socketserver
import threading
from typing import cast

import numpy as np

from pixelforge.core.builder import Asset
from pixelforge.core.types import AssetSpec, PaletteColor, StylePack
from pixelforge.export.bundle import ExportBundleOptions, LoadedAsset, export_asset_bundle
from pixelforge.export.png import decode_png_to_rgba
from pixelforge.export.scene import LoadedScene, SceneMountSpec, SceneSpec, export_scene_bundle
from pixelforge.export.studio import (
    StudioState,
    build_studio_html,
    dispatch_studio_request,
    make_studio_handler,
)


def _sample_style() -> StylePack:
    return StylePack(
        id="studio-test",
        perspective="iso-2:1",
        lighting_angle="top-left",
        outline_index=0,
        palette=(
            PaletteColor(index=0, name="INK", hex="#0d1117", flags=("outline",)),
            PaletteColor(index=1, name="WALL", hex="#304050", flags=("surface",)),
            PaletteColor(index=2, name="LED", hex="#3fb950", flags=("emissive", "bright")),
        ),
        variants={
            "night": {
                "WALL": "#101822",
            }
        },
    )


def _make_sample_state() -> StudioState:
    style = _sample_style()
    prop_spec = AssetSpec(
        id="lamp_prop",
        style_id=style.id,
        perspective="iso-2:1",
        width=8,
        height=8,
        states=("idle", "active"),
        frames=2,
        fps=4,
        seed=7,
    )

    def _render_prop(a: Asset) -> None:
        p = a.pal
        with a.layer("body", outline=p.INK):
            a.rect(2, 2, 4, 4, p.WALL)
            if a.state == "active" or a.frame == 1:
                a.put(3, 3, p.LED)
        a.anchor("foot", 4, 7)
        a.hitbox("body", 1, 1, 6, 6)

    base_spec = AssetSpec(
        id="desk_base",
        style_id=style.id,
        perspective="iso-2:1",
        width=16,
        height=16,
        states=("day", "night"),
        frames=1,
        fps=1,
        seed=3,
    )

    def _render_base(a: Asset) -> None:
        p = a.pal
        with a.layer("desk", outline=p.INK):
            a.rect(1, 5, 14, 10, p.WALL)
        a.anchor("lamp_slot", 8, 10)

    loaded_prop = LoadedAsset(SPEC=prop_spec, render=_render_prop)
    loaded_base = LoadedAsset(SPEC=base_spec, render=_render_base)
    scene_spec = SceneSpec(
        id="desk_scene",
        parent_id="desk_base",
        depth_sort="iso_y",
        mounts=(
            SceneMountSpec(
                prop_id="lamp_prop",
                anchor="lamp_slot",
                prop_anchor="foot",
                state_map={"day": "idle", "night": "active"},
            ),
        ),
    )

    assets_by_id = {"lamp_prop": loaded_prop, "desk_base": loaded_base}
    opts = ExportBundleOptions(emissive=True)
    bundles = {
        "lamp_prop": export_asset_bundle(loaded_prop, style, opts),
        "desk_base": export_asset_bundle(loaded_base, style, opts),
        "desk_scene": export_scene_bundle(scene_spec, loaded_base, assets_by_id, style, opts),
    }
    scenes = {"desk_scene": LoadedScene(SCENE=scene_spec)}

    state = StudioState()
    rev = state.sync({style.id: style}, bundles, scenes=scenes, assets_by_id=assets_by_id)
    assert rev == 1
    return state


def test_studio_state_catalog_variants_emissive_and_spritesheet() -> None:
    """Verify StudioState renders spritesheets, day/night variants, emissive masks, and mounts."""
    state = _make_sample_state()

    status = state.status_payload()
    assert status["revision"] == 1
    assert status["assetCount"] == 3
    assert status["sceneCount"] == 1
    assert status["lastError"] is None

    catalog = state.catalog_payload()
    assets_list = cast(list[dict[str, object]], catalog["assets"])
    by_id = {cast(str, entry["id"]): entry for entry in assets_list}
    assert set(by_id) == {"desk_base", "desk_scene", "lamp_prop"}
    assert by_id["lamp_prop"]["variants"] == ["default", "night"]
    assert by_id["lamp_prop"]["hasEmissive"] is True
    assert by_id["desk_scene"]["kind"] == "scene"

    scene_info = cast(dict[str, object], by_id["desk_scene"]["scene"])
    placements_by_frame = cast(dict[str, list[dict[str, object]]], scene_info["placementsByFrame"])
    assert "day:0" in placements_by_frame
    assert "night:1" in placements_by_frame
    assert placements_by_frame["day:0"][0]["prop_id"] == "lamp_prop"
    assert placements_by_frame["day:0"][0]["state"] == "idle"
    assert placements_by_frame["night:1"][0]["state"] == "active"

    # Spritesheet PNG dimensions: (frames * width) x (states * height) = 16 x 16
    sheet_png = state.render_png("lamp_prop", sheet=True)
    sheet_rgba = decode_png_to_rgba(sheet_png)
    assert sheet_rgba.shape == (16, 16, 4)

    # Day (base) vs night variant differ in painted wall color
    day_rgba = decode_png_to_rgba(state.render_png("lamp_prop", state="idle", frame=0))
    night_rgba = decode_png_to_rgba(
        state.render_png("lamp_prop", state="idle", frame=0, variant="night")
    )
    assert not np.array_equal(day_rgba, night_rgba)

    # Explicit `day` alias resolves cleanly to base palette
    day_alias = state.render_png("lamp_prop", state="idle", frame=0, variant="day")
    assert day_alias == state.render_png("lamp_prop", state="idle", frame=0)

    # Emissive-only mask keeps only glowing LED pixels opaque
    em_f0 = decode_png_to_rgba(
        state.render_png("lamp_prop", state="idle", frame=0, emissive_only=True)
    )
    em_f1 = decode_png_to_rgba(
        state.render_png("lamp_prop", state="idle", frame=1, emissive_only=True)
    )
    assert int(np.count_nonzero(em_f0[:, :, 3])) == 0
    assert int(np.count_nonzero(em_f1[:, :, 3])) == 1

    # Error banner updates revision without erasing cached bundles
    rev2 = state.set_error("broken asset")
    assert rev2 == 2
    assert state.status_payload()["lastError"] == "broken asset"


def test_dispatch_studio_request_routes_and_self_contained_html() -> None:
    """Verify studio request routing, error codes, and zero-CDN self-contained HTML."""
    state = _make_sample_state()

    code, ctype, body = dispatch_studio_request(state, "/")
    assert code == 200
    assert ctype.startswith("text/html")
    html = body.decode("utf-8")
    assert html == build_studio_html()
    assert "http://" not in html and "https://" not in html
    assert "/api/catalog" in html
    assert "/api/status" in html
    assert "Day / Night" in html
    assert "Spritesheet" in html
    assert "Bloom" in html
    assert "Scene Mounts" in html

    code_cat, ctype_cat, body_cat = dispatch_studio_request(state, "/api/catalog")
    assert code_cat == 200
    assert ctype_cat.startswith("application/json")
    assert json.loads(body_cat.decode("utf-8"))["revision"] == 1

    code_png, ctype_png, body_png = dispatch_studio_request(
        state, "/api/sprite/lamp_prop.png?state=active&frame=1&variant=night&emissive=1"
    )
    assert code_png == 200
    assert ctype_png == "image/png"
    assert decode_png_to_rgba(body_png).shape == (8, 8, 4)

    assert dispatch_studio_request(state, "/api/sprite/missing")[0] == 404
    assert dispatch_studio_request(state, "/api/sprite/lamp_prop?variant=bogus")[0] == 404
    assert dispatch_studio_request(state, "/api/sprite/lamp_prop?frame=abc")[0] == 400
    assert dispatch_studio_request(state, "/api/sprite/lamp_prop?frame=99")[0] == 400
    assert dispatch_studio_request(state, "/unknown")[0] == 404


def test_studio_http_handler_over_unix_socket() -> None:
    """Exercise stdlib BaseHTTPRequestHandler over AF_UNIX socketpair (--allow-unix-socket)."""
    state = _make_sample_state()
    handler_cls = make_studio_handler(state)
    dummy_server = socketserver.BaseServer(("127.0.0.1", 0), handler_cls)

    def _raw_get(target: str) -> tuple[bytes, bytes]:
        client_sock, server_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        client_sock.settimeout(5.0)
        server_sock.settimeout(5.0)

        def _serve_one() -> None:
            try:
                handler_cls(server_sock, ("127.0.0.1", 0), dummy_server)
            finally:
                server_sock.close()

        thread = threading.Thread(target=_serve_one, daemon=True)
        thread.start()
        try:
            req = f"GET {target} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
            client_sock.sendall(req.encode("ascii"))
            client_sock.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            while True:
                data = client_sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
        finally:
            client_sock.close()
            thread.join(timeout=2.0)
        raw = b"".join(chunks)
        head, _, body = raw.partition(b"\r\n\r\n")
        return head, body

    head_cat, body_cat = _raw_get("/api/catalog")
    assert b"200 OK" in head_cat
    assert b"Cache-Control: no-store" in head_cat
    assert json.loads(body_cat.decode("utf-8"))["revision"] == 1

    head_png, body_png = _raw_get("/api/sprite/lamp_prop?sheet=1&variant=night")
    assert b"200 OK" in head_png
    assert b"Content-Type: image/png" in head_png
    assert decode_png_to_rgba(body_png).shape == (16, 16, 4)
