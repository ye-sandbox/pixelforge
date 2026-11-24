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

## Active Contracts

### 1. Core Module & Output Contracts

Full specification lives in [`docs/DESIGN_MVP.md`](../docs/DESIGN_MVP.md). High-level contracts:

| Interface / Artifact | Producer | Consumer | Schema / Contract | Notes |
|---|---|---|---|---|
| `StylePack` (`styles/*.style.ts`) | Style Author / Agent | `src/core`, `src/export`, `src/guard` | `{ id, perspective, lightingAngle, outlineIndex, palette[0..254], variants? }` | Index `255` permanently reserved as `TRANSPARENT_INDEX` (binary alpha 0) |
| `AssetModule` (`assets/**/*.asset.ts`) | Asset Author / Agent | `src/cli`, `src/export`, `src/guard` | `{ id, styleId, width, height, perspective, states, frames, fps?, seed?, render(ctx) }` | Pure deterministic function; zero DOM, zero `Math.random`, zero image imports |
| Sprite PNG (`dist/sprites/<id>_<state>.png`) | `src/export/bundle.ts` | Downstream Games / UIs | 1× pixel-perfect RGBA PNG, binary alpha (`0` or `255`) | Optional horizontal spritesheet (`<id>_sheet.png`) when `frames > 1` |
| Emissive Mask (`dist/sprites/<id>_<state>_emissive.png`) | `src/export/bundle.ts` | WebGL2 Bloom / Shaders | RGBA PNG containing only pixels with palette flag `emissive` | Generated when `--emissive` flag is active or StylePack defines emissives |
| Manifest (`dist/manifest.json`) | `src/export/bundle.ts` | Game Engines / Frontend Manifests | `{ id, styleId, width, height, states, frames, fps, files, anchors[], hitboxes[], sha256 }` | Anchors/hitboxes emitted directly by `ctx.anchor()` / `ctx.hitbox()` during render |
| Contact Sheet (`.pixelforge/sheets/<id>.contact.png`) | `src/export/contact-sheet.ts` | Multimodal Agent Critic / Human | Composite PNG: 1× dark/light previews + 4×/8× grid with `(x,y)` ruler + state/frame matrix + palette swatches | Ephemeral visual-critic artifact (git-ignored under `.pixelforge/`) |
| CLI (`pixelforge`) | `src/cli/main.ts` | Developers / AI Agents / CI | `init`, `render`, `check`, `diff` | Exit code `0` on pass; non-zero with `file:line [rule] detail` on guard violations |

### 2. Multi-Agent Collaboration Contracts (Optional)

> Canonical 3-tier subagent topology, Tier 2 (`dev-harness`) micro-contracts (`files_read`, `files_edit`, `verify`), and model tiers (`default-tier` / `escalation-tier`). If operating single-agent, leave as default.

| Role | Interface / Channel | Responsibilities | Boundary & Invariants |
|---|---|---|---|
| **`Lead / Orchestrator`** | `.agent/TASK.md` / Interactive Prompt | Decomposes tasks, manages lifecycle, routes `default-tier` / `escalation-tier`, interacts with human. | Sole manager of `TASK.md` and commit log. |
| **`Worker / Implementer`** | Worktree / Target Workspace | Executes atomic changes adhering to micro-contract (`files_read`, `files_edit`, `verify`). | Restricted to `files_edit`. Adheres to DoD in `AGENTS.md`. |
| **`Reviewer / Visual Critic`** | Diffs / `.contact.png` / `pixelforge check` | Read-only inspection of guard results, diffs, and rendered contact sheets. | Read-only; reports structured Pass/Fail and exact coordinate fixes. |

---

## Gotchas & Pitfalls

- **Transparent Index Sentinel (`255`):** Never allocate palette color index `255` in any `StylePack`; `IndexedSurface` treats `255` as transparent (`alpha = 0`) across `put`, `spr`, `blitLayer`, and `autoOutline`.
- **Integer Coordinate Rounding:** Always truncate or round coordinates before surface writes (`x | 0`, `y | 0`) and clamp out-of-bounds pixels silently rather than wrapping across scanlines.
- **Git Hygiene for Scratch Visuals:** Contact sheets (`.pixelforge/sheets/*.contact.png`) and reference photos MUST stay untracked (`.pixelforge/` is git-ignored). Never commit third-party reference photos.
- **No Browser Required for MVP Rendering:** Do not add Playwright or headless Chromium for static sprite/contact-sheet exports; Node-native indexed-to-PNG encoding keeps the visual critic loop under 50 ms per asset.

---

## Deliberate Technical Debt

| Debt | Rationale | Revisit When |
|---|---|---|
| Single-package layout (`src/core`, `src/export`, `src/guard`, `src/cli`) | Avoids premature monorepo workspace overhead during MVP iteration | Phase 2 (when Svelte 5 Web Studio is introduced) |
