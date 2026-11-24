# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log`. User requests during conversation
> take precedence — report discrepancies before acting.

---

## Active Task

*(No active task — backlog is empty. See Future Backlog below or queue a new task.)*

---

## Completed Tasks Log

| Task | Title | Commit(s) | Date |
|---|---|---|---|
| `[00.0]` | Initial greenfield scaffolding, MVP design spec & ADRs | `initial` | 2026-11-24 |
| `[00.1]` | Project Bootstrap & Toolchain Setup (`fast-png`, Biome, Vitest, TS strict, CLI skeleton) | `a07b3fe` | 2026-11-24 |
| `[01.1]` | Core Indexed Framebuffer Engine (`IndexedSurface`, `StylePack`, PRNG, `isoBox`/`isoTile`) | `c729089` | 2026-11-24 |
| `[01.2]` | Headless Exporter & Coordinate-Ruled Contact Sheet (`fast-png`, bundle, manifest, `.contact.png`) | `5934755` | 2026-11-24 |
| `[02.1]` | Guard Suite & `pixelforge` CLI (`rules`, `runner`, `diff`, `init`/`render`/`check`/`diff`) | `3ea44d0` | 2026-11-24 |
| `[02.2]` | Hermetic Agent Skill (`create-pixel-asset` planning, guards, Visual Critic Loop) | `061be36` | 2026-11-24 |
| `[03.1]` | Pilot Validation Benchmark (`homelab-16bit` StylePack + 4 pilot assets) | `4660738` | 2026-11-24 |
| `[04.1]` | Tilted-Plane & Quadrilateral Primitives (`quad` / `planeProject`) | `5dced5a` | 2026-11-24 |
| `[04.2]` | Typed Palette Lookup Helper (`createPaletteLookup`) | `2889e3e` | 2026-11-24 |

---

## Backlog (Upcoming, in priority order)

*(No queued tasks — see Future Backlog below)*

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

- Phase 2: Interactive Web Studio (Svelte 5 + Tailwind v4 + WebGL2 bloom/CRT preview with live `.asset.ts` hot-reload and coordinate hover inspector)
- Phase 2: Animated GIF / APNG preview export alongside horizontal PNG spritesheets
- Phase 3: Optional automated multimodal critic scoring via `hydra-llm-router` OpenAI v1 gateway for CI regressions
