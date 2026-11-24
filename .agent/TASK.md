# TASK.md — Current Task and Roadmap (`v2-py`)

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[00.1]` Python V2 Project Bootstrap & Toolchain Setup

Objective: initialize the `v2-py` Python package (`pyproject.toml`, `uv`, Python `>= 3.14`, `ruff`, `pyright` strict, `pytest` + `pytest-socket`), obtain consultative approval for runtime/dev dependencies, remove legacy V1 TS scaffolding on `v2-py` (V1 remains preserved on `main`), and verify canonical checks exit `0`.

- [ ] Present consultative dependency plan (`numpy`, `pillow`, `pydantic`, `pydantic-settings`, CLI parser choice `argparse` vs `typer`, plus dev tools `ruff`, `pyright`, `pytest`, `pytest-socket`) and obtain explicit user approval
- [ ] Configure `pyproject.toml`, `.python-version`, `src/pixelforge/` package skeleton, and `.gitignore` updates for Python (`.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`)
- [ ] Transition branch `v2-py` cleanly off legacy TS files (`package.json`, `tsconfig*.json`, `vitest.config.ts`, `biome.json`, `src/**/*.ts`) while keeping `main` untouched
- [ ] Configure `ruff` (`ASYNC`, `S`, `ANN`, `T20`, `DTZ`, `UP`, `TID`), `pyright` (`strict`), and `pytest` (`--disable-socket --allow-unix-socket`)
- [ ] Add smoke test (`tests/test_smoke.py`) and CLI entrypoint (`pixelforge --help`, `--version`)
- [ ] Verify `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` exits `0`

---

## Completed Tasks Log

| Task | Title | Commit(s) | Date |
|---|---|---|---|
| `[00.0]` | V2 Python (`build123d`-style) branch, architecture spec (`DESIGN_V2.md`), ADR & roadmap | `v2-init` | 2026-11-24 |

---

## Backlog (Upcoming, in priority order)

### `[01.1]` Core Indexed Framebuffer, Deterministic PRNG & Pixel Primitives
Objective: implement the `numpy.ndarray(dtype=np.uint8)` indexed framebuffer (`TRANSPARENT_INDEX = 255`), deterministic `mulberry32`/`hashf`, `StylePack` + fail-loud `PaletteLookup`, and full pixel-art primitive set.
- [ ] Implement `StylePack`, `PaletteColor`, `PaletteFlag`, `AnchorPoint`, `HitboxRect`, and `AssetSpec` Pydantic/dataclass contracts in `src/pixelforge/core/types.py`
- [ ] Implement `mulberry32`, `xorshift32`, and `hashf` deterministic uint32 PRNG in `src/pixelforge/core/prng.py`
- [ ] Implement fail-loud `PaletteLookup` and variant LUT resolution in `src/pixelforge/core/palette.py`
- [ ] Implement `IndexedSurface` (`numpy` uint8) with `put`, `erase`, `get`, `rect`, `rounded_rect`, `line`, `circle`, `ellipse`, `polygon`, `quad`, `fill`, `dither` (Bayer 2×2/4×4, checker), `spr`, `blit_layer`, `mirror_x`, `flip_x`, `flip_y`, `auto_outline`, `sel_out`, `edge_mask`
- [ ] Add comprehensive deterministic unit tests in `tests/core/`

### `[01.2]` Compositional `build123d`-Style Context API (`Asset`, `Layer`, `Plane`, `Iso`)
Objective: implement the hierarchical context-manager authoring API so AI agents build sprites parametrically with local coordinates, masks, tilted planes, isometric volumes, and 1px escape hatches.
- [ ] Implement `iso_project`, `iso_tile`, and `iso_box` (2:1 isometric) in `src/pixelforge/core/iso.py`
- [ ] Implement `Plane` context manager (`with a.plane(p0, p1, p2) as p:`) with `(u, v)` `rect`, `grid`, `line`, `dot`, `quad`, `extrude_y`, and `anchor`
- [ ] Implement `Asset` and `Layer` context managers (`with a.layer(name, offset=..., outline=..., sel_out=..., mirror_x=...)`) with masked `scatter`, code-coupled `anchor`/`hitbox`, and direct 1px escape hatches
- [ ] Add unit tests covering nested layers, masking, plane projections, bevels, and code-coupled metadata

### `[02.1]` Headless Exporter, Animated Previews, Contact Sheet & Svelte `manifest.d.ts`
Objective: implement `Pillow`-backed PNG/spritesheet/emissive-sheet/LUT/GIF-APNG export, upgraded coordinate-ruled `.contact.png`, pixel-diff generator, and auto-generated `manifest.d.ts` for Svelte 5.
- [ ] Implement `surface_to_rgba`, `assert_binary_alpha`, indexed texture + 1D LUT export, and PNG/GIF/APNG encoding in `src/pixelforge/export/png.py`
- [ ] Implement `export_asset_bundle` generating state PNGs, `<id>_sheet.png`, `<id>_<state>_emissive.png`, `<id>_sheet_emissive.png`, optional GIF/APNG preview, and `manifest.json` (preserving per-state/per-frame metadata when varying)
- [ ] Implement `generate_svelte_manifest_dts` emitting strictly typed `manifest.d.ts` (IDs, states, frames, fps, anchors, hitboxes)
- [ ] Implement upgraded `generate_contact_sheet` (full untruncated palette names + `[E]` flag, hitbox dashed overlays, anchor crosshairs, 1× dark/light, zoomed `(x, y)` ruler, state/frame matrix, variant previews, and bounding-box/orphan metrics)
- [ ] Implement `generate_pixel_diff` (side-by-side + magenta diff PNG) and unit tests in `tests/export/`

### `[03.1]` AST Static + Runtime Guard Suite & `pixelforge` CLI (`init`, `render`, `check`, `diff`, `watch`)
Objective: build stdlib `ast` static guards, runtime invariants, orphan-pixel diagnostics, and the full CLI including git-ref `.asset.py` diffing and `watch` hot-reload for Svelte 5 development.
- [ ] Implement `ast.parse`-based static guard rules (`no-stdlib-random`, `no-external-assets`, `no-raw-hex`, `no-io-or-eval`) in `src/pixelforge/guard/ast_rules.py`
- [ ] Implement runtime guard rules (`exact-dimensions`, `closed-palette`, `binary-alpha`, `bit-determinism`, `valid-anchors`) + `orphan-pixels` diagnostic in `src/pixelforge/guard/runtime_rules.py`
- [ ] Implement `importlib` module discovery + `git show` historical `.asset.py` loader in `src/pixelforge/guard/runner.py`
- [ ] Implement CLI commands (`init`, `render`, `check`, `diff`, `watch`) with `pydantic-settings` env var support (`PIXELFORGE_OUT_DIR`, `PIXELFORGE_SHEETS_DIR`, `PIXELFORGE_DEFAULT_STYLE`)
- [ ] Add end-to-end hermetic CLI & guard tests in `tests/guard/` and `tests/cli/`

### `[03.2]` Hermetic Agent Skill (`create-pixel-asset` v2) & Docs Sync
Objective: rewrite `.agent/skills/create-pixel-asset/SKILL.md` for Python `build123d`-style authoring and synchronize `README.md` and `README.pt-br.md` to v2.
- [ ] Update `.agent/skills/create-pixel-asset/SKILL.md` with compositional `with a.layer` / `with a.plane` workflow, AST guards, GIF/contact-sheet critique protocol, and canonical `.asset.py` examples
- [ ] Synchronize `README.md` and `README.pt-br.md` (zero heading emojis, Mermaid diagrams, real CLI flags, Svelte 5 `manifest.d.ts` integration, and `uv` validation commands)

### `[04.1]` Pilot Pack Port & Benchmark Validation (`homelab-16bit` + ThinkPad)
Objective: port `homelab-16bit` `StylePack` (fixing `WINDOW_SKY` emissive separation) and pilot assets (`old_laptop`, `used_gpu_rig`, `ai_cluster_node`, `bedroom_desk_iso`, `thinkpad_r51_iso`, `thinkpad_r51_front`) to `.asset.py`, validating `< 40 ms` renders, zero guard violations, clean 1× visuals, and Svelte `manifest.d.ts` output.
- [ ] Author `styles/homelab_16bit.style.py` separating non-emissive accent blue (`ACCENT_BLUE`) from emissive `WINDOW_SKY`
- [ ] Port all 4 `homelab/` assets and ThinkPad showcase assets using `with a.layer` / `with a.plane` / `dither` / `iso_box`
- [ ] Run Visual Critic Loop on `.contact.png` + animated `.gif` previews (fix any orphan pixels or outline defects)
- [ ] Add `tests/test_homelab_pilot.py` asserting all guards pass, render time budget holds, and generated `manifest.d.ts` is valid

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
