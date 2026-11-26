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


def _draw_floor_and_walls(a: Asset, p: PaletteLookup) -> prefabs.IsoRoomGeometry:
    is_night = a.state == "night"
    floor_base = p.FLOOR_D if is_night else p.FLOOR_M
    floor_alt = p.VOID if is_night else p.FLOOR_D
    left_wall = p.WALL_D if is_night else p.WALL_L
    right_wall = p.WALL_D if is_night else p.WALL_M

    room = prefabs.iso_room_shell(
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
    return room


def _draw_window(a: Asset, p: PaletteLookup, room: prefabs.IsoRoomGeometry) -> None:
    is_night = a.state == "night"

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

    prefabs.iso_room_window(
        a,
        room,
        "left",
        u0=0.38,
        u1=0.78,
        v0=0.20,
        v1=0.62,
        frame=p.METAL_M,
        sky=p.WINDOW_SKY,
        outline=p.INK,
        mullion=p.METAL_M,
        cols=2,
        rows=2,
        glint=p.GLASS_L,
        sill=p.METAL_L,
        scene=_draw_vista,
        spill_color=p.FLOOR_L,
        spill_secondary=p.TILE_L if is_night else p.FLOOR_M,
        spill_depth=0.34,
        spill_near_ratio=0.32 if is_night else 0.72,
        spill_far_ratio=0.05 if is_night else 0.18,
    )


def _draw_desk_and_slots(
    a: Asset,
    p: PaletteLookup,
    room: prefabs.IsoRoomGeometry,
) -> prefabs.IsoDeskSlots:
    # Rectangular PC desk tucked flush against the right back wall near the room corner.
    shadow_plane = ((162, 83), (238, 121), (134, 97))
    with prefabs.clipped_pane(a, shadow_plane) as sp:
        sp.surface.data[sp.mask] = p.VOID
        sp.surface.dither(
            0,
            0,
            sp.width,
            sp.height,
            255,
            p.VOID,
            pattern="checker",
            ratio=0.5,
            mask="opaque",
        )

    desk_x, desk_y = room.wall_box_center(
        "right",
        74,
        28,
        19,
        along=0.0,
        margin=1,
        corner_margin=4,
    )
    slots = prefabs.iso_desk_set(
        a,
        desk_x,
        desk_y,
        74,
        28,
        leg_h=15,
        top_h=4,
        top=p.WOOD_L,
        left=p.WOOD_M,
        right=p.WOOD_D,
        leg_top=p.METAL_M,
        leg_left=p.METAL_D,
        leg_right=p.VOID,
        outline=p.INK,
        highlight=p.WOOD_L,
        mat_color=p.METAL_D,
        mat_w=40,
        chair_u=0.45,
        chair_pull_out=10,
        chair_seat_w=12,
        chair_seat_d=12,
        chair_seat_h=3,
        chair_back_h=10,
        chair_leg_h=5,
        chair_top=p.METAL_L,
        chair_left=p.METAL_M,
        chair_right=p.METAL_D,
        chair_back=p.METAL_M,
        chair_leg=p.INK,
        chair_facing="ne",
        shadow_color=p.VOID,
    )

    # Side floor rack stand beside the right end of the desk
    prefabs.contact_shadow(a, 242, 143, 12, 6, color=p.VOID, dither_ratio=0.5)
    prefabs.iso_rack(
        a,
        242,
        136,
        16,
        16,
        6,
        top=p.METAL_H,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        anchor="center",
    )
    return slots


def _draw_breaker_panel(a: Asset, p: PaletteLookup) -> None:
    prefabs.wall_panel(
        a,
        p0=(240, 74),
        p1=(258, 83),
        p2=(240, 100),
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
    room = _draw_floor_and_walls(a, p)
    _draw_window(a, p, room)
    portal_pt = prefabs.iso_portal_door(
        a,
        room,
        "left",
        u0=0.08,
        u1=0.25,
        v0=0.26,
        v1=1.0,
        frame=p.WOOD_D,
        panel=p.WOOD_M,
        recess=p.WOOD_D,
        handle=p.HAIR_Y,
        outline=p.INK,
        window=p.WINDOW_SKY,
        threshold=p.METAL_D,
    )
    slots = _draw_desk_and_slots(a, p, room)
    _draw_breaker_panel(a, p)

    mon_pt = slots.top_point(0.44, 0.34)
    lamp_pt = slots.top_point(0.14, 0.46)
    pc_pt = slots.top_point(0.86, 0.45)
    kbd_pt = slots.top_point(0.43, 0.68)
    mouse_pt = slots.top_point(0.61, 0.68)

    a.anchor_slots("hardware_", (mon_pt, lamp_pt, (242, 134)))
    a.anchor("breaker", 249, 89)
    a.anchor("desk_pc", pc_pt[0], pc_pt[1])
    a.anchor("desk_keyboard", kbd_pt[0], kbd_pt[1])
    a.anchor("desk_mouse", mouse_pt[0], mouse_pt[1])
    a.anchor("portal_homelab", portal_pt[0], portal_pt[1])

    a.hitbox("desk", 134, 63, 104, 72)
    a.hitbox("rack", 226, 128, 32, 22)
    a.hitbox("breaker", 240, 74, 18, 35)
    a.hitbox("room", 48, 6, 224, 186)
