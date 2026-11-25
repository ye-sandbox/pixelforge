# NOTES.md — Active Contracts and Runtime Memory

> Stores active runtime contracts (WHAT interacts with WHAT), CLI/output schemas, and critical gotchas.
> Historical architectural decisions live in [`docs/adr/decisions.md`](../docs/adr/decisions.md).

---

## How to Use this File

1. **Read before planning.** Active contracts and gotchas here take precedence over unstated defaults.
2. **Keep this file lean:** Only store ACTIVE contracts, schemas, open technical debt, and critical gotchas.
3. **Architectural decisions:** Record in [`docs/adr/decisions.md`](../docs/adr/decisions.md). Do NOT accumulate historical decisions here to prevent context bloat.
4. **CRITICAL INVARIANT:** NEVER create task-specific headings (e.g., `## [Task XX.Y] Description` or `### [Task XX.Y]`) in `NOTES.md`. Task completion history lives in `git log` and `.agent/ARCHIVE.md`. Architectural decisions live in `docs/adr/decisions.md`. In `NOTES.md`, maintain and update ONLY the live tables/lists of active contracts, interfaces, and topology.

---

## Active Contracts (`v2-py`)

### 1. Core Module & Output Contracts

Full V2 specification lives in [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md). High-level contracts:

| Interface / Artifact | Producer | Consumer | Schema / Contract | Notes |
|---|---|---|---|---|
| `StylePack` (`styles/*.style.py`) | Style Author / Agent | `pixelforge.core`, `export`, `guard` | `{ id, perspective, lighting_angle, outline_index, palette[0..254], reflections?, variants? }` (`PaletteFlag` includes `emissive`, `bright`, `outline`, etc.) | Index `255` permanently reserved as `TRANSPARENT_INDEX` (binary alpha 0); `reflections` maps `src_token -> dst_token` for floor reflection tables (`REFL`) |
| `Asset` Module (`assets/**/*.asset.py`) | Asset Author / Agent | `pixelforge.cli`, `export`, `guard` | `SPEC: AssetSpec` + `render(a: Asset) -> None` (`with a.layer`, `with a.plane`, plus 1px `put`/`erase`/`spr`) | Pure deterministic Python; zero `random`, zero I/O, zero raw hex, zero external images |
| Sprite PNG (`dist/sprites/<id>_<state>.png`) | `pixelforge.export.bundle` | Svelte 5 Game / Any Engine | 1× pixel-perfect RGBA PNG, binary alpha (`0` or `255`) | Horizontal spritesheet (`<id>_sheet.png`) when `frames > 1` |
| Emissive Mask (`dist/sprites/<id>_<state>_emissive.png`) | `pixelforge.export.bundle` | WebGL2 Bloom / Shaders | RGBA PNG containing only pixels with palette flag `emissive` | Also emits `<id>_sheet_emissive.png` when `frames > 1` |
| Indexed + LUT PNG (`<id>_<state>_idx.png`, `<style>_lut.png`) | `pixelforge.export.png` | Svelte 5 WebGL2 Palette Swap | Optional (`--lut`): R channel = palette index `0..254`, A = `0/255`, paired with `256×N` 1D LUT PNG | Enables 60 FPS runtime day/night/status swaps in WebGL2 shaders without executing `.asset.py` |
| Indexed TS Bundle (`dist/indexed/{sprites,palette,manifest}.generated.ts`) | `pixelforge.export.indexed_ts` | CPU Indexed Framebuffer (`idle-datacenter`) | Optional (`--indexed-ts`): RLE/base64 `Uint8Array` index buffers (`255 = transparent`) + `PALETTE_HEX`, `EMISSIVE`, `BRIGHT`, `REFL` + typed manifest | Direct `Framebuffer.blit()` preserving live reactive `buildPalette32()` grading, `REFL` floor reflections, and unified WebGL2 post-processing |
| Animated Preview (`.pixelforge/previews/<id>_<state>.gif`) | `pixelforge.export.bundle` | Human / Agent Critic | Optional (`--animate`): looping nearest-neighbor GIF/APNG when `frames > 1` | Ephemeral QA artifact (git-ignored under `.pixelforge/`) |
| Manifest (`dist/manifest.json` + `dist/manifest.d.ts`) | `pixelforge.export.bundle` & `svelte_types` | Svelte 5 Game / Engines | `{ id, styleId, width, height, states, frames, fps, files, anchors[], hitboxes[], sha256 }` + TS `.d.ts` | Generated `.d.ts` provides strict compile-time autocomplete in Svelte 5 |
| Contact Sheet (`.pixelforge/sheets/<id>.contact.png`) | `pixelforge.export.contact_sheet` | Multimodal Agent Critic / Human | 1× dark/light + zoomed grid with `(x,y)` ruler + anchors + hitboxes + state/frame matrix + full swatches + metrics | Ephemeral visual-critic artifact (git-ignored under `.pixelforge/`) |
| CLI (`pixelforge`) | `pixelforge.cli.main` | Developers / AI Agents / CI | `init`, `render`, `check`, `diff`, `watch`, `analyze-ref` | Exit `0` on pass; `file:line [rule] detail` on guard violations; honors `PIXELFORGE_*` env vars |

### 2. Multi-Agent Collaboration Contracts (Optional)

| Role | Interface / Channel | Responsibilities | Boundary & Invariants |
|---|---|---|---|
| **`Lead / Orchestrator`** | `.agent/TASK.md` / Interactive Prompt | Decomposes tasks, manages lifecycle, interacts with human. | Sole manager of `TASK.md` and commit log. |
| **`Worker / Implementer`** | Worktree / Target Workspace | Executes atomic changes adhering to micro-contract (`files_read`, `files_edit`, `verify`). | Restricted to `files_edit`. Adheres to DoD in `AGENTS.md`. |
| **`Reviewer / Visual Critic`** | Diffs / `.contact.png` / `pixelforge check` | Read-only inspection of guard results, diffs, and rendered contact sheets/GIFs. | Read-only; reports structured Pass/Fail and exact coordinate or parametric fixes. |

---

## Gotchas & Pitfalls

- **Transparent Index Sentinel (`255`):** Never allocate palette color index `255` in any `StylePack`; `IndexedSurface` treats `255` as transparent (`alpha = 0`) across all drawing, blitting, masking, and outline ops.
- **Keep Emissive Tokens Separate from Paint Tokens:** Never reuse an `emissive`-flagged token (like `WINDOW_SKY`) for non-glowing painted surfaces (like blue keycaps or badges), or they will bleed into WebGL2 bloom masks.
- **Avoid Pure-Python Per-Pixel Loops in Large Assets:** Prefer vectorized core primitives (`plane.rect`, `iso_box`, `dither`, `scatter`, `spr`) backed by `numpy.ndarray(uint8)` so renders stay `< 40 ms`.
- **Git Hygiene for Scratch Visuals:** Contact sheets (`.pixelforge/sheets/`), diffs (`.pixelforge/diffs/`), animated previews (`.pixelforge/previews/`), and reference photos MUST stay untracked (`.pixelforge/` is git-ignored). Never commit third-party reference photos.
- **No Browser Required for Asset Compilation:** Keep compilation 100% headless in Python (`numpy` + `Pillow`). Live preview in Svelte 5 uses `pixelforge watch --out <svelte-app>/static/sprites` (or `--indexed-ts --out <svelte-app>/src/lib/gfx/generated` for CPU indexed framebuffers).
- **Single-Source 64-Color Palette Alignment (`idle-datacenter`):** When targeting `--indexed-ts`, `StylePack` indices (`0..63`), `emissive`, `bright`, and `reflections` (`REFL`) are the canonical source of truth exported into `palette.generated.ts` so the compiler and game framebuffer never drift.

---

## Deliberate Technical Debt

_None currently open._
