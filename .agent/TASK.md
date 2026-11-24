# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log`. User requests during conversation
> take precedence — report discrepancies before acting.

---

## Active Task

### [00.1] Project Bootstrap & Toolchain Setup

Objective: initialize the Node.js 26 LTS / TypeScript strict / `pnpm` / Vitest / linter toolchain and CLI skeleton so all canonical validation commands (`pnpm test`, `pnpm typecheck`, `pnpm lint`, `pnpm build`) exit with code 0.

- [ ] Propose consultative dependency choices (PNG encoder, lint/format choice: ESLint+Prettier vs Biome, CLI arg parsing) and await human approval before installing packages
- [ ] Initialize `package.json`, `tsconfig.json` (`strict: true`, Node ESM), Vitest config, and linter/formatter config
- [ ] Scaffold minimal `src/` directory layout (`core/`, `export/`, `guard/`, `cli/`, `index.ts`) with a passing smoke test
- [ ] Verify `pnpm typecheck && pnpm lint && pnpm test && pnpm build && git diff --check` exit with code 0

---

## Completed Tasks Log

| Task | Title | Commit(s) | Date |
|---|---|---|---|
| `[00.0]` | Initial greenfield scaffolding, MVP design spec & ADRs | `initial` | 2026-11-24 |

---

## Backlog (Upcoming, in priority order)

- `[01.1]` Core indexed framebuffer engine (`IndexedSurface`, `StylePack`/semantic palette, seeded PRNG, 2D & isometric 2:1 primitives, `autoOutline`, `edgeMask`, anchors/hitboxes)
- `[01.2]` Headless exporter (`png`, horizontal spritesheet, emissive mask, `manifest.json`, and 4×/8× coordinate-ruled `.contact.png` generator)
- `[02.1]` Static + runtime guard suite (`no-math-random`, `closed-palette`, `binary-alpha`, `bit-determinism`) and `pixelforge` CLI (`init`, `render`, `check`, `diff`)
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
