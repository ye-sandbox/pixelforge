"""Isometric multi-room bedroom + homelab showcase (`360x220` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup, prefabs

SPEC = AssetSpec(
    id="multiroom_homelab_iso",
    style_id="homelab-16bit",
    width=360,
    height=220,
    perspective="iso-2:1",
    states=("day", "night"),
    frames=1,
    fps=1,
    seed=108,
)

_FLOOR_CX = 180
_FLOOR_CY = 148
_FLOOR_HW = 128
_FLOOR_HH = 64
_WALL_H = 72


def _draw_shell_and_zones(
    a: Asset,
    p: PaletteLookup,
) -> tuple[prefabs.IsoRoomGeometry, prefabs.IsoRoomGeometry, prefabs.IsoRoomGeometry]:
    is_night = a.state == "night"
    room = prefabs.iso_room_shell(
        a,
        _FLOOR_CX,
        _FLOOR_CY,
        _FLOOR_HW,
        _FLOOR_HH,
        _WALL_H,
        floor=p.FLOOR_D if is_night else p.FLOOR_M,
        left_wall=p.WALL_D if is_night else p.WALL_L,
        right_wall=p.WALL_D if is_night else p.WALL_M,
        floor_alt=p.VOID if is_night else p.FLOOR_D,
        floor_dither_ratio=0.10,
        baseboard=(p.WOOD_M, p.WOOD_D),
        wall_seam=p.WALL_D,
        outline=p.INK,
    )

    prefabs.iso_floor_zone(
        a,
        room,
        0.0,
        0.0,
        0.48,
        1.0,
        fill=p.WOOD_D if is_night else p.WOOD_M,
        alt=p.VOID if is_night else p.WOOD_D,
        pattern_color=p.VOID if is_night else p.WOOD_D,
        mode="planks",
        step=14,
        dither_ratio=0.10,
    )
    prefabs.iso_floor_zone(
        a,
        room,
        0.52,
        0.0,
        1.0,
        1.0,
        fill=p.TILE_D if is_night else p.FLOOR_M,
        alt=p.FLOOR_D,
        pattern_color=p.TILE_L if is_night else p.FLOOR_D,
        mode="tiles",
        step=16,
        dither_ratio=0.12,
    )
    prefabs.iso_floor_threshold(
        a,
        room,
        "left",
        at=0.50,
        span=(0.0, 1.0),
        fill=p.METAL_M,
        highlight=p.METAL_H,
        outline=p.INK,
    )

    bedroom_zone = room.subroom(0.0, 0.0, 0.48, 1.0)
    lab_zone = room.subroom(0.52, 0.0, 1.0, 1.0)
    return room, bedroom_zone, lab_zone


def _draw_bedroom_zone(
    a: Asset,
    p: PaletteLookup,
    room: prefabs.IsoRoomGeometry,
    bedroom_zone: prefabs.IsoRoomGeometry,
) -> tuple[int, int]:
    is_night = a.state == "night"

    def _draw_vista(pane: prefabs.ClippedPane) -> None:
        if is_night:
            prefabs.sky_backdrop(pane, bands=(p.VOID, p.WINDOW_SKY, p.SCREEN_D))
            prefabs.starfield(pane, count=8, color=p.STAR, seed=a.seed)
            prefabs.moon(pane, 0.72, 0.30, radius=3, color=p.WHITE, crescent=True)
            return
        prefabs.sky_backdrop(pane, bands=(p.SOLAR_B, p.GLASS_L, p.SCREEN_L))
        prefabs.sun(pane, 0.28, 0.30, radius=3, color=p.HAIR_Y, halo=p.WHITE)

    prefabs.iso_room_window(
        a,
        room,
        "left",
        u0=0.24,
        u1=0.54,
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
        curtain_fabric=p.SHIRT_IND if is_night else p.SHIRT_TEAL,
        curtain_fold=p.INK,
        curtain_rod=p.METAL_H,
        curtain_open_ratio=0.55,
        spill_color=p.FLOOR_L,
        spill_secondary=p.TILE_L if is_night else p.FLOOR_M,
        spill_depth=0.26,
        spill_near_ratio=0.28 if is_night else 0.58,
        spill_far_ratio=0.04 if is_night else 0.14,
    )

    portal_pt = prefabs.iso_portal_door(
        a,
        room,
        "left",
        u0=0.74,
        u1=0.92,
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

    rug_cx, rug_cy = bedroom_zone.floor_point(0.56, 0.64)
    prefabs.iso_rug(
        a,
        rug_cx,
        rug_cy,
        hw=32,
        hh=16,
        fill=p.SHIRT_IND if is_night else p.SHIRT_TEAL,
        border=p.DUST_L,
        pattern=p.FLOOR_L,
        outline=p.INK,
    )

    bed_x, bed_y = bedroom_zone.wall_box_center(
        "left",
        38,
        20,
        6,
        along=0.78,
        margin=1,
        corner_margin=4,
    )
    prefabs.iso_bed(
        a,
        bed_x,
        bed_y,
        w=38,
        d=20,
        frame_h=6,
        headboard_h=10,
        frame=p.WOOD_L,
        frame_left=p.WOOD_M,
        frame_right=p.WOOD_D,
        mattress=p.WHITE,
        blanket=p.SHIRT_BLUE if is_night else p.SHIRT_EMER,
        blanket_shade=p.SOLAR_B if is_night else p.PCB_G,
        pillow=p.DUST_L,
        outline=p.INK,
        anchor="center",
    )
    return portal_pt


def _draw_lab_zone(
    a: Asset,
    p: PaletteLookup,
    room: prefabs.IsoRoomGeometry,
    lab_zone: prefabs.IsoRoomGeometry,
) -> tuple[prefabs.IsoDeskSlots, tuple[int, int]]:
    is_night = a.state == "night"
    bp0, bp1, bp2 = room.right_wall_plane(0.76, 0.28, 0.90, 0.56)
    prefabs.wall_panel(
        a,
        p0=bp0,
        p1=bp1,
        p2=bp2,
        frame=p.METAL_H,
        recess=p.METAL_D,
        slot=p.VOID,
        outline=p.INK,
        cols=2,
        rows=3,
        status_led=p.LED_A if is_night else p.LED_G,
    )

    desk_x, desk_y = lab_zone.wall_box_center(
        "right",
        68,
        26,
        18,
        along=0.22,
        margin=1,
        corner_margin=4,
    )
    slots = prefabs.iso_desk(
        a,
        desk_x,
        desk_y,
        68,
        26,
        leg_h=14,
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
        mat_w=36,
    )

    chair_x, chair_y = lab_zone.floor_point(0.42, 0.44)
    prefabs.contact_shadow(a, chair_x, chair_y + 8, 8, 4, color=p.VOID, dither_ratio=0.5)
    prefabs.iso_chair(
        a,
        chair_x,
        chair_y,
        seat_w=11,
        seat_d=11,
        seat_h=3,
        back_h=9,
        leg_h=5,
        top=p.METAL_L,
        left=p.METAL_M,
        right=p.METAL_D,
        back=p.METAL_M,
        leg=p.INK,
        outline=p.INK,
        facing="ne",
    )

    rack_x, rack_y = lab_zone.floor_point(0.84, 0.24)
    prefabs.contact_shadow(a, rack_x, rack_y + 7, 11, 5, color=p.VOID, dither_ratio=0.5)
    prefabs.iso_rack(
        a,
        rack_x,
        rack_y,
        16,
        16,
        6,
        top=p.METAL_H,
        left=p.METAL_M,
        right=p.METAL_D,
        outline=p.INK,
        anchor="center",
    )
    return slots, (rack_x, rack_y - 2)


def render(a: Asset) -> None:
    """Render the `multiroom_homelab_iso` two-zone room with zone & divider anchors."""
    p = a.pal
    room, bedroom_zone, lab_zone = _draw_shell_and_zones(a, p)
    portal_pt = _draw_bedroom_zone(a, p, room, bedroom_zone)
    slots, rack_pt = _draw_lab_zone(a, p, room, lab_zone)

    # Zone 0: Bedroom anchors
    bed_plant_pt = bedroom_zone.floor_point(0.22, 0.42)
    bed_crate_pt = bedroom_zone.floor_point(0.72, 0.90)
    a.anchor("bed_plant", bed_plant_pt[0], bed_plant_pt[1])
    a.anchor("bed_crate", bed_crate_pt[0], bed_crate_pt[1])
    a.anchor("portal_bedroom", portal_pt[0], portal_pt[1])

    # Zone 1: Center divider anchors along at=0.50 (ordered back-to-front by iso_y)
    div_wall_pt = room.floor_point(0.50, 0.16)
    div_pillar_pt = room.floor_point(0.50, 0.36)
    div_glass_pt = room.floor_point(0.50, 0.56)
    a.anchor("div_wall_back", div_wall_pt[0], div_wall_pt[1])
    a.anchor("div_pillar", div_pillar_pt[0], div_pillar_pt[1])
    a.anchor("div_glass", div_glass_pt[0], div_glass_pt[1])

    # Zone 2: Homelab workstation anchors
    mon_pt = slots.top_point(0.44, 0.34)
    lamp_pt = slots.top_point(0.14, 0.46)
    pc_pt = slots.top_point(0.86, 0.45)
    kbd_pt = slots.top_point(0.43, 0.68)
    mouse_pt = slots.top_point(0.61, 0.68)
    a.anchor("desk_monitor", mon_pt[0], mon_pt[1])
    a.anchor("desk_lamp", lamp_pt[0], lamp_pt[1])
    a.anchor("desk_pc", pc_pt[0], pc_pt[1])
    a.anchor("desk_keyboard", kbd_pt[0], kbd_pt[1])
    a.anchor("desk_mouse", mouse_pt[0], mouse_pt[1])
    a.anchor("rack_switch", rack_pt[0], rack_pt[1])

    a.hitbox("bedroom_zone", 52, 76, 128, 120)
    a.hitbox("lab_zone", 180, 76, 128, 120)
    a.hitbox("room", 52, 12, 256, 200)
