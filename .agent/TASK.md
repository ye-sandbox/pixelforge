# TASK.md — Current Task and Roadmap

> WHAT to do now. Detailed history lives in `git log` and `.agent/ARCHIVE.md`.
> User requests during conversation take precedence — report discrepancies before acting.
> Full V2 specification: [`docs/DESIGN_V2.md`](../docs/DESIGN_V2.md).

---

## Active Task

### `[23.1]` Living & Workstation Furniture Prefab Expansion (`prefabs.furniture`)
- [ ] `iso_l_desk` (corner L-shaped desk returning `IsoDeskSlots`), `iso_nightstand` / `iso_side_table`, `iso_sofa` / `iso_armchair`, `iso_coffee_table`, `iso_wardrobe` / `iso_locker`, and `iso_mini_fridge` / `iso_filing_cabinet`.
- [ ] Unit tests in `tests/test_prefabs.py` and `pixelforge check --strict-orphans` + `pyright` + `ruff` validation.

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
| `[09.1]` | Automated Multimodal Critic in CI (`hydra-llm-router` + `httpx2`, `self-hosted`, `pixelforge critic`) | `11cf32e` | 2026-11-25 |
| `[10.1]` | Aseprite JSON & TexturePacker Atlas Export (`pixelforge.export.atlas`, `--atlas {aseprite,texturepacker,all}`) | `c148fba` | 2026-11-25 |
| `[11.1]` | Catalog Scalability (`watch` Incremental Rebuild & Lazy `--indexed-ts`) | `fd9a338` | 2026-11-25 |
| `[12.1]` | Structured `pixelforge diff` (`--json` & Anchor/Hitbox Metadata Diff) | `1690b36` | 2026-11-25 |
| `[13.1]` | CI TypeScript Validation (`tsc --noEmit` for `manifest.d.ts` & `--indexed-ts`) | `6f5929f` | 2026-11-25 |
| `[14.1]` | Environment & Detail Prefab Kits (`src/pixelforge/core/prefabs/`) | `0a7f4fb` | 2026-11-25 |
| `[15.1]` | Reusable Micro-Props Library (`assets/props/*.asset.py`) & Scene Composition Pack | `c426ed1` | 2026-11-25 |
| `[16.1]` | Rich Atmospheric Prefabs, Clipped Window Scenes & Authoring Instructions | `3070848` | 2026-11-25 |
| `[17.1]` | Spatial Room Context (`IsoRoomGeometry`) & Furniture Surface Slots (`IsoDeskSlots`, `IsoRackSlots`, `IsoShelfSlots`) | `14a85f5` | 2026-11-25 |
| `[18.1]` | Local Lighting, Cast Shadows & Internal Atmospheric Prefabs (`point_light_spill`, `cast_shadow`, `floor_reflection`, `dust_motes`, `rising_steam`, `weather_lightning`, `window_condensation`, `screen_telemetry`, `horizon_silhouette` modes) | `fcb7b4e` | 2026-11-25 |
| `[19.1]` | Room Fill & Architectural Prefab Expansion (`iso_door`, `front_door`, `iso_raised_floor`, `iso_rug`, `iso_cable_tray`, `window_blinds`, `window_curtains`, `iso_chair`, `iso_wall_shelf`, `iso_bed`, `iso_workbench`, `iso_drawer_unit`, `wall_ac_unit`, `wall_whiteboard`, `power_strip`, `wall_outlet`, `iso_cable_catenary`) | `4fc633f` | 2026-11-25 |
| `[20.1]` | Declarative & Animated Multi-Frame Scene Composition (`compose_scene` v2: `*.scene.py`, `render`/`watch`/`check`/`manifest`/`--indexed-ts`, `iso_y` depth sorting, `frame % prop.frames` sync, `--animate` GIF) | `ae230b0` | 2026-11-25 |
| `[21.1]` | Multi-Zone Floor & Interior Partition Prefabs (`IsoRoomGeometry.subroom`, `partition_plane`, `floor_plane`, `iso_floor_zone`, `iso_floor_threshold`, `iso_partition_wall`, `iso_glass_partition`, `iso_pillar`, `wall_molding`) | `dc3d014` | 2026-11-26 |
| `[22.1]` | Modular Partition Props & Multi-Room `compose_scene` Showcase (`partition_wall_iso`, `glass_partition_iso`, `pillar_iso`, `multiroom_homelab_iso`, `multiroom_homelab_scene`) | `dbdef25` | 2026-11-26 |

---

## Backlog (Upcoming, in priority order)

1. **`[24.1]` Wall Decor, Emissive Accents & Shelf/Corner Micro-Props (`prefabs.details` + `assets/props/`)**
   - `prefabs.details`: `wall_light_switch` / `wall_thermostat`, `wall_clock`, `wall_corkboard`, `wall_pegboard`, `wall_neon_sign` / `led_strip` (`emissive` tokens), and `wall_sconce`.
   - `assets/props/`: shelf/desk props (`books_stack_iso`, `desk_speaker_iso`, `headphones_stand_iso`, `router_iso`, `soda_can_iso`) and floor/corner props (`tall_plant_iso`, `floor_lamp_iso`, `trash_bin_iso`, `ups_battery_iso`, `air_purifier_iso`) with `mount_bottom` anchors and guard/unit tests.

---

## Release / Cycle Wrap-up (Not the next task)

Release/tag only with explicit human request. When triggered, the ID is `[99.1]`. Do not number feature, hygiene, or CI tasks as `99.x`. Do not calculate next task ID from this section.

---

## Future Backlog / Ideas (Unprioritized)

_None currently queued (all items promoted to the active cycle above)._
