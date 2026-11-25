# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-11-25

### Added
- Deterministic Python compositional indexed pixel art compiler (`Asset`, `Layer`, `Plane`, `Iso`) backed by `numpy` `uint8` framebuffers and seeded PRNG (`pixelforge.core`).
- Headless exporter for PNGs, animated GIFs, multi-scale contact sheets with emissive-only previews, Svelte 5 `manifest.json` / `manifest.d.ts`, and `--indexed-ts` modules (`pixelforge.export`).
- AST static and runtime guard suite enforcing palette closure, determinism, and surface invariants (`pixelforge.guard`).
- `pixelforge` CLI with `init`, `render`, `check`, `diff` (with historical `StylePack` resolution), `watch`, and `analyze-ref` subcommands (`pixelforge.cli`).
- Canonical `homelab-16bit` 64-color style pack and 7 pilot assets under `styles/` and `assets/`.
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) and Apache-2.0 `LICENSE`.
