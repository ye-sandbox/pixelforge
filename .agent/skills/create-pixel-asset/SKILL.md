---
name: create-pixel-asset
description: Author, guard-check, and visually refine deterministic code-drawn indexed pixel art modules (assets/**/*.asset.ts) using the pixelforge core engine and multimodal Visual Critic Loop.
---

# Create Pixel Asset (`pixelforge`)

## 1. Context and Objective

`pixelforge` generates production game and UI pixel art exclusively from deterministic TypeScript code (`assets/**/*.asset.ts`) targeting an indexed `Uint8Array` framebuffer (`IndexedSurface`) and a closed semantic `StylePack`.

This skill enforces:
- **Zero Mixels:** All pixels are authored on an integer grid (`x | 0, y | 0`).
- **Binary Alpha:** Index `255` (`TRANSPARENT_INDEX`) maps strictly to alpha `0`; indices `0..254` map strictly to alpha `255`.
- **Closed Semantic Palette:** Drawing uses named `StylePack` palette indices only—no raw `#rrggbb` strings.
- **Bit-for-Bit Determinism:** Identical `(state, frame, seed)` inputs produce identical SHA-256 pixel digests (`ctx.rng()` only; `Math.random()` is banned).
- **Code-Coupled Metadata:** `ctx.anchor()` and `ctx.hitbox()` are emitted directly by the rendering code.
- **Surgical Visual Critique:** Agents inspect coordinate-ruled `.contact.png` sheets and apply exact coordinate fixes over 2–4 passes rather than blind regeneration.

---

## 2. When to Use (Triggers)

Activate this skill whenever the task involves:
- Creating a new code-drawn pixel art asset in `assets/**/*.asset.ts`
- Iterating on or fixing visual defects in an existing `.asset.ts` module
- Updating state variants (`healthy`, `dusty`, `faulty`, `day`, `night`) or animation frames
- Running `pixelforge check`, `pixelforge render --sheet`, or `pixelforge diff`

---

## 3. Associated Tools and MCP Servers

- **MCP Servers:** `None (local CLI and filesystem)`
- **CLI Tools / Scripts:**
  - `pixelforge check [asset-id]` — Static + runtime guard verification
  - `pixelforge render [asset-id] --sheet [--emissive] [--scale 1] [--variant <name>] [--out dist]` — Render PNGs, spritesheets, emissive masks, `manifest.json`, and `.pixelforge/sheets/<id>.contact.png`
  - `pixelforge diff <asset-id> [--base HEAD]` — Side-by-side + highlighted pixel-diff PNG against a baseline
  - `pnpm test`, `pnpm typecheck`, `pnpm lint`, `pnpm build` — Repository validation gates

---

## 4. Step-by-Step Operational Procedure

### Step 1: Plan (Silhouette, Layering, and Anchor Checklist)

Before writing code, define the asset's structural blueprint:

1. **Contract & Grid:**
   - `id` (snake_case or kebab-case), `styleId`, `perspective` (`front-2.5d` | `iso-2:1` | `top-down` | `side`), `width` × `height`.
   - `states` (e.g., `['healthy', 'dusty', 'faulty']` or `['day', 'night']`), `frames` (`>= 1`), `fps` (required when `frames > 1`), `seed`.
2. **Silhouette & Proportions:**
   - Ensure the outer contour reads unmistakably at `1×` native resolution.
   - Reserve at least `1px` margin inside `[0, width) × [0, height)` if applying `autoOutline()` so the contour is not clipped at the canvas edge.
3. **Strict Layer Order:**
   - **Layer 1 — Base Silhouette / Chassis:** Primary volumes (`surface.rect`, `surface.circle`, `isoBox`, `isoTile`).
   - **Layer 2 — Structural Recesses & Panels:** Screen bezels, vents, drive bays, ports, cables (`surface.rect`, `surface.line`, `surface.spr`).
   - **Layer 3 — Directional Shading & Edge Highlights:** Follow `style.lightingAngle` (default `top-left`: top/left faces lit, bottom/right faces shaded; `surface.edgeMask`).
   - **Layer 4 — Material Texture & Procedural Detail:** Subtle dithering or noise using `ctx.rng()` (never `Math.random()`).
   - **Layer 5 — Emissive & State Overlays:** LEDs, terminal glyphs, coolant glow, `dusty` speckles, `faulty` sparks/amber-red indicators, frame-dependent blink/fan rotation (`ctx.frame`).
   - **Layer 6 — Outer Contour:** Call `surface.autoOutline(PAL.OUTLINE)` last (or selectively on opaque regions) to seal the silhouette.
4. **Code-Coupled Anchors & Hitboxes:**
   - List required anchors (e.g., `foot`, `led`, `socket`, `breaker`) and hitboxes (e.g., `body`, `interact`).
   - Emit `ctx.anchor(name, x, y)` and `ctx.hitbox(name, x, y, w, h)` using the exact coordinates where those features are drawn, keeping all coordinates within `[0, width] × [0, height]` with unique names.

---

### Step 2: Author (`assets/<pack>/<id>.asset.ts`)

Implement the `AssetModule` using `@pixelforge/core` (`src/index.ts`) primitives and named indices from the target `StylePack`:

- Use `createPaletteLookup(ctx, [...])` (or `createPaletteLookup(ctx)`) from `../../src/index.js` to resolve `StylePack` token names to `PaletteIndex` with explicit missing-token errors.
- Use `surface.put`, `surface.rect`, `surface.line`, `surface.circle`, `surface.fill`, `surface.spr`, `surface.autoOutline`, `surface.edgeMask`, and `isoBox` / `isoTile` / `isoProject`.
- Keep all coordinates integer (`x | 0`, `y | 0`).
- Never reference `Math.random`, raw `#rrggbb` hex strings, DOM/Canvas APIs, or external image files (`.png`, `.jpg`, `.webp`, `.svg`).

---

### Step 3: Guard Check (`pixelforge check`)

Run the guard suite before inspecting visuals:

```bash
pnpm exec pixelforge check <asset-id>
```

`pixelforge check` MUST exit with code `0`. It enforces 8 rules:

| Rule ID | Mode | Requirement |
| :--- | :---: | :--- |
| `no-math-random` | Static | Bans `Math.random` in `assets/**`, `styles/**`, and `src/core/**` |
| `no-external-assets` | Static | Bans image imports/paths and DOM/Canvas APIs in asset modules |
| `no-raw-hex` | Static | Bans literal `#rrggbb` strings inside `assets/**` |
| `exact-dimensions` | Runtime | Surface dimensions match `asset.width × asset.height` |
| `closed-palette` | Runtime | Every pixel is `TRANSPARENT_INDEX (255)` or a declared `StylePack` index |
| `binary-alpha` | Runtime | Exported RGBA buffer contains exclusively alpha `0` or `255` |
| `valid-anchors` | Runtime | Anchors and hitboxes lie within `[0, width] × [0, height]` with unique names |
| `bit-determinism` | Runtime | Rendering `(state, frame)` twice yields identical SHA-256 digests |

If any violation is reported (`file:line [rule] detail`), fix it immediately and re-run `pixelforge check <asset-id>`.

---

### Step 4: Render & Inspect (`pixelforge render --sheet`)

Generate the coordinate-ruled contact sheet and inspect it directly:

```bash
pnpm exec pixelforge render <asset-id> --sheet --emissive
```

Open `.pixelforge/sheets/<asset-id>.contact.png` (and inspect it visually via your multimodal image view). The contact sheet provides:
1. **Header Bar:** `id`, `W×H`, `styleId`, `perspective`, and frame count.
2. **1× True-Size Strip:** Dark (`#0d1117`) and light (`#e6edf3`) checkerboards for silhouette and contrast verification.
3. **Zoomed Inspection Panel (`4×` / `8×`):** Nearest-neighbor upscale with 1px grid lines, **every-4px `(x, y)` coordinate ruler**, and anchor crosshairs.
4. **State & Frame Matrix:** Side-by-side `(state, frame)` cells plus an emissive-only silhouette preview.
5. **Used Palette Swatches:** Exact subset of palette tokens rendered by the asset.

---

### Step 5: Multimodal Visual Critic Loop (2–4 Surgical Passes Max)

Evaluate the rendered contact sheet against these five criteria:

1. **1× Silhouette & Readability:** Is the object immediately recognizable at `1×` on both dark and light backgrounds?
2. **Lighting Consistency:** Do highlights sit on `top-left` edges and shadows on `bottom-right` edges?
3. **Pixel Cluster Cleanliness:** Are there stray 1px orphan pixels, broken `autoOutline` corners, or unintentional stair-stepping?
4. **State & Frame Legibility:** Are `healthy`, `dusty`, and `faulty` (or `day`/`night`) clearly distinguishable, and do animation frames (`frame 0` vs `frame 1`) change cleanly without jitter?
5. **Anchor & Hitbox Alignment:** Do the crosshairs on the zoomed panel land on the exact intended pixel features (e.g., base foot, LED center, socket)?

**Refinement Loop:**
- Read the exact `(x, y)` coordinates of any defect from the contact-sheet ruler.
- Apply surgical coordinate edits in `assets/<pack>/<id>.asset.ts`.
- Re-run `pnpm exec pixelforge check <asset-id> && pnpm exec pixelforge render <asset-id> --sheet`.
- Optionally run `pnpm exec pixelforge diff <asset-id>` to verify only the intended pixels changed.
- Repeat for **2–4 passes maximum** until all five criteria pass. Do not commit `.pixelforge/` scratch files.

---

## 5. Code Standards and Canonical Examples

### Standard Asset Module Example

```typescript
import { type AssetModule, createPaletteLookup } from '../../src/index.js';

type ServerState = 'healthy' | 'dusty' | 'faulty';

export const asset: AssetModule<ServerState> = {
  id: 'mini_node',
  styleId: 'homelab-16bit',
  width: 16,
  height: 16,
  perspective: 'front-2.5d',
  states: ['healthy', 'dusty', 'faulty'],
  frames: 2,
  fps: 2,
  seed: 101,

  render(ctx) {
    const pal = createPaletteLookup(ctx, [
      'OUTLINE',
      'SHADOW',
      'METAL_DARK',
      'METAL_MID',
      'METAL_LIGHT',
    ]);
    const { surface, state, frame, rng } = ctx;

    // 1. Base chassis (1px inset for autoOutline)
    surface.rect(2, 3, 12, 10, pal.METAL_MID, true);
    // 2. Top-left bevel highlight & bottom-right shadow
    surface.line(2, 3, 13, 3, pal.METAL_LIGHT);
    surface.line(2, 12, 13, 12, pal.METAL_DARK);

    // 3. Drive bay recess via ASCII sprite grid
    surface.spr(['........', '.######.', '........'], 4, 6, {
      '#': pal.SHADOW,
    });

    // 4. Deterministic dust speckles
    if (state === 'dusty') {
      for (let i = 0; i < 4; i++) {
        const dx = 3 + ((rng() * 10) | 0);
        const dy = 4 + ((rng() * 8) | 0);
        surface.put(dx, dy, pal.DUST);
      }
    }

    // 5. Emissive status LED (blinks on frame 1)
    const ledColor =
      state === 'faulty'
        ? pal.FAULT_RED
        : frame === 0
          ? pal.LED_GREEN
          : pal.SHADOW;
    surface.put(11, 5, ledColor);

    // 6. Outer contour + code-coupled metadata
    surface.autoOutline(ctx.style.outlineIndex);
    ctx.anchor('led', 11, 5);
    ctx.anchor('foot', 8, 13);
    ctx.hitbox('body', 1, 2, 14, 12);
  },
};
```

---

## 6. Known Gotchas and Anti-Patterns

- **DO NOT** allocate or write palette index `255` (`TRANSPARENT_INDEX`) as a visible color; it is permanently reserved for binary alpha `0`.
- **DO NOT** use `Math.random()` in `assets/**`, `styles/**`, or `src/core/**`; always use `ctx.rng()` or `mulberry32` / `hashf`.
- **DO NOT** write raw `#rrggbb` hex strings inside `assets/**`; all colors must resolve through `StylePack` palette indices.
- **DO NOT** pass fractional coordinates without integer truncation (`x | 0`), and **DO NOT** import `.png`/`.svg` files or DOM/Canvas APIs.
- **DO NOT** commit `.pixelforge/sheets/*.contact.png` or third-party reference photos to Git.
- **DO** emit `ctx.anchor()` and `ctx.hitbox()` in the same `render(ctx)` pass that draws the pixels so metadata never drifts.
- **DO** run `pixelforge check` before `pixelforge render --sheet` on every iteration.

---

## 7. Skill Completion Checklist

- [ ] Silhouette, layer order, and anchor plan defined before coding
- [ ] `assets/<pack>/<id>.asset.ts` strictly typed with zero `any`, zero raw hex, zero `Math.random`
- [ ] `pixelforge check <id>` exits with code `0` (all 8 static + runtime guards pass)
- [ ] `pixelforge render <id> --sheet` inspected visually and refined (2–4 surgical passes max)
- [ ] `pnpm typecheck`, `pnpm test`, `pnpm lint`, and `pnpm build` exit with code `0`
- [ ] `.pixelforge/` scratch artifacts remain untracked
