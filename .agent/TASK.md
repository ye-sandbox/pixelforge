# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log`. User requests during conversation
> take precedence — report discrepancies before acting.

---

## Active Task

### [02.1] Guard Suite & `pixelforge` CLI

Objective: implement static and runtime guard rules (`no-math-random`, `no-external-assets`, `no-raw-hex`, `closed-palette`, `exact-dimensions`, `binary-alpha`, `bit-determinism`, `valid-anchors`) and wire the `pixelforge` CLI (`init`, `render`, `check`, `diff`).

- [ ] Implement static source and runtime guard rules (`src/guard/rules.ts`)
- [ ] Implement guard runner and structured `file:line [rule] detail` reporter (`src/guard/runner.ts`)
- [ ] Implement pixel-diff PNG generator (`src/export/diff.ts`) and wire `pixelforge` CLI commands (`init`, `render`, `check`, `diff`) in `src/cli/main.ts`
- [ ] Add hermetic unit tests for guard violations, CLI exit codes, and pixel-diff output (`pnpm test` exits 0)

---

## Completed Tasks Log

| Task | Title | Commit(s) | Date |
|---|---|---|---|
| `[00.0]` | Initial greenfield scaffolding, MVP design spec & ADRs | `initial` | 2026-11-24 |
| `[00.1]` | Project Bootstrap & Toolchain Setup (`fast-png`, Biome, Vitest, TS strict, CLI skeleton) | `a07b3fe` | 2026-11-24 |
| `[01.1]` | Core Indexed Framebuffer Engine (`IndexedSurface`, `StylePack`, PRNG, `isoBox`/`isoTile`) | `c729089` | 2026-11-24 |
| `[01.2]` | Headless Exporter & Coordinate-Ruled Contact Sheet (`fast-png`, bundle, manifest, `.contact.png`) | `5934755` | 2026-11-24 |

---

## Backlog (Upcoming, in priority order)

- `[02.2]` Hermetic agent skill `.agent/skills/create-pixel-asset/SKILL.md` codifying the planning + multimodal Visual Critic Loop protocol
- `[03.1]` Pilot validation benchmark (`homelab-16bit` StylePack + `old_laptop`, `used_gpu_rig`, `ai_cluster_node`, and `bedroom_desk_iso` 320×200 scene)

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

- Phase 2: Interactive Web Studio (Svelte 5 + Tailwind v4 + WebGL2 bloom/CRT preview with live `.asset.ts` hot-reload and coordinate hover inspector)
- Phase 2: Animated GIF / APNG preview export alongside horizontal PNG spritesheets
- Phase 3: Optional automated multimodal critic scoring via `hydra-llm-router` OpenAI v1 gateway for CI regressions
