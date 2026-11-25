"""Isometric Tier-1 bedroom homelab scene (`320x200` iso-2:1) for `homelab-16bit`."""

from __future__ import annotations

from pixelforge import Asset, AssetSpec, PaletteLookup

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

    # Isometric floor diamond + subtle dithered plank texture
    a.iso_tile(_FLOOR_CX, _FLOOR_CY, _FLOOR_HW * 2, floor_base, height=_FLOOR_HH * 2)
    a.dither(
        _FLOOR_CX - _FLOOR_HW,
        _FLOOR_CY - _FLOOR_HH,
        _FLOOR_HW * 2,
        _FLOOR_HH * 2,
        None,
        floor_alt,
        pattern="bayer4",
        ratio=0.12,
        mask="opaque",
    )

    for i in range(-3, 4):
        off = i * 16
        a.line(
            _FLOOR_CX - _FLOOR_HW + abs(off),
            _FLOOR_CY + (off >> 1),
            _FLOOR_CX + abs(off) - 8,
            _FLOOR_CY - _FLOOR_HH + (off >> 1) + 4,
            p.FLOOR_D,
        )

    # Back-left wall polygon + trim
    apex_y = _FLOOR_CY - _FLOOR_HH
    left_y = _FLOOR_CY
    right_y = _FLOOR_CY
    a.polygon(
        (
            (_FLOOR_CX - _FLOOR_HW, left_y),
            (_FLOOR_CX, apex_y),
            (_FLOOR_CX, apex_y - _WALL_H),
            (_FLOOR_CX - _FLOOR_HW, left_y - _WALL_H),
        ),
        left_wall,
    )
    a.polygon(
        (
            (_FLOOR_CX, apex_y),
            (_FLOOR_CX + _FLOOR_HW, right_y),
            (_FLOOR_CX + _FLOOR_HW, right_y - _WALL_H),
            (_FLOOR_CX, apex_y - _WALL_H),
        ),
        right_wall,
    )

    # Wooden baseboard along both back walls
    a.line(_FLOOR_CX - _FLOOR_HW, left_y - 1, _FLOOR_CX, apex_y - 1, p.WOOD_M)
    a.line(_FLOOR_CX - _FLOOR_HW, left_y, _FLOOR_CX, apex_y, p.WOOD_D)
    a.line(_FLOOR_CX, apex_y - 1, _FLOOR_CX + _FLOOR_HW, right_y - 1, p.WOOD_M)
    a.line(_FLOOR_CX, apex_y, _FLOOR_CX + _FLOOR_HW, right_y, p.WOOD_D)

    # Wall top rim, corner seam, and outer silhouette lines
    a.line(
        _FLOOR_CX - _FLOOR_HW,
        left_y - _WALL_H,
        _FLOOR_CX,
        apex_y - _WALL_H,
        p.INK,
    )
    a.line(
        _FLOOR_CX,
        apex_y - _WALL_H,
        _FLOOR_CX + _FLOOR_HW,
        right_y - _WALL_H,
        p.INK,
    )
    a.line(_FLOOR_CX, apex_y, _FLOOR_CX, apex_y - _WALL_H, p.WALL_D)
    a.line(_FLOOR_CX - _FLOOR_HW, left_y, _FLOOR_CX - _FLOOR_HW, left_y - _WALL_H, p.INK)
    a.line(_FLOOR_CX + _FLOOR_HW, right_y, _FLOOR_CX + _FLOOR_HW, right_y - _WALL_H, p.INK)
    a.line(_FLOOR_CX - _FLOOR_HW, left_y, _FLOOR_CX, _FLOOR_CY + _FLOOR_HH, p.INK)
    a.line(_FLOOR_CX, _FLOOR_CY + _FLOOR_HH, _FLOOR_CX + _FLOOR_HW, right_y, p.INK)


def _draw_window(a: Asset, p: PaletteLookup) -> None:
    is_night = a.state == "night"
    sky_color = p.WINDOW_SKY if is_night else p.SOLAR_B

    # Skewed isometric window mounted on back-left wall via Plane
    with a.plane(p0=(76, 64), p1=(122, 41), p2=(76, 98)) as win:
        win.rect(0.0, 0.0, 1.0, 1.0, fill=p.METAL_M, outline=p.INK)
        win.rect(0.07, 0.08, 0.86, 0.84, fill=sky_color)
        if not is_night:
            win.dither(0.07, 0.08, 0.86, 0.45, p.GLASS_L, p.SOLAR_B, pattern="bayer4", ratio=0.4)
        # Window mullion bar
        win.rect(0.05, 0.48, 0.90, 0.06, fill=p.METAL_M)

    if is_night:
        a.rect(92, 74, 3, 3, p.STAR)
        a.put(108, 70, p.STAR)
        a.put(85, 82, p.STAR)
    else:
        a.iso_tile(118, 126, 40, p.FLOOR_L, height=20)


def _draw_desk_and_slots(a: Asset, p: PaletteLookup) -> None:
    is_night = a.state == "night"

    # Desk legs (2:1 isometric prisms)
    a.iso_box(
        120,
        112,
        4,
        4,
        18,
        top=p.METAL_M,
        left=p.METAL_D,
        right=p.VOID,
        anchor="center",
    )
    a.iso_box(
        184,
        112,
        4,
        4,
        18,
        top=p.METAL_M,
        left=p.METAL_D,
        right=p.VOID,
        anchor="center",
    )

    # Main wooden desk top
    a.iso_box(
        152,
        108,
        44,
        44,
        5,
        top=p.WOOD_L,
        left=p.WOOD_M,
        right=p.WOOD_D,
        outline=p.INK,
        highlight=p.WOOD_L,
        anchor="center",
    )

    # Desk mat
    a.iso_tile(148, 108, 44, p.METAL_D, height=22)

    # Side floor rack stand for AI cluster node
    a.iso_box(
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
    with a.plane(p0=(224, 66), p1=(242, 75), p2=(224, 92)) as panel:
        panel.rect(0.0, 0.0, 1.0, 1.0, fill=p.METAL_H, outline=p.INK)
        panel.rect(0.22, 0.25, 0.56, 0.45, fill=p.METAL_D)
        panel.grid(0.28, 0.30, 0.44, 0.35, cols=2, rows=3, color=p.VOID)
        panel.dot(0.75, 0.18, p.LED_A if a.state == "night" else p.LED_G)


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
