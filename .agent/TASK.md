# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[09.1]` Automated Multimodal Critic in CI (`hydra-llm-router` + `httpx2`, `self-hosted`)

- [ ] Design and implement batch visual regression scoring on changed assets via internal-only `hydra-llm-router` OpenAI v1 (`POST /v1/chat/completions`, virtual model `fast`) using `httpx2` (request explicit dependency/budget approval before adding `httpx2` to `pyproject.toml`)
- [ ] Add a dedicated `self-hosted` homelab runner job in `.github/workflows/ci.yml` gated to trusted repo branches/PRs while keeping the main `ubuntu-24.04` CI job isolated and deterministic
- [ ] Cover prompt/payload construction and response parsing with hermetic unit tests (`uv run pytest`)

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

---

## Backlog (Upcoming, in priority order)

1. **`[10.1]` Aseprite JSON & TexturePacker Atlas Export** — Optional atlas metadata export alongside `manifest.json` + `manifest.d.ts` for third-party game engines (Godot, Phaser, PixiJS, Unity).
2. **`[11.1]` Catalog Scalability (`watch` Incremental Rebuild & Lazy `--indexed-ts`)** — Dependency-tracked incremental recompilation in `pixelforge watch` and optional lazy decoding in generated `--indexed-ts` bundles for larger asset catalogs.
3. **`[12.1]` Structured `pixelforge diff` (`--json` & Anchor/Hitbox Metadata Diff)** — Machine-readable `--json` diff summary plus anchor/hitbox coordinate delta detection against `--base`.
4. **`[13.1]` CI TypeScript Validation (`tsc --noEmit`)** — Add a CI validation step confirming generated `manifest.d.ts` and `--indexed-ts` TypeScript outputs typecheck cleanly under strict `tsc`.

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

_None currently queued (all items promoted to the active cycle above)._
