---
name: create-pixel-asset
description: Author, guard-check, and visually refine deterministic code-drawn indexed pixel art modules (assets/**/*.asset.py) using the pixelforge core engine and multimodal Visual Critic Loop.
---

# Create Pixel Asset (`pixelforge` v2)

## 1. Context and Objective

`pixelforge` compiles deterministic Python pixel art modules (`assets/**/*.asset.py`) targeting a `numpy` `uint8` indexed framebuffer (`IndexedSurface`) and a closed semantic `StylePack` (`styles/*.style.py`).

This skill enforces:
- **Zero Mixels:** All pixels are authored on an integer grid inside a fixed `height x width` `numpy.ndarray(dtype=np.uint8)` buffer.
- **Binary Alpha:** Index `255` (`TRANSPARENT_INDEX`) maps strictly to alpha `0`; indices `0..254` map strictly to alpha `255`.
- **Closed Semantic Palette:** Drawing uses named `StylePack` palette tokens (`P = a.pal`) only—raw `#rrggbb` strings are banned in `assets/**`.
- **Keep Emissive Tokens Separate from Paint Tokens:** Never reuse an `emissive`-flagged token (such as `WINDOW_SKY`) for non-glowing painted surfaces, or they will bleed into WebGL2 bloom masks.
- **Bit-for-Bit Determinism:** Identical `(state, frame, seed)` inputs produce identical SHA-256 pixel digests (`a.rng()` / `a.hashf()` / `mulberry32` only; `random`, `secrets`, `numpy.random`, `time`, and `datetime` are banned).
- **Code-Coupled Metadata:** `a.anchor()` / `plane.anchor()` and `a.hitbox()` are emitted directly by the rendering code.
- **Surgical Visual Critique:** Agents inspect coordinate-ruled `.contact.png` sheets (and `.gif` previews when `frames > 1`) and apply exact coordinate or parametric fixes over 2–4 passes rather than blind regeneration.

---

## 2. When to Use (Triggers)

Activate this skill whenever the task involves:
- Creating a new code-drawn pixel art asset in `assets/**/*.asset.py`
- Iterating on or fixing visual defects in an existing `.asset.py` module
- Updating state variants (`healthy`, `dusty`, `faulty`, `day`, `night`) or animation frames (`frames > 1`)
- Running `pixelforge check`, `pixelforge render --sheet`, `pixelforge render --animate`, or `pixelforge diff`

---

## 3. Associated Tools and MCP Servers

- **MCP Servers:** `None (local CLI and filesystem)`
- **CLI Tools:**
  - `uv run pixelforge check [asset_id] [--strict-orphans]` — AST static + runtime guard verification
  - `uv run pixelforge render [asset_id] --sheet [--animate] [--emissive] [--lut] [--indexed-ts] [--scale 1] [--variant <name>] [--out dist]` — Compile PNGs, spritesheets, emissive masks, `manifest.json`, `manifest.d.ts`, `.pixelforge/sheets/<id>.contact.png`, and `.pixelforge/previews/<id>_<state>.gif`
  - `uv run pixelforge diff <asset_id> [--base HEAD] [--out .pixelforge/diffs]` — Side-by-side + highlighted magenta pixel-diff PNG against a git baseline
  - `uv run ruff check . && uv run ruff format --check .`, `uv run pyright`, `uv run pytest` — Repository validation gates

---

## 4. Step-by-Step Operational Procedure

### Step 1: Plan (Silhouette, Layering, and Anchor Checklist)

Before writing code, define the asset's structural blueprint:

1. **Contract & Grid (`AssetSpec`):**
   - `id` (`snake_case`), `style_id` (e.g., `"homelab-16bit"`), `perspective` (`"front-2.5d"` | `"iso-2:1"` | `"top-down"` | `"side"`), `width` × `height`.
   - `states` (e.g., `("healthy", "dusty", "faulty")` or `("day", "night")`), `frames` (`>= 1`), `fps` (required when `frames > 1`), `seed`.
2. **Silhouette & Proportions:**
   - Ensure the outer contour reads unmistakably at `1×` native resolution.
   - Reserve at least `1px` margin inside `[0, width) × [0, height)` when using `outline=P.OUTLINE` on `a.layer(...)` or `auto_outline()` so the contour is not clipped at the canvas edge.
3. **Compositional Layer Order (`with a.layer(...)` / `with a.plane(...)`):**
   - **Layer 1 — Base Silhouette / Chassis:** Primary volumes (`with a.layer("chassis", outline=P.OUTLINE):`, `with a.plane(p0, p1, p2) as p:`, `iso_box`, `iso_tile`, `rect`, `rounded_rect`).
   - **Layer 2 — Structural Recesses & Panels:** Screen bezels, vents, drive bays, keyboards, ports (`plane.rect`, `plane.grid`, `a.line`, `a.spr`).
   - **Layer 3 — Directional Shading & Edge Highlights:** Follow `style.lighting_angle` (default `"top-left"`: top/left faces lit, bottom/right faces shaded; `bevel=(light, dark)`, `edge_mask`, `sel_out`).
   - **Layer 4 — Material Texture & Procedural Detail:** Vectorized `dither` (`"bayer2"`, `"bayer4"`, `"checker"`) or `a.scatter(..., mask="opaque")` using deterministic PRNG (avoid pure-Python per-pixel loops on large canvases so renders stay `< 40 ms`).
   - **Layer 5 — Emissive & State Overlays:** LEDs, terminal glyphs, `dusty` speckles, `faulty` sparks/amber-red indicators, frame-dependent blink/fan rotation (`a.state`, `a.frame`).
   - **Layer 6 — Surgical 1px Polish:** Direct integer-coordinate refinements (`a.put(x, y, P.TOKEN)`, `a.erase(x, y)`) guided by the `.contact.png` ruler.
4. **Code-Coupled Anchors & Hitboxes:**
   - Emit `a.anchor(name, x, y)` / `plane.anchor(name, u, v)` and `a.hitbox(name, x, y, w, h)` in the same `render(a)` pass that draws the pixels, keeping all coordinates within `[0, width] × [0, height]` with unique names per `(state, frame)`.

---

### Step 2: Author (`assets/<pack>/<id>.asset.py`)

Implement `SPEC: AssetSpec` and `def render(a: Asset) -> None:` using `pixelforge`:

- Access palette tokens via `P = a.pal` (fail-loud `PaletteLookup` bound to the active `StylePack`).
- Use compositional `with a.layer(name, *, offset=(0, 0), outline=None, sel_out=None, mirror_x=False):` and `with a.plane(p0, p1, p2) as plane:` for angled/isometric faces.
- Use vectorized primitives (`rect`, `rounded_rect`, `line`, `circle`, `ellipse`, `polygon`, `quad`, `fill`, `dither`, `spr`, `scatter`, `iso_box`, `iso_tile`, `mirror_x`, `flip_x`, `flip_y`, `auto_outline`, `sel_out`, `edge_mask`).
- Never import `random`, `secrets`, `numpy.random`, `os`, `pathlib`, `subprocess`, `time`, `datetime`, `io`, or `PIL`, and never call `open`, `eval`, `exec`, `__import__`, or `compile`.
- Never write raw `#rrggbb` hex strings (outside `spr()` ASCII grids) or external image file references (`.png`, `.jpg`, `.webp`, `.svg`, `.gif`).

---

### Step 3: Guard Check (`pixelforge check`)

Run the AST static and runtime guard suite before inspecting visuals:

```bash
uv run pixelforge check <asset_id>
```

`pixelforge check` MUST exit with code `0`. It enforces:

| Rule ID | Mode | Requirement |
| :--- | :---: | :--- |
| `syntax-error` | AST | Module parses cleanly as valid Python |
| `no-stdlib-random` | AST | Bans `random`, `secrets`, `numpy.random` in `assets/**`, `styles/**`, and `src/pixelforge/core/**` |
| `no-external-assets` | AST | Bans image paths (`.png`, `.jpg`, `.webp`, `.svg`, `.gif`, etc.) and `PIL`/`Image` imports in `assets/**` |
| `no-raw-hex` | AST | Bans literal `#rrggbb` strings inside `assets/**` (ignores `spr()` ASCII grids) |
| `no-io-or-eval` | AST | Bans `open`, `eval`, `exec`, `compile`, `__import__`, and `os`/`pathlib`/`subprocess`/`time`/`datetime`/`io` in `assets/**` |
| `exact-dimensions` | Runtime | Rendered surface shape equals `(asset.height, asset.width)` |
| `closed-palette` | Runtime | Every pixel is `255` (`TRANSPARENT_INDEX`) or a declared `StylePack` index |
| `binary-alpha` | Runtime | Exported RGBA buffer contains exclusively alpha `0` or `255` |
| `bit-determinism` | Runtime | Rendering every `(state, frame)` twice yields identical SHA-256 pixel digests |
| `valid-anchors` | Runtime | Anchors and hitboxes lie within `[0, width] × [0, height]` with unique names per `(state, frame)` |
| `orphan-pixels` | Diagnostic | Reports isolated `1×1` pixels (advisory by default; `--strict-orphans` turns into error) |

If any violation is reported (`file:line [rule] detail`), fix it immediately and re-run `uv run pixelforge check <asset_id>`.

---

### Step 4: Render & Inspect (`pixelforge render --sheet --animate`)

Generate the coordinate-ruled contact sheet (and animated GIF previews when `frames > 1`) and inspect them directly:

```bash
uv run pixelforge render <asset_id> --sheet --animate --emissive
```

Open `.pixelforge/sheets/<asset_id>.contact.png` (and `.pixelforge/previews/<asset_id>_<state>.gif` if animated) via your multimodal image view. The contact sheet provides:
1. **Header Bar:** `id`, `W×H`, `style_id`, `perspective`, and frame count.
2. **1× True-Size Strip:** Dark (`#0d1117`) and light (`#e6edf3`) checkerboards for silhouette and contrast verification.
3. **Zoomed Inspection Panel (`4×` / `8×`):** Nearest-neighbor upscale with 1px grid lines, **every-4px `(x, y)` coordinate ruler**, hitbox overlays, and anchor crosshairs.
4. **State & Frame Matrix:** Side-by-side `(state, frame)` cells plus an emissive-only silhouette preview.
5. **Used Palette Swatches & Metrics:** Untruncated palette token names with `[E]` emissive markers and pixel/orphan metrics.

---

### Step 5: Multimodal Visual Critic Loop (2–4 Surgical Passes Max)

Evaluate the rendered contact sheet (and GIFs) against these five criteria:

1. **1× Silhouette & Readability:** Is the object immediately recognizable at `1×` on both dark and light backgrounds?
2. **Lighting Consistency:** Do highlights sit on `top-left` edges and shadows on `bottom-right` edges?
3. **Pixel Cluster Cleanliness:** Are there stray `1×1` orphan pixels, broken outlines, or unintentional stair-stepping?
4. **State & Frame Legibility:** Are `healthy`, `dusty`, and `faulty` (or `day`/`night`) clearly distinguishable, and do animation frames (`frame 0` vs `frame 1`) change cleanly without jitter?
5. **Anchor & Hitbox Alignment:** Do the crosshairs on the zoomed panel land on the exact intended pixel features?

**Refinement Loop:**
- Read the exact `(x, y)` coordinates of any defect from the contact-sheet ruler.
- Apply surgical coordinate or parametric edits in `assets/<pack>/<id>.asset.py`.
- Re-run `uv run pixelforge check <asset_id> && uv run pixelforge render <asset_id> --sheet --animate --emissive`.
- Optionally run `uv run pixelforge diff <asset_id> --base HEAD` to verify only the intended pixels changed.
- Repeat for **2–4 passes maximum** until all five criteria pass. Never commit `.pixelforge/` scratch artifacts.

---

## 5. Code Standards and Canonical Example

### Standard Asset Module Example (`assets/homelab/mini_node.asset.py`)

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
    with a.layer("lid", outline=P.OUTLINE):
        with a.plane(p0=(11, 4), p1=(26, 8), p2=(6, 15)) as lid:
            lid.rect(0.0, 0.0, 1.0, 1.0, fill=P.SLATE_DARK, bevel=(P.SLATE_LIGHT, P.SHADOW))
            lid.rect(0.12, 0.14, 0.76, 0.72, fill=P.METAL_MID)
            lid.anchor("top", 0.5, 0.5)

    # 2. Front deck with extruded height and keyboard grid
    with a.layer("deck", outline=P.OUTLINE):
        with a.plane(p0=(6, 16), p1=(26, 20), p2=(3, 24)) as deck:
            deck.rect(0.0, 0.0, 1.0, 1.0, fill=P.SLATE_MID, extrude_y=3, side=P.SHADOW)
            deck.grid(0.1, 0.12, 0.8, 0.45, cols=6, rows=2, color=P.SLATE_DARK)

    # 3. Deterministic dusty speckles masked to opaque pixels
    if a.state == "dusty":
        a.scatter(count=8, colors=(P.DUST_LIGHT, P.DUST_DARK), mask="opaque")

    # 4. Emissive status LED (blinks on frame 1 when healthy)
    led_color = P.FAULT_RED if a.state == "faulty" else P.LED_GREEN if a.frame == 0 else P.SHADOW
    a.put(22, 18, led_color)
    a.anchor("led", 22, 18)
    a.anchor("foot", 16, 27)
    a.hitbox("body", 2, 3, 28, 25)
```

---

## 6. Known Gotchas and Anti-Patterns

- **DO NOT** allocate or write palette index `255` (`TRANSPARENT_INDEX`) as a visible color; it is permanently reserved for binary alpha `0`.
- **DO NOT** use `random`, `secrets`, `numpy.random`, `time`, `datetime`, `open`, `eval`, or `exec` in `assets/**`.
- **DO NOT** write raw `#rrggbb` hex strings inside `assets/**`; all colors must resolve through `a.pal`.
- **DO NOT** reuse `emissive` tokens for non-glowing painted surfaces.
- **DO NOT** commit `.pixelforge/` scratch artifacts or third-party reference photos to Git.
- **DO** emit `a.anchor()` / `plane.anchor()` and `a.hitbox()` in the same `render(a)` pass that draws the pixels so metadata never drifts.
- **DO** run `uv run pixelforge check <id>` before `uv run pixelforge render <id> --sheet` on every iteration.

---

## 7. Skill Completion Checklist

- [ ] Silhouette, layer order, and anchor plan defined before coding
- [ ] `assets/<pack>/<id>.asset.py` strictly typed (`pyright` strict + `ruff` pass)
- [ ] `uv run pixelforge check <id>` exits with code `0` (all AST + runtime guards pass)
- [ ] `uv run pixelforge render <id> --sheet --animate --emissive` inspected visually and refined (2–4 surgical passes max)
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` exits with code `0`
- [ ] `.pixelforge/` scratch artifacts remain untracked
