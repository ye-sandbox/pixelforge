# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[58.1]` Zero-Boilerplate `UiPalette.from_style()` & StylePack UI Semantic Mapping
Goal: Add `UiPalette.from_style(target, **overrides)` deriving all UI color tokens deterministically from `StylePack` aliases/ramps/flags, migrate `assets/ui/hud_*.asset.py`, and test portability across all built-in presets.

- [ ] Design and implement `UiPalette.from_style(target, **overrides)` deriving UI surface, border, text, accent, and state tokens deterministically from `StylePack` aliases, ramps, and palette flags.
- [ ] Migrate `assets/ui/hud_*.asset.py` to use `UiPalette.from_style(...)` without manual per-theme color boilerplate.
- [ ] Add hermetic unit and guard tests verifying `UiPalette.from_style()` portability across all built-in `StylePack` presets.
- [ ] Pass full DoD (`ruff`, `pyright`, `pytest`, `git diff --check`) and update `.agent/NOTES.md` if contracts change.

---

## Completed Tasks Log

_Archived under `v0.2.0` and `v0.3.0` in [`.agent/ARCHIVE.md`](ARCHIVE.md)._

- `[57.1]` Project Build Profiles (`pixelforge.toml` / `[tool.pixelforge]`) (`d5e9c56`)

- `[56.1]` Pixel UI Rendering Modes ADR & Build-Time Boundary Contract (`30be435`)
- `[55.1]` Exterior Prefab Kit (`src/pixelforge/core/prefabs/exterior/`) (`a1f7ca0`)
- `[54.1]` Modularize Domain-Specific Skill References (`create-pixel-asset`) (`238ca49`)
- `[53.1]` Silhouette-First Authoring Skill Protocol & Reproducible Agent Eval Benchmark (`a8908b8`)

- `[52.1]` Perceptual Reference Pipeline (`analyze-ref` OKLab, `--trim`, `--emit-spr`) (`dbf2630`)
- `[51.1]` Deterministic Pixel-Art Craft Lints in `pixelforge check` (`52ad1d8`)

- `[50.1]` Layer Alpha-Lock (`clip="opaque"`) & Organic Pixel Primitives (`a25f3c7`)
- `[49.1]` First-Class Color Ramps (`StylePack.ramps`) & Directional Volume Shading (`51dd689`)
- `[48.1]` Category-Aware 5-Axis Visual Critic (`pixelforge critic` & `blind-critic` Alignment) (`7cacf39`)
- `[47.1]` Upgraded Diagnostic Contact Sheet & Enriched MCP Visual Loop (`e3a4747`)
- `[46.1]` Native Stdio MCP Server (`pixelforge mcp`) (`3fb1ab4`)
- `[45.1]` Environment Health Check (`pixelforge doctor`) & Blind Visual Critic Skill (`e7be5d2`)

- `[44.1]` Batch Pack Contact Sheet (`pixelforge render --pack-sheet`) (`e06b7fb`)
- `[43.1]` Zero-Reference Asset, Scene & Style Scaffolders (`pixelforge new`) (`ecfc95c`)

- `[42.1]` Exact Pixel & Layer Diagnostics (`pixelforge probe`) (`16591e6`)
- `[41.1]` Core Drawing API Introspection (`pixelforge inspect api`) (`4a561c9`)
- `[40.1]` Spatial Ergonomics Guards & Snapped Furniture Sets (`e2e6ff4`)
- `[39.1]` Multi-Room Portal Prefab, Real Scene World Graph & Window Prefabs (`08bdbc7`)

- `[38.3]` Multi-Genre Preset Showcase & Guard Verification (`304fc34`)
- `[38.2]` Semantic Palette Aliases & `UniversalPalette` Protocol (`0d03ff8`)
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

### Track J — Pixel UI Architecture, Build Profiles & Core Foundations
- `[59.1]` **Auto-Synced `NineSliceMargins` & `content` Hitbox Emission for UI Primitives** *(Depends on: `[58.1]`)* — Return/emit synchronized `NineSliceMargins` and `hitbox("content", ...)` directly from `ui_panel`/`ui_button` and framed UI primitives so spec margins, drawn bevels, and inner content padding cannot drift.

### Track K — Complete Pixel UI Controls, Multi-Genre Icons & PT-BR Typography
- `[60.1]` **Complete Game UI Controls Library (`prefabs/ui/`)** *(Depends on: `[58.1]`, `[59.1]`)* — Subdivide `src/pixelforge/core/prefabs/ui.py` into `prefabs/ui/` and add `ui_slot` (empty/hover/selected/locked), `ui_dialogue_box` (tail + portrait frame), `ui_tabs`, `ui_slider`, `ui_toggle`/`ui_checkbox`, `ui_scrollbar`, `ui_divider`, and `ui_cursor` (with `hotspot` anchor).
- `[61.1]` **Multi-Genre Pixel Icon Packs (`ui_icons_core`, `ui_icons_rpg`, `ui_icons_tech`)** *(Depends on: `[58.1]`, `[60.1]`)* — Replace closed homelab-only `UiIconKind` with modular, extensible icon registries (`8x8`, `12x12`, `16x16`) spanning universal UI controls, RPG/game HUD glyphs, and tech/homelab icons while preserving `ui_icon_16` backwards compatibility.
- `[62.1]` **Production Bitmap Fonts: PT-BR/Latin-1, Proportional Metrics, Title Presets & Native Outline** *(Depends on: none)* — Upgrade `src/pixelforge/core/font.py` with Latin-1/PT-BR diacritics + HUD symbols (`♥ ★ → ← ↑ ↓ × •`), true per-glyph `proportional=True` (`x_advance`/`x_offset`) + `tabular_digits=True`, display/title presets (`6x8`/`8x10` bold), native 1px `outline=` pass, and optional BMFont (`.fnt`) export.
- `[63.1]` **Cohesive UI Theme Kit Generator (`pixelforge new ui-kit`) & UI Styleguide Sheet** *(Depends on: `[57.1]`, `[58.1]`, `[59.1]`, `[60.1]`, `[61.1]`, `[62.1]`)* — Scaffold a unified UI component kit parameterized by theme style (`pixel_chamfer`, `rpg_wood`, `flat_crt`, `minimal_1bit`) plus a single comparative UI Styleguide `.contact.png` showcasing panels, button states, bars, slots, badges, cursors, icons, and font samples together.

### Track L — UI Guards, Design-System Export, HUD Critic & Runtime Bridge
- `[64.1]` **Deterministic UI Quality Guards in `pixelforge check`** *(Depends on: `[59.1]`, `[60.1]`, `[63.1]`)* — Add UI runtime rules verifying minimum text/surface luminance contrast (reusing `_hex_luminance`), 9-slice margin integrity (`left + right < width`, `top + bottom < height`, clean >= 1px stretchable core without slicing bevels/title bars), and cursor `hotspot` anchor bounds.
- `[65.1]` **Pixel UI Design-System Exporter (`--ui-css`: `theme.generated.css`, 9-Slice Utilities & Cursors)** *(Depends on: `[56.1]`, `[57.1]`, `[59.1]`, `[60.1]`, `[62.1]`, `[64.1]`)* — Emit CSS custom properties (`--pf-*`) from `StylePack` + `[data-pf-variant="..."]` overrides, integer-scaled `border-image` 9-slice classes with `:hover`/`:active`/`:disabled` + `content` padding, cursor hotspot classes, and crisp bitmap font CSS helpers across `render`, `watch`, and `pixelforge.toml`.
- `[66.1]` **HUD / UI Screen Composition & Visual Critic Loop (`*.ui.py` / `compose --hud`)** *(Depends on: `[60.1]`, `[62.1]`, `[63.1]`, `[64.1]`)* — Compose declarative full-screen HUD/modal previews anchored over a target viewport or compiled `*.scene.py` backdrop (`320x200`, etc.) with contact-sheet rendering and UI-aware `pixelforge critic` scoring (1x legibility, text contrast, pixel-grid alignment, HUD-to-gameplay ratio).
- `[67.1]` **Preview Studio UI Playground (`watch --serve`: 9-Slice Live Resizer & Bitmap Font Tester)** *(Depends on: `[59.1]`, `[62.1]`, `[65.1]`)* — Add an interactive UI Playground view in `src/pixelforge/export/studio.py` with a live 9-Slice Resizer (width/height sliders, state switcher, integer zoom) and live Bitmap Font Tester (PT-BR text input, proportional/tabular toggle, panel contrast background preview).
- `[68.1]` **Thin Runtime UI Primitives Kit (`--ui-svelte` / Typed Svelte 5 & Canvas Bridge)** *(Depends on: `[56.1]`, `[62.1]`, `[65.1]`, `[66.1]`)* — Provide an optional zero-dependency Svelte 5 / TypeScript UI starter/adapter (`PixelViewport`, `PixelPanel`, `PixelButton`, `PixelText`, `PixelBar`, `PixelSlot`, `PixelModal`) bound strictly to `manifest.d.ts`, `theme.generated.css`, and/or `--indexed-ts` with `tsc --noEmit` CI validation.

### Track I — Exterior & Domain Authoring
_All Track I items promoted or completed._

### Track H — Agent Visual Assertiveness & Pixel-Art Craft
_All Track H items promoted or completed._

### Track G — Agent QoL & Developer Ergonomics
_All Track G items promoted or completed._

### Track F — Generic Multi-Game Palette & Preset System
_All Track F items promoted or completed._

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
