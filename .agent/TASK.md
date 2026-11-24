# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log`. User requests during conversation
> take precedence — report discrepancies before acting.

---

## Active Task

### [02.2] Hermetic Agent Skill (`create-pixel-asset`)

Objective: author `.agent/skills/create-pixel-asset/SKILL.md` codifying the planning, authoring, guard-check, and multimodal Visual Critic Loop protocol.

- [ ] Define silhouette, layering, and anchor planning checklist
- [ ] Document `pixelforge check` and `pixelforge render --sheet` iteration loop (2–4 surgical passes)
- [ ] Verify skill completeness against `docs/DESIGN_MVP.md` and `AGENTS.md`

---

## Completed Tasks Log

| Task | Title | Commit(s) | Date |
|---|---|---|---|
| `[00.0]` | Initial greenfield scaffolding, MVP design spec & ADRs | `initial` | 2026-11-24 |
| `[00.1]` | Project Bootstrap & Toolchain Setup (`fast-png`, Biome, Vitest, TS strict, CLI skeleton) | `a07b3fe` | 2026-11-24 |
| `[01.1]` | Core Indexed Framebuffer Engine (`IndexedSurface`, `StylePack`, PRNG, `isoBox`/`isoTile`) | `c729089` | 2026-11-24 |
| `[01.2]` | Headless Exporter & Coordinate-Ruled Contact Sheet (`fast-png`, bundle, manifest, `.contact.png`) | `5934755` | 2026-11-24 |
| `[02.1]` | Guard Suite & `pixelforge` CLI (`rules`, `runner`, `diff`, `init`/`render`/`check`/`diff`) | `3ea44d0` | 2026-11-24 |

---

## Backlog (Upcoming, in priority order)

- `[03.1]` Pilot validation benchmark (`homelab-16bit` StylePack + `old_laptop`, `used_gpu_rig`, `ai_cluster_node`, and `bedroom_desk_iso` 320×200 scene)

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

- Phase 2: Interactive Web Studio (Svelte 5 + Tailwind v4 + WebGL2 bloom/CRT preview with live `.asset.ts` hot-reload and coordinate hover inspector)
- Phase 2: Animated GIF / APNG preview export alongside horizontal PNG spritesheets
- Phase 3: Optional automated multimodal critic scoring via `hydra-llm-router` OpenAI v1 gateway for CI regressions
