"""Animated frontal atmospheric & window vista showcase (`80x64` front-2.5d)."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup, prefabs

SPEC = AssetSpec(
    id="window_vistas_front",
    style_id="homelab-16bit",
    width=80,
    height=64,
    perspective="front-2.5d",
    states=("day", "cycle", "starry_night", "full_moon", "rain", "snow"),
    frames=6,
    fps=4,
    seed=1602,
)

_WIN_RECT = (14, 6, 52, 38)


def _draw_wall_and_floor(a: Asset, p: PaletteLookup) -> None:
    is_dark = a.state in ("starry_night", "full_moon", "rain")
    is_cycle_night = a.state == "cycle" and (a.frame / float(a.frames)) >= 0.50
    dim = is_dark or is_cycle_night

    a.rect(4, 2, 72, 48, p.WALL_D if dim else p.WALL_M)
    a.dither(
        4,
        2,
        72,
        48,
        None,
        p.VOID if dim else p.WALL_D,
        pattern="bayer4",
        ratio=0.14,
        mask="opaque",
    )
    a.rect(4, 48, 72, 2, p.WOOD_M)
    a.rect(4, 50, 72, 11, p.FLOOR_D if dim else p.FLOOR_M)
    a.rect(4, 2, 72, 59, p.INK, fill=False)


def _draw_window_and_beam(a: Asset, p: PaletteLookup) -> None:
    phase = a.frame / float(a.frames)
    beam_near = 0.65
    beam_far = 0.16
    beam_color = p.FLOOR_L
    beam_alt = p.WALL_L

    def _vista(pane: prefabs.ClippedPane) -> None:
        nonlocal beam_near, beam_far, beam_color, beam_alt
        st = a.state
        if st == "day":
            prefabs.sky_backdrop(pane, bands=(p.SOLAR_B, p.GLASS_L, p.SCREEN_L))
            prefabs.sun(pane, 0.25, 0.26, radius=3, color=p.HAIR_Y, halo=p.WHITE, rays=True)
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
                star_count=12,
                frame=a.frame,
                frames=a.frames,
                seed=a.seed,
            )
            beam_near = 0.72 * step.spill_intensity
            beam_far = 0.18 * step.spill_intensity
            if step.celestial_kind == "moon":
                beam_color = p.TILE_L
                beam_alt = p.FLOOR_D
            return

        if st == "starry_night":
            prefabs.sky_backdrop(pane, bands=(p.VOID, p.WINDOW_SKY, p.SCREEN_D))
            prefabs.starfield(
                pane,
                count=14,
                color=p.STAR,
                twinkle_color=p.WHITE,
                frame=a.frame,
                frames=a.frames,
                seed=a.seed,
            )
            prefabs.moon(pane, 0.76, 0.26, radius=3, color=p.WHITE, crescent=True)
            prefabs.horizon_silhouette(
                pane,
                color=p.WALL_D,
                accent=p.WARM_LAMP,
                mode="city",
                base_v=0.76,
                seed=a.seed,
            )
            beam_color = p.TILE_L
            beam_alt = p.FLOOR_D
            beam_near = 0.36
            beam_far = 0.08
            return

        if st == "full_moon":
            prefabs.sky_backdrop(pane, bands=(p.VOID, p.WINDOW_SKY, p.GLASS_D))
            prefabs.starfield(
                pane,
                count=8,
                color=p.STAR,
                twinkle_color=p.WHITE,
                frame=a.frame,
                frames=a.frames,
                seed=a.seed + 3,
            )
            prefabs.moon(
                pane,
                0.72,
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
                seed=a.seed + 7,
            )
            prefabs.horizon_silhouette(
                pane,
                color=p.WALL_D,
                accent=p.TILE_D,
                mode="hills",
                base_v=0.78,
                seed=a.seed,
            )
            beam_color = p.TILE_L
            beam_alt = p.FLOOR_D
            beam_near = 0.48
            beam_far = 0.12
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
                seed=a.seed + 11,
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
                count=20,
                phase=phase,
                slant=-0.14,
                length=0.18,
                seed=a.seed,
            )
            beam_color = p.TILE_L
            beam_alt = p.FLOOR_D
            beam_near = 0.30
            beam_far = 0.06
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
            seed=a.seed + 19,
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
            count=22,
            phase=phase,
            drift=0.09,
            seed=a.seed,
        )
        beam_color = p.FLOOR_L
        beam_alt = p.TILE_L
        beam_near = 0.52
        beam_far = 0.14

    prefabs.front_window(
        a,
        *_WIN_RECT,
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

    prefabs.light_beam(
        a,
        (16, 44, 48, 1),
        color=beam_color,
        secondary_color=beam_alt,
        dx=0,
        dy=15,
        spread=8,
        pattern="bayer4",
        near_ratio=beam_near,
        far_ratio=beam_far,
        mask="opaque",
    )


def render(a: Asset) -> None:
    """Render the `window_vistas_front` multi-state animated atmospheric showcase."""
    p = a.pal
    _draw_wall_and_floor(a, p)
    _draw_window_and_beam(a, p)
    a.anchor("window", 40, 25)
    a.anchor("sill", 40, 44)
    a.hitbox("window", 14, 6, 52, 38)
