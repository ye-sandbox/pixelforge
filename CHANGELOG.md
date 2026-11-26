# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-11-26

### Added
- LLM-first CLI output (`--format llm|json|human`, default `llm`), `pixelforge inspect` (`style`, `prefabs`, `assets`, `scenes`), and fuzzy lookup diagnostics.
- Typed `StylePack` palette `Protocol` stubs (`styles/*_palette.py`, `pixelforge check --sync-stubs`) and advisory emissive-bleed / coverage diagnostics.
- Modular character avatar primitives and animation cycles, UI pixel primitives with `nine_slice` export metadata, deterministic 16/47-tile autotile generators (Godot, Tiled, Phaser, Svelte), and deterministic bitmap fonts (`pixelforge.core.font`) with glyph atlas compilation.
- Second reference `topdown-rpg` `StylePack` with sample assets, zero-dependency Preview Studio (`pixelforge watch --serve`), and scoped `--root` `.env` settings for external repositories.
- Deterministic scene ergonomics guards in `pixelforge check`, scene-aware `pixelforge critic`, enriched `diff` metrics with PR summary mode, `analyze-ref --scaffold`, and multi-scene portal graph validation (`ScenePortalSpec`).
- Derived gameplay semantics (`collision_grid`, `walkable_mask`, `y_sort_pivot`, `interact_zones`), 2D normal/height maps (`--normals` / `--height`), and typed per-frame events / audio cues (`frameMetadata.events`).

### Changed
- Decomposed dense scene, prefab details, builder, and watch modules into focused subpackages.

## [0.3.0] - 2026-11-26

### Added
- Declarative and animated multi-frame scene composition (`compose_scene`, `generate_scene_sheet`, `*.scene.py`, `pixelforge compose`) with `iso_y` depth sorting, frame synchronization, perspective mismatch warnings, and `--animate` GIF support.
- Isometric prefab kits under `pixelforge.core.prefabs` covering `IsoRoomGeometry` & surface slots, multi-zone floors & interior partitions, living & workstation furniture, wall decor, local lighting, cast shadows, reflections, and atmospheric window/weather effects.
- Reusable `iso-2:1` micro-props library (`assets/props/*.asset.py`), ergonomic workstation props, modular partition props, and `multiroom_homelab_scene` showcase.
- Aseprite JSON and TexturePacker atlas export (`pixelforge.export.atlas`, `--atlas {aseprite,texturepacker,all}`).
- Automated multimodal visual critic (`pixelforge critic`) via `hydra-llm-router` and `httpx2`, plus self-hosted CI critic job and `tsc --noEmit` TypeScript validation for generated manifests.
- Incremental `watch` dependency graph, lazy `--indexed-ts` decoding, typed anchor/hitbox metadata, and structured `pixelforge diff --json` output with anchor/hitbox deltas.

### Changed
- Modularized `pixelforge.cli.workflow` by subcommand domain, decomposed `guard.runner.run_checks` and `export.scene`, and subdivided prefab modules and tests into focused packages.

## [0.2.0] - 2026-11-25

### Added
- Deterministic Python compositional indexed pixel art compiler (`Asset`, `Layer`, `Plane`, `Iso`) backed by `numpy` `uint8` framebuffers and seeded PRNG (`pixelforge.core`).
- Headless exporter for PNGs, animated GIFs, multi-scale contact sheets with emissive-only previews, Svelte 5 `manifest.json` / `manifest.d.ts`, and `--indexed-ts` modules (`pixelforge.export`).
- AST static and runtime guard suite enforcing palette closure, determinism, and surface invariants (`pixelforge.guard`).
- `pixelforge` CLI with `init`, `render`, `check`, `diff` (with historical `StylePack` resolution), `watch`, and `analyze-ref` subcommands (`pixelforge.cli`).
- Canonical `homelab-16bit` 64-color style pack and 7 pilot assets under `styles/` and `assets/`.
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) and Apache-2.0 `LICENSE`.
