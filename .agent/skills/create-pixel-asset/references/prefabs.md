# Prefab Kits & Atmospheric Window Recipes (`pixelforge.prefabs`)

Import `from pixelforge import prefabs`. Every prefab is `StylePack`-agnostic (accepting explicit palette indices via `P = a.pal`), 100% deterministic, and compatible with both `Asset` and `Layer` targets.

> **Live Signature Discovery:** Run `uv run pixelforge inspect prefabs [category|name]` at any time to get exact parameter signatures and defaults directly from the codebase.

---

## 1. Architecture (`prefabs.architecture`)

- `iso_room_shell(target, cx, cy, hw, hh, wall_h, *, floor, left_wall, right_wall, floor_alt=None, floor_dither_ratio=0.12, baseboard=None, wall_seam=None, outline=None, lighting_angle=None) -> IsoRoomGeometry` — 2:1 isometric room diamond, two back walls, baseboard trim, corner seam, and outer ink contour. Returns `IsoRoomGeometry` with `left_wall_plane(u0, v0, u1, v1)`, `right_wall_plane(u0, v0, u1, v1)`, `floor_point(u, v)`, `wall_box_center(wall, w, d, h=0, *, along=0.5, margin=2, corner_margin=2)`, and `window_spill_quad(u0, u1, *, wall="left", depth=0.35, inset=0.025)`.
- `iso_floor_pattern(target, cx, cy, hw, hh, *, color, step=16, mode="planks")` — Bounded `"planks"`, `"tiles"`, or `"grid"` floor lines.
- `iso_raised_floor(...)`, `iso_rug(...)`, `iso_cable_tray(...)`, `iso_floor_zone(...)`, `iso_floor_threshold(...)` — Raised datacenter flooring, area rugs, cable trays, zone pads, and doorway thresholds.
- `iso_partition_wall(...)`, `iso_glass_partition(...)`, `iso_pillar(...)`, `wall_molding(...)` — Interior room dividers, glass partitions, pillars, and wall moldings.
- `iso_window(...)`, `front_window(...)`, `iso_window_glass_region(...)`, `front_window_glass_region(...)` — Isometric and `front-2.5d` windows with mullions, glass glint, sill, and optional clipped `scene(pane)` callback.
- `iso_door(...)`, `front_door(...)`, `wall_vent(...)`, `window_blinds(...)`, `window_curtains(...)` — Doors, louvered vents, blinds, and curtains.

---

## 2. Furniture (`prefabs.furniture`)

- **Workstations:** `iso_desk(...) -> IsoDeskSlots`, `iso_workbench(...)`, `iso_l_desk(...)`, `iso_side_table(...)`, `iso_coffee_table(...)`.
- **Storage & Racks:** `iso_rack(...) -> IsoRackSlots` (`front_style="bays"|"grille"|"glass_door"`), `iso_shelf(...) -> IsoShelfSlots`, `iso_wall_shelf(...)`, `iso_drawer_unit(...)`, `iso_nightstand(...)`, `iso_filing_cabinet(...)`, `iso_wardrobe(...)`, `iso_locker(...)`, `iso_mini_fridge(...)`.
- **Seating & Beds:** `iso_chair(..., facing="ne"|"nw"|"se"|"sw")`, `iso_armchair(...)`, `iso_sofa(...)`, `iso_bed(...)`.

---

## 3. Details (`prefabs.details`)

- **Shadows & Reflections:** `contact_shadow(...)`, `cast_shadow(...)`, `floor_reflection(...)`.
- **Cables & Power:** `iso_cable_run(...)`, `iso_cable_catenary(...)`, `power_strip(...)`, `wall_outlet(...)`, `wall_light_switch(...)`.
- **Wall Decor & Lighting:** `wall_panel(...)`, `wall_poster(...)`, `wall_ac_unit(...)`, `wall_whiteboard(...)`, `wall_thermostat(...)`, `wall_clock(...)`, `wall_corkboard(...)`, `wall_pegboard(...)`, `wall_neon_sign(...)`, `led_strip(...)`, `wall_sconce(...)`.

---

## 4. Atmosphere, Clipped Vistas & Light Spill (`prefabs.atmosphere`)

All atmospheric primitives accept either a `ClippedPane` (inside `scene=` or `with prefabs.clipped_pane(a, region) as pane:`) or `(target, region=...)` directly, supporting **both** `iso-2:1` planes `(p0, p1, p2)` and `front-2.5d` rectangles `(x, y, w, h)`:

- `clipped_pane(target, region)` — Auxiliary `IndexedSurface` + boolean glass mask preventing sky/weather bleed onto frames or mullions.
- `sky_backdrop(...)`, `sun(...)`, `moon(...)`, `starfield(...)`, `clouds(...)`, `horizon_silhouette(...)` (`"city"`, `"rooftops"`, `"hills"`, `"trees"`).
- `weather_rain(...)`, `weather_snow(...)`, `weather_lightning(...)`, `window_condensation(...)`, `dust_motes(...)`, `rising_steam(...)`.
- `eval_day_night_cycle(...)` / `day_night_cycle(...)` — Sweeps sky bands, sun/moon arc, stars, clouds, and horizon across `phase` (`0.0..1.0`), returning `CycleStep` (`spill_intensity`, `celestial_kind`).
- `window_light_spill(...)`, `light_beam(...)`, `point_light_spill(...)`, `screen_telemetry(...)` — Tapered ordered-dither floor/wall light projection and animated monitor telemetry.

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
- **NEVER emissive:** sky bands (`WINDOW_SKY`, `SOLAR_B`, `SCREEN_D`, `GLASS_D`, `GLASS_L`), clouds (`WHITE`, `SMOKE`), daytime sun (`HAIR_Y`), moon body (`WHITE`), rain/snow (`GLASS_L`, `WHITE`, `SMOKE`), horizon silhouettes (`WALL_D`, `WALL_M`), and interior `window_light_spill` / `light_beam` (`FLOOR_L`, `FLOOR_M`, `TILE_L`).
- **Intentionally emissive:** night `starfield` (`STAR`), optional distant lit city windows (`WARM_LAMP`), and powered interior LEDs/lamps (`LED_*`, `WARM_LAMP`).

---

## 5. Modular Characters & Avatars (`prefabs.characters`)

- **Pose & Cycles:** `eval_character_cycle(state, frame, frames, *, seed=0, seated=False) -> CharacterPose` (`"idle"`, `"walk"`, `"typing"`, `"alert"`).
- **Parts:** `avatar_legs(...) -> LegsAnchors`, `avatar_torso(...) -> TorsoAnchors`, `avatar_head(...) -> HeadAnchors`, `avatar_hair(..., style="short"|"parted"|"spiky"|"bob"|"ponytail"|"buzz")`, `avatar_accessory(..., kind="none"|"glasses"|"visor"|"headphones"|"headset"|"cap"|"badge")`.
- **Assembler & Palette Binding:** `CharacterPalette.from_lookup(pal, ...)` + `avatar_character(target, cx, foot_y, pal, *, state="idle", frame=0, frames=4, facing="front"|"iso-se"|"iso-sw", hair_style="parted", accessory="none")` (supports `PaletteLookup.with_overrides(...)` / `a.palette_override(...)` for skin/hair/outfit swaps).
