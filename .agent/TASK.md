# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log`. User requests during conversation
> take precedence — report discrepancies before acting.

---

## Active Task

### [01.1] Core Indexed Framebuffer Engine

Objective: implement the deterministic `Uint8Array` `IndexedSurface`, `StylePack`/semantic palette types, seeded PRNG, 2D & isometric 2:1 primitives, `autoOutline`, `edgeMask`, and anchors/hitboxes metadata emitter.

- [ ] Define `StylePack`, `PaletteEntry`, `PerspectiveMode`, `Anchor`, and `Hitbox` contracts in `src/core/types.ts`
- [ ] Implement seeded deterministic PRNG (`mulberry32` / `xorshift32`) in `src/core/prng.ts`
- [ ] Implement `IndexedSurface` (`Uint8Array` buffer, `TRANSPARENT_INDEX = 255`, integer truncation/clamping, `put`, `get`, `rect`, `line`, `circle`, `fill`, `spr`, `blitLayer`, `autoOutline`, `edgeMask`) in `src/core/surface.ts`
- [ ] Implement isometric 2:1 projection helpers (`isoProject`, `isoBox`, `isoTile`) in `src/core/iso.ts`
- [ ] Add comprehensive unit tests for determinism, clipping, binary alpha sentinel (`255`), and isometric primitives (`pnpm test` exits 0)

---

## Completed Tasks Log

| Task | Title | Commit(s) | Date |
|---|---|---|---|
| `[00.0]` | Initial greenfield scaffolding, MVP design spec & ADRs | `initial` | 2026-11-24 |
| `[00.1]` | Project Bootstrap & Toolchain Setup (`fast-png`, Biome, Vitest, TS strict, CLI skeleton) | `a07b3fe` | 2026-11-24 |

---

## Backlog (Upcoming, in priority order)

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
