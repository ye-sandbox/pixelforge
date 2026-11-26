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
- **Keep Emissive Tokens Separate from Paint Tokens:** Never reuse an `emissive`-flagged token (such as `SOLAR_L`, `LED_C`, or `VISOR_C`) for non-glowing painted surfaces (such as `WINDOW_SKY`), or they will bleed into WebGL2 bloom masks.
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
  - `uv run pixelforge analyze-ref <image_path> [--style homelab-16bit] [--size 32x32]` — Extract aspect ratio, palette histogram, and quantized ASCII sketch from a local reference image without importing external rasters into `.asset.py`
  - `uv run pixelforge compose <parent_id> --mount <prop_id>@<anchor>[:<prop_anchor>] [--state <name>] [--strict-bounds] [--sheet]` — Mount micro-props onto parent scene anchors and verify zero clipping/occlusion
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
   - Reserve at least `1px` margin inside `[0, width) × [0, height)` when using `outline=P.INK` on `a.layer(...)` or `auto_outline()` so the contour is not clipped at the canvas edge.
3. **Compositional Layer Order (`with a.layer(...)` / `with a.plane(...)`):**
   - **Layer 1 — Base Silhouette / Chassis:** Primary volumes (`with a.layer("chassis", outline=P.INK):`, `with a.plane(p0, p1, p2) as p:`, `iso_box`, `iso_tile`, `rect`, `rounded_rect`).
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

## 6. Known Gotchas and Anti-Patterns

- **DO NOT** allocate or write palette index `255` (`TRANSPARENT_INDEX`) as a visible color; it is permanently reserved for binary alpha `0`.
- **DO NOT** use `random`, `secrets`, `numpy.random`, `time`, `datetime`, `open`, `eval`, or `exec` in `assets/**`.
- **DO NOT** write raw `#rrggbb` hex strings inside `assets/**`; all colors must resolve through `a.pal`.
- **DO NOT** reuse `emissive` tokens for non-glowing painted surfaces.
- **DO NOT** commit `.pixelforge/` scratch artifacts or third-party reference photos to Git.
- **DO** emit `a.anchor()` / `plane.anchor()` and `a.hitbox()` in the same `render(a)` pass that draws the pixels so metadata never drifts.
- **DO** run `uv run pixelforge check <id>` before `uv run pixelforge render <id> --sheet` on every iteration.

---

## 7. Prefab Kits Reference (`pixelforge.prefabs`)

Import `from pixelforge import prefabs`. Every prefab is `StylePack`-agnostic (accepting explicit palette indices via `P = a.pal`), 100% deterministic, and compatible with both `Asset` and `Layer` targets.

### Architecture (`prefabs.architecture`)
- `iso_room_shell(target, cx, cy, hw, hh, wall_h, *, floor, left_wall, right_wall, floor_alt=None, floor_dither_ratio=0.12, baseboard=None, wall_seam=None, outline=None, lighting_angle=None) -> IsoRoomGeometry` — 2:1 isometric room diamond, two back walls, baseboard trim, corner seam, and outer ink contour. Returns `IsoRoomGeometry` with `left_wall_plane(u0, v0, u1, v1)`, `right_wall_plane(u0, v0, u1, v1)`, `floor_point(u, v)`, and `window_spill_quad(u0, u1, *, wall="left", depth=0.35, inset=0.025)` aligned to `StylePack.lighting_angle`.
- `iso_floor_pattern(target, cx, cy, hw, hh, *, color, step=16, mode="planks")` — Bounded `"planks"`, `"tiles"`, or `"grid"` floor lines.
- `iso_window(target, p0, p1, p2, *, frame, sky, outline=None, sky_alt=None, mullion=None, sill=None, cols=1, rows=2, glint=None, scene=None)` — Skewed isometric wall window with multi-pane mullions, glass glint, sill, and optional clipped `scene(pane)` callback.
- `front_window(target, x, y, w, h, *, frame, sky, outline=None, sky_alt=None, mullion=None, sill=None, cols=1, rows=2, glint=None, frame_thickness=2, scene=None)` — `front-2.5d` rectangular window with clipped glass `scene(pane)`, mullions, glint, and sill.
- `iso_window_glass_region(p0, p1, p2)` / `front_window_glass_region(x, y, w, h, *, frame_thickness=2)` — Return the exact inner glass `PaneRegion` for standalone atmospheric calls.
- `wall_vent(target, p0, p1, p2, *, frame, slat, outline=None, slats=3)` — Louvered isometric wall vent.

### Furniture (`prefabs.furniture`)
- `iso_desk(target, x, y, w, d, *, leg_h=18, top_h=5, top, left, right, leg_top, leg_left, leg_right, outline=None, highlight=None, mat_color=None, mat_w=None) -> IsoDeskSlots` — 2:1 isometric desk with legs, beveled top, optional desk mat, and `IsoDeskSlots` (`center`, `top_plane()`, `top_point(u, v)`, `slots(count)`).
- `iso_rack(target, x, y, w, d, h, *, top, left, right, outline=None, highlight=None, bay_color=None, led_color=None, bays=3, anchor="center", front_style="bays", door_color=None) -> IsoRackSlots` — Isometric equipment/server rack with `"bays"`, `"grille"`, or `"glass_door"` front styling, status LEDs, and `IsoRackSlots` (`top_center`, `top_point(u, v)`, `front_mounts`, `front_plane()`).
- `iso_shelf(target, x, y, w, d, h, *, shelves=2, top, left, right, post, outline=None, anchor="center") -> IsoShelfSlots` — Open corner-post shelving unit returning `IsoShelfSlots` (`tiers`, `top_center`, `tier_point(tier, u, v)`).

### Details (`prefabs.details`)
- `contact_shadow(target, cx, cy, rx, ry, *, color, dither_ratio=0.5)` — Grounded elliptical checker/Bayer contact shadow.
- `iso_cable_run(target, points, *, color, highlight=None)` — Pixel-crisp cable polyline with optional 1px highlight.
- `wall_panel(target, p0, p1, p2, *, frame, recess, slot, outline=None, cols=2, rows=3, status_led=None)` — Isometric breaker/control panel.
- `wall_poster(target, p0, p1, p2, *, border, fill, accent=None, outline=None)` — Framed isometric wall poster.

### Atmosphere, Clipped Vistas & Light Spill (`prefabs.atmosphere`)
All atmospheric primitives accept either a `ClippedPane` (inside `scene=` or `with prefabs.clipped_pane(a, region) as pane:`) or `(target, region=...)` directly, supporting **both** `iso-2:1` planes `(p0, p1, p2)` and `front-2.5d` rectangles `(x, y, w, h)`:

- `clipped_pane(target, region)` — Auxiliary `IndexedSurface` + boolean glass mask that guarantees celestial bodies, clouds, skylines, rain, and snow never bleed onto frames or mullions.
- `sky_backdrop(target, *, bands, region=None, pattern="bayer4", dither_width=0.65)` — Multi-band ordered-dither gradient across `bands` (top to bottom).
- `sun(target, u=0.28, v=0.28, *, radius=3, color, halo=None, rays=False, ray_color=None, region=None)` — Pixel sun with optional checker halo and cardinal/diagonal rays.
- `moon(target, u=0.72, v=0.28, *, radius=3, color, crater_color=None, shadow_color=None, crescent=False, halo=None, region=None)` — Full moon with pixel craters or carved crescent moon preserving sky/stars behind it.
- `starfield(target, *, count=12, color, twinkle_color=None, frame=0, frames=1, seed=0, max_v=0.78, region=None)` — Fixed-position stars with smooth periodic twinkling.
- `clouds(target, *, color, shade_color=None, count=2, phase=0.0, min_v=0.14, max_v=0.48, seed=0, region=None)` — Vectorized flat-bottomed clouds drifting seamlessly with `phase = a.frame / a.frames`.
- `horizon_silhouette(target, *, color, accent=None, mode="city", base_v=0.74, seed=0, region=None)` — `"city"`, `"rooftops"`, `"hills"`, or `"trees"` horizon clipped to the glass bottom.
- `weather_rain(target, *, color, splash_color=None, count=16, phase=0.0, slant=-0.14, length=0.14, seed=0, region=None)` — Looping diagonal rain streaks (`speed in {1, 2}` integer cycles so `phase=0` wraps cleanly to `phase=1`).
- `weather_snow(target, *, color, alt_color=None, count=18, phase=0.0, drift=0.08, seed=0, region=None)` — Looping swaying snowflakes with depth parallax (`phase = a.frame / a.frames`).
- `eval_day_night_cycle(...)` / `day_night_cycle(target, *, phase, day_bands, dusk_bands, night_bands, sun_color, moon_color, star_color, ...)` — Sweeps sky bands, sun/moon arc, star visibility, clouds, and horizon across `phase` (`0.0..1.0`), returning `CycleStep` (with `spill_intensity` and `celestial_kind`) to drive interior lighting.
- `window_light_spill(target, *, points, color, secondary_color=None, pattern="bayer4", near_ratio=0.70, far_ratio=0.18, mask="opaque")` & `light_beam(target, region, *, color, secondary_color=None, dx=24, dy=16, spread=6, ...)` — Tapered ordered-dither floor/wall light projection.

---

## 8. Atmospheric Window Recipes & Token Discipline

### Clipped Window Recipe (`iso-2:1` & `front-2.5d`)
```python
phase = a.frame / float(a.frames)


def _vista(pane: prefabs.ClippedPane) -> None:
    if a.state == "cycle":
        prefabs.day_night_cycle(
            pane,
            phase=phase,
            day_bands=(p.SOLAR_B, p.GLASS_L, p.SCREEN_L),
            dusk_bands=(p.WINDOW_SKY, p.WARM_AMBER, p.ORANGE),
            night_bands=(p.VOID, p.WINDOW_SKY, p.SCREEN_D),
            sun_color=p.HAIR_Y,
            moon_color=p.WHITE,
            star_color=p.STAR,
            sun_halo=p.WHITE,
            moon_crater=p.SMOKE,
            cloud_color=p.SMOKE,
            horizon_color=p.WALL_D,
            horizon_accent=p.WARM_LAMP,
            frame=a.frame,
            frames=a.frames,
            seed=a.seed,
        )
    elif a.state == "rain":
        prefabs.sky_backdrop(pane, bands=(p.VOID, p.WALL_M, p.GLASS_D))
        prefabs.clouds(
            pane, color=p.METAL_M, shade_color=p.METAL_D, count=3, phase=phase, seed=a.seed
        )
        prefabs.horizon_silhouette(pane, color=p.WALL_D, mode="rooftops", seed=a.seed)
        prefabs.weather_rain(
            pane, color=p.GLASS_L, splash_color=p.WHITE, count=18, phase=phase, seed=a.seed
        )


# Use iso_window(...) for iso-2:1 wall planes, or front_window(...) for front-2.5d rects
prefabs.iso_window(
    a,
    p0=(14, 24),
    p1=(44, 9),
    p2=(14, 49),
    frame=p.METAL_M,
    sky=p.WINDOW_SKY,
    outline=p.INK,
    mullion=p.METAL_L,
    cols=2,
    rows=2,
    glint=p.GLASS_L,
    sill=p.WOOD_L,
    scene=_vista,
)
```

### Emissive vs. Non-Emissive Token Discipline (`homelab-16bit`)
- **NEVER emissive:** sky bands (`WINDOW_SKY`, `SOLAR_B`, `SCREEN_D`, `GLASS_D`, `GLASS_L`), clouds (`WHITE`, `SMOKE`), daytime sun (`HAIR_Y`), moon body (`WHITE`), rain/snow (`GLASS_L`, `WHITE`, `SMOKE`), horizon silhouettes (`WALL_D`, `WALL_M`), and interior `window_light_spill` / `light_beam` (`FLOOR_L`, `FLOOR_M`, `TILE_L`). Using `SOLAR_L` or `WARM_LAMP` on sky/clouds/floor spills will blow out the WebGL2 bloom mask.
- **Intentionally emissive (only true light emitters):** night `starfield` (`STAR`), optional distant lit city windows (`WARM_LAMP`), and powered interior LEDs/lamps (`LED_*`, `WARM_LAMP`).

### `analyze-ref` & `compose` Workflow Tips
- **Proportions from reference:** Run `uv run pixelforge analyze-ref photo.png --style homelab-16bit --size 32x32` before drawing complex props to get exact aspect ratio, dominant palette tokens, and a terminal ASCII blockout—never import the image inside `.asset.py`.
- **Scene prop mounting:** Emit `mount_bottom` on props and `hardware_0..N` on scenes, then run `uv run pixelforge compose bedroom_desk_iso --mount monitor_iso@hardware_0:mount_bottom --strict-bounds --sheet` to validate zero clipping or overlap before committing.

---

## 9. Skill Completion Checklist

- [ ] Silhouette, layer order, and anchor plan defined before coding
- [ ] `assets/<pack>/<id>.asset.py` strictly typed (`pyright` strict + `ruff` pass)
- [ ] `uv run pixelforge check <id>` exits with code `0` (all AST + runtime guards pass)
- [ ] `uv run pixelforge render <id> --sheet --animate --emissive` inspected visually and refined (2–4 surgical passes max)
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` exits with code `0`
- [ ] `.pixelforge/` scratch artifacts remain untracked
