# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[38.2]` Semantic Palette Aliases & `UniversalPalette` Protocol
- [ ] Add `aliases: dict[str, str] = Field(default_factory=dict)` to `StylePack` (`src/pixelforge/core/types.py`) with integrity validation (alias targets must exist in `palette`).
- [ ] Resolve `aliases` in `PaletteLookup` (`src/pixelforge/core/palette.py`) and `pixelforge check --sync-stubs` (`src/pixelforge/core/palette_stub.py`).
- [ ] Define a `UniversalPalette` `Protocol` (`INK`, `BG_D`/`BG_M`/`BG_L`, `SURFACE_D`/`SURFACE_M`/`SURFACE_L`, `ACCENT_1`/`ACCENT_2`, `EMISSIVE_1`/`EMISSIVE_2`) and wire standard aliases into built-in presets where applicable.
- [ ] Add hermetic `pytest` coverage verifying compiling a single `.asset.py` across multiple `StylePack`s via `UniversalPalette` aliases; run `ruff`, `pyright`, and `pytest`.

---

## Completed Tasks Log

_Archived under `v0.2.0` and `v0.3.0` in [`.agent/ARCHIVE.md`](ARCHIVE.md)._

- `[38.1]` Dynamic `default_style` Resolution & Built-In StylePack Presets (`pixelforge init --style`) (`0c4d5e7`)
- `[90.5]` Decompose Remaining Dense Modules (`export/scene.py`, `core/prefabs/details.py`, `core/builder.py`, `cli/watch_cmd.py`) (`5bfea27`)
- `[37.1]` AI Ergonomics (`analyze-ref --scaffold` & Multi-Scene World Graph) (`43d3adb`)

- `[36.1]` Typed Frame Events & Audio Cues (`frameMetadata.events`) (`2cfcf42`)
- `[35.1]` First-Class Bitmap Fonts & Pixel Text Atlas (`14747b9`)
- `[34.1]` Derived Lighting & Surface Maps (`_normal.png` & `_height.png`) (`b8659fc`)
- `[33.1]` Derived Gameplay Semantics (`collision_grid`, `walkable_mask`, `y_sort_pivot` & `interact_zones`) (`98fc73c`)
- `[32.2]` External Repository Consumption & Packaging Ergonomics (`6c7b4ba`)
- `[32.1]` Lightweight Local Preview Studio (`pixelforge watch --serve`) (`86578ce`)
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

### Track F — Generic Multi-Game Palette & Preset System
- `[38.3]` **Multi-Genre Preset Showcase & Guard Verification**: Add smoke/showcase assets exercising `ink-1bit`, `retro-pocket-4`, `sweetie-16`, `endesga-32`, `cozy-pastel`, and `scifi-neon` (including emissive bloom isolation) and verify `pixelforge check` + `pytest` across all presets.

### Track C — Deterministic Spatial Guards & Visual Critic Loop
_All Track C items promoted or completed._

### Track D — Consumption Experience & Distribution
_All Track D items promoted or completed._

### Track E — Gameplay Semantics, Derived Maps & AI Ergonomics
_All Track E items promoted or completed._

### Refactoring
_All Refactoring items promoted or completed._

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

_None currently queued (all items promoted to the active cycle above)._
