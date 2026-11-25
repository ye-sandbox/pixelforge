# TASK.md — Current Task and Roadmap (`v2-py`)

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[06.3]` Protect Filtered `render`/`watch --indexed-ts` Against Partial Bundle Overwrites
Objective: prevent `pixelforge render <asset_id> --indexed-ts` (and `watch <asset_id> --indexed-ts`) from silently truncating `dist/indexed/{sprites,manifest}.generated.ts` to a single asset.
- [ ] Decide and implement safe behavior in `src/pixelforge/cli/main.py` (either compile all assets belonging to the affected `StylePack` when writing `dist/indexed/` or reject `<asset_id>` combined with `--indexed-ts` with a clear actionable error message)
- [ ] Document the exact `--indexed-ts` filtering contract in `.agent/NOTES.md`, `README.md`, and `README.pt-br.md`
- [ ] Add regression tests in `tests/cli/test_cli.py` verifying full vs. filtered `--indexed-ts` invocations never silently drop sibling assets

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
