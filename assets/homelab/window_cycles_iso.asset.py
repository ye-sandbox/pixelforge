"""Animated isometric atmospheric & window cycle showcase (`96x80` iso-2:1)."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup, prefabs

SPEC = AssetSpec(
    id="window_cycles_iso",
    style_id="homelab-16bit",
    width=96,
    height=80,
    perspective="iso-2:1",
    states=("day", "cycle", "starry_night", "full_moon", "rain", "snow"),
    frames=6,
    fps=2,
    seed=1601,
)


def _draw_room(a: Asset, p: PaletteLookup) -> prefabs.IsoRoomGeometry:
    is_dark = a.state in ("starry_night", "full_moon", "rain")
    is_cycle_night = a.state == "cycle" and (a.frame / float(a.frames)) >= 0.50
    dim = is_dark or is_cycle_night
    room = prefabs.iso_room_shell(
        a,
        48,
        56,
        40,
        20,
        40,
        floor=p.FLOOR_D if dim else p.FLOOR_M,
        left_wall=p.WALL_D if dim else p.WALL_L,
        right_wall=p.WALL_D if dim else p.WALL_M,
        floor_alt=p.VOID if dim else p.FLOOR_D,
        floor_dither_ratio=0.14,
        baseboard=(p.WOOD_M, p.WOOD_D),
        wall_seam=p.WALL_D,
        outline=p.INK,
    )
    prefabs.iso_floor_pattern(a, 48, 56, 40, 20, color=p.FLOOR_D, step=18, mode="planks")
    vent_p0, vent_p1, vent_p2 = room.right_wall_plane(0.25, 0.525, 0.60, 0.85)
    prefabs.wall_vent(
        a,
        p0=vent_p0,
        p1=vent_p1,
        p2=vent_p2,
        frame=p.METAL_M,
        slat=p.VOID,
        outline=p.INK,
        slats=3,
    )
    return room


def _draw_window_and_spill(a: Asset, p: PaletteLookup, room: prefabs.IsoRoomGeometry) -> None:
    phase = a.frame / float(a.frames)
    spill_near = 0.65
    spill_far = 0.16
    spill_color = p.FLOOR_L
    spill_alt = p.FLOOR_M

    def _vista(pane: prefabs.ClippedPane) -> None:
        nonlocal spill_near, spill_far, spill_color, spill_alt
        st = a.state
        if st == "day":
            prefabs.sky_backdrop(pane, bands=(p.SOLAR_B, p.GLASS_L, p.SCREEN_L))
            prefabs.sun(pane, 0.28, 0.28, radius=3, color=p.HAIR_Y, halo=p.WHITE, rays=True)
            prefabs.clouds(
                pane,
                color=p.WHITE,
                shade_color=p.SMOKE,
                count=2,
                phase=phase,
                seed=a.seed,
            )
            prefabs.horizon_silhouette(
                pane,
                color=p.WALL_D,
                mode="city",
                base_v=0.76,
                seed=a.seed,
            )
            return

        if st == "cycle":
            step = prefabs.day_night_cycle(
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
                horizon_mode="city",
                star_count=10,
                frame=a.frame,
                frames=a.frames,
                seed=a.seed,
            )
            spill_near = 0.72 * step.spill_intensity
            spill_far = 0.18 * step.spill_intensity
            if step.celestial_kind == "moon":
                spill_color = p.TILE_L
                spill_alt = p.FLOOR_D
            return

        if st == "starry_night":
            prefabs.sky_backdrop(pane, bands=(p.VOID, p.WINDOW_SKY, p.SCREEN_D))
            prefabs.starfield(
                pane,
                count=12,
                color=p.STAR,
                twinkle_color=p.WHITE,
                frame=a.frame,
                frames=a.frames,
                seed=a.seed,
            )
            prefabs.moon(pane, 0.74, 0.28, radius=3, color=p.WHITE, crescent=True)
            prefabs.horizon_silhouette(
                pane,
                color=p.WALL_D,
                accent=p.WARM_LAMP,
                mode="city",
                base_v=0.76,
                seed=a.seed,
            )
            spill_color = p.TILE_L
            spill_alt = p.FLOOR_D
            spill_near = 0.36
            spill_far = 0.08
            return

        if st == "full_moon":
            prefabs.sky_backdrop(pane, bands=(p.VOID, p.WINDOW_SKY, p.GLASS_D))
            prefabs.starfield(
                pane,
                count=7,
                color=p.STAR,
                twinkle_color=p.WHITE,
                frame=a.frame,
                frames=a.frames,
                seed=a.seed + 5,
            )
            prefabs.moon(
                pane,
                0.74,
                0.28,
                radius=4,
                color=p.WHITE,
                crater_color=p.SMOKE,
                halo=p.GLASS_L,
            )
            prefabs.clouds(
                pane,
                color=p.SCREEN_L,
                shade_color=p.SCREEN_D,
                count=2,
                phase=phase,
                seed=a.seed + 9,
            )
            prefabs.horizon_silhouette(
                pane,
                color=p.WALL_D,
                accent=p.TILE_D,
                mode="hills",
                base_v=0.78,
                seed=a.seed,
            )
            spill_color = p.TILE_L
            spill_alt = p.FLOOR_D
            spill_near = 0.48
            spill_far = 0.12
            return

        if st == "rain":
            prefabs.sky_backdrop(pane, bands=(p.VOID, p.WALL_M, p.GLASS_D))
            prefabs.clouds(
                pane,
                color=p.METAL_M,
                shade_color=p.METAL_D,
                count=3,
                phase=phase,
                min_v=0.10,
                max_v=0.34,
                seed=a.seed + 13,
            )
            prefabs.horizon_silhouette(
                pane,
                color=p.WALL_D,
                mode="rooftops",
                base_v=0.78,
                seed=a.seed,
            )
            prefabs.weather_rain(
                pane,
                color=p.GLASS_L,
                splash_color=p.WHITE,
                count=18,
                phase=phase * 2.0,
                slant=-0.16,
                length=0.18,
                seed=a.seed,
            )
            spill_color = p.TILE_L
            spill_alt = p.FLOOR_D
            spill_near = 0.30
            spill_far = 0.06
            return

        # snow
        prefabs.sky_backdrop(pane, bands=(p.SCREEN_D, p.GLASS_D, p.METAL_M))
        prefabs.clouds(
            pane,
            color=p.SMOKE,
            shade_color=p.METAL_L,
            count=2,
            phase=phase,
            min_v=0.10,
            max_v=0.32,
            seed=a.seed + 21,
        )
        prefabs.horizon_silhouette(
            pane,
            color=p.WALL_M,
            accent=p.WHITE,
            mode="trees",
            base_v=0.80,
            seed=a.seed,
        )
        prefabs.weather_snow(
            pane,
            color=p.WHITE,
            alt_color=p.SMOKE,
            count=20,
            phase=phase * 2.0,
            drift=0.09,
            seed=a.seed,
        )
        spill_color = p.FLOOR_L
        spill_alt = p.TILE_L
        spill_near = 0.52
        spill_far = 0.14

    win_p0, win_p1, win_p2 = room.left_wall_plane(0.15, 0.275, 0.90, 0.90)
    prefabs.iso_window(
        a,
        p0=win_p0,
        p1=win_p1,
        p2=win_p2,
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

    prefabs.window_light_spill(
        a,
        points=room.window_spill_quad(0.15, 0.90, wall="left", depth=0.75, inset=0.025),
        color=spill_color,
        secondary_color=spill_alt,
        pattern="bayer4",
        near_ratio=spill_near,
        far_ratio=spill_far,
        mask="opaque",
    )


def render(a: Asset) -> None:
    """Render the `window_cycles_iso` multi-state animated atmospheric showcase."""
    p = a.pal
    room = _draw_room(a, p)
    _draw_window_and_spill(a, p, room)
    a.anchor("window", 29, 29)
    spill_ax, spill_ay = room.floor_point(0.39, 0.46)
    a.anchor("floor_spill", spill_ax, spill_ay)
    a.hitbox("window", 14, 9, 31, 41)
