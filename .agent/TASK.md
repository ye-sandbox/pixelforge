# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log`. User requests during conversation
> take precedence — report discrepancies before acting.

---

## Active Task

### [04.2] Typed Palette Lookup Helper (`createPaletteLookup`)

Objective: eliminate per-asset palette lookup boilerplate by exporting a typed `createPaletteLookup(ctx)` helper from `src/core/`.

- [ ] Export a typed `createPaletteLookup(ctx)` (or `paletteMap(ctx)`) helper from `src/core/` (`src/index.ts`) that resolves `StylePack` token names to `PaletteIndex` with explicit missing-token errors
- [ ] Update `.agent/skills/create-pixel-asset/SKILL.md` and `src/cli/main.ts` (`init` template) to use the shared helper, eliminating ~25 lines of boilerplate per asset
- [ ] Add unit tests in `tests/core/` and verify `pnpm typecheck && pnpm test && pnpm lint && pnpm build` exit 0

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
