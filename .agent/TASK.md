# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[32.1]` Lightweight Local Preview Studio (`pixelforge watch --serve`)

- [ ] Add an optional zero-dependency local preview server (or generated self-contained HTML studio) fed by `watch`.
- [ ] Support inspecting spritesheets, toggling `day`/`night` variants, previewing simulated emissive bloom, and inspecting anchors/mounts interactively.
- [ ] Add unit and CLI tests for the preview studio server/output.

---

## Completed Tasks Log

_Archived under `v0.2.0` and `v0.3.0` in [`.agent/ARCHIVE.md`](ARCHIVE.md)._

- `[31.2]` Scene-Aware `pixelforge critic`, Enriched `diff` Metrics & PR Summary Mode (`1eb9ef4`)
- `[31.1]` Deterministic Scene Ergonomics Guards in `pixelforge check` (`be22749`)
- `[30.1]` Second Reference `StylePack` & Style-Agnosticism Verification (`a4f1f9f`)
- `[29.1]` Tilemaps & Deterministic Autotiling (16-Tile / 47-Tile Blob) (`719b8ab`)
- `[28.1]` UI Pixel Art Primitives & 9-Slice Export (`nine_slice`) (`a4ba768`)
- `[27.1]` Modular Characters, Avatars & Part-Based Animation Kits (`a943cd9`)
- `[26.3]` Typed StylePack Palette Stubs & Emissive-Bleed Diagnostics (`ac6b1d1`)
- `[26.2]` Agent Introspection CLI (`pixelforge inspect`) & Modular Skill (`4a49910`)
- `[26.1]` LLM-First CLI Output by Default (`--format llm|json|human`) (`6cd0ce7`)
- `[25.1]` Post-v0.3.0 Hygiene, Public Re-Exports & Fuzzy Lookup Diagnostics (`e0ea838`)

---

## Backlog (Upcoming, in priority order)

### Track C — Deterministic Spatial Guards & Visual Critic Loop
_All Track C items promoted or completed._

### Track D — Consumption Experience & Distribution
- `[32.2]` **External Repository Consumption & Packaging Ergonomics:** Verify and document installing/running `pixelforge` as a standalone tool (`uv tool` / git dependency) against external consumer repositories via `--root` with hermetic end-to-end tests.

### Refactoring
- `[90.5]` **Decompose Remaining Dense Modules (`export/scene.py`, `core/prefabs/details.py`, `core/builder.py`, `cli/watch_cmd.py`):** Split `export/scene.py` (models, composition engine, scene contact sheet) and `core/prefabs/details.py` (wall decor vs. shadows/cables), and streamline `core/builder.py` and `cli/watch_cmd.py` preserving public exports.

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

_None currently queued (all items promoted to the active cycle above)._
