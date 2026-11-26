# Declarative Scenes (`*.scene.py`), `compose`, & Spatial Ergonomics

## 1. Declarative `*.scene.py` Modules

A `.scene.py` module composes a parent room/desk `.asset.py` with mounted prop `.asset.py` modules into a unified compiled sprite, spritesheet, emissive mask, and manifest entry.

```python
from pixelforge import SceneMountSpec, SceneSpec

SCENE = SceneSpec(
    id="homelab_desk_scene",
    parent_id="bedroom_desk_iso",
    style_id="homelab-16bit",
    depth_sort="iso_y",
    strict_bounds=True,
    strict_perspective=True,
    mounts=(
        SceneMountSpec(
            prop_id="monitor_iso",
            anchor="hardware_0",
            prop_anchor="mount_bottom",
            state_map={"day": "idle", "night": "active"},
        ),
        SceneMountSpec(
            prop_id="desk_lamp_iso",
            anchor="hardware_1",
            prop_anchor="mount_bottom",
            z_index=1,
        ),
    ),
)
```

### Key `SceneSpec` & `SceneMountSpec` Fields
- `parent_id`: ID of the parent `.asset.py` module.
- `style_id` / `states` / `frames` / `fps`: Optional overrides; inherited from `parent_id` when omitted.
- `depth_sort`: `"iso_y"` (isometric Y-sort + `z_index` tie-break) or `"z_index"` (explicit layering).
- `strict_bounds=True`: Fails if any mounted prop clips outside the parent canvas.
- `strict_perspective=True`: Fails if any mounted prop's `perspective` differs from the parent.
- `state_map`: Maps parent scene states (e.g., `"day"`, `"night"`) to prop states (e.g., `"idle"`, `"active"`).
- `offset_x`, `offset_y`, `z_index`: Fine-grained mount offsets and layer ordering.

---

## 2. Ad-Hoc Composition CLI (`pixelforge compose`)

Discover parent anchors and prop anchors first:
```bash
uv run pixelforge inspect assets bedroom_desk_iso
uv run pixelforge inspect scenes
```

Test-mount props onto a parent asset before writing `.scene.py`:
```bash
uv run pixelforge compose bedroom_desk_iso \
  --mount monitor_iso@hardware_0:mount_bottom \
  --mount desk_lamp_iso@hardware_1:mount_bottom \
  --state night --strict-bounds --strict-perspective --sheet
```

---

## 3. Spatial Ergonomics & Scene Coherence

Enforce physical room ergonomics alongside pixel-level cleanliness:

1. **Wall-Hugging Furniture Placement (`1–3px` Baseboard Clearance):**
   - Place desks, racks, shelves, beds, and workbenches flush against a back wall via `room.wall_box_center(wall, w, d, h, along=..., margin=2, corner_margin=...)` on `IsoRoomGeometry` (pass `h=leg_h + top_h` for `iso_desk`/`iso_workbench`, or `h=h` for `iso_rack`/`iso_shelf`/`iso_drawer_unit`).
   - Avoid floating furniture in the center of the room unless intentionally freestanding (rug, central island, task chair).
   - Ground floor-standing furniture with `contact_shadow(...)` or `cast_shadow(...)`.
2. **Functional Furniture Proportions:**
   - Author workstation desks as **rectangular slabs** (`long_span >= 2 * depth`, e.g., `w=74, d=28` along right wall or `w=28, d=74` along left wall) so monitors, keyboards, mice, and towers have realistic working depth.
   - Reserve compact/square footprints (`12x12`–`16x16`) for side racks, drawer pedestals, and task chairs.
3. **Consistent Isometric Orientation & Facing:**
   - **Right-wall desk (`wall="right"`, long axis along `+u` NW–SE):** User sits on SW side facing NE toward the wall; mount SW-facing peripherals and pair with `iso_chair(..., facing="ne")`.
   - **Left-wall desk (`wall="left"`, long axis along `+v` NE–SW):** User sits on SE side facing NW toward the wall; orient peripherals SE-facing and pair with `iso_chair(..., facing="nw")`.
   - Mount wall fixtures (`iso_window`, `wall_panel`, `wall_ac_unit`, `wall_whiteboard`, `iso_wall_shelf`) via `room.left_wall_plane(...)` / `room.right_wall_plane(...)`.
4. **Complete Functional Prop Kits & Zero Duplication:**
   - A PC workstation should provide: **monitor + keyboard + mouse + PC tower (or laptop) + chair** (plus optional `desk_lamp_iso`, `network_switch_iso`, `coffee_mug_iso`).
   - **Zero baked-in vs. mounted duplication:** Never draw static monitor, keyboard, mouse, tower, or lamp pixels directly into the parent room `.asset.py` when those items are mounted via `.scene.py` or `pixelforge compose`.
