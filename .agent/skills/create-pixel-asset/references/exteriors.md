# Outdoor Environments & Exteriors (`iso-2:1`, `top-down`, `front-2.5d`)

Author outdoor props, foliage, buildings, terrain sheets, and exterior scenes using `pixelforge.core` primitives, `pixelforge.tilemap`, and `iso_y` scene composition.

> **Shared Invariants & Gates:** Follow [../SKILL.md](../SKILL.md) for palette closure, determinism, 2-phase blockout-first workflow, `--strict-craft`, and `blind-critic` handoff.

---

## 1. Perspective Selection

| Perspective | Best For | Key Primitives |
|---|---|---|
| **`iso-2:1`** | Isometric trees, cottages, fences, terrain blocks, multi-prop exterior dioramas | `iso_box`, `iso_tile`, `a.plane(p0, p1, p2)`, `SceneSpec(depth_sort="iso_y")` |
| **`top-down`** | RPG overworld trees, shrubs, roofs, roads, 47-tile blob terrain | `ellipse`, `capsule`, `bevel_rect`, `tilemap.autotile_terrain` |
| **`front-2.5d`** | Side-view building facades, storefronts, parallax horizons | `front_door`, `front_window`, `polygon`, `clipped_pane` |

---

## 2. Organic Trees & Foliage Clusters

Build trees and shrubs from **overlapping leaf clusters** rather than a single lollipop circle:

1. **Ground Contact Shadow:** Draw an `ellipse` (e.g. `p.VOID` or `p.INK`) at the base before the trunk.
2. **Trunk & Branches:** Use `capsule` or `polygon` inside `with a.layer("trunk", outline=p.INK):`, shaded on one side with `clip="opaque"`.
3. **Canopy Massing (Phase 1):** Overlap 3–5 `ellipse`/`circle` lobes inside `with a.layer("canopy", outline=p.INK):` to create an irregular, readable silhouette.
4. **Directional Volume & Leaf Texture (Phase 2):**
   - Wrap `with a.layer("canopy_shade", clip="opaque"):` and call `a.shade_ramp(ramp, lighting_angle="top-left", dither=True)` or paint offset upper-left highlight lobes.
   - Add deterministic leaf speckles via `a.scatter(count=..., colors=(...), mask="opaque")` and smooth stepped edges with `a.cleanup_jaggies()`.
5. **Anchor:** Emit `a.anchor("foot", cx, base_y, kind="ground")` at the trunk base so `iso_y` depth sorting places characters behind or in front of the canopy accurately.

---

## 3. Pitched Roofs & Building Facades

- **Pitched Roofs (`iso-2:1` / `front-2.5d`):**
  - Construct walls first with `iso_box` or `bevel_rect`.
  - Project roof slopes using `with a.plane(p0, p1, p2) as roof:` (or `polygon` for gable triangles) with a `1–2px` **eave overhang** past the wall silhouette so the roof reads distinctly at `1×`.
  - Add shingle or seam lines with `roof.grid(...)` or `roof.line(...)`, keeping the sunlit slope brighter than the shaded slope.
- **Building Facades:**
  - Combine `prefabs.front_door` / `prefabs.iso_door`, `prefabs.front_window` / `prefabs.iso_arched_window`, and `prefabs.wall_molding` (see [prefabs.md](prefabs.md)).
  - Use `clipped_pane` (`scene=_vista`) for windows so interior curtains/lights or sky reflections never bleed onto mullions.
  - Keep `emissive` tokens strictly on lit windows/lanterns (`WARM_LAMP`, `LED_A`), never on roof tiles or daytime sky.

---

## 4. Terrain Autotiling (`pixelforge.tilemap`)

Use `tilemap` to generate deterministic 16-tile cardinal or 47-tile blob sheets without manual tile-by-tile loops:

```python
from pixelforge import Asset, AssetSpec, tilemap

SPEC = AssetSpec(
    id="meadow_terrain",
    style_id="topdown-rpg",
    width=128,
    height=96,
    perspective="top-down",
    states=("default",),
    frames=1,
    seed=701,
)


def render(a: Asset) -> None:
    p = a.pal
    style = tilemap.AutotileStyle(
        fill=p.GRASS_M,
        edge=p.INK,
        highlight=p.GRASS_L,
        shadow=p.GRASS_D,
        detail=p.GRASS_D,
        inner_corner=p.INK,
    )
    tilemap.autotile_terrain(
        a,
        style,
        tile_w=16,
        tile_h=16,
        mode="blob47",
        columns=8,
        seed=a.seed,
    )
```

- `mode="blob47"` produces 47 canonical bitmasks (`canonical_blob47_masks()`); `mode="cardinal16"` produces 16 masks for paths/fences/cables.
- Use `tilemap.compute_grid_bitmasks(grid, mode="blob47")` to map a boolean occupancy grid to tile indices at runtime/build time.

---

## 5. `iso_y` Scene Composition

Compose outdoor buildings, trees, fences, and characters in a `.scene.py` module using `depth_sort="iso_y"`:

- Every prop `.asset.py` MUST emit a ground anchor (`a.anchor("foot", cx, ground_y, kind="ground")`) and match `prop_anchor="foot"` in `SceneMountSpec`.
- `depth_sort="iso_y"` sorts mounted props by their resolved ground `y` coordinate (with `z_index` as tie-breaker), ensuring trees/buildings occlude props behind them cleanly.
- Keep `strict_bounds=True` and `strict_perspective=True` enabled (see [scenes.md](scenes.md)).

---

## 6. Few-Shot Recipe — Isometric Pine / Oak Tree (`iso-2:1`)

```python
from pixelforge import Asset, AssetSpec

SPEC = AssetSpec(
    id="iso_oak_tree",
    style_id="sweetie-16",
    width=32,
    height=40,
    perspective="iso-2:1",
    states=("calm", "wind"),
    frames=2,
    fps=2,
    seed=512,
)


def render(a: Asset) -> None:
    p = a.pal
    sway = 1 if (a.state == "wind" and a.frame == 1) else 0

    a.ellipse(16, 35, 9, 4, p.BLACK)  # ground shadow
    with a.layer("trunk", outline=p.BLACK):
        a.capsule(16, 24, 16, 34, 2, p.BROWN)
        with a.layer("trunk_lit", clip="opaque"):
            a.rect(14, 24, 2, 10, p.ORANGE)

    with a.layer("canopy", outline=p.BLACK):
        a.ellipse(16 + sway, 17, 10, 8, p.DARK_GREEN)
        a.ellipse(11 + sway, 19, 6, 5, p.DARK_GREEN)
        a.ellipse(21 + sway, 19, 6, 5, p.DARK_GREEN)
        with a.layer("canopy_volume", clip="opaque"):
            a.ellipse(14 + sway, 14, 8, 6, p.GREEN)
            a.ellipse(12 + sway, 12, 4, 3, p.LIGHT_GREEN)
            a.scatter(count=10, colors=(p.DARK_GREEN, p.LIGHT_GREEN), mask="opaque")
        a.cleanup_jaggies()

    a.anchor("foot", 16, 35, kind="ground")
    a.hitbox("trunk", 13, 28, 6, 8)
```

---

## 7. Exterior Anti-Patterns

- **Lollipop Trees:** Single flat circle on a vertical stick without overlapping canopy lobes or ground shadow.
- **Unanchored Props:** Omitting `a.anchor("foot", ..., kind="ground")` breaks `iso_y` depth sorting in `.scene.py`.
- **Flat Facades Without Overhang:** Drawing roof edges flush with wall edges flattens `1×` readability.
- **Emissive Sky/Foliage:** Never assign `emissive` tokens to daytime sky, grass, or leaves.
