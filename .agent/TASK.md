# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[15.1]` Reusable Micro-Props Library (`assets/props/*.asset.py`) & Scene Composition Pack

- [ ] Create starter `iso-2:1` micro-props under `assets/props/` (e.g., `desk_lamp_iso.asset.py`, `monitor_iso.asset.py`, `potted_plant_iso.asset.py`, `storage_crate_iso.asset.py`, `network_switch_iso.asset.py`, `coffee_mug_iso.asset.py`) with `mount_bottom` anchors, `hitboxes`, and multi-state support (`day`/`night` or `idle`/`active`).
- [ ] Add `tests/test_props_compose.py` verifying `compose_scene` mounts the props onto `bedroom_desk_iso` anchors with `in_bounds=True` and zero clipping, plus `pixelforge check` and visual `.contact.png` inspection.
- [ ] Run `uv run ruff check . && uv run ruff format --check .`, `uv run pyright`, `uv run pytest`, and `git diff --check`.

---

## Completed Tasks Log

| Task | Title | Commit(s) | Date |
|---|---|---|---|
| `[00.0]` | V2 Python (`build123d`-style) branch, architecture spec (`DESIGN_V2.md`), ADR & roadmap | `6b94817` | 2026-11-24 |
| `[00.1]` | Python V2 Project Bootstrap & Toolchain Setup (`uv`, `ruff`, `pyright`, `pytest`, `argparse`, V1 TS cleanup) | `78cb1bf` | 2026-11-25 |
| `[01.1]` | Core Indexed Framebuffer, Deterministic PRNG & Pixel Primitives (`numpy` uint8, `StylePack`, `PaletteLookup`, `IndexedSurface`) | `fb6b7cf` | 2026-11-25 |
| `[01.2]` | Compositional `build123d`-Style Context API (`Asset`, `Layer`, `Plane`, `Iso`) | `d324ba5` | 2026-11-25 |
| `[02.1]` | Headless Exporter, Animated Previews, Contact Sheet, Svelte `manifest.d.ts` & `--indexed-ts` | `eef6045` | 2026-11-25 |
| `[03.1]` | AST Static + Runtime Guard Suite & `pixelforge` CLI (`init`, `render`, `check`, `diff`, `watch`) | `4fa94ee` | 2026-11-25 |
| `[03.2]` | Hermetic Agent Skill (`create-pixel-asset` v2) & Docs Sync (`README.md`, `README.pt-br.md`) | `0219a5f` | 2026-11-25 |
| `[04.1]` | Pilot Pack Port & Benchmark Validation (`homelab-16bit` 64-color canonical pack + 7 pilot/ThinkPad assets) | `eff4945` | 2026-11-25 |
| `[05.1]` | Reference Proportion & Quantized Sketch Analyzer (`pixelforge analyze-ref`) | `75dfc6c` | 2026-11-25 |
| `[06.1]` | Contact Sheet Emissive-Only Preview Column (`contact_sheet.py`) | `6f7287e` | 2026-11-25 |
| `[06.2]` | Historical `StylePack` Resolution in `pixelforge diff` (`load_style_from_git`) | `5c1dedf` | 2026-11-25 |
| `[06.3]` | Protect Filtered `render`/`watch --indexed-ts` Against Partial Bundle Overwrites | `cdfefa8` | 2026-11-25 |
| `[07.1]` | Guard, CLI & Core Contract Bug Fixes | `3f1b3cb` | 2026-11-25 |
| `[07.2]` | Multi-Frame Emissive Contact Sheet, Strict Asset Typing & Docs/Skill Sync | `ce23210` | 2026-11-25 |
| `[07.3]` | GitHub Actions CI Workflow (`.github/workflows/ci.yml` with pinned SHAs, `uv` caching, Python 3.14) | `4245d1e` | 2026-11-25 |
| `[90.1]` | Structural Refactoring & Helper Deduplication (`PaletteLookup.with_overrides`, `_canvas.py`, `orphan_pixel_mask`, CLI `scaffold.py`/`workflow.py`) | `ef0cd95` | 2026-11-25 |
| `[08.1]` | Scene-Composition Helper & Anchor Prop Validation (`compose_scene`, `generate_scene_sheet`, `pixelforge compose`) | `6a821e9` | 2026-11-25 |
| `[09.1]` | Automated Multimodal Critic in CI (`hydra-llm-router` + `httpx2`, `self-hosted`, `pixelforge critic`) | `11cf32e` | 2026-11-25 |
| `[10.1]` | Aseprite JSON & TexturePacker Atlas Export (`pixelforge.export.atlas`, `--atlas {aseprite,texturepacker,all}`) | `c148fba` | 2026-11-25 |
| `[11.1]` | Catalog Scalability (`watch` Incremental Rebuild & Lazy `--indexed-ts`) | `fd9a338` | 2026-11-25 |
| `[12.1]` | Structured `pixelforge diff` (`--json` & Anchor/Hitbox Metadata Diff) | `1690b36` | 2026-11-25 |
| `[13.1]` | CI TypeScript Validation (`tsc --noEmit` for `manifest.d.ts` & `--indexed-ts`) | `6f5929f` | 2026-11-25 |
| `[14.1]` | Environment & Detail Prefab Kits (`src/pixelforge/core/prefabs/`) | `0a7f4fb` | 2026-11-25 |

---

## Backlog (Upcoming, in priority order)

_None currently queued (all items promoted to the active cycle above)._

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

_None currently queued (all items promoted to the active cycle above)._
