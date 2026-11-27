---
name: create-pixel-asset
description: Author, guard-check, and visually refine deterministic code-drawn indexed pixel art modules (assets/**/*.asset.py) using the pixelforge core engine and multimodal Visual Critic Loop.
---

# Create Pixel Asset (`pixelforge` v2)

## 1. Core Invariants

`pixelforge` compiles deterministic Python pixel art modules (`assets/**/*.asset.py`) targeting a `numpy` `uint8` indexed framebuffer (`IndexedSurface`) and a closed semantic `StylePack` (`styles/*.style.py`).

- **Zero Mixels:** All pixels are authored on an integer grid inside a fixed `height x width` `numpy.ndarray(dtype=np.uint8)` buffer.
- **Binary Alpha:** Index `255` (`TRANSPARENT_INDEX`) maps strictly to alpha `0`; indices `0..254` map strictly to alpha `255`.
- **Closed Semantic Palette:** Drawing uses named `StylePack` palette tokens (`P = a.pal`) only—raw `#rrggbb` strings are banned in `assets/**`.
- **Emissive Token Separation:** Never reuse an `emissive`-flagged token (such as `SOLAR_L`, `LED_C`, `VISOR_C`) for non-glowing painted surfaces (such as `WINDOW_SKY`), or they will bleed into WebGL2 bloom masks.
- **Bit-for-Bit Determinism:** Identical `(state, frame, seed)` inputs produce identical SHA-256 pixel digests (`a.rng()` / `a.hashf()` / `mulberry32` only; `random`, `secrets`, `numpy.random`, `time`, and `datetime` are banned).
- **Code-Coupled Metadata:** `a.anchor()` / `plane.anchor()` and `a.hitbox()` are emitted in the same `render(a)` pass that draws the pixels.
- **Silhouette-First & Surgical Critique:** Block out `1×` readable massing before adding surface detail, then refine via coordinate-ruled `.contact.png` sheets over 2–4 surgical passes.

---

## 2. Progressive Disclosure References

Load these references on demand when the task involves them:

- **Prefab Kits & Window Recipes:** [references/prefabs.md](references/prefabs.md) — Complete `architecture`, `furniture`, `details`, and `atmosphere` prefab kits + clipped window recipes.
- **Declarative Scenes & Spatial Ergonomics:** [references/scenes.md](references/scenes.md) — `*.scene.py` (`SceneSpec` / `SceneMountSpec`), `pixelforge compose`, and room ergonomics.
- **Multimodal Visual Critic & `critic` CLI:** [references/critic.md](references/critic.md) — Manual 5-criteria contact-sheet loop and automated `pixelforge critic` scoring.
- **Blind Visual Critic Subagent:** [../blind-critic/SKILL.md](../blind-critic/SKILL.md) — Read-only unbiased review protocol on compiled `.contact.png` / `.gif` / `.diff.png` without source-code leakage.

---

## 3. Mandatory 2-Phase Blockout-First Authoring Protocol

Never jump straight to 1px surface greebles, dithering, or emissives. Author every new or substantially refactored asset in two explicit passes:

### Phase 1 — Silhouette & Blockout Pass
1. **Introspect First:** Run `uv run pixelforge inspect style <style_id>` (check `paint`, `emissive`, `bright`, `ramps`) and `uv run pixelforge inspect prefabs`.
2. **Optional Reference Proportions:** If working from a reference image, run `uv run pixelforge analyze-ref <image_path> --style <style_id> --size <WxH> --trim --emit-spr` (never store reference images inside `assets/` or `styles/`).
3. **Massing Only:** Define `SPEC: AssetSpec` and draw ONLY primary silhouettes (`with a.layer(..., outline=P.INK):` wrapping `iso_box`, `Plane`, `ellipse`, `capsule`, `polygon`, or `spr`) using flat midtone fills + ground contact shadow + `a.anchor()` / `a.hitbox()`.
4. **Verify 1× Readability Gate:**
   ```bash
   uv run pixelforge check <asset_id> && uv run pixelforge render <asset_id> --sheet --emissive
   ```
   Inspect `.pixelforge/sheets/<asset_id>.contact.png` at native `1×` on both dark (`#0d1117`) and light (`#e6edf3`) checkerboards. Confirm the silhouette is immediately recognizable and anchors/hitboxes land cleanly before proceeding.

### Phase 2 — Volume, Texture, State & Polish Pass
1. **Directional Volume & Alpha-Lock:** Shade inside existing silhouettes using `with a.layer(..., clip="opaque"):`, `a.shade_ramp(...)`, `a.bevel_rect(...)`, or `a.edge_mask(...)` aligned to `style.lighting_angle` (typically `top-left` lit, `bottom-right` shaded).
2. **Surface Detail & States:** Add structural recesses, `dither()`, `a.scatter(..., mask="opaque")`, state-specific overlays, and clean frame-to-frame animation deltas (avoiding no-op frames). Keep `emissive` tokens strictly isolated to glowing emitters.
3. **Cluster Cleanliness & Surgical Polish:** Run `a.cleanup_jaggies()` on organic outlines if needed, and apply 1px surgical `a.put()` / `a.erase()` fixes anchored to exact `(x, y)` coordinates from the 4px contact-sheet ruler.
4. **Craft & Visual Gate:**
   ```bash
   uv run pixelforge check <asset_id> --strict-craft && uv run pixelforge render <asset_id> --sheet --animate --emissive
   ```

---

## 4. Hybrid `spr()` vs `Plane` / `iso_box` / Organic Primitives

Choose the right drawing primitive per structural role—hybrid combinations are encouraged:

| Primitive Family | Best For | Why |
|---|---|---|
| **`Plane` (`with a.plane(...)`) / `iso_box` / `iso_tile`** | Isometric `iso-2:1` & `top-down` architecture, racks, desks, crates, monitors, beveled panels | Automatic affine projection, normalized `(u, v)` coordinates, `extrude_y`, `bevel`, and `plane.anchor()`. |
| **`spr(grid, x, y, color_map)`** | Micro-details, runes, faces, foliage clusters, icons, `--emit-spr` reference stamps | Exact pixel-by-pixel cluster control where geometric primitives look blocky. |
| **Organic Primitives (`ellipse`, `capsule`, `polygon`, `bezier`, `arc`) + `clip="opaque"`** | Characters, creatures, rounded vessels, cables, curved silhouettes, directional volume | Clean integer-grid curves + alpha-locked shading (`shade_ramp`) without spilling past outlines. |
| **Hybrid Pattern** | Hero props & scenes | Build structural hull with `iso_box`/`Plane`, shade with `clip="opaque"`, then stamp crisp emblems/faces/screens with `a.spr()`. |

---

## 5. Archetype Few-Shot Recipes

### Recipe A — Character / Creature (`character`)
Use organic massing (`ellipse`/`capsule`), `clip="opaque"` volume shading, squash/bob frame deltas, and `foot`/`core` anchors:

```python
from pixelforge import Asset, AssetSpec

SPEC = AssetSpec(
    id="pocket_slime",
    style_id="retro-pocket-4",
    width=24,
    height=24,
    perspective="top-down",
    states=("idle", "bounce"),
    frames=2,
    fps=4,
    seed=402,
)


def render(a: Asset) -> None:
    p = a.pal
    squish = a.state == "bounce" and a.frame == 1
    rx, ry, cy = (8, 5, 14) if squish else (7, 6, 13)

    a.ellipse(12, 18, 7, 3, p.INK)  # ground contact shadow
    with a.layer("slime", outline=p.INK):
        a.ellipse(12, cy, rx, ry, p.SHADE_D)
        with a.layer("highlight", clip="opaque"):
            a.ellipse(11, cy - 1, rx - 1, ry - 1, p.SHADE_L)
            a.rect(8, cy - 4, 3, 2, p.HIGHLIGHT)
        a.rect(9, cy, 2, 2, p.INK)
        a.rect(14, cy, 2, 2, p.INK)

    a.anchor("foot", 12, 19, kind="ground")
    a.anchor("core", 12, cy, kind="center")
    a.hitbox("body", 4, 7, 16, 14)
```

### Recipe B — Isometric Prop (`iso_prop`)
Use `iso_box` / `Plane` for `iso-2:1` geometry, keep `emissive` LEDs isolated, and emit `mount_bottom` / `foot` anchors:

```python
from pixelforge import Asset, AssetSpec

SPEC = AssetSpec(
    id="mini_node",
    style_id="homelab-16bit",
    width=32,
    height=32,
    perspective="iso-2:1",
    states=("healthy", "dusty", "faulty"),
    frames=2,
    fps=2,
    seed=101,
)


def render(a: Asset) -> None:
    p = a.pal
    with a.layer("chassis", outline=p.INK):
        a.iso_box(
            16, 28, 12, 12, 10, top=p.METAL_L, left=p.METAL_M, right=p.METAL_D, anchor="bottom"
        )
    with a.layer("front_panel"), a.plane(p0=(6, 16), p1=(16, 21), p2=(6, 24)) as face:
        face.rect(0.12, 0.2, 0.76, 0.45, fill=p.VOID)
        face.grid(0.16, 0.28, 0.52, 0.3, cols=4, rows=1, color=p.METAL_D)
        led = p.LED_R if a.state == "faulty" else p.LED_G if a.frame == 0 else p.VOID
        face.dot(0.80, 0.42, led)

    if a.state == "dusty":
        a.scatter(count=8, colors=(p.DUST_L, p.DUST_D), mask="opaque")

    a.anchor("foot", 16, 28, kind="ground")
    a.hitbox("body", 4, 8, 24, 21)
```

### Recipe C — Hybrid `Plane`/`bevel_rect` + `spr()` Prop (`iso_prop` / `top-down`)
Combine beveled geometric massing with `spr()` ASCII pixel clusters for emblems, clasps, or runes:

```python
from pixelforge import Asset, AssetSpec

SPEC = AssetSpec(
    id="relic_chest",
    style_id="topdown-rpg",
    width=32,
    height=32,
    perspective="top-down",
    states=("closed", "open"),
    frames=1,
    seed=305,
)

_CLASP_SPR = (
    ".GG.",
    "GLLG",
    "GDDG",
    ".GG.",
)


def render(a: Asset) -> None:
    p = a.pal
    a.rect(5, 22, 22, 5, p.VOID)
    with a.layer("chest", outline=p.INK):
        a.bevel_rect(6, 10, 20, 14, (p.BARK_D, p.BARK_M, p.BARK_L))
        if a.state == "open":
            a.rect(8, 12, 16, 6, p.VOID)
            a.rect(10, 14, 12, 3, p.GOLD_M)
        else:
            a.spr(_CLASP_SPR, 14, 15, {"G": p.GOLD_M, "L": p.GOLD_L, "D": p.BARK_D})

    a.anchor("foot", 16, 25, kind="ground")
    a.hitbox("body", 5, 10, 22, 17)
```

### Recipe D — UI / Tilemap (`ui_tilemap`)
Use `NineSliceMargins` + `prefabs.ui_button` / `prefabs.ui_icon_16` (or `tilemap.autotile_sheet`) with crisp corner symmetry:

```python
from pixelforge import Asset, AssetSpec, NineSliceMargins, prefabs

SPEC = AssetSpec(
    id="hud_btn",
    style_id="homelab-16bit",
    width=28,
    height=20,
    perspective="front-2.5d",
    states=("normal", "hover", "pressed", "disabled"),
    frames=1,
    seed=802,
    nine_slice=NineSliceMargins(left=7, right=7, top=6, bottom=6),
)


_STATE_MAP: dict[str, prefabs.UiButtonState] = {
    "normal": "normal",
    "hover": "hover",
    "pressed": "pressed",
    "disabled": "disabled",
}


def render(a: Asset) -> None:
    p = a.pal
    pal = prefabs.UiPalette(
        bg=p.WALL_M,
        bg_dark=p.WALL_D,
        bg_light=p.WALL_L,
        border_outer=p.INK,
        border_highlight=p.METAL_H,
        border_shadow=p.VOID,
        accent=p.SOLAR_B,
        accent_bright=p.SHIRT_BLUE,
        text=p.WHITE,
        text_muted=p.SMOKE,
        success=p.LED_G,
        warning=p.LED_A,
        danger=p.LED_R,
    )
    prefabs.ui_button(a, 2, 2, 24, 16, pal, state=_STATE_MAP[a.state], accent=True, corner_cut=1)
    a.hitbox("bounds", 2, 2, 24, 16, kind="ui_button")
```

---

## 6. `blind-critic` Handoff Triggers & Protocol

Delegate an unbiased visual review using [../blind-critic/SKILL.md](../blind-critic/SKILL.md) whenever ANY of these triggers fire:

1. **New or Refactored Asset/Scene Gate:** Phase 2 passes `pixelforge check <id>` on a newly authored or substantially modified `.asset.py` / `.scene.py`.
2. **Craft Lint or Readability Uncertainty:** `pixelforge check --strict-craft` reports any craft warning (`craft-jaggies`, `craft-pillow-shading`, `craft-lighting`, `craft-contrast`, `craft-noop-delta`, `craft-anchor-fidelity`) or `1×` readability is ambiguous.
3. **Pre-PR / Pack Verification:** Before finalizing a multi-asset pack (`pixelforge render --pack-sheet`) or reviewing changes (`pixelforge diff <id> --base HEAD`).

**Handoff Payload Contract (Zero Source Leakage):**
- Pass ONLY: `asset_id`, `SPEC` summary (`width x height`, `perspective`, `states`, `frames`), and compiled artifact paths (`.pixelforge/sheets/<id>.contact.png`, `.pixelforge/previews/<id>_<state>.gif`, optional `.pixelforge/diffs/<id>.diff.png`).
- **NEVER** pass `.asset.py` / `.scene.py` source code or implementation intent to the blind critic subagent.
- Apply returned coordinate-anchored `fixes` in `assets/<pack>/<id>.asset.py`, re-run `check` + `render --sheet`, and re-verify (2–4 passes max).

---

## 7. CLI & Repository Validation Gates

1. `uv run pixelforge check [asset_id] [--strict-craft]` — Exits `0` (AST + runtime + craft lints).
2. `uv run pixelforge render <asset_id> --sheet --animate --emissive` — Generates `.contact.png` + `.gif`.
3. `uv run pixelforge critic <asset_id>` — Optional automated 5-axis multimodal LLM scoring.
4. `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` — Must exit `0`.

---

## 8. Completion Checklist

- [ ] `pixelforge inspect style` / `prefabs` consulted before authoring
- [ ] Phase 1 blockout `.contact.png` verified at `1×` before Phase 2 detail
- [ ] `uv run pixelforge check <id> --strict-craft` exits with code `0`
- [ ] `blind-critic` (or `pixelforge critic`) triggered when required; 2–4 surgical passes max
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` exits with code `0`
- [ ] `.pixelforge/` scratch artifacts remain untracked
