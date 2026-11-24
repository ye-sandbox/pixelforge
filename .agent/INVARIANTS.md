# INVARIANTS.md — System Invariants and Untouchable Rules

> Runtime-aware guardrails and inviolable rendering contracts for `pixelforge`.
> Record project-specific invariants here as they are discovered; preserve the shared Invariant 7 section verbatim.

---

## 1. Indexed Framebuffer & Binary Alpha Invariant

- **Zero Mixels & Integer Grid:** All pixel writes operate on integer coordinates inside a `Uint8Array` buffer of exact `width * height` size. Sub-pixel blending and anti-aliasing are prohibited in `src/core/`.
- **Binary Alpha (`0` or `255`):** Index `255` (`TRANSPARENT_INDEX`) maps exclusively to alpha `0`. Palette indices `0..254` map exclusively to alpha `255`. Exported PNGs must never contain intermediate alpha values (`1..254`).

---

## 2. Deterministic Rendering & Closed Palette Invariant

- **Seeded Randomness Only:** `Math.random()`, `Date.now()`, and wall-clock/locale APIs are strictly forbidden inside `src/core/`, `styles/`, and `assets/`. Random variation must flow exclusively through the seeded PRNG (`mulberry32` / `hashf`).
- **Closed Semantic Palette:** Asset modules must draw solely via declared `StylePack` indices; raw `#rrggbb` literals and external raster image imports are prohibited inside `assets/**`.

---

## 3. Code-Coupled Metadata Invariant

- **Single Source of Coordinates:** Anchors (`foot`, `led`, `socket`) and hitboxes exported in `manifest.json` must be emitted directly by the asset's `render(ctx)` execution so geometry and metadata can never drift out of sync.

---

## 7. Adaptive Interface Verification & UI Protocol

- **Invariant 7.1 (Runtime-Aware Interface Verification):**
  - **Inside T3 Code:** When undertaking frontend, preview, or UI component tasks in a T3 Code environment, agents must verify visual and interactive behaviors using preview and device MCP tools (`preview_status`, `preview_open`, `preview_snapshot`, `preview_act`, `device_open`). Agents must check `preview_status` before opening tabs and prefer accessibility/snapshot locators over coordinates.
  - **Outside T3 Code (Headless CLI / CI):** In headless terminal runtimes or CI pipelines, agents must verify interfaces through non-blocking build, component, and E2E test suites (`npm run build`, `vitest`, `playwright --headless`), without hanging on graphical display servers.
- **Invariant 7.2 (Prohibition of Blind Preview Launches):**
  - Agents must NEVER invoke `preview_open` or launch mobile emulators to retrieve static web documentation or perform general search queries. Static web research belongs exclusively to headless HTTP tools (`read_url_content`, web search).
- **Invariant 7.3 (Mandatory Preview Lifecycle Cleanup):**
  - Any preview browser tab or device emulator session opened by an agent during execution MUST be explicitly closed (`preview_close`, `device_close`) before handing back control to the human or completing the task.
- **Invariant 7.4 (Non-Blocking Server Containment):**
  - Local development or preview servers started for interface testing must be run as manageable background tasks on ephemeral ports, and terminated immediately once verification concludes.
