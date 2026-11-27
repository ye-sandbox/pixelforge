# Characters & Creatures (`16×16` to `32×32`)

Author readable characters, NPCs, and creatures using `pixelforge.prefabs` (`avatar_character`, `eval_character_cycle`) or custom organic primitives with deterministic frame deltas and semantic anchors.

> **Shared Invariants & Gates:** Follow [../SKILL.md](../SKILL.md) for palette closure, determinism, 2-phase blockout-first workflow, `--strict-craft`, and `blind-critic` handoff.

---

## 1. Scale & Silhouette Rules (`16×16` to `32×32`)

- **16×16 (Micro / Chibi):** Emphasize head-to-body ratio (`~1:1`), `1px` outer ink outline (`outline=p.INK`), and 2–3 value steps per material. Avoid `1px` facial clutter—two `1×1` or `1×2` eyes carry expression.
- **24×24 (Standard RPG / Top-Down):** Room for distinct headgear, shoulder/arm separation, and clear `2–3px` stride deltas.
- **32×32 (Detailed / Isometric Avatar):** Full modular head, hair, torso, legs, and wearable accessories (`avatar_character`).
- **Silhouette First (Phase 1):** Always draw a ground contact shadow (`ellipse(..., p.INK)` or `p.VOID`) beneath `foot_y`, then block out limbs/torso/head inside `with a.layer(..., outline=p.INK):` before adding shading or eyes.

---

## 2. Modular Avatars (`avatar_character` & `eval_character_cycle`)

For humanoid NPCs and operators, use `prefabs.CharacterPalette.from_lookup(...)` and `prefabs.avatar_character(...)` (see [prefabs.md](prefabs.md)):

- **Cycle States (`CharacterCycleState`):** `"idle"`, `"walk"`, `"typing"`, `"alert"`.
- **Facings (`CharacterFacing`):** `"front"`, `"iso-se"`, `"iso-sw"`.
- **Hair Styles (`HairStyle`):** `"short"`, `"parted"`, `"spiky"`, `"bob"`, `"ponytail"`, `"buzz"`.
- **Accessories (`AccessoryKind`):** `"none"`, `"glasses"`, `"visor"`, `"headphones"`, `"headset"`, `"cap"`, `"badge"`.
- **Custom Part Composition:** Call `pose = prefabs.eval_character_cycle(state, frame, frames, seed=seed, seated=seated)` and drive `avatar_legs`, `avatar_torso`, `avatar_head`, `avatar_hair`, and `avatar_accessory` individually when you need custom props in `hand_left` / `hand_right`.

```python
from pixelforge import Asset, AssetSpec, prefabs

SPEC = AssetSpec(
    id="operator_npc",
    style_id="homelab-16bit",
    width=32,
    height=32,
    perspective="front-2.5d",
    states=("idle", "walk", "alert"),
    frames=4,
    fps=6,
    seed=204,
)

_STATE_MAP: dict[str, prefabs.CharacterCycleState] = {
    "idle": "idle",
    "walk": "walk",
    "alert": "alert",
}


def render(a: Asset) -> None:
    p = a.pal
    pal = prefabs.CharacterPalette.from_lookup(
        p,
        skin_light="SKIN_L",
        skin_mid="SKIN_M",
        skin_dark="SKIN_D",
        hair_base="HAIR_B",
        hair_highlight="HAIR_Y",
        hair_shadow="HAIR_K",
        shirt_base="SHIRT_BLUE",
        shirt_shade="SOLAR_B",
        shirt_highlight="WHITE",
        pants_base="WALL_M",
        pants_shade="WALL_D",
        shoe="INK",
        eye="INK",
        outline="INK",
        accessory_base="METAL_L",
        accessory_accent="LED_C",
    )
    a.ellipse(16, 29, 6, 2, p.VOID)
    prefabs.avatar_character(
        a,
        16,
        29,
        pal,
        state=_STATE_MAP[a.state],
        frame=a.frame,
        frames=a.frames,
        facing="front",
        hair_style="parted",
        accessory="headset",
        seed=a.seed,
    )
```

---

## 3. Squash-and-Stretch & Frame Deltas

`pixelforge check --strict-craft` flags **no-op animation frames** (`craft-noop-delta`) where consecutive frames produce identical buffers:

- **Idle (`2–4` frames):** Subtle `1px` chest/head `bob_y` or deterministic blink (`frame == blink_slot`)—never vibrate the `foot` anchor.
- **Walk (`4` frames):** 4-beat gait (`stride` `-1, 0, +1, 0`) paired with `-1px` vertical lift on passing/contact beats and opposing arm swing (`arm_left_dy = stride`, `arm_right_dy = -stride`).
- **Squash-and-Stretch (Creatures / Jumps):** Expand `rx` by `+1px` and compress `ry` by `-1px` while keeping the `foot` anchor pinned to the ground contact shadow.

---

## 4. Required Anchors & Hitboxes

Emit consistent semantic anchors in every character `render(a)` pass (handled automatically by `avatar_character(..., emit_metadata=True)`):

- **`foot` (`kind="ground"`):** Bottom-center contact pixel `(cx, foot_y)` used for `iso_y` sorting and tile placement.
- **`core` (`kind="center"`):** Torso/body center for projectile targeting, hit flashes, and particle emitters.
- **`hand` / `hand_left` / `hand_right` (`kind="part"`):** Attachment points for held weapons, tools, or items.
- **`body` (`a.hitbox(..., kind="character")`):** Tight integer bounding box around the character silhouette (excluding wide ground shadow).

---

## 5. Character Anti-Patterns

- **Floating Feet:** Drawing characters without a ground contact shadow or shifting `foot` Y between idle/walk frames.
- **Pillow-Shaded Blobs:** Shading from a bright center dot outward instead of directional `top-left` volume (`clip="opaque"` + `shade_ramp`).
- **No-Op Frames:** Declaring `frames=4` where `frame 1` and `frame 2` are pixel-identical.
- **Unisolated Visor/Eye Emissives:** Never use `emissive` tokens (`VISOR_C`, `LED_C`) for ordinary sclera or shirt highlights.
