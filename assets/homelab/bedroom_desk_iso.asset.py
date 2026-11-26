"""Isometric Tier-1 bedroom homelab scene (`320x200` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup, prefabs

SPEC = AssetSpec(
    id="bedroom_desk_iso",
    style_id="homelab-16bit",
    width=320,
    height=200,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=42,
)

_FLOOR_CX = 160
_FLOOR_CY = 136
_FLOOR_HW = 112
_FLOOR_HH = 56
_WALL_H = 74


def _draw_floor_and_walls(a: Asset, p: PaletteLookup) -> None:
    is_night = a.state == "night"
    floor_base = p.FLOOR_D if is_night else p.FLOOR_M
    floor_alt = p.VOID if is_night else p.FLOOR_D
    left_wall = p.WALL_D if is_night else p.WALL_L
    right_wall = p.WALL_D if is_night else p.WALL_M

    prefabs.iso_room_shell(
        a,
        _FLOOR_CX,
        _FLOOR_CY,
        _FLOOR_HW,
        _FLOOR_HH,
        _WALL_H,
        floor=floor_base,
        left_wall=left_wall,
        right_wall=right_wall,
        floor_alt=floor_alt,
        floor_dither_ratio=0.12,
        baseboard=(p.WOOD_M, p.WOOD_D),
        wall_seam=p.WALL_D,
        outline=p.INK,
    )
    prefabs.iso_floor_pattern(
        a,
        _FLOOR_CX,
        _FLOOR_CY,
        _FLOOR_HW,
        _FLOOR_HH,
        color=p.FLOOR_D,
        step=24,
        mode="planks",
    )


def _draw_window(a: Asset, p: PaletteLookup) -> None:
    is_night = a.state == "night"
    win_p0 = (76, 64)
    win_p1 = (122, 41)
    win_p2 = (76, 98)

    def _draw_vista(pane: prefabs.ClippedPane) -> None:
        if is_night:
            prefabs.sky_backdrop(pane, bands=(p.VOID, p.WINDOW_SKY, p.SCREEN_D))
            prefabs.starfield(pane, count=9, color=p.STAR, seed=a.seed)
            prefabs.moon(
                pane,
                0.72,
                0.28,
                radius=3,
                color=p.WHITE,
                crater_color=p.SMOKE,
                crescent=True,
            )
            prefabs.horizon_silhouette(
                pane,
                color=p.WALL_D,
                accent=p.WARM_AMBER,
                mode="city",
                base_v=0.76,
                seed=a.seed,
            )
            return

        prefabs.sky_backdrop(pane, bands=(p.SOLAR_B, p.GLASS_L, p.SCREEN_L))
        prefabs.sun(pane, 0.28, 0.28, radius=3, color=p.HAIR_Y, halo=p.WHITE)
        prefabs.clouds(
            pane,
            color=p.WHITE,
            shade_color=p.SMOKE,
            count=2,
            phase=0.15,
            seed=a.seed,
        )
        prefabs.horizon_silhouette(
            pane,
            color=p.WALL_M,
            mode="city",
            base_v=0.78,
            seed=a.seed,
        )

    prefabs.iso_window(
        a,
        p0=win_p0,
        p1=win_p1,
        p2=win_p2,
        frame=p.METAL_M,
        sky=p.WINDOW_SKY,
        outline=p.INK,
        mullion=p.METAL_M,
        cols=2,
        rows=2,
        glint=p.GLASS_L,
        sill=p.METAL_L,
        scene=_draw_vista,
    )

    # Crisp isometric floor light spill using strictly non-emissive floor tokens.
    prefabs.window_light_spill(
        a,
        points=((78, 122), (120, 101), (154, 118), (112, 139)),
        color=p.FLOOR_L,
        secondary_color=p.TILE_L if is_night else p.FLOOR_M,
        pattern="bayer4",
        near_ratio=0.32 if is_night else 0.72,
        far_ratio=0.05 if is_night else 0.18,
        mask="opaque",
    )


def _draw_desk_and_slots(a: Asset, p: PaletteLookup) -> None:
    is_night = a.state == "night"

    prefabs.contact_shadow(a, 152, 122, 34, 16, color=p.VOID, dither_ratio=0.5)
    prefabs.iso_desk(
        a,
        152,
        108,
        44,
        44,
        leg_h=18,
        top_h=5,
        top=p.WOOD_L,
        left=p.WOOD_M,
        right=p.WOOD_D,
        leg_top=p.METAL_M,
        leg_left=p.METAL_D,
        leg_right=p.VOID,
        outline=p.INK,
        highlight=p.WOOD_L,
        mat_color=p.METAL_D,
        mat_w=44,
    )

    # Side floor rack stand for AI cluster node
    prefabs.iso_rack(
        a,
        218,
        138,
        18,
        18,
        6,
        top=p.METAL_H,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        anchor="center",
    )

    # Desk lamp on back corner of desk (emissive warm glow at night)
    a.rect(149, 86, 2, 7, p.METAL_H)
    a.rect(147, 84, 6, 3, p.METAL_M)
    if is_night:
        a.rect(148, 86, 4, 1, p.WARM_LAMP)


def _draw_breaker_panel(a: Asset, p: PaletteLookup) -> None:
    prefabs.wall_panel(
        a,
        p0=(224, 66),
        p1=(242, 75),
        p2=(224, 92),
        frame=p.METAL_H,
        recess=p.METAL_D,
        slot=p.VOID,
        outline=p.INK,
        cols=2,
        rows=3,
        status_led=p.LED_A if a.state == "night" else p.LED_G,
    )


def render(a: Asset) -> None:
    """Render the `bedroom_desk_iso` scene with hardware placement anchors."""
    p = a.pal
    _draw_floor_and_walls(a, p)
    _draw_window(a, p)
    _draw_desk_and_slots(a, p)
    _draw_breaker_panel(a, p)

    a.anchor_slots("hardware_", ((136, 104), (168, 112), (218, 136)))
    a.anchor("breaker", 233, 81)

    a.hitbox("desk", 108, 86, 88, 49)
    a.hitbox("breaker", 224, 66, 18, 35)
    a.hitbox("room", 48, 6, 224, 186)
