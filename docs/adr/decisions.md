---
author_type: agent-assisted
author: Antigravity
reviewed_by: Human Lead
date: 2026-11-24
status: accepted
type: architectural-decision-log
---

# Architectural Decisions Log — `pixelforge`

> **Progressive Disclosure:** Historical and cumulative architectural decisions live here so AI agents do not load them into working context on every interaction.
> Active runtime contracts stay in [`.agent/NOTES.md`](../../.agent/NOTES.md).

---

## How to Record Architectural Decisions

1. When a substantive design decision or trade-off is approved, append it here chronologically.
2. Maintain decisions compact and falsifiable using the canonical schema below.
3. If an extraordinary architectural decision requires an extensive specification or C4 diagrams, link it from an entry here (e.g. [`docs/DESIGN_MVP.md`](../DESIGN_MVP.md)).
4. In `.agent/NOTES.md`, maintain only **Active Contracts** and link to this file for background rationale.

---

## Cumulative Decisions

### [2026-11-24] Code-Drawn Indexed Framebuffer (`Uint8Array`) Over Raster Diffusion

- **Context:** Diffusion-based pixel art generators produce mixels, anti-aliased alpha fringes, cross-asset palette drift, unstable animation frames, and raw PNGs devoid of anchor/emissive metadata.
- **Decision:** Author pixel art as deterministic TypeScript modules writing semantic palette indices (`0..254`, `255 = transparent`) into an integer-coordinate `Uint8Array` framebuffer, iterated by multimodal AI agents inspecting generated contact sheets.
- **Alternatives Considered:** (1) Prompting SDXL/Flux + nearest-neighbor downscaling (fails on surgical edits, strict palette lock, and consistent animation frames); (2) SVG `shape-rendering="crispEdges"` (lacks native indexed LUT swaps, dithering/flood-fill/edge-mask pixel operations, and emissive masks).
- **Consequences:** Eliminates mixels and palette drift by construction, makes assets git-diffable and metadata-coupled, and trades away freeform high-resolution organic illustration (explicitly out of scope for MVP).

### [2026-11-24] Node-Native Headless PNG & Contact Sheet Rendering Over Browser Capture

- **Context:** Browser-based screenshot loops (`Playwright`) add multi-second startup overhead and Chromium runtime dependencies for every iteration of an agent's visual critique loop.
- **Decision:** Encode 1× PNGs, horizontal spritesheets, emissive masks, and 4×/8× coordinate-ruled contact sheets directly in Node.js from the indexed framebuffer using a lightweight pure-TS/JS PNG encoder (final library selected consultatively in `[00.1]` / `[01.2]`).
- **Alternatives Considered:** (1) Headless Chromium/Playwright for every sprite render (slow feedback loop, heavy CI dependency); (2) Native C++ bindings like `sharp` or `node-canvas` (platform-specific compilation/binary bloat).
- **Consequences:** Enables `< 50 ms` headless asset rendering and zero-browser CI guard checks. Browser/WebGL2 rendering (bloom, CRT shaders) is cleanly deferred to Phase 2 Web Studio.

### [2026-11-24] Single-Package TypeScript Architecture (Node 26 LTS, `pnpm`, Vitest)

- **Context:** Early MVP development covers four tightly coupled internal modules (`core`, `export`, `guard`, `cli`) with a single distribution surface (`pixelforge` CLI + SDK).
- **Decision:** Align with `ye-sandbox` `stack-decisions` defaults: single-package strict TypeScript project on Node.js 26 Active LTS (floor 24), `pnpm`, Vitest (hermetic tests), and ESLint flat + Prettier (or Biome), organized into `src/core/`, `src/export/`, `src/guard/`, and `src/cli/`.
- **Alternatives Considered:** Multi-package `pnpm` workspace monorepo from day one (adds build-graph and workspace config overhead before public package boundaries stabilize).
- **Consequences:** Fast setup, single typecheck/test/build pipeline, and clean internal boundaries that can split into separate workspace packages later if a Phase 2 Svelte 5 Web Studio is added.

### [2026-11-24] V2 Pivot to Python Compositional Compiler (`build123d`-Style) Decoupled from Svelte 5 Game Runtime

- **Context:** Real-world pilot evaluation (`homelab-16bit` + `thinkpad_r51_*`) revealed that authoring assets as imperative low-level TypeScript loops incurs heavy syntactic noise (`| 0` everywhere, boilerplate palette helpers, fragile regex static guards, ESM/`--experimental-strip-types` loader friction, and `diff --base HEAD` failing on git-ignored `dist/`). Meanwhile, the primary workflow is 100% AI-agent-driven asset generation (analogous to `build123d` code-CAD), while the downstream consumer is a Svelte 5 browser game that loads compiled raster textures and typed manifests rather than executing procedural drawing code in the browser.
- **Decision:** Branch `v2-py` pivots `pixelforge` to a Python (`>= 3.14`, `uv`, `numpy`, `Pillow`, `ruff`, `pyright` strict, `pytest` + `pytest-socket`) compositional pixel art compiler inspired by `build123d` (`with Asset(...)`, `with Layer(...)`, `with Plane(...)`, plus 1px surgical escape hatches `put`/`erase`/`spr`), using stdlib `ast` for static guards and emitting Svelte-ready bundles (1× PNGs, spritesheets, emissive sheets, optional indexed+1D LUT PNGs, animated GIF/APNG previews, `manifest.json`, and auto-generated `manifest.d.ts`). V1 TypeScript MVP remains preserved on `main`.
- **Alternatives Considered:** (1) Keeping TypeScript and adding ergonomic wrappers (`defineAsset`, `dither`, `ellipse`, AST via TypeScript Compiler API) — retains client-side browser execution of `.asset.ts`, but keeps heavier LLM syntax, transpiler/loader friction, and weaker image/animation tooling; (2) Hybrid TS engine + Python asset bridge — adds two-runtime coupling and serialization complexity for marginal benefit.
- **Consequences:** Shorter, cleaner, more LLM-friendly asset code; exact AST static guards; native GIF/APNG previews and `git show`-based `.asset.py` diffs; zero runtime overhead in Svelte 5 with full TypeScript autocomplete via generated `manifest.d.ts` and `pixelforge watch` live-reload into Svelte `static/`. Trades away running `.asset.*` geometry generators directly inside the browser client (runtime palette swaps remain supported via exported indexed textures + 1D LUT shaders). Full specification lives in [`docs/DESIGN_V2.md`](../DESIGN_V2.md).

### [2026-11-24] Direct `--indexed-ts` Export Target & `bright`/`reflections` StylePack Metadata

- **Context:** Auditing the downstream Svelte 5 consumer (`idle-datacenter`) revealed that its stage composites all hardware, avatars, and room backgrounds on CPU into a shared `320×200` indexed `Uint8Array` `Framebuffer` (`0..63`, `255 = transparent`) before applying per-frame reactive palette grading (`buildPalette32()` for NOAA METAR weather, daylight, solar boost, and overload pulsing), automatic raised-floor reflections (`REFL` index table), and unified 3-pass WebGL2 bloom/CRT/grain post-processing. Consuming only baked RGBA PNGs would bypass live grading and `REFL` reflections.
- **Decision:** Extend `StylePack` with the `bright` palette flag and an optional `reflections` (`src_token -> dst_token`) map, and add an optional `--indexed-ts` export target (`src/pixelforge/export/indexed_ts.py`, wired to `render` and `watch`) alongside standard RGBA PNG/spritesheet/emissive/LUT exports. `--indexed-ts` emits compact RLE/base64 `Uint8Array` index buffers (`sprites.generated.ts`), single-source palette tables (`palette.generated.ts` exporting `PALETTE_HEX`, `EMISSIVE`, `BRIGHT`, `REFL`), and a typed `manifest.generated.ts`. Align the pilot `homelab-16bit` pack to the canonical 64-color palette.
- **Alternatives Considered:** (1) Exporting baked RGBA PNGs only (loses live per-frame weather/daylight/overload palette grading and `REFL` floor reflections); (2) Replacing PNG/LUT outputs with `--indexed-ts` only (would couple `pixelforge` exclusively to CPU indexed renderers and lose engine-agnostic distribution).
- **Consequences:** Preserves 100% of `idle-datacenter`'s live reactive palette and reflection pipeline with tiny compiled payloads and zero palette drift, while keeping standard PNG/emissive/LUT/GIF exports intact for visual critique and other game engines.

### [2026-11-25] Python V2 Bootstrap Toolchain & `stdlib argparse` CLI Entrypoint

- **Context:** Task `[00.1]` bootstraps the `v2-py` Python `>= 3.14` package (`uv`, `ruff`, `pyright` strict, `pytest` + `pytest-socket`) and requires choosing between `stdlib argparse` and `typer` for the thin CLI layer (`src/pixelforge/cli/main.py`).
- **Decision:** Adopt `numpy` (`>=2.5.0`), `pillow` (`>=13.0.0`), `pydantic` (`>=2.11.0`), `pydantic-settings` (`>=2.16.0`), `hatchling`, and `stdlib argparse` for the CLI parser, paired with `ruff` (`>=0.17.0`), `pyright` (`>=1.1.400`), `pytest` (`>=8.4.0`), and `pytest-socket` (`>=0.8.0`).
- **Alternatives Considered:** `typer` (`0.29.2`) — offers declarative type-hinted subcommands and rich terminal formatting, but pulls in `rich`, `shellingham`, and `annotated-doc` with slower CLI startup and occasional strict `pyright` decorator friction for an AI-agent/CI-first compiler CLI.
- **Consequences:** Zero extra CLI runtime dependencies, fast startup, strict `pyright` compatibility, and clean separation between `argparse` parsing and domain services in `core/`, `export/`, and `guard/`.

### [2026-11-25] Automated Multimodal Critic in CI via `hydra-llm-router` + `httpx2`

- **Context:** Task `[09.1]` introduces optional automated batch visual regression scoring on changed `.asset.py` / `.style.py` files in CI against the internal `hydra-llm-router` OpenAI v1 endpoint (`POST /v1/chat/completions`).
- **Decision:** Add `httpx2` (`>=2.16.2`) as a project dependency, implement `pixelforge.guard.critic` restricted strictly to virtual model `fast` (`LLM_MODEL_FAST=fast`), wire `pixelforge critic` into the CLI, and run it in a dedicated `visual-critic` `self-hosted` job in `.github/workflows/ci.yml` gated to trusted repo branches/PRs (`continue-on-error: true` advisory mode) while keeping the primary `ubuntu-24.04` `ci` job isolated and deterministic.
- **Alternatives Considered:** `stdlib urllib.request` (zero dependency, but requires manual JSON/status/timeout boilerplate and lacks `MockTransport` for clean hermetic `pytest` coverage under `--disable-socket`); adding `openai` SDK (heavier dependency tree for a single `POST /v1/chat/completions` call).
- **Consequences:** Clean hermetic testability via `httpx2.MockTransport`, zero upstream provider coupling, and isolated homelab runner execution without impacting deterministic `ubuntu-24.04` CI.

### [2026-11-26] Build-Time Compiler Boundary, Track E Semantics & Companion Repositories (`pixelforge-runtime`, `chipforge`)

- **Context:** As `pixelforge` expanded from individual sprites to declarative multi-prop scenes (`*.scene.py`), 16/47-tile autotiling, 9-slice UI, modular characters, multi-engine exports, and the Preview Studio (`[32.1]`), a strategic boundary question emerged: should `pixelforge` absorb runtime game-engine concerns (game loop, collision solver, WebGL2 rendering, procedural audio synthesis), or remain a decoupled build-time compiler? The immediate target remains idle/management games like `idle-datacenter` (Svelte 5 + indexed framebuffer + reactive WebGL2 grading), with a gradual path toward fuller 2D games over time.
- **Decision:** Keep `pixelforge` strictly scoped as a **build-time deterministic 2D content compiler** and expand its output contracts via Track E (`[33.1]`–`[37.1]` in `.agent/TASK.md`), while delegating runtime execution and procedural audio to separate companion repositories when needed:
  1. **`pixelforge` (this repository — Python build-time compiler):** Retains all deterministic, static, geometry-derived generation and validation: pixel art, scenes, tilemaps, 9-slice UI, derived gameplay semantics (`collision_grid`, `walkable_mask`, `y_sort_pivot`, `interact_zones`), optional derived surface maps (`_normal.png`, `_height.png`), first-class bitmap fonts, typed `frameMetadata.events` cue tags, AI scaffolding (`analyze-ref --scaffold`), multi-scene portal validation, guards, `critic`, and the `watch --serve` inspection studio. Explicitly excludes real-time game loops, physics solvers, input handling, runtime WebGL2 game rendering, and audio DSP.
  2. **`pixelforge-runtime` (separate TypeScript repository, preferred over generic `pixelengine`):** Thin typed runtime (~1.5k–3k LOC) for `idle-datacenter`-class Svelte 5 / WebGL2 indexed games and progressive 2D titles. Consumes `manifest.d.ts`, `--indexed-ts`, `collision_grid`, `nine_slice`, `REFL`, `emissive`, `normal`, and `frameMetadata.events`, plus an optional headless AI playtest harness (`step(input) -> state_json + screenshot`). For heavy action/platformer workloads, prefer thin adapters for **Phaser / LittleJS / Godot** rather than building a full general-purpose engine.
  3. **`chipforge` / `pixelforge-sfx` (optional separate repository, preferred over `pixelsynth`):** Procedural retro SFX/chiptune compiler/bridge wrapping proven synthesis engines (`ZzFX` / `@zzfx-studio/zzfxm`, `sfxr` / `jsfxr` / `pyfxr`) instead of reinventing raw DSP oscillators, synchronizing deterministically to `pixelforge` frame event tags (`[36.1]`). Avoids `pixelsynth` (collides with ICCV 2021 *PixelSynth* and `ojack/PIXELSYNTH`, and misleadingly implies image-to-sound).
- **Alternatives Considered:** (1) Monolithic Python AI game engine inside `src/pixelforge/` (couples compiler to a single runtime, breaks `uv tool` standalone packaging `[32.2]` and sub-40ms headless build isolation); (2) Using generic engines like Phaser/Godot without a thin indexed WebGL2 runtime (loses `idle-datacenter`'s live `buildPalette32()` grading, `REFL` reflections, and unified emissive/CRT pass unless reimplemented per game).
- **Consequences:** Preserves fast, hermetic Python compilation (`numpy` + `Pillow` + `ast`), keeps `pixelforge` reusable from idle sims up to full 2D games, avoids reinventing audio DSP or heavy game engines, and establishes clean typed contracts (`manifest.d.ts` / `--indexed-ts`) across repository boundaries.

### [2026-11-26] Native Stdio MCP Server (`pixelforge mcp`) via Official `mcp` Python SDK

- **Context:** Task `[46.1]` exposes `pixelforge` introspection, guard checking, canvas probing, dry-run scene composition, contact-sheet rendering, and git-diff inspection directly to AI editors and agent runtimes over the Model Context Protocol (MCP) stdio transport, returning PNG artifacts inline as MCP image content blocks.
- **Decision:** Add `mcp` (`>=2.3.0`) to `pyproject.toml` and implement `src/pixelforge/cli/mcp_cmd.py` using `mcp.server.mcpserver.MCPServer` over stdio (`server.run_stdio_async()`), isolating tool output buffers from `sys.stdout` and emitting contact-sheet/diff PNGs via `ImageContent(mime_type="image/png")`.
- **Alternatives Considered:** Zero-dependency `stdlib` JSON-RPC 2.0 stdio transport (smaller dependency footprint, but requires maintaining protocol version negotiation, capability schemas, and content-block serialization in-house).
- **Consequences:** Guaranteed compatibility with MCP clients (Claude Desktop, Cursor, T3 Code) and strict `pyright` typing with zero `httpx` transitive dependency added.
