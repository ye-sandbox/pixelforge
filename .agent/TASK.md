# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[25.1]` Post-v0.3.0 Hygiene, Public Re-Exports & Fuzzy Lookup Diagnostics

- [ ] Align package version to `0.3.0` across `pyproject.toml` and `src/pixelforge/__init__.py`.
- [ ] Re-export `SceneSpec` and `SceneMountSpec` from top-level `src/pixelforge/__init__.py` and simplify imports in `assets/homelab/*.scene.py`.
- [ ] Add `difflib.get_close_matches` typo suggestions to `PaletteLookup` errors and missing-anchor errors in `export/scene.py`.
- [ ] Sync `.agent/NOTES.md` Active Contracts table with `*.scene.py` (`SceneSpec`) and `pixelforge critic`.
- [ ] Add unit tests for public re-exports and fuzzy error suggestions, and verify `ruff`, `pyright`, `pytest`, and `pixelforge check` exit with `0`.

---

## Completed Tasks Log

_Archived under `v0.2.0` and `v0.3.0` in [`.agent/ARCHIVE.md`](ARCHIVE.md)._

---

## Backlog (Upcoming, in priority order)

### Track A — Agent Ergonomics & LLM-First CLI
- `[26.1]` **LLM-First CLI Output by Default (`--format llm|json|human`):** Adapt `pixelforge` CLI subcommands (`check`, `render`, `diff`, `compose`, `analyze-ref`, `critic`, `watch`) to emit concise, token-dense, structured LLM-oriented output by default (deterministic key-value / compact structured fields, exact paths/coordinates, and actionable fix hints), while supporting explicit `--json` (strict JSON) and `--human` modes; update CLI tests, `NOTES.md`, and READMEs.
- `[26.2]` **Agent Introspection CLI (`pixelforge inspect`) & Modular Skill:** Add `pixelforge inspect style|prefabs|assets|scenes` (LLM-first by default + `--json`) exposing palette tokens grouped by `paint`/`emissive`/`bright`/`reflections`, prefab signatures/categories, and prop/scene anchors/states; refactor `.agent/skills/create-pixel-asset/SKILL.md` into a lean core playbook with progressive-disclosure `references/*.md` covering `*.scene.py`, `critic`, and the complete prefab kits.
- `[26.3]` **Typed StylePack Palette Stubs & Emissive-Bleed Diagnostics:** Add typed palette stub generation/validation so `pyright strict` catches `a.pal.<TOKEN>` typos statically, and add advisory emissive-bleed and canvas-coverage diagnostics to `pixelforge check`.

### Track B — New Pixel Art Domains
- `[27.1]` **Modular Characters, Avatars & Part-Based Animation Kits:** Build compositional character/avatar primitives (`head`, `torso`, `legs`, `hair`, `accessory`), deterministic animation cycles (`idle`, `walk`, `typing`, `alert`), and `PaletteLookup.with_overrides` skin/hair/outfit variants with showcase assets.
- `[28.1]` **UI Pixel Art Primitives & 9-Slice Export (`nine_slice`):** Add 9-slice margin metadata to `AssetSpec`, `manifest.json`, and `manifest.d.ts` alongside reusable UI pixel primitives (buttons, panels, progress bars, badges, `16x16` icons) sharing active `StylePack` tokens.
- `[29.1]` **Tilemaps & Deterministic Autotiling (16-Tile / 47-Tile Blob):** Add a vectorized autotile generator for walls, floors, cables, and terrain bitmasks with tile-metadata atlas export compatible with Godot, Tiled, Phaser, and Svelte.
- `[30.1]` **Second Reference `StylePack` & Style-Agnosticism Verification:** Author a second non-homelab `StylePack` (e.g., `topdown_rpg` or `cyber_hud_32`) with sample assets and tests proving `core/` and `prefabs/` have zero `homelab-16bit` coupling.

### Track C — Deterministic Spatial Guards & Visual Critic Loop
- `[31.1]` **Deterministic Scene Ergonomics Guards in `pixelforge check`:** Extend `pixelforge check` with deterministic `*.scene.py` validation (occlusion thresholds, anchor-within-parent-bbox checks, duplicate mount detection, and strict bounds/perspective audits).
- `[31.2]` **Scene-Aware `pixelforge critic`, Enriched `diff` Metrics & PR Summary Mode:** Extend `pixelforge critic` to score composed `*.scene.py` outputs, enrich `pixelforge diff` output with pixel/emissive/orphan/canvas-coverage deltas, and support Markdown PR regression summaries in CI.

### Track D — Consumption Experience & Distribution
- `[32.1]` **Lightweight Local Preview Studio (`pixelforge watch --serve`):** Add an optional zero-dependency local preview server (or generated self-contained HTML studio) fed by `watch` to inspect spritesheets, toggle `day`/`night` variants, preview simulated emissive bloom, and inspect anchors/mounts interactively.
- `[32.2]` **External Repository Consumption & Packaging Ergonomics:** Verify and document installing/running `pixelforge` as a standalone tool (`uv tool` / git dependency) against external consumer repositories via `--root` with hermetic end-to-end tests.

### Refactoring
- `[90.5]` **Decompose Remaining Dense Modules (`export/scene.py`, `core/prefabs/details.py`, `core/builder.py`, `cli/watch_cmd.py`):** Split `export/scene.py` (models, composition engine, scene contact sheet) and `core/prefabs/details.py` (wall decor vs. shadows/cables), and streamline `core/builder.py` and `cli/watch_cmd.py` preserving public exports.

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

_None currently queued (all items promoted to the active cycle above)._
