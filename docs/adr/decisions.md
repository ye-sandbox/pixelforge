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
