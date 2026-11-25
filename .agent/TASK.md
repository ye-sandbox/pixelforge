# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[90.1]` Structural Refactoring & Helper Deduplication

- [ ] Decompose oversized functions (`generate_contact_sheet`, `export_asset_bundle`, `check_asset_runtime`) and extract CLI scaffold/orchestration helpers out of `src/pixelforge/cli/main.py`
- [ ] Deduplicate 8-connected orphan-pixel detection (`guard/runtime_rules.py` vs `export/contact_sheet.py`) and RGBA checkerboard/compositing helpers (`export/contact_sheet.py` vs `export/diff.py`)
- [ ] Replace `object.__setattr__` mutation in `src/pixelforge/core/builder.py` with a dedicated `PaletteLookup.with_overrides(...)` method

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

---

## Backlog (Upcoming, in priority order)

_None currently queued._

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

- Automated multimodal critic scoring via OpenAI v1 gateway (`hydra-llm-router`, using `httpx2`) for batch CI visual regressions
- Optional Aseprite JSON / TexturePacker atlas export format alongside `manifest.json` + `manifest.d.ts`
- Scene-composition helper allowing room assets (`bedroom_desk_iso`) to preview/validate child prop assets placed on declared anchors
- Optional `--json` structured CLI output and anchor/hitbox metadata diffing in `pixelforge diff`
- Incremental `pixelforge watch` recompilation and lazy decoding in `--indexed-ts` once asset catalogs grow beyond tens of sprites
- Optional `tsc --noEmit` validation job in CI for generated `manifest.d.ts` and `--indexed-ts` TypeScript modules
