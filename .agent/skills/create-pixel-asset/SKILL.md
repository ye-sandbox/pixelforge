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
- **Surgical Visual Critique:** Inspect coordinate-ruled `.contact.png` sheets (and `.gif` previews when `frames > 1`) and apply exact coordinate or parametric fixes over 2–4 passes.

---

## 2. Progressive Disclosure References

Load these references on demand when the task involves them:

- **Prefab Kits & Window Recipes:** [references/prefabs.md](references/prefabs.md) — Complete `architecture`, `furniture`, `details`, and `atmosphere` prefab kits + clipped window recipes.
- **Declarative Scenes & Spatial Ergonomics:** [references/scenes.md](references/scenes.md) — `*.scene.py` (`SceneSpec` / `SceneMountSpec`), `pixelforge compose`, and room ergonomics.
- **Multimodal Visual Critic & `critic` CLI:** [references/critic.md](references/critic.md) — Manual 5-criteria contact-sheet loop and automated `pixelforge critic` scoring.

---

## 3. CLI Discovery & Validation Workflow

All CLI commands emit LLM-first compact output by default (`--format llm|json|human`, `--json`, `--human`).

1. **Introspect First (`pixelforge inspect`):**
   - `uv run pixelforge inspect style [style_id]` — Palette tokens grouped by `paint`, `emissive`, `bright`, and `reflections`.
   - `uv run pixelforge inspect prefabs [category|name]` — Live prefab signatures and categories (`architecture`, `furniture`, `details`, `atmosphere`).
   - `uv run pixelforge inspect api [target]` — Public methods, signatures, and 1-line summaries of `Asset`, `Layer`, `Plane`, `IndexedSurface`, `tilemap`, and `font`.
   - `uv run pixelforge inspect assets [asset_id]` — Existing asset dimensions, states, anchors, and hitboxes.
   - `uv run pixelforge inspect scenes [scene_id]` — Declarative `.scene.py` mounts, state maps, and strict flags.
2. **Optional Reference Proportions:**
   - `uv run pixelforge analyze-ref <image_path> [--style homelab-16bit] [--size 32x32]` — Ephemeral aspect ratio, palette histogram, and ASCII sketch (never place reference images inside `assets/` or `styles/`).
3. **Author (`assets/<pack>/<id>.asset.py`):**
   - Define `SPEC: AssetSpec` and `def render(a: Asset) -> None:`.
   - Layer order: (1) Base silhouette (`with a.layer(..., outline=P.INK):` / `with a.plane(...)`), (2) Structural recesses & panels, (3) Directional shading (`top-left` lit, `bottom-right` shaded), (4) Vectorized texture (`dither`, `a.scatter(..., mask="opaque")`), (5) Emissive & state overlays, (6) 1px surgical polish (`a.put`, `a.erase`) + `a.anchor()` / `a.hitbox()`.
4. **Guard Check (`pixelforge check`):**
   - `uv run pixelforge check [asset_id] [--strict-orphans]` — Must exit `0` (enforces AST bans on `random`/I/O/raw hex/external assets + runtime checks on dimensions, closed palette, binary alpha, determinism, anchors, and orphan pixels).
5. **Render & Inspect (`pixelforge render --sheet --animate --emissive`):**
   - `uv run pixelforge render <asset_id> --sheet --animate --emissive` — Generates `.pixelforge/sheets/<id>.contact.png` (1× dark/light strips, zoomed 4px-ruled grid, anchors, hitboxes, state/frame matrix, swatches) and `.pixelforge/previews/<id>_<state>.gif`.
   - Optionally compare against git baseline: `uv run pixelforge diff <asset_id> --base HEAD`.
   - Run automated multimodal critic if configured: `uv run pixelforge critic <asset_id>`.
6. **Repository Validation Gates:**
   - `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest`

---

## 4. Canonical Asset Example (`assets/homelab/mini_node.asset.py`)

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
    P = a.pal

    # 1. Isometric lid/top face with automatic outline on layer exit
    with a.layer("lid", outline=P.INK):
        with a.plane(p0=(11, 4), p1=(26, 8), p2=(6, 15)) as lid:
            lid.rect(0.0, 0.0, 1.0, 1.0, fill=P.WALL_D, bevel=(P.METAL_L, P.VOID))
            lid.rect(0.12, 0.14, 0.76, 0.72, fill=P.METAL_M)
            lid.anchor("top", 0.5, 0.5)

    # 2. Front deck with extruded height and keyboard grid
    with a.layer("deck", outline=P.INK):
        with a.plane(p0=(6, 16), p1=(26, 20), p2=(3, 24)) as deck:
            deck.rect(0.0, 0.0, 1.0, 1.0, fill=P.WALL_M, extrude_y=3, side=P.VOID)
            deck.grid(0.1, 0.12, 0.8, 0.45, cols=6, rows=2, color=P.WALL_D)

    # 3. Deterministic dusty speckles masked to opaque pixels
    if a.state == "dusty":
        a.scatter(count=8, colors=(P.DUST_L, P.DUST_D), mask="opaque")

    # 4. Emissive status LED (blinks on frame 1 when healthy)
    led_color = P.LED_R if a.state == "faulty" else P.LED_G if a.frame == 0 else P.VOID
    a.put(22, 18, led_color)
    a.anchor("led", 22, 18)
    a.anchor("foot", 16, 27)
    a.hitbox("body", 2, 3, 28, 25)
```

---

## 5. Completion Checklist

- [ ] `pixelforge inspect style` / `prefabs` consulted before authoring
- [ ] Silhouette, layer order, and anchor plan defined
- [ ] `uv run pixelforge check <id>` exits with code `0`
- [ ] `uv run pixelforge render <id> --sheet --animate --emissive` visually inspected (2–4 surgical passes max)
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` exits with code `0`
- [ ] `.pixelforge/` scratch artifacts remain untracked
