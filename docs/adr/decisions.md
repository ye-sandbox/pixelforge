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
