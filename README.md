# pixelforge

Deterministic Python compositional indexed pixel art compiler (`build123d`-style), CLI/SDK, and multimodal AI agent visual critic loop for producing pixel-perfect PNGs, animated spritesheets, emissive masks, typed Svelte 5 manifests, and indexed `Uint8Array` framebuffer bundles with zero mixels.

**[English](README.md)** | **[Português (Brasil)](README.pt-br.md)**

[![Python >= 3.14](https://img.shields.io/badge/Python-%3E%3D3.14_(uv)-3776AB.svg)](https://www.python.org/)
[![Typing: Pyright Strict](https://img.shields.io/badge/Pyright-Strict-3178C6.svg)](https://github.com/microsoft/pyright)
[![Linter: Ruff](https://img.shields.io/badge/Ruff-Checked-D7FF64.svg)](https://docs.astral.sh/ruff/)
[![Architecture: V2 Python](https://img.shields.io/badge/Architecture-V2_Python-teal.svg)](docs/DESIGN_V2.md)

---

## Overview

`pixelforge` eliminates the structural failure modes of raster image-diffusion pixel art (mixels, blurry alpha halos, cross-asset palette drift, jittery animation frames, and silent PNGs without anchor coordinates) by authoring assets as compositional Python modules (`*.asset.py`) over a `numpy` `uint8` indexed framebuffer.

Core capabilities ([`docs/DESIGN_V2.md`](docs/DESIGN_V2.md)):
- **Compositional `build123d`-Style API & Prefab Kits:** Context managers (`with a.layer(...)`, `with a.plane(...)`) with automatic outlines, selective outlines (`sel_out`), mirroring, affine `(u, v)` projection (`rect`, `grid`, `line`, `dot`, `anchor`), `2:1` isometric primitives (`iso_box`, `iso_tile`), reusable `prefabs` (`architecture`, `furniture`, `details`, and clipped `atmosphere` vistas/weather/cycles/light spill for both `iso-2:1` and `front-2.5d`), and 1px surgical escape hatches (`put`, `erase`, `spr`).
- **Zero-Mixel Indexed Framebuffer:** Integer-coordinate `numpy.ndarray(dtype=np.uint8)` surfaces (`0..254` semantic palette indices, `255` permanently reserved for binary alpha `0`).
- **Semantic Palettes & LUT Swaps:** Named color tokens with material flags (`outline`, `emissive`, `bright`, `shadow`, `metal`, `accent`) and `reflections` tables enabling lossless state/time swaps (`healthy`/`dusty`/`faulty`, `day`/`night`) without redrawing geometry.
- **Headless Millisecond Exports:** Vectorized `numpy` + `Pillow` encoding outputting 1× (or `--scale N`) binary-alpha PNGs, horizontal spritesheets, emissive masks, optional `--lut` textures, `manifest.json` + **`manifest.d.ts`**, and **`--indexed-ts`** RLE/base64 `Uint8Array` bundles for Svelte 5 games.
- **Multimodal Visual Critic Loop:** Generates `.contact.png` diagnostic sheets (1× dark/light strips, zoomed grid with `(x, y)` coordinate rulers, hitbox/anchor overlays, untruncated palette swatches) and animated `.gif` previews (`--animate`) so AI agents inspect rendered pixels and apply exact coordinate-level edits.
- **AST + Runtime Guard Suite:** Static `ast.parse` and runtime checks blocking `random`/`secrets`/`numpy.random`, external raster imports, raw `#rrggbb` literals, I/O/`eval`, out-of-palette pixels, non-binary alpha, and non-deterministic outputs.

## Architecture

```mermaid
flowchart LR
    Spec["Prompt + StylePack (*.style.py)"] --> Agent["AI Agent (create-pixel-asset v2)"]
    Agent --> Asset["Compositional Asset (*.asset.py)"]
    Asset --> Guard["AST + Runtime Guards (pixelforge check)"]
    Asset --> Core["pixelforge.core (numpy uint8, Layer, Plane, Iso, PRNG)"]
    Core --> Sheet["Contact Sheet (.contact.png) + GIF (--animate)"]
    Sheet --> Critic["Visual Critic (Inspects & Issues Coordinate Fixes)"]
    Critic -->|"2-4 Surgical Passes"| Agent
    Core --> Export["pixelforge.export (PNG, Sheet, Emissive, LUT, Indexed-TS, manifest.d.ts)"]
    Export --> Svelte["Svelte 5 Game (Framebuffer / WebGL2 / pixelforge watch)"]
```

Architectural trade-offs are recorded in [`docs/adr/decisions.md`](docs/adr/decisions.md), and full contracts live in [`docs/DESIGN_V2.md`](docs/DESIGN_V2.md).

## Quickstart

### Prerequisites

- Python `>= 3.14`
- [`uv`](https://docs.astral.sh/uv/)

### Local Setup

```bash
cp .env.example .env
uv sync --frozen
uv run pytest
```

### External Repository Consumption

Install `pixelforge` as a standalone CLI tool or add it as a dependency in an external consumer repository (for example, a Svelte 5 game repo), then target that repository with `--root`:

```bash
# Option A: Install globally as an isolated uv tool
uv tool install git+https://github.com/yegear/pixelforge.git
pixelforge init --root /path/to/consumer-repo
pixelforge check --sync-stubs --root /path/to/consumer-repo
pixelforge render --emissive --lut --indexed-ts --root /path/to/consumer-repo

# Option B: Run ephemerally without installing globally
uvx --from git+https://github.com/yegear/pixelforge.git pixelforge render --root /path/to/consumer-repo

# Option C: Add to a consumer repo's pyproject.toml
# uv add --dev "pixelforge @ git+https://github.com/yegear/pixelforge.git"
uv run pixelforge watch --out static/sprites --serve
```

When `--root <path>` is passed, `pixelforge` resolves `styles/`, `assets/`, `.env` (`PIXELFORGE_*` overrides), `dist/`, and `.pixelforge/` relative to `<path>` regardless of the caller's working directory.

## Configuration

Optional environment overrides declared in [`.env.example`](.env.example) (loaded via `pydantic-settings` with the `PIXELFORGE_` prefix):

| Variable | Description | Default | Required |
| :--- | :--- | :--- | :--- |
| `PIXELFORGE_OUT_DIR` | Output directory for exported PNGs, spritesheets, emissive masks, `manifest.json`, `manifest.d.ts`, and `indexed/` | `dist` | No |
| `PIXELFORGE_SHEETS_DIR` | Directory for ephemeral visual-critic `.contact.png` sheets (git-ignored) | `.pixelforge/sheets` | No |
| `PIXELFORGE_PREVIEWS_DIR` | Directory for ephemeral animated `.gif` previews (git-ignored) | `.pixelforge/previews` | No |
| `PIXELFORGE_DIFFS_DIR` | Directory for ephemeral pixel-diff PNGs generated by `pixelforge diff` (git-ignored) | `.pixelforge/diffs` | No |
| `PIXELFORGE_DEFAULT_STYLE` | Optional `StylePack` override for `pixelforge init` (`sweetie-16`) and multi-style commands | _(auto / unset)_ | No |
| `LLM_BASE_URL` | Optional OpenAI v1 gateway endpoint (`hydra-llm-router`) for Phase 3 automated critic mode | `http://127.0.0.1:3000/v1` | No |
| `LLM_API_KEY` | Optional gateway token when Phase 3 automated critic mode is enabled | `sk-replace-with-hydra-tier-token` | Only for Phase 3 automated mode |
| `LLM_MODEL_FAST` | Low-latency virtual model alias on the LLM gateway | `fast` | No |
| `LLM_MODEL_DEEP` | Reasoning virtual model alias on the LLM gateway | `deep` | No |
| `LLM_TIMEOUT_SECONDS` | HTTP timeout in seconds for deep reasoning gateway calls | `180` | No |

## CLI Reference

```bash
# Scaffold starter StylePack, sample .asset.py, and .env.example
uv run pixelforge init [--style sweetie-16] [--force] [--root .]

# Compile .asset.py modules into PNGs, spritesheets, emissive masks, manifests, and diagnostics
uv run pixelforge render [asset_id] [--out dist] [--sheet] [--pack-sheet] [--dir <subdir>] [--pack <style_id>] [--ids <a,b>] [--animate] [--emissive] [--lut] [--normals] [--height] [--indexed-ts] [--indexed-ts-lazy] [--atlas {aseprite,texturepacker,all}] [--scale 1] [--variant <name>] [--format llm|json|human] [--json] [--human] [--root .]

# Execute AST static and runtime guard checks (exit code 0 on pass)
uv run pixelforge check [asset_id] [--strict-orphans] [--format llm|json|human] [--json] [--human] [--root .]

# Generate a side-by-side + magenta pixel-diff PNG against a git ref
uv run pixelforge diff <asset_id> [--base HEAD] [--out .pixelforge/diffs] [--scale 1] [--variant <name>] [--summary-md <path>] [--format llm|json|human] [--json] [--human] [--root .]

# Watch .asset.py and .style.py files and hot-reload compiled outputs (optional --serve Preview Studio)
uv run pixelforge watch [asset_id] [--out dist] [--sheet] [--emissive] [--lut] [--normals] [--height] [--indexed-ts] [--indexed-ts-lazy] [--atlas {aseprite,texturepacker,all}] [--scale 1] [--variant <name>] [--interval 0.5] [--max-cycles N] [--serve] [--host 127.0.0.1] [--port 4173] [--format llm|json|human] [--json] [--human] [--root .]

# Extract an ephemeral aspect ratio, palette histogram, and quantized ASCII sketch from a local reference image
uv run pixelforge analyze-ref <image_path> [--style homelab-16bit] [--size 32x32] [--scaffold [--id ASSET_ID] [--out PATH] [--force]] [--format llm|json|human] [--json] [--human] [--root .]

# Compose child prop assets onto declared parent scene anchors and validate bounds/occlusion
uv run pixelforge compose <parent_id> --mount <prop_id>@<anchor>[:<prop_anchor>] [--state <name>] [--strict-bounds] [--sheet] [--format llm|json|human] [--json] [--human] [--root .]

# Score changed assets and scenes via internal hydra-llm-router multimodal critic (OpenAI v1, virtual model 'fast')
uv run pixelforge critic [asset_id] [--base HEAD] [--threshold 70] [--variant <name>] [--summary-md <path>] [--format llm|json|human] [--json] [--human] [--root .]

# Introspect StylePack token groups, prefab signatures, asset anchors/states, and scene mounts
uv run pixelforge inspect {style|presets|prefabs|api|assets|scenes} [target] [--format llm|json|human] [--json] [--human] [--root .]

# Probe exact token-mapped ASCII slices, layer bboxes, token histograms, and orphan-pixel coordinates
uv run pixelforge probe <asset_id> [--region x,y,w,h] [--state <name>] [--frame 0] [--layers] [--format llm|json|human] [--json] [--human] [--root .]

# Scaffold zero-reference typed assets, scenes, or styles (with automatic palette stub sync)
uv run pixelforge new {asset|scene|style} <name> [--kind iso-prop|front-prop|character|tile-blob47|9slice|font] [--parent <asset_id>] [--from-preset <preset_id>] [--style <id>] [--out PATH] [--force] [--format llm|json|human] [--root .]
```

## Svelte 5 Integration

- **Standard PNG + WebGL2 Workflow:** Run `pixelforge render --emissive --lut` (or `pixelforge watch --out ../my-svelte-game/static/sprites`) to emit `manifest.json` and `manifest.d.ts` with strict TypeScript types for sprite IDs, state names, frame counts, FPS, anchors, and hitboxes.
- **CPU Indexed Framebuffer Workflow (`--indexed-ts`):** Pass `--indexed-ts` to emit `dist/indexed/palette.generated.ts` (`PALETTE_HEX`, `EMISSIVE`, `BRIGHT`, `REFL`), `dist/indexed/sprites.generated.ts` (RLE/base64 `Uint8Array` index buffers with `255 = transparent`), and `dist/indexed/manifest.generated.ts` for direct `Framebuffer.blit()` composition. Filtered `render <asset_id> --indexed-ts` and `watch <asset_id> --indexed-ts` still compile all sibling assets belonging to the affected `StylePack` into `dist/indexed/` so partial runs never truncate the TypeScript bundle.

## Development

### Project Structure

```text
├── .agent/
│   ├── TASK.md                    # Active task checklist and roadmap
│   ├── NOTES.md                   # Active module/CLI contracts and gotchas
│   ├── INVARIANTS.md              # Rendering and interface verification guardrails
│   ├── ARCHIVE.md                 # Archived task cycles
│   └── skills/create-pixel-asset/ # Hermetic asset authoring & critic skill
├── docs/
│   ├── DESIGN_V2.md               # Canonical v2 Python specification & contracts
│   └── adr/decisions.md           # Architectural Decisions Log (ADR diary)
├── src/pixelforge/
│   ├── core/                      # IndexedSurface, StylePack, PRNG, Iso, Plane, Asset/Layer, Prefabs (architecture/furniture/details/atmosphere)
│   ├── export/                    # PNG/GIF, bundle, svelte_types, indexed_ts, contact_sheet, diff
│   ├── guard/                     # AST static rules, runtime rules, runner
│   └── cli/                       # Thin CLI entrypoint and pydantic-settings config
├── tests/                         # Hermetic pytest suites (core, export, guard, cli)
├── .env.example                   # Environment variable template
├── pyproject.toml                 # uv, ruff, pyright strict, pytest configuration
└── AGENTS.md                      # Engineering constitution and agent rules
```

### Validation Commands

All checks below must exit with code `0` before marking any task complete:

```bash
uv sync --frozen
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest
git diff --check
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
