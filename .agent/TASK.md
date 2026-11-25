# TASK.md — Current Task and Roadmap (`v2-py`)

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[03.2]` Hermetic Agent Skill (`create-pixel-asset` v2) & Docs Sync
Objective: rewrite `.agent/skills/create-pixel-asset/SKILL.md` for Python `build123d`-style authoring and synchronize `README.md` and `README.pt-br.md` to v2.
- [ ] Update `.agent/skills/create-pixel-asset/SKILL.md` with compositional `with a.layer` / `with a.plane` workflow, AST guards, GIF/contact-sheet critique protocol, and canonical `.asset.py` examples
- [ ] Synchronize `README.md` and `README.pt-br.md` (zero heading emojis, Mermaid diagrams, real CLI flags, Svelte 5 `manifest.d.ts` + `--indexed-ts` integration, and `uv` validation commands)

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

---

## Backlog (Upcoming, in priority order)

### `[04.1]` Pilot Pack Port & Benchmark Validation (`homelab-16bit` 64-Color Canonical Pack + ThinkPad)
Objective: author the canonical 64-color `homelab-16bit` `StylePack` aligned with `idle-datacenter` (`emissive`, `bright`, `reflections`, fixing `WINDOW_SKY` emissive separation) and port pilot assets (`old_laptop`, `used_gpu_rig`, `ai_cluster_node`, `bedroom_desk_iso`, `thinkpad_r51_iso`, `thinkpad_r51_front`) to `.asset.py`, validating `< 40 ms` renders, zero guard violations, clean 1× visuals, Svelte `manifest.d.ts`, and `--indexed-ts` framebuffer export.
- [ ] Author `styles/homelab_16bit.style.py` aligned with `idle-datacenter`'s 64-color palette (`VOID..GLASS_L`, `emissive`, `bright`, `reflections`), keeping non-emissive accent tokens distinct from emissive glow tokens
- [ ] Port all 4 `homelab/` assets and ThinkPad showcase assets using `with a.layer` / `with a.plane` / `dither` / `iso_box`
- [ ] Run Visual Critic Loop on `.contact.png` + animated `.gif` previews (fix any orphan pixels or outline defects)
- [ ] Add `tests/test_homelab_pilot.py` asserting all guards pass, render time budget holds, and both `manifest.d.ts` and `--indexed-ts` outputs match expected contracts

### `[05.1]` Reference Proportion & Quantized Sketch Analyzer (`pixelforge analyze-ref`)
Objective: add an optional, strictly ephemeral CLI helper that extracts aspect ratio and a low-resolution palette-quantized ASCII sketch from a local reference image to guide agent planning without ever importing external rasters into assets.
- [ ] Implement `analyze_reference_image(path, style, size)` outputting aspect ratio, dominant palette token histogram, and quantized ASCII draft
- [ ] Wire `pixelforge analyze-ref` CLI command with explicit guardrails ensuring outputs stay ephemeral
- [ ] Add hermetic tests using programmatically generated in-memory PNG fixtures

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

- Automated multimodal critic scoring via OpenAI v1 gateway (`hydra-llm-router`, using `httpx2`) for batch CI visual regressions
- Optional Aseprite JSON / TexturePacker atlas export format alongside `manifest.json` + `manifest.d.ts`
- Scene-composition helper allowing room assets (`bedroom_desk_iso`) to preview/validate child prop assets placed on declared anchors
