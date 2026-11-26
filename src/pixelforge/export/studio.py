"""Zero-dependency local Preview Studio HTTP server and self-contained HTML UI."""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final, cast
from urllib.parse import parse_qs, unquote, urlparse

from pixelforge.core.types import AssetSpec, PerspectiveMode, StylePack
from pixelforge.export.bundle import (
    ExportBundleResult,
    ExportedAssetManifestEntry,
    LoadedAsset,
    build_spritesheet_surface,
)
from pixelforge.export.png import surface_to_png
from pixelforge.export.scene import (
    LoadedScene,
    MountedPropPlacement,
    SceneCompositionError,
    compose_scene_results,
)

_DEFAULT_HOST: Final[str] = "127.0.0.1"
_DEFAULT_PORT: Final[int] = 4173


def _manifest_to_asset_spec(manifest: ExportedAssetManifestEntry) -> AssetSpec:
    return AssetSpec(
        id=manifest.id,
        style_id=manifest.styleId,
        perspective=cast(PerspectiveMode, manifest.perspective),
        width=manifest.width,
        height=manifest.height,
        states=manifest.states,
        frames=manifest.frames,
        fps=manifest.fps,
    )


def _serialize_mount_placement(p: MountedPropPlacement) -> dict[str, object]:
    return {
        "prop_id": p.prop_id,
        "anchor": p.anchor,
        "prop_anchor": p.prop_anchor,
        "perspective": p.perspective,
        "perspective_match": p.perspective_match,
        "state": p.state,
        "frame": p.frame,
        "z_index": p.z_index,
        "dest_x": p.dest_x,
        "dest_y": p.dest_y,
        "width": p.width,
        "height": p.height,
        "opaque_bbox": list(p.opaque_bbox) if p.opaque_bbox is not None else None,
        "in_bounds": p.in_bounds,
        "clipped_pixels": p.clipped_pixels,
        "occluded_by": list(p.occluded_by),
        "occluded_pixels": p.occluded_pixels,
        "opaque_pixels": p.opaque_pixels,
    }


def _compute_scene_placements(
    scenes: Mapping[str, LoadedScene],
    assets_by_id: Mapping[str, LoadedAsset],
    styles: Mapping[str, StylePack],
) -> dict[str, dict[tuple[str, int], tuple[MountedPropPlacement, ...]]]:
    placements_by_scene: dict[str, dict[tuple[str, int], tuple[MountedPropPlacement, ...]]] = {}
    for scene_id, loaded_scene in scenes.items():
        scene = loaded_scene.SCENE
        parent = assets_by_id.get(scene.parent_id)
        if parent is None:
            continue
        style_id = scene.style_id or parent.SPEC.style_id
        style = styles.get(style_id)
        if style is None:
            continue
        try:
            spec, results, _ = compose_scene_results(scene, parent, assets_by_id, style)
        except SceneCompositionError:
            continue
        per_frame: dict[tuple[str, int], tuple[MountedPropPlacement, ...]] = {}
        for idx, res in enumerate(results):
            per_frame[(res.parent_state, idx % spec.frames)] = res.placements
        placements_by_scene[scene_id] = per_frame
    return placements_by_scene


def _resolve_variant_name(style: StylePack, requested: str | None) -> str | None:
    if requested is None or requested in ("", "default", "base"):
        return None
    if requested in style.variants:
        return requested
    # INVARIANT: `day` acts as the implicit base palette alias when a StylePack only defines
    # night/dusk overrides, so toggling day<->night in the studio never fails on base styles.
    if requested == "day":
        return None
    available = ", ".join(("default", *sorted(style.variants)))
    msg = f"Unknown variant {requested!r} for style {style.id!r} (available: {available})"
    raise KeyError(msg)


@dataclass
class StudioState:
    """Thread-safe in-memory snapshot of compiled assets, styles, and scene mounts."""

    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    revision: int = 0
    styles: dict[str, StylePack] = field(default_factory=dict[str, StylePack])
    bundles: dict[str, ExportBundleResult] = field(default_factory=dict[str, ExportBundleResult])
    scenes: dict[str, LoadedScene] = field(default_factory=dict[str, LoadedScene])
    scene_placements: dict[str, dict[tuple[str, int], tuple[MountedPropPlacement, ...]]] = field(
        default_factory=dict[str, dict[tuple[str, int], tuple[MountedPropPlacement, ...]]]
    )
    last_error: str | None = None
    _png_cache: dict[tuple[str, str, int | None, str | None, bool, bool], bytes] = field(
        default_factory=dict[tuple[str, str, int | None, str | None, bool, bool], bytes],
        init=False,
        repr=False,
    )

    def sync(
        self,
        styles: Mapping[str, StylePack],
        bundles: Mapping[str, ExportBundleResult],
        *,
        scenes: Mapping[str, LoadedScene] | None = None,
        assets_by_id: Mapping[str, LoadedAsset] | None = None,
        last_error: str | None = None,
    ) -> int:
        """Atomically replace compiled bundles/styles/scenes and bump studio revision."""
        scene_map = (
            {sid: s for sid, s in scenes.items() if sid in bundles} if scenes is not None else {}
        )
        placements = (
            _compute_scene_placements(scene_map, assets_by_id, styles)
            if scene_map and assets_by_id is not None
            else {}
        )
        with self._lock:
            self.styles = dict(styles)
            self.bundles = dict(bundles)
            self.scenes = scene_map
            self.scene_placements = placements
            self.last_error = last_error
            self._png_cache.clear()
            self.revision += 1
            return self.revision

    def set_error(self, error_message: str | None) -> int:
        """Update live error banner state without dropping last-known good frames."""
        with self._lock:
            self.last_error = error_message
            self.revision += 1
            return self.revision

    def status_payload(self) -> dict[str, object]:
        """Return lightweight polling status payload for `/api/status`."""
        with self._lock:
            return {
                "revision": self.revision,
                "assetCount": len(self.bundles),
                "sceneCount": len(self.scenes),
                "styleCount": len(self.styles),
                "lastError": self.last_error,
            }

    def catalog_payload(self) -> dict[str, object]:
        """Return complete JSON catalog for `/api/catalog`."""
        with self._lock:
            styles_doc: dict[str, object] = {}
            for sid in sorted(self.styles):
                style = self.styles[sid]
                emissive_tokens = [c.name for c in style.palette if "emissive" in c.flags]
                styles_doc[sid] = {
                    "id": style.id,
                    "perspective": style.perspective,
                    "lightingAngle": style.lighting_angle,
                    "variants": ["default", *sorted(style.variants)],
                    "emissiveTokens": emissive_tokens,
                    "palette": [
                        {
                            "index": c.index,
                            "name": c.name,
                            "hex": c.hex,
                            "flags": list(c.flags),
                        }
                        for c in style.palette
                    ],
                    "variantOverrides": {k: dict(v) for k, v in style.variants.items()},
                }

            assets_doc: list[dict[str, object]] = []
            for asset_id in sorted(self.bundles):
                bundle = self.bundles[asset_id]
                manifest = bundle.manifest
                style = self.styles.get(manifest.styleId)
                is_scene = asset_id in self.scenes
                variant_list = (
                    ["default", *sorted(style.variants)] if style is not None else ["default"]
                )
                has_emissive = bool(style and any("emissive" in c.flags for c in style.palette))

                entry_doc: dict[str, object] = {
                    **manifest.model_dump(exclude_none=True, mode="json"),
                    "kind": "scene" if is_scene else "asset",
                    "variants": variant_list,
                    "hasEmissive": has_emissive,
                }
                if is_scene:
                    scene_spec = self.scenes[asset_id].SCENE
                    frame_placements = self.scene_placements.get(asset_id, {})
                    entry_doc["scene"] = {
                        "parentId": scene_spec.parent_id,
                        "depthSort": scene_spec.depth_sort,
                        "strictBounds": scene_spec.strict_bounds,
                        "strictPerspective": scene_spec.strict_perspective,
                        "mounts": [
                            m.model_dump(exclude_none=True, mode="json") for m in scene_spec.mounts
                        ],
                        "placementsByFrame": {
                            f"{state}:{frame}": [_serialize_mount_placement(p) for p in placements]
                            for (state, frame), placements in sorted(frame_placements.items())
                        },
                    }
                assets_doc.append(entry_doc)

            return {
                "revision": self.revision,
                "lastError": self.last_error,
                "styles": styles_doc,
                "assets": assets_doc,
            }

    def render_png(
        self,
        asset_id: str,
        *,
        state: str | None = None,
        frame: int | None = None,
        sheet: bool = False,
        variant: str | None = None,
        emissive_only: bool = False,
    ) -> bytes:
        """Render and cache a sprite frame or spritesheet PNG for the requested variant."""
        with self._lock:
            bundle = self.bundles.get(asset_id)
            if bundle is None:
                msg = f"Unknown asset {asset_id!r}"
                raise KeyError(msg)
            style = self.styles.get(bundle.manifest.styleId)
            if style is None:
                msg = f"Missing style {bundle.manifest.styleId!r} for asset {asset_id!r}"
                raise KeyError(msg)

            resolved_variant = _resolve_variant_name(style, variant)
            resolved_state = state if state is not None else bundle.manifest.states[0]
            if resolved_state not in bundle.manifest.states:
                msg = f"Unknown state {resolved_state!r} for asset {asset_id!r}"
                raise ValueError(msg)

            resolved_frame = None if sheet else (0 if frame is None else frame)
            if resolved_frame is not None and (
                resolved_frame < 0 or resolved_frame >= bundle.manifest.frames
            ):
                msg = f"Frame {resolved_frame} out of range [0..{bundle.manifest.frames - 1}]"
                raise ValueError(msg)

            cache_key = (
                asset_id,
                resolved_state,
                resolved_frame,
                resolved_variant,
                emissive_only,
                sheet,
            )
            cached = self._png_cache.get(cache_key)
            if cached is not None:
                return cached

            if sheet:
                spec = _manifest_to_asset_spec(bundle.manifest)
                surface = build_spritesheet_surface(spec, bundle.rendered_frames)
            else:
                target_frame = 0 if resolved_frame is None else resolved_frame
                match = next(
                    (
                        rf
                        for rf in bundle.rendered_frames
                        if rf.state == resolved_state and rf.frame == target_frame
                    ),
                    None,
                )
                if match is None:
                    msg = (
                        f"Missing rendered frame ({resolved_state}, {target_frame}) "
                        f"for {asset_id!r}"
                    )
                    raise KeyError(msg)
                surface = match.surface

            png_bytes = surface_to_png(
                surface,
                style,
                variant=resolved_variant,
                scale=1,
                emissive_only=emissive_only,
            )
            self._png_cache[cache_key] = png_bytes
            return png_bytes


def _parse_bool_param(query: Mapping[str, list[str]], key: str) -> bool:
    raw = query.get(key, [""])[0].strip().lower()
    return raw in ("1", "true", "yes", "on")


def _json_response(status: int, payload: dict[str, object]) -> tuple[int, str, bytes]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return (status, "application/json; charset=utf-8", body)


def dispatch_studio_request(state: StudioState, target: str) -> tuple[int, str, bytes]:
    """Route a Preview Studio HTTP GET path+query without socket dependencies."""
    parsed = urlparse(target)
    path = parsed.path or "/"
    query = parse_qs(parsed.query)

    if path in ("/", "/index.html"):
        return (HTTPStatus.OK, "text/html; charset=utf-8", build_studio_html().encode("utf-8"))

    if path == "/api/status":
        return _json_response(HTTPStatus.OK, state.status_payload())

    if path == "/api/catalog":
        return _json_response(HTTPStatus.OK, state.catalog_payload())

    if path.startswith("/api/sprite/"):
        raw_id = unquote(path[len("/api/sprite/") :]).strip("/")
        if raw_id.endswith(".png"):
            raw_id = raw_id[:-4]
        if not raw_id or "/" in raw_id:
            return _json_response(HTTPStatus.NOT_FOUND, {"error": "invalid_sprite_path"})

        req_state = query.get("state", [None])[0]
        variant = query.get("variant", [None])[0]
        sheet = _parse_bool_param(query, "sheet")
        emissive = _parse_bool_param(query, "emissive")

        frame: int | None = None
        if "frame" in query and query["frame"][0] != "":
            try:
                frame = int(query["frame"][0])
            except ValueError:
                return _json_response(HTTPStatus.BAD_REQUEST, {"error": "invalid_frame"})

        try:
            png_bytes = state.render_png(
                raw_id,
                state=req_state,
                frame=frame,
                sheet=sheet,
                variant=variant,
                emissive_only=emissive,
            )
        except KeyError as exc:
            return _json_response(HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except ValueError as exc:
            return _json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        return (HTTPStatus.OK, "image/png", png_bytes)

    return _json_response(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})


def make_studio_handler(state: StudioState) -> type[BaseHTTPRequestHandler]:
    """Create a `BaseHTTPRequestHandler` subclass bound to a `StudioState` instance."""

    class _StudioHTTPHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            status, content_type, body = dispatch_studio_request(state, self.path)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            _ = (format, args)

    return _StudioHTTPHandler


class _QuietThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class StudioServer:
    """Lifecycle wrapper around a background `ThreadingHTTPServer` for `watch --serve`."""

    def __init__(
        self,
        state: StudioState,
        *,
        host: str = _DEFAULT_HOST,
        port: int = _DEFAULT_PORT,
    ) -> None:
        self.state = state
        self.host = host
        self.port = port
        self._server: _QuietThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def bound_port(self) -> int:
        """Return the actual bound TCP port (resolves ephemeral `--port 0`)."""
        if self._server is None:
            return self.port
        addr = self._server.server_address
        return int(addr[1])

    @property
    def url(self) -> str:
        """Return the local HTTP URL for the running Preview Studio."""
        is_wildcard = self.host in ("", "::") or self.host.split(".") == ["0", "0", "0", "0"]
        host_label = "127.0.0.1" if is_wildcard else self.host
        return f"http://{host_label}:{self.bound_port}/"

    def start(self) -> str:
        """Bind the HTTP server on a daemon thread and return its URL."""
        if self._server is not None:
            return self.url
        handler_cls = make_studio_handler(self.state)
        self._server = _QuietThreadingHTTPServer((self.host, self.port), handler_cls)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="pixelforge-studio-server",
            daemon=True,
        )
        self._thread.start()
        return self.url

    def stop(self) -> None:
        """Shut down the background HTTP server and release its socket."""
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)


def build_studio_html() -> str:
    """Return the self-contained HTML/CSS/JS Preview Studio UI (zero external dependencies)."""
    return _STUDIO_HTML


_STUDIO_HTML: Final[str] = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>pixelforge Preview Studio</title>
<style>
  :root {
    --bg: #0b0f17;
    --panel: #111827;
    --panel-alt: #161f2e;
    --border: #263246;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #58a6ff;
    --ok: #3fb950;
    --warn: #d29922;
    --err: #f85149;
    --emissive: #79c0ff;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; height: 100%; background: var(--bg); color: var(--text);
    font: 13px/1.4 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }
  .app {
    display: grid;
    grid-template-columns: 260px 1fr 310px;
    grid-template-rows: 48px 1fr;
    height: 100vh;
    overflow: hidden;
  }
  header {
    grid-column: 1 / -1;
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 14px; background: var(--panel); border-bottom: 1px solid var(--border);
    gap: 12px;
  }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 700; }
  .pill {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 2px 8px; border-radius: 999px; font-size: 11px;
    background: var(--panel-alt); border: 1px solid var(--border); color: var(--muted);
  }
  .pill.live { color: var(--ok); border-color: rgba(63,185,80,0.4); }
  .pill.err { color: var(--err); border-color: rgba(248,81,73,0.5); }
  aside, .inspector {
    background: var(--panel); overflow: auto; padding: 10px;
  }
  aside { border-right: 1px solid var(--border); }
  .inspector { border-left: 1px solid var(--border); }
  main {
    display: flex; flex-direction: column; overflow: hidden; background: var(--bg);
  }
  .toolbar {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
    padding: 8px 12px; background: var(--panel-alt); border-bottom: 1px solid var(--border);
  }
  .group {
    display: inline-flex; align-items: center; gap: 4px;
    padding-right: 8px; border-right: 1px solid var(--border);
  }
  .group:last-child { border-right: none; }
  button, select, input[type="search"] {
    background: var(--panel); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 4px 8px; font: inherit; font-size: 12px; cursor: pointer;
  }
  button:hover { border-color: var(--accent); }
  button.active {
    background: rgba(88, 166, 255, 0.16); border-color: var(--accent); color: #ffffff;
  }
  button.night-on {
    background: rgba(121, 192, 255, 0.18); border-color: var(--emissive); color: var(--emissive);
  }
  input[type="search"] { width: 100%; cursor: text; margin-bottom: 8px; }
  input[type="range"] { width: 76px; accent-color: var(--accent); }
  .asset-item {
    display: flex; align-items: center; justify-content: space-between;
    width: 100%; text-align: left; padding: 7px 8px; margin-bottom: 4px;
    border-radius: 6px; border: 1px solid transparent; background: transparent;
  }
  .asset-item:hover { background: var(--panel-alt); }
  .asset-item.selected { background: rgba(88,166,255,0.14); border-color: var(--accent); }
  .tag {
    font-size: 10px; padding: 1px 5px; border-radius: 4px;
    background: #1f2937; color: var(--muted);
  }
  .tag.scene { color: #bc8cff; background: rgba(188,140,255,0.14); }
  .viewport-wrap {
    position: relative; flex: 1; overflow: auto; display: flex;
    align-items: center; justify-content: center; padding: 24px;
  }
  .checker-dark {
    background-color: #0d1117;
    background-image:
      linear-gradient(45deg, #161d27 25%, transparent 25%),
      linear-gradient(-45deg, #161d27 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #161d27 75%),
      linear-gradient(-45deg, transparent 75%, #161d27 75%);
    background-size: 16px 16px;
    background-position: 0 0, 0 8px, 8px -8px, -8px 0;
  }
  .checker-light {
    background-color: #e6edf3;
    background-image:
      linear-gradient(45deg, #d0d7de 25%, transparent 25%),
      linear-gradient(-45deg, #d0d7de 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #d0d7de 75%),
      linear-gradient(-45deg, transparent 75%, #d0d7de 75%);
    background-size: 16px 16px;
    background-position: 0 0, 0 8px, 8px -8px, -8px 0;
  }
  .solid-void { background: #090d14; }
  canvas {
    image-rendering: pixelated;
    image-rendering: crisp-edges;
    box-shadow: 0 0 0 1px rgba(255,255,255,0.08);
    cursor: crosshair;
  }
  .status-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 6px 12px; background: var(--panel); border-top: 1px solid var(--border);
    color: var(--muted); font-size: 11px;
  }
  .error-banner {
    display: none; padding: 8px 12px; background: rgba(248,81,73,0.14);
    border-bottom: 1px solid var(--err); color: #ffb4ae; font-size: 12px;
  }
  .error-banner.visible { display: block; }
  h3 {
    margin: 12px 0 6px; font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--muted);
  }
  h3:first-child { margin-top: 2px; }
  .kv {
    display: grid; grid-template-columns: 96px 1fr; gap: 3px 8px;
    font-size: 12px; padding: 6px; background: var(--panel-alt);
    border: 1px solid var(--border); border-radius: 6px;
  }
  .kv span:nth-child(odd) { color: var(--muted); }
  .inspect-row {
    width: 100%; text-align: left; display: flex; flex-direction: column; gap: 2px;
    padding: 6px 8px; margin-bottom: 4px; border-radius: 6px;
    background: var(--panel-alt); border: 1px solid var(--border);
  }
  .inspect-row.selected { border-color: var(--accent); background: rgba(88,166,255,0.14); }
  .inspect-row .sub { color: var(--muted); font-size: 11px; }
  .swatches { display: flex; flex-wrap: wrap; gap: 4px; }
  .swatch {
    width: 16px; height: 16px; border-radius: 3px; border: 1px solid rgba(255,255,255,0.2);
    position: relative;
  }
  .swatch.emissive::after {
    content: ""; position: absolute; right: 1px; top: 1px;
    width: 4px; height: 4px; border-radius: 50%; background: #ffffff;
  }
</style>
</head>
<body>
<div class="app">
  <header>
    <div class="brand">
      <span>pixelforge studio</span>
      <span id="live-pill" class="pill live">rev 0</span>
    </div>
    <div id="header-meta" class="pill">loading catalog...</div>
  </header>

  <aside>
    <input id="search-input" type="search" placeholder="Filter assets & scenes..." />
    <div id="asset-list"></div>
  </aside>

  <main>
    <div id="error-banner" class="error-banner"></div>
    <div class="toolbar">
      <div class="group">
        <button id="mode-frame" class="active" type="button">Frame</button>
        <button id="mode-sheet" type="button">Spritesheet</button>
      </div>
      <div class="group" id="state-buttons"></div>
      <div class="group">
        <button id="day-night-btn" type="button" title="Toggle day/night">Day / Night</button>
        <select id="variant-select" aria-label="Style variant"></select>
      </div>
      <div class="group">
        <button id="bloom-btn" class="active" type="button">Bloom</button>
        <input
          id="bloom-range" type="range" min="0" max="2" step="0.1" value="1.0"
          title="Bloom intensity"
        />
        <button id="emissive-only-btn" type="button">Mask</button>
      </div>
      <div class="group">
        <button id="ov-anchors" class="active" type="button">Anchors</button>
        <button id="ov-hitboxes" class="active" type="button">Hitboxes</button>
        <button id="ov-mounts" class="active" type="button">Mounts</button>
        <button id="ov-grid" type="button">Grid</button>
      </div>
      <div class="group">
        <select id="bg-select" aria-label="Background">
          <option value="checker-dark">Dark Checker</option>
          <option value="checker-light">Light Checker</option>
          <option value="solid-void">Void</option>
        </select>
        <select id="zoom-select" aria-label="Zoom">
          <option value="1">1x</option>
          <option value="2">2x</option>
          <option value="4" selected>4x</option>
          <option value="8">8x</option>
        </select>
      </div>
      <div class="group" id="anim-controls">
        <button id="play-btn" type="button">Pause</button>
        <button id="prev-frame-btn" type="button">&lt;</button>
        <span id="frame-label">f0</span>
        <button id="next-frame-btn" type="button">&gt;</button>
      </div>
    </div>

    <div id="viewport" class="viewport-wrap checker-dark">
      <canvas id="stage"></canvas>
    </div>

    <div class="status-bar">
      <span id="cursor-coords">px: (-, -)</span>
      <span id="stage-info">ready</span>
    </div>
  </main>

  <section class="inspector">
    <h3>Asset Metadata</h3>
    <div id="meta-kv" class="kv"></div>
    <h3>Anchors</h3>
    <div id="anchors-list"></div>
    <h3>Hitboxes</h3>
    <div id="hitboxes-list"></div>
    <div id="mounts-section">
      <h3>Scene Mounts</h3>
      <div id="mounts-list"></div>
    </div>
    <h3>Style Palette</h3>
    <div id="palette-swatches" class="swatches"></div>
  </section>
</div>

<script>
(() => {
  const ui = {
    catalog: null,
    selectedId: null,
    viewMode: "frame",
    stateName: null,
    frame: 0,
    playing: true,
    variant: "default",
    bloom: true,
    bloomIntensity: 1.0,
    emissiveOnly: false,
    showAnchors: true,
    showHitboxes: true,
    showMounts: true,
    showGrid: false,
    zoom: 4,
    bg: "checker-dark",
    filter: "",
    selectedAnchor: null,
    selectedHitbox: null,
    selectedMountIdx: null,
    imgCache: new Map(),
    animTimer: null,
  };

  const el = (id) => document.getElementById(id);
  const stage = el("stage");
  const ctx = stage.getContext("2d");

  function currentAsset() {
    if (!ui.catalog || !ui.catalog.assets.length) return null;
    return ui.catalog.assets.find((a) => a.id === ui.selectedId) || ui.catalog.assets[0];
  }

  function currentStyle(asset) {
    return asset && ui.catalog ? ui.catalog.styles[asset.styleId] || null : null;
  }

  function darkVariantFor(style) {
    if (!style) return null;
    if (style.variants.includes("night")) return "night";
    if (style.variants.includes("dusk")) return "dusk";
    return style.variants.find((v) => v !== "default") || null;
  }

  function loadImg(url) {
    const existing = ui.imgCache.get(url);
    if (existing) return existing;
    const p = new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = url;
    });
    ui.imgCache.set(url, p);
    return p;
  }

  function spriteUrl(asset, opts = {}) {
    const rev = ui.catalog ? ui.catalog.revision : 0;
    const params = new URLSearchParams({
      state: opts.state || ui.stateName || asset.states[0],
      variant: ui.variant || "default",
      rev: String(rev),
    });
    if (opts.sheet) {
      params.set("sheet", "1");
    } else {
      params.set("frame", String(opts.frame ?? ui.frame));
    }
    if (opts.emissive) params.set("emissive", "1");
    return `/api/sprite/${encodeURIComponent(asset.id)}?${params.toString()}`;
  }

  function activeMetadata(asset) {
    const st = ui.stateName || asset.states[0];
    if (asset.frameMetadata && asset.frameMetadata[st]) {
      const fm = asset.frameMetadata[st].find((e) => e.frame === ui.frame);
      if (fm) return { anchors: fm.anchors || [], hitboxes: fm.hitboxes || [] };
    }
    return { anchors: asset.anchors || [], hitboxes: asset.hitboxes || [] };
  }

  function activeMounts(asset) {
    if (!asset.scene || !asset.scene.placementsByFrame) return [];
    const st = ui.stateName || asset.states[0];
    return asset.scene.placementsByFrame[`${st}:${ui.frame}`] || [];
  }

  async function drawStage() {
    const asset = currentAsset();
    if (!asset) {
      stage.width = 1; stage.height = 1;
      return;
    }
    const isSheet = ui.viewMode === "sheet";
    const baseImg = await loadImg(spriteUrl(asset, { sheet: isSheet, emissive: ui.emissiveOnly }));
    const emImg = (!ui.emissiveOnly && ui.bloom && asset.hasEmissive)
      ? await loadImg(spriteUrl(asset, { sheet: isSheet, emissive: true }))
      : null;
    if (!baseImg) return;

    const z = ui.zoom;
    const w = baseImg.width * z;
    const h = baseImg.height * z;
    if (stage.width !== w || stage.height !== h) {
      stage.width = w; stage.height = h;
    }
    ctx.clearRect(0, 0, w, h);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(baseImg, 0, 0, w, h);

    if (emImg && ui.bloomIntensity > 0) {
      const glow = document.createElement("canvas");
      glow.width = w; glow.height = h;
      const gctx = glow.getContext("2d");
      gctx.imageSmoothingEnabled = false;
      gctx.drawImage(emImg, 0, 0, w, h);

      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = Math.min(1, 0.45 * ui.bloomIntensity);
      ctx.filter = `blur(${Math.max(2, z * 1.5)}px)`;
      ctx.drawImage(glow, 0, 0);
      ctx.globalAlpha = Math.min(1, 0.25 * ui.bloomIntensity);
      ctx.filter = `blur(${Math.max(4, z * 3.5)}px)`;
      ctx.drawImage(glow, 0, 0);
      ctx.restore();

      ctx.save();
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(emImg, 0, 0, w, h);
      ctx.restore();
    }

    if (ui.showGrid && z >= 4) {
      ctx.save();
      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      ctx.lineWidth = 1;
      for (let gx = 0; gx <= baseImg.width; gx++) {
        ctx.beginPath(); ctx.moveTo(gx * z + 0.5, 0); ctx.lineTo(gx * z + 0.5, h); ctx.stroke();
      }
      for (let gy = 0; gy <= baseImg.height; gy++) {
        ctx.beginPath(); ctx.moveTo(0, gy * z + 0.5); ctx.lineTo(w, gy * z + 0.5); ctx.stroke();
      }
      ctx.restore();
    }

    if (isSheet) {
      drawSheetGrid(asset, z);
    } else {
      drawOverlays(asset, z);
    }

    const modeTag = isSheet ? "sheet" : `${ui.stateName} f${ui.frame}`;
    const dims = `${baseImg.width}x${baseImg.height} @ ${z}x`;
    el("stage-info").textContent = `${asset.id} | ${modeTag} | variant=${ui.variant} | ${dims}`;
  }

  function drawSheetGrid(asset, z) {
    ctx.save();
    ctx.strokeStyle = "rgba(121, 192, 255, 0.45)";
    ctx.lineWidth = 1;
    ctx.font = "11px monospace";
    ctx.fillStyle = "rgba(230, 237, 243, 0.9)";
    const totalW = asset.frames * asset.width * z;
    const totalH = asset.states.length * asset.height * z;
    for (let s = 0; s < asset.states.length; s++) {
      const y = s * asset.height * z;
      ctx.beginPath(); ctx.moveTo(0, y + 0.5); ctx.lineTo(totalW, y + 0.5); ctx.stroke();
      ctx.fillText(asset.states[s], 4, y + 12);
    }
    for (let f = 0; f < asset.frames; f++) {
      const x = f * asset.width * z;
      ctx.beginPath(); ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, totalH); ctx.stroke();
    }
    ctx.restore();
  }

  function drawOverlays(asset, z) {
    const meta = activeMetadata(asset);
    if (ui.showHitboxes) {
      for (const hb of meta.hitboxes) {
        const sel = ui.selectedHitbox === hb.name;
        ctx.save();
        ctx.strokeStyle = sel ? "#ffd866" : "#58a6ff";
        ctx.lineWidth = sel ? 2 : 1;
        ctx.setLineDash([4, 3]);
        ctx.strokeRect(hb.x * z + 0.5, hb.y * z + 0.5, hb.w * z, hb.h * z);
        ctx.fillStyle = sel ? "#ffd866" : "#58a6ff";
        ctx.font = "10px monospace";
        ctx.fillText(hb.name, hb.x * z + 2, Math.max(10, hb.y * z - 2));
        ctx.restore();
      }
    }

    if (ui.showMounts && asset.kind === "scene") {
      const mounts = activeMounts(asset);
      mounts.forEach((m, idx) => {
        const sel = ui.selectedMountIdx === idx;
        const box = m.opaque_bbox || [m.dest_x, m.dest_y, m.width, m.height];
        const color = !m.in_bounds ? "#f85149" : (m.occluded_pixels > 0 ? "#d29922" : "#3fb950");
        ctx.save();
        ctx.strokeStyle = sel ? "#ffffff" : color;
        ctx.lineWidth = sel ? 2 : 1;
        ctx.strokeRect(box[0] * z + 0.5, box[1] * z + 0.5, box[2] * z, box[3] * z);
        ctx.fillStyle = sel ? "#ffffff" : color;
        ctx.font = "10px monospace";
        ctx.fillText(`${m.prop_id}@${m.anchor}`, box[0] * z + 2, Math.max(10, box[1] * z - 2));
        ctx.restore();
      });
    }

    if (ui.showAnchors) {
      for (const a of meta.anchors) {
        const sel = ui.selectedAnchor === a.name;
        const cx = (a.x + 0.5) * z;
        const cy = (a.y + 0.5) * z;
        ctx.save();
        ctx.strokeStyle = sel ? "#ffd866" : "#f85149";
        ctx.lineWidth = sel ? 2 : 1.25;
        ctx.beginPath();
        ctx.moveTo(cx - 6, cy); ctx.lineTo(cx + 6, cy);
        ctx.moveTo(cx, cy - 6); ctx.lineTo(cx, cy + 6);
        ctx.stroke();
        ctx.strokeRect(a.x * z, a.y * z, z, z);
        ctx.fillStyle = sel ? "#ffd866" : "#ff9b95";
        ctx.font = "10px monospace";
        ctx.fillText(a.name, cx + 6, cy - 3);
        ctx.restore();
      }
    }
  }

  function renderSidebar() {
    if (!ui.catalog) return;
    const q = ui.filter.trim().toLowerCase();
    const list = el("asset-list");
    list.innerHTML = "";
    for (const a of ui.catalog.assets) {
      if (q && !a.id.toLowerCase().includes(q) && !a.styleId.toLowerCase().includes(q)) continue;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "asset-item" + (a.id === ui.selectedId ? " selected" : "");
      const badge = a.kind === "scene" ? "SCENE" : `${a.width}x${a.height}`;
      btn.innerHTML = `<span>${a.id}</span><span class="tag ${a.kind}">${badge}</span>`;
      btn.onclick = () => selectAsset(a.id);
      list.appendChild(btn);
    }
  }

  function renderControls() {
    const asset = currentAsset();
    if (!asset) return;
    const style = currentStyle(asset);

    el("mode-frame").classList.toggle("active", ui.viewMode === "frame");
    el("mode-sheet").classList.toggle("active", ui.viewMode === "sheet");

    const stWrap = el("state-buttons");
    stWrap.innerHTML = "";
    for (const st of asset.states) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = st;
      b.className = st === ui.stateName ? "active" : "";
      b.onclick = () => {
        ui.stateName = st; ui.frame = 0;
        renderControls(); renderInspector(); drawStage();
      };
      stWrap.appendChild(b);
    }

    const varSelect = el("variant-select");
    varSelect.innerHTML = "";
    const variants = asset.variants || ["default"];
    for (const v of variants) {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v === "default" ? "day (base)" : v;
      varSelect.appendChild(opt);
    }
    if (!variants.includes(ui.variant)) ui.variant = "default";
    varSelect.value = ui.variant;

    const darkVar = darkVariantFor(style);
    const hasDayNightStates = asset.states.includes("day") && asset.states.includes("night");
    const dnBtn = el("day-night-btn");
    const isNight =
      (darkVar && ui.variant === darkVar) ||
      (!darkVar && hasDayNightStates && ui.stateName === "night");
    dnBtn.classList.toggle("night-on", Boolean(isNight));
    dnBtn.textContent = isNight ? "Night ON" : "Day / Night";
    dnBtn.disabled = !darkVar && !hasDayNightStates;

    el("bloom-btn").classList.toggle("active", ui.bloom);
    el("emissive-only-btn").classList.toggle("active", ui.emissiveOnly);
    el("ov-anchors").classList.toggle("active", ui.showAnchors);
    el("ov-hitboxes").classList.toggle("active", ui.showHitboxes);
    el("ov-mounts").classList.toggle("active", ui.showMounts);
    el("ov-mounts").style.display = asset.kind === "scene" ? "" : "none";
    el("ov-grid").classList.toggle("active", ui.showGrid);

    el("anim-controls").style.display = asset.frames > 1 && ui.viewMode === "frame" ? "" : "none";
    el("play-btn").textContent = ui.playing ? "Pause" : "Play";
    el("frame-label").textContent = `f${ui.frame}/${asset.frames}`;
  }

  function renderInspector() {
    const asset = currentAsset();
    if (!asset) return;
    const style = currentStyle(asset);
    const meta = activeMetadata(asset);

    el("meta-kv").innerHTML = [
      ["id", asset.id],
      ["kind", asset.kind],
      ["style", asset.styleId],
      ["size", `${asset.width} x ${asset.height}`],
      ["perspective", asset.perspective],
      ["frames", `${asset.frames} @ ${asset.fps} fps`],
      ["sha256", asset.sha256.slice(0, 12)],
    ].map(([k, v]) => `<span>${k}</span><span>${v}</span>`).join("");

    const aList = el("anchors-list");
    aList.innerHTML = meta.anchors.length ? "" : `<div class="sub">none</div>`;
    for (const a of meta.anchors) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "inspect-row" + (ui.selectedAnchor === a.name ? " selected" : "");
      const kindTxt = a.kind ? " • " + a.kind : "";
      const dirTxt = a.dir ? " • dir=[" + a.dir.join(",") + "]" : "";
      btn.innerHTML =
        `<strong>${a.name}</strong>` +
        `<span class="sub">(${a.x}, ${a.y})${kindTxt}${dirTxt}</span>`;
      btn.onclick = () => {
        ui.selectedAnchor = ui.selectedAnchor === a.name ? null : a.name;
        renderInspector();
        drawStage();
      };
      aList.appendChild(btn);
    }

    const hList = el("hitboxes-list");
    hList.innerHTML = meta.hitboxes.length ? "" : `<div class="sub">none</div>`;
    for (const hb of meta.hitboxes) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "inspect-row" + (ui.selectedHitbox === hb.name ? " selected" : "");
      const kindTxt = hb.kind ? " • " + hb.kind : "";
      btn.innerHTML =
        `<strong>${hb.name}</strong>` +
        `<span class="sub">x=${hb.x} y=${hb.y} ${hb.w}x${hb.h}${kindTxt}</span>`;
      btn.onclick = () => {
        ui.selectedHitbox = ui.selectedHitbox === hb.name ? null : hb.name;
        renderInspector();
        drawStage();
      };
      hList.appendChild(btn);
    }

    const mSec = el("mounts-section");
    const mList = el("mounts-list");
    mSec.style.display = asset.kind === "scene" ? "" : "none";
    mList.innerHTML = "";
    if (asset.kind === "scene") {
      const mounts = activeMounts(asset);
      mounts.forEach((m, idx) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "inspect-row" + (ui.selectedMountIdx === idx ? " selected" : "");
        const occList = m.occluded_by.join(",");
        const occ = m.occluded_pixels > 0 ? ` • occ=${m.occluded_pixels}px (${occList})` : "";
        const bounds = m.in_bounds ? "in-bounds" : `clipped=${m.clipped_pixels}px`;
        const info = `state=${m.state} f${m.frame} z=${m.z_index}` +
          ` • (${m.dest_x},${m.dest_y}) ${m.width}x${m.height} • ${bounds}${occ}`;
        btn.innerHTML =
          `<strong>${m.prop_id} @ ${m.anchor}</strong>` +
          `<span class="sub">${info}</span>`;
        btn.onclick = () => {
          ui.selectedMountIdx = ui.selectedMountIdx === idx ? null : idx;
          renderInspector();
          drawStage();
        };
        mList.appendChild(btn);
      });
    }

    const sw = el("palette-swatches");
    sw.innerHTML = "";
    if (style) {
      const overrides = (style.variantOverrides && style.variantOverrides[ui.variant]) || {};
      for (const c of style.palette) {
        const hex = overrides[c.name] || c.hex;
        const d = document.createElement("div");
        d.className = "swatch" + (c.flags.includes("emissive") ? " emissive" : "");
        d.style.background = hex;
        const flagSuffix = c.flags.length ? " [" + c.flags.join(",") + "]" : "";
        d.title = `${c.index}: ${c.name} (${hex})${flagSuffix}`;
        sw.appendChild(d);
      }
    }
  }

  function resetAnimLoop() {
    if (ui.animTimer) clearInterval(ui.animTimer);
    ui.animTimer = null;
    const asset = currentAsset();
    if (!asset || asset.frames <= 1 || !ui.playing || ui.viewMode !== "frame") return;
    const period = Math.max(50, Math.round(1000 / Math.max(1, asset.fps)));
    ui.animTimer = setInterval(() => {
      ui.frame = (ui.frame + 1) % asset.frames;
      el("frame-label").textContent = `f${ui.frame}/${asset.frames}`;
      drawStage();
    }, period);
  }

  function selectAsset(id) {
    ui.selectedId = id;
    ui.selectedAnchor = null;
    ui.selectedHitbox = null;
    ui.selectedMountIdx = null;
    const asset = currentAsset();
    if (asset) {
      if (!asset.states.includes(ui.stateName)) ui.stateName = asset.states[0];
      ui.frame = 0;
    }
    renderSidebar();
    renderControls();
    renderInspector();
    resetAnimLoop();
    drawStage();
  }

  async function refreshCatalog() {
    const res = await fetch("/api/catalog", { cache: "no-store" });
    ui.catalog = await res.json();
    ui.imgCache.clear();

    const pill = el("live-pill");
    pill.textContent = `rev ${ui.catalog.revision}`;
    pill.className = "pill " + (ui.catalog.lastError ? "err" : "live");
    el("header-meta").textContent =
      `${ui.catalog.assets.length} targets | ${Object.keys(ui.catalog.styles).length} styles`;

    const banner = el("error-banner");
    if (ui.catalog.lastError) {
      banner.textContent = ui.catalog.lastError;
      banner.classList.add("visible");
    } else {
      banner.textContent = "";
      banner.classList.remove("visible");
    }

    if (!ui.selectedId || !ui.catalog.assets.some((a) => a.id === ui.selectedId)) {
      ui.selectedId = ui.catalog.assets.length ? ui.catalog.assets[0].id : null;
    }
    const asset = currentAsset();
    if (asset && !asset.states.includes(ui.stateName)) {
      ui.stateName = asset.states[0];
      ui.frame = 0;
    }
    renderSidebar();
    renderControls();
    renderInspector();
    resetAnimLoop();
    drawStage();
  }

  async function pollStatus() {
    try {
      const res = await fetch("/api/status", { cache: "no-store" });
      if (!res.ok) return;
      const st = await res.json();
      if (!ui.catalog || st.revision !== ui.catalog.revision) {
        await refreshCatalog();
      }
    } catch (_) {
      el("live-pill").className = "pill err";
      el("live-pill").textContent = "disconnected";
    }
  }

  el("search-input").addEventListener("input", (e) => {
    ui.filter = e.target.value;
    renderSidebar();
  });
  el("mode-frame").onclick = () => {
    ui.viewMode = "frame"; renderControls(); resetAnimLoop(); drawStage();
  };
  el("mode-sheet").onclick = () => {
    ui.viewMode = "sheet"; renderControls(); resetAnimLoop(); drawStage();
  };
  el("variant-select").onchange = (e) => {
    ui.variant = e.target.value; renderControls(); renderInspector(); drawStage();
  };
  el("day-night-btn").onclick = () => {
    const asset = currentAsset();
    const style = currentStyle(asset);
    const darkVar = darkVariantFor(style);
    const hasDayNight = asset && asset.states.includes("day") && asset.states.includes("night");
    const goingNight = !(
      (darkVar && ui.variant === darkVar) ||
      (!darkVar && hasDayNight && ui.stateName === "night")
    );
    if (darkVar) ui.variant = goingNight ? darkVar : "default";
    if (hasDayNight) ui.stateName = goingNight ? "night" : "day";
    renderControls();
    renderInspector();
    drawStage();
  };
  el("bloom-btn").onclick = () => {
    ui.bloom = !ui.bloom; renderControls(); drawStage();
  };
  el("bloom-range").oninput = (e) => {
    ui.bloomIntensity = parseFloat(e.target.value); drawStage();
  };
  el("emissive-only-btn").onclick = () => {
    ui.emissiveOnly = !ui.emissiveOnly; renderControls(); drawStage();
  };
  el("ov-anchors").onclick = () => {
    ui.showAnchors = !ui.showAnchors; renderControls(); drawStage();
  };
  el("ov-hitboxes").onclick = () => {
    ui.showHitboxes = !ui.showHitboxes; renderControls(); drawStage();
  };
  el("ov-mounts").onclick = () => {
    ui.showMounts = !ui.showMounts; renderControls(); drawStage();
  };
  el("ov-grid").onclick = () => {
    ui.showGrid = !ui.showGrid; renderControls(); drawStage();
  };
  el("bg-select").onchange = (e) => {
    el("viewport").className = "viewport-wrap " + e.target.value;
  };
  el("zoom-select").onchange = (e) => { ui.zoom = parseInt(e.target.value, 10) || 4; drawStage(); };
  el("play-btn").onclick = () => { ui.playing = !ui.playing; renderControls(); resetAnimLoop(); };
  el("prev-frame-btn").onclick = () => {
    const a = currentAsset(); if (!a) return;
    ui.playing = false; ui.frame = (ui.frame - 1 + a.frames) % a.frames;
    renderControls(); resetAnimLoop(); drawStage();
  };
  el("next-frame-btn").onclick = () => {
    const a = currentAsset(); if (!a) return;
    ui.playing = false; ui.frame = (ui.frame + 1) % a.frames;
    renderControls(); resetAnimLoop(); drawStage();
  };

  stage.addEventListener("mousemove", (e) => {
    const rect = stage.getBoundingClientRect();
    const px = Math.floor((e.clientX - rect.left) / ui.zoom);
    const py = Math.floor((e.clientY - rect.top) / ui.zoom);
    el("cursor-coords").textContent = `px: (${px}, ${py})`;
  });

  stage.addEventListener("click", (e) => {
    const asset = currentAsset();
    if (!asset || ui.viewMode !== "frame") return;
    const rect = stage.getBoundingClientRect();
    const px = Math.floor((e.clientX - rect.left) / ui.zoom);
    const py = Math.floor((e.clientY - rect.top) / ui.zoom);
    const meta = activeMetadata(asset);
    let bestAnchor = null;
    let bestDist = 5;
    for (const a of meta.anchors) {
      const d = Math.hypot(a.x - px, a.y - py);
      if (d <= bestDist) { bestDist = d; bestAnchor = a.name; }
    }
    if (bestAnchor) {
      ui.selectedAnchor = bestAnchor;
      renderInspector();
      drawStage();
      return;
    }
    if (asset.kind === "scene") {
      const mounts = activeMounts(asset);
      for (let i = mounts.length - 1; i >= 0; i--) {
        const m = mounts[i];
        const b = m.opaque_bbox || [m.dest_x, m.dest_y, m.width, m.height];
        if (px >= b[0] && px < b[0] + b[2] && py >= b[1] && py < b[1] + b[3]) {
          ui.selectedMountIdx = i;
          renderInspector();
          drawStage();
          return;
        }
      }
    }
  });

  refreshCatalog();
  setInterval(pollStatus, 500);
})();
</script>
</body>
</html>
"""
