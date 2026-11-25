# TASK.md — Current Task and Roadmap (`v2-py`)

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[01.1]` Core Indexed Framebuffer, Deterministic PRNG & Pixel Primitives
Objective: implement the `numpy.ndarray(dtype=np.uint8)` indexed framebuffer (`TRANSPARENT_INDEX = 255`), deterministic `mulberry32`/`hashf`, `StylePack` (with `emissive`, `bright`, and optional `reflections` tables) + fail-loud `PaletteLookup`, and full pixel-art primitive set.
- [ ] Implement `StylePack`, `PaletteColor`, `PaletteFlag` (including `emissive` and `bright`), `reflections: dict[str, str]`, `AnchorPoint`, `HitboxRect`, and `AssetSpec` Pydantic/dataclass contracts in `src/pixelforge/core/types.py`
- [ ] Implement `mulberry32`, `xorshift32`, and `hashf` deterministic uint32 PRNG in `src/pixelforge/core/prng.py`
- [ ] Implement fail-loud `PaletteLookup`, reflection index table (`REFL`) resolution, and variant LUT resolution in `src/pixelforge/core/palette.py`
- [ ] Implement `IndexedSurface` (`numpy` uint8) with `put`, `erase`, `get`, `rect`, `rounded_rect`, `line`, `circle`, `ellipse`, `polygon`, `quad`, `fill`, `dither` (Bayer 2×2/4×4, checker), `spr`, `blit_layer`, `mirror_x`, `flip_x`, `flip_y`, `auto_outline`, `sel_out`, `edge_mask`
- [ ] Add comprehensive deterministic unit tests in `tests/core/`

---

## Completed Tasks Log

| Task | Title | Commit(s) | Date |
|---|---|---|---|
| `[00.0]` | V2 Python (`build123d`-style) branch, architecture spec (`DESIGN_V2.md`), ADR & roadmap | `6b94817` | 2026-11-24 |
| `[00.1]` | Python V2 Project Bootstrap & Toolchain Setup (`uv`, `ruff`, `pyright`, `pytest`, `argparse`, V1 TS cleanup) | `78cb1bf` | 2026-11-25 |

---

## Backlog (Upcoming, in priority order)

### `[01.2]` Compositional `build123d`-Style Context API (`Asset`, `Layer`, `Plane`, `Iso`)
Objective: implement the hierarchical context-manager authoring API so AI agents build sprites, multi-style avatars, and `320×200` static scenes parametrically with local coordinates, masks, tilted planes, isometric volumes, and 1px escape hatches.
- [ ] Implement `iso_project`, `iso_tile`, and `iso_box` (2:1 isometric) in `src/pixelforge/core/iso.py`
- [ ] Implement `Plane` context manager (`with a.plane(p0, p1, p2) as p:`) with `(u, v)` `rect`, `grid`, `line`, `dot`, `quad`, `extrude_y`, and `anchor`
- [ ] Implement `Asset` and `Layer` context managers (`with a.layer(name, offset=..., outline=..., sel_out=..., mirror_x=...)`) with masked `scatter`, token-override/recoloring helpers (for shared-silhouette avatars), multi-anchor scene registration (`hw_slot_*`, `window`, `solar`, `breaker`), code-coupled `hitbox`, and direct 1px escape hatches
- [ ] Add unit tests covering nested layers, masking, plane projections, bevels, avatar token-swaps, and multi-anchor scene metadata

### `[02.1]` Headless Exporter, Animated Previews, Contact Sheet, Svelte `manifest.d.ts` & `--indexed-ts`
Objective: implement `Pillow`-backed PNG/spritesheet/emissive-sheet/LUT/GIF-APNG export, direct `--indexed-ts` `Uint8Array` + palette (`EMISSIVE`/`BRIGHT`/`REFL`) export for CPU indexed framebuffers (`idle-datacenter`), upgraded coordinate-ruled `.contact.png`, pixel-diff generator, and auto-generated `manifest.d.ts` for Svelte 5.
- [ ] Implement `surface_to_rgba`, `assert_binary_alpha`, indexed texture + 1D LUT export, and PNG/GIF/APNG encoding in `src/pixelforge/export/png.py`
- [ ] Implement `export_asset_bundle` generating state PNGs, `<id>_sheet.png`, `<id>_<state>_emissive.png`, `<id>_sheet_emissive.png`, optional GIF/APNG preview, and `manifest.json` (preserving per-state/per-frame metadata when varying)
- [ ] Implement `generate_svelte_manifest_dts` emitting strictly typed `manifest.d.ts` (IDs, states, frames, fps, anchors, hitboxes)
- [ ] Implement `export_indexed_ts` in `src/pixelforge/export/indexed_ts.py` emitting compact RLE/base64 `Uint8Array` buffers (`255 = transparent`), `palette.generated.ts` (`PALETTE_HEX`, `EMISSIVE`, `BRIGHT`, `REFL`), and typed `manifest.generated.ts` compatible with `idle-datacenter`'s `Framebuffer.blit()`
- [ ] Implement upgraded `generate_contact_sheet` (full untruncated palette names + `[E]` flag, hitbox dashed overlays, anchor crosshairs, 1× dark/light, zoomed `(x, y)` ruler, state/frame matrix, variant previews, and bounding-box/orphan metrics)
- [ ] Implement `generate_pixel_diff` (side-by-side + magenta diff PNG) and unit tests in `tests/export/`

### `[03.1]` AST Static + Runtime Guard Suite & `pixelforge` CLI (`init`, `render`, `check`, `diff`, `watch`)
Objective: build stdlib `ast` static guards, runtime invariants, orphan-pixel diagnostics, and the full CLI including `--indexed-ts`, git-ref `.asset.py` diffing, and `watch` hot-reload for Svelte 5 / `idle-datacenter` development.
- [ ] Implement `ast.parse`-based static guard rules (`no-stdlib-random`, `no-external-assets`, `no-raw-hex`, `no-io-or-eval`) in `src/pixelforge/guard/ast_rules.py`
- [ ] Implement runtime guard rules (`exact-dimensions`, `closed-palette`, `binary-alpha`, `bit-determinism`, `valid-anchors`) + `orphan-pixels` diagnostic in `src/pixelforge/guard/runtime_rules.py`
- [ ] Implement `importlib` module discovery + `git show` historical `.asset.py` loader in `src/pixelforge/guard/runner.py`
- [ ] Implement CLI commands (`init`, `render`, `check`, `diff`, `watch`, including `--indexed-ts` on `render` and `watch`) with `pydantic-settings` env var support (`PIXELFORGE_OUT_DIR`, `PIXELFORGE_SHEETS_DIR`, `PIXELFORGE_DEFAULT_STYLE`)
- [ ] Add end-to-end hermetic CLI & guard tests in `tests/guard/` and `tests/cli/`

### `[03.2]` Hermetic Agent Skill (`create-pixel-asset` v2) & Docs Sync
Objective: rewrite `.agent/skills/create-pixel-asset/SKILL.md` for Python `build123d`-style authoring and synchronize `README.md` and `README.pt-br.md` to v2.
- [ ] Update `.agent/skills/create-pixel-asset/SKILL.md` with compositional `with a.layer` / `with a.plane` workflow, AST guards, GIF/contact-sheet critique protocol, and canonical `.asset.py` examples
- [ ] Synchronize `README.md` and `README.pt-br.md` (zero heading emojis, Mermaid diagrams, real CLI flags, Svelte 5 `manifest.d.ts` + `--indexed-ts` integration, and `uv` validation commands)

### `[04.1]` Pilot Pack Port & Benchmark Validation (`homelab-16bit` 64-Color Canonical Pack + ThinkPad)
Objective: author the canonical 64-color `homelab-16bit` `StylePack` aligned with `idle-datacenter` (`emissive`, `bright`, `reflections`, fixing `WINDOW_SKY` emissive separation) and port pilot assets (`old_laptop`, `used_gpu_rig`, `ai_cluster_node`, `bedroom_desk_iso`, `thinkpad_r51_iso`, `thinkpad_r51_front`) to `.asset.py`, validating `< 40 ms` renders, zero guard violations, clean 1× visuals, Svelte `manifest.d.ts`, and `--indexed-ts` framebuffer export.
- [ ] Author `styles/homelab_16bit.style.py` aligned with `idle-datacenter`'s 64-color palette (`VOID..GLASS_L`, `emissive`, `bright`, `reflections`), keeping non-emissive accent tokens distinct from emissive glow tokens
- [ ] Port all 4 `homelab/` assets and ThinkPad showcase assets using `with a.layer` / `with a.plane` / `dither` / `iso_box`
- [ ] Run Visual Critic Loop on `.contact.png` + animated `.gif` previews (fix any orphan pixels or outline defects)
- [ ] Add `tests/test_homelab_pilot.py` asserting all guards pass, render time budget holds, and both `manifest.d.ts` and `--indexed-ts` outputs match expected contracts

### `[05.1]` Reference Proportion & Quantized Sketch Analyzer (`pixelforge analyze-ref`)
Objective: add an optional, strictly ephemeral CLI helper that extracts aspect ratio and a low-resolution palette-quantized ASCII sketch from a local reference image to guide agent planning without ever importing external rasters into assets.
- [ ] Implement `analyze_reference_image(path, style, size)` outputting aspect ratio, dominant palette token histogram, and quantized ASCII draft
- [ ] Wire `pixelforge analyze-ref` CLI command with explicit guardrails ensuring outputs stay ephemeral
- [ ] Add hermetic tests using programmatically generated in-memory PNG fixtures

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

- Automated multimodal critic scoring via OpenAI v1 gateway (`hydra-llm-router`, using `httpx2`) for batch CI visual regressions
- Optional Aseprite JSON / TexturePacker atlas export format alongside `manifest.json` + `manifest.d.ts`
- Scene-composition helper allowing room assets (`bedroom_desk_iso`) to preview/validate child prop assets placed on declared anchors
