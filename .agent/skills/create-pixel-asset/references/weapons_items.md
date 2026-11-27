# Weapons, Tools, Consumables & Icons (`16×16` / `24×24`)

Author readable handheld weapons, tools, consumables, and compact `16×16` / `24×24` inventory icons with crisp orientation, value separation, and clean pixel clusters.

> **Shared Invariants & Gates:** Follow [../SKILL.md](../SKILL.md) for palette closure, determinism, 2-phase blockout-first workflow, `--strict-craft`, and `blind-critic` handoff.

---

## 1. Orientation: 45° Diagonal vs. Orthogonal

Choose orientation intentionally based on gameplay role and aspect ratio:

| Orientation | Best For | Why |
|---|---|---|
| **45° Diagonal** (bottom-left hilt → top-right tip) | Swords, daggers, axes, spears, wands, staves, pickaxes, wrenches | Maximizes length inside a square `16×16` / `24×24` icon (`~1.4×` span) and creates dynamic action silhouettes. |
| **Orthogonal / Upright** | Potions, scrolls, books, shields, chests, keys, HUD badges | Preserves bilateral symmetry, crisp horizontal liquid levels, and clean `1px` vertical/horizontal borders. |

- For standard HUD/toolbar icons, inspect `prefabs.ui_icon_16(...)` before authoring custom `spr()` grids.

---

## 2. Value Separation & Specular Edge

At `16×16` and `24×24`, every pixel counts:

- **Outer Ink Silhouette:** Wrap the entire item in `with a.layer("item", outline=p.INK):` (or `p.VOID`) so it separates cleanly on both `#0d1117` dark and `#e6edf3` light checkerboards.
- **Material Separation:** Never let hilt, crossguard, and blade share the same midtone value across their seam—use a `1px` dark divider (`p.INK` or ramp shadow) or a contrasting metal/wood/gem ramp.
- **Directional Specular Edge:** Place the brightest ramp tone (`WHITE` or `METAL_H`) along the **top-left** cutting edge and upper guard; keep the **bottom-right** edge in the shadow tone (`METAL_D` / `WOOD_D`).
- **Emissive Discipline:** Reserve `emissive` tokens (`LED_C`, `SPARK`, `LED_P`) strictly for magical runes, potion cores, or power cells—never for ordinary steel highlights.

---

## 3. `cleanup_jaggies()` & Anti-Pillow-Shading Rules

- **Jaggy Cleanup on Diagonals:** Diagonal blades and curved flasks easily form `2×1` + `1×1` L-corner stair-steps (`craft-jaggies`). Run `a.cleanup_jaggies()` inside the item layer after drawing `line()`/`polygon()`/`ellipse()` strokes, then inspect the zoomed panel ruler to verify clean `1px` diagonal runs.
- **No Pillow Shading (`craft-pillow-shading`):**
  - **Wrong:** Placing bright pixels in the dead center of a blade/shield/flask and stepping darker toward all four edges.
  - **Right:** Shade directionally along `style.lighting_angle` (`top-left` lit, `bottom-right` shaded) using `a.shade_ramp(ramp, lighting_angle="top-left")` inside `clip="opaque"`, or explicit upper-left highlight strips.

---

## 4. Few-Shot Recipe — 45° Diagonal Blade (`16×16`)

```python
from pixelforge import Asset, AssetSpec

SPEC = AssetSpec(
    id="iron_shortsword",
    style_id="topdown-rpg",
    width=16,
    height=16,
    perspective="top-down",
    states=("default", "enchanted"),
    frames=1,
    seed=608,
)


def render(a: Asset) -> None:
    p = a.pal
    blade_lit = p.CYAN if a.state == "enchanted" else p.WHITE

    with a.layer("sword", outline=p.INK):
        # Pommel & grip (bottom-left)
        a.put(2, 13, p.GOLD_M)
        a.line(3, 12, 5, 10, p.BARK_M)
        # Crossguard (perpendicular to 45° blade)
        a.line(4, 8, 8, 12, p.GOLD_M)
        a.put(5, 9, p.GOLD_L)
        # Blade (top-right) with directional top-left edge highlight
        a.line(6, 9, 13, 2, p.METAL_M)
        a.line(6, 8, 12, 2, blade_lit)
        a.line(7, 9, 13, 3, p.METAL_D)
        a.cleanup_jaggies()

    a.anchor("grip", 4, 11, kind="hand")
    a.anchor("tip", 13, 2, kind="part")
    a.hitbox("bounds", 1, 1, 14, 14)
```

---

## 5. Weapons & Items Anti-Patterns

- **Pillow-Shaded Blades/Flasks:** Bright center stripe surrounded on both sides by dark borders without directional light.
- **Broken Diagonal Outlines:** Thick `2px` L-corners on 45° edges—always run `a.cleanup_jaggies()` and inspect at `1×`.
- **Missing Grip Anchor:** Weapons without `a.anchor("grip", ..., kind="hand")` cannot snap cleanly to character `hand_left` / `hand_right` anchors.
- **Unreadable `1×` Silhouette:** Low-contrast handles or thin `1px` staves without an `outline=p.INK` contour disappearing on dark/light backgrounds.
