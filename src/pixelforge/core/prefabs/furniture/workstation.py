"""Isometric desk, workbench, and table prefabs."""

from __future__ import annotations

from pixelforge.core.iso import IsoAnchor
from pixelforge.core.prefabs.details import contact_shadow
from pixelforge.core.prefabs.furniture._common import (
    Canvas,
    ChairFacing,
    IsoDeskSlots,
    project_diamond,
    resolve_box_top_origin,
)
from pixelforge.core.prefabs.furniture.seating import iso_chair


def _draw_table_legs(
    target: Canvas,
    p_top: tuple[int, int],
    p_right: tuple[int, int],
    p_left: tuple[int, int],
    iw: int,
    id_: int,
    itop_h: int,
    ileg_h: int,
    leg_top: int,
    leg_left: int,
    leg_right: int,
    uv_points: tuple[tuple[float, float], ...],
) -> None:
    leg_span = max(2, min(4, min(iw, id_) // 6))
    coords = [project_diamond(p_top, p_right, p_left, lu, lv) for lu, lv in uv_points]
    coords.sort(key=lambda pt: (pt[1], pt[0]))
    for lx, ly in coords:
        target.iso_box(
            lx,
            ly + itop_h - 1,
            leg_span,
            leg_span,
            ileg_h + 1,
            top=leg_top,
            left=leg_left,
            right=leg_right,
            anchor="center",
        )


def iso_desk(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    *,
    leg_h: int = 18,
    top_h: int = 5,
    top: int,
    left: int,
    right: int,
    leg_top: int,
    leg_left: int,
    leg_right: int,
    outline: int | None = None,
    highlight: int | None = None,
    mat_color: int | None = None,
    mat_w: int | None = None,
) -> IsoDeskSlots:
    """Draw a 2:1 isometric desk with corner legs, beveled tabletop, and optional desk mat."""
    iw = max(4, int(w))
    id_ = max(4, int(d))
    ileg_h = max(1, int(leg_h))
    itop_h = max(1, int(top_h))

    tx, ty = resolve_box_top_origin(x, y, iw, id_, itop_h, "center")
    p_top = (tx, ty)
    p_right = (tx + iw, ty + iw // 2)
    p_left = (tx - id_, ty + id_ // 2)
    p_front = (tx + iw - id_, ty + iw // 2 + id_ // 2)

    leg_span = max(2, min(4, min(iw, id_) // 6))
    du = min(0.24, max(0.08, (leg_span + 1.5) / float(iw)))
    dv = min(0.24, max(0.10, (leg_span + 1.5) / float(id_)))

    # INVARIANT: Draw all 4 corner legs back-to-front before the tabletop so the slab
    # cleanly occludes leg tops across both square and rectangular desk ratios.
    _draw_table_legs(
        target,
        p_top,
        p_right,
        p_left,
        iw,
        id_,
        itop_h,
        ileg_h,
        leg_top,
        leg_left,
        leg_right,
        ((du, dv), (du, 1.0 - dv), (1.0 - du, dv), (1.0 - du, 1.0 - dv)),
    )

    target.iso_box(
        x,
        y,
        iw,
        id_,
        itop_h,
        top=top,
        left=left,
        right=right,
        outline=outline,
        highlight=highlight,
        anchor="center",
    )

    if mat_color is not None:
        mw = max(4, int(mat_w) if mat_w is not None else round(iw * 0.56))
        u_span = min(0.84, max(0.24, mw / float(iw)))
        u0 = (1.0 - u_span) * 0.5
        with target.plane(p0=p_top, p1=p_right, p2=p_left) as desk_top:
            desk_top.rect(u0, 0.24, u_span, 0.58, fill=mat_color)

    return IsoDeskSlots(
        center=(round(x), round(y)),
        p_top=p_top,
        p_right=p_right,
        p_left=p_left,
        p_front=p_front,
        leg_h=ileg_h,
    )


def iso_desk_set(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    *,
    leg_h: int = 18,
    top_h: int = 5,
    top: int,
    left: int,
    right: int,
    leg_top: int,
    leg_left: int,
    leg_right: int,
    outline: int | None = None,
    highlight: int | None = None,
    mat_color: int | None = None,
    mat_w: int | None = None,
    chair_u: float = 0.45,
    chair_pull_out: int = 10,
    chair_seat_w: int = 12,
    chair_seat_d: int = 12,
    chair_seat_h: int = 3,
    chair_back_h: int = 10,
    chair_leg_h: int = 5,
    chair_top: int | None = None,
    chair_left: int | None = None,
    chair_right: int | None = None,
    chair_back: int | None = None,
    chair_leg: int | None = None,
    chair_facing: ChairFacing = "ne",
    shadow_color: int | None = None,
) -> IsoDeskSlots:
    """Draw a 2:1 isometric desk paired with a floor-snapped task chair and contact shadow."""
    slots = iso_desk(
        target,
        x,
        y,
        w,
        d,
        leg_h=leg_h,
        top_h=top_h,
        top=top,
        left=left,
        right=right,
        leg_top=leg_top,
        leg_left=leg_left,
        leg_right=leg_right,
        outline=outline,
        highlight=highlight,
        mat_color=mat_color,
        mat_w=mat_w,
    )
    cx, cy = slots.chair_point(chair_u, pull_out=chair_pull_out)
    if shadow_color is not None:
        shadow_y = cy + chair_seat_h + chair_leg_h + 2
        contact_shadow(
            target,
            cx,
            shadow_y,
            max(5, chair_seat_w - 3),
            max(3, chair_seat_d // 3),
            color=shadow_color,
            dither_ratio=0.5,
        )
    iso_chair(
        target,
        cx,
        cy,
        seat_w=chair_seat_w,
        seat_d=chair_seat_d,
        seat_h=chair_seat_h,
        back_h=chair_back_h,
        leg_h=chair_leg_h,
        top=leg_top if chair_top is None else chair_top,
        left=leg_left if chair_left is None else chair_left,
        right=leg_right if chair_right is None else chair_right,
        back=leg_top if chair_back is None else chair_back,
        leg=(outline if outline is not None else leg_right) if chair_leg is None else chair_leg,
        outline=outline,
        facing=chair_facing,
    )
    return slots


def iso_workbench(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 28,
    d: int = 16,
    *,
    leg_h: int = 14,
    top_h: int = 4,
    top: int,
    left: int,
    right: int,
    leg_top: int,
    leg_left: int,
    leg_right: int,
    back_panel: int | None = None,
    pegboard_dot: int | None = None,
    lower_shelf: int | None = None,
    outline: int | None = None,
    highlight: int | None = None,
) -> IsoDeskSlots:
    """Draw a 2:1 isometric workbench with optional lower shelf and rear pegboard."""
    iw = max(8, int(w))
    id_ = max(6, int(d))
    ileg_h = max(4, int(leg_h))
    itop_h = max(2, int(top_h))

    if lower_shelf is not None:
        target.iso_box(
            x,
            y + max(3, ileg_h // 2),
            max(4, iw - 4),
            max(4, id_ - 4),
            2,
            top=lower_shelf,
            left=leg_left,
            right=leg_right,
            anchor="center",
        )

    slots = iso_desk(
        target,
        x,
        y,
        iw,
        id_,
        leg_h=ileg_h,
        top_h=itop_h,
        top=top,
        left=left,
        right=right,
        leg_top=leg_top,
        leg_left=leg_left,
        leg_right=leg_right,
        outline=outline,
        highlight=highlight,
    )

    if back_panel is not None:
        panel_h = max(6, ileg_h - 2)
        p0 = (slots.p_top[0], slots.p_top[1] - panel_h)
        p1 = (slots.p_right[0], slots.p_right[1] - panel_h)
        p2 = slots.p_top
        with target.plane(p0=p0, p1=p1, p2=p2) as peg:
            peg.rect(0.0, 0.0, 1.0, 1.0, fill=back_panel, outline=outline)
            if pegboard_dot is not None:
                peg.grid(0.12, 0.16, 0.76, 0.68, cols=4, rows=3, color=pegboard_dot, cell_fill=0.4)

    return slots


def _draw_l_desk_perimeter(
    target: Canvas,
    p_top: tuple[int, int],
    p_right: tuple[int, int],
    p_left: tuple[int, int],
    p_r_front: tuple[int, int],
    p_l_front: tuple[int, int],
    p_inner: tuple[int, int],
    itop_h: int,
    highlight: int | None,
    outline: int | None,
) -> None:
    if highlight is not None:
        target.line(p_top[0], p_top[1], p_right[0], p_right[1], highlight)
        target.line(p_top[0], p_top[1], p_left[0], p_left[1], highlight)

    if outline is not None:
        perimeter = (p_top, p_right, p_r_front, p_inner, p_l_front, p_left, p_top)
        for idx in range(len(perimeter) - 1):
            a_pt, b_pt = perimeter[idx], perimeter[idx + 1]
            target.line(a_pt[0], a_pt[1], b_pt[0], b_pt[1], outline)
        drops = (p_left, p_l_front, p_inner, p_r_front, p_right)
        for pt in drops:
            target.line(pt[0], pt[1], pt[0], pt[1] + itop_h, outline)
        for idx in range(len(drops) - 1):
            a_pt, b_pt = drops[idx], drops[idx + 1]
            target.line(a_pt[0], a_pt[1] + itop_h, b_pt[0], b_pt[1] + itop_h, outline)


def iso_l_desk(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 32,
    d: int = 28,
    *,
    wing_w: int = 14,
    wing_d: int = 12,
    leg_h: int = 18,
    top_h: int = 5,
    top: int,
    left: int,
    right: int,
    leg_top: int,
    leg_left: int,
    leg_right: int,
    outline: int | None = None,
    highlight: int | None = None,
    mat_color: int | None = None,
    anchor: IsoAnchor = "center",
) -> IsoDeskSlots:
    """Draw a 2:1 isometric corner L-shaped desk and return bounding `IsoDeskSlots`."""
    iw = max(12, int(w))
    id_ = max(12, int(d))
    ww = max(6, min(iw - 4, int(wing_w)))
    wd = max(6, min(id_ - 4, int(wing_d)))
    ileg_h = max(2, int(leg_h))
    itop_h = max(2, int(top_h))

    tx, ty = resolve_box_top_origin(x, y, iw, id_, itop_h, anchor)
    p_top = (tx, ty)
    p_right = (tx + iw, ty + iw // 2)
    p_left = (tx - id_, ty + id_ // 2)
    p_front = (tx + iw - id_, ty + iw // 2 + id_ // 2)

    du = min(0.22, max(0.08, 3.0 / float(iw)))
    dv = min(0.22, max(0.08, 3.0 / float(id_)))
    u_wing, v_wing = ww / float(iw), wd / float(id_)
    leg_uvs = (
        (du, dv),
        (1.0 - du, dv),
        (du, 1.0 - dv),
        (max(du, u_wing - du), 1.0 - dv),
        (1.0 - du, max(dv, v_wing - dv)),
        (u_wing, v_wing),
    )
    _draw_table_legs(
        target,
        p_top,
        p_right,
        p_left,
        iw,
        id_,
        itop_h,
        ileg_h,
        leg_top,
        leg_left,
        leg_right,
        leg_uvs,
    )

    # INVARIANT: Draw both overlapping wings without outlines first, then paint the unified
    # top surface and outer perimeter so the corner junction has zero internal seam.
    target.iso_box(tx, ty, ww, id_, itop_h, top=top, left=left, right=right, anchor="top")
    target.iso_box(tx, ty, iw, wd, itop_h, top=top, left=left, right=right, anchor="top")

    p_r_front = (p_right[0] - wd, p_right[1] + wd // 2)
    p_l_front = (p_left[0] + ww, p_left[1] + ww // 2)
    p_inner = (tx + ww - wd, ty + ww // 2 + wd // 2)
    p_top_l = (tx - wd, ty + wd // 2)
    p_top_r = (tx + ww, ty + ww // 2)

    with target.plane(p0=p_top, p1=p_top_r, p2=p_left) as left_wing_top:
        left_wing_top.rect(0.0, 0.0, 1.0, 1.0, fill=top)
    with target.plane(p0=p_top, p1=p_right, p2=p_top_l) as main_wing_top:
        main_wing_top.rect(0.0, 0.0, 1.0, 1.0, fill=top)
        if mat_color is not None:
            main_wing_top.rect(0.38, 0.24, 0.42, 0.56, fill=mat_color)

    _draw_l_desk_perimeter(
        target,
        p_top,
        p_right,
        p_left,
        p_r_front,
        p_l_front,
        p_inner,
        itop_h,
        highlight,
        outline,
    )

    return IsoDeskSlots(
        center=(round(x), round(y)),
        p_top=p_top,
        p_right=p_right,
        p_left=p_left,
        p_front=p_front,
        leg_h=ileg_h,
    )


def _draw_table_with_shelf(
    target: Canvas,
    x: int | float,
    y: int | float,
    iw: int,
    id_: int,
    ileg_h: int,
    itop_h: int,
    *,
    top: int,
    left: int,
    right: int,
    leg_top: int,
    leg_left: int,
    leg_right: int,
    lower_shelf: int | None,
    inlay_color: int | None,
    outline: int | None,
    highlight: int | None,
) -> IsoDeskSlots:
    if lower_shelf is not None and ileg_h >= 5:
        target.iso_box(
            x,
            y + max(2, ileg_h // 2),
            max(4, iw - 4),
            max(4, id_ - 4),
            2,
            top=lower_shelf,
            left=leg_left,
            right=leg_right,
            anchor="center",
        )
    slots = iso_desk(
        target,
        x,
        y,
        iw,
        id_,
        leg_h=ileg_h,
        top_h=itop_h,
        top=top,
        left=left,
        right=right,
        leg_top=leg_top,
        leg_left=leg_left,
        leg_right=leg_right,
        outline=outline,
        highlight=highlight,
    )
    if inlay_color is not None:
        with target.plane(p0=slots.p_top, p1=slots.p_right, p2=slots.p_left) as top_plane:
            top_plane.rect(0.18, 0.18, 0.64, 0.64, fill=inlay_color)
    return slots


def iso_side_table(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 12,
    d: int = 12,
    *,
    leg_h: int = 12,
    top_h: int = 3,
    top: int,
    left: int,
    right: int,
    leg_top: int,
    leg_left: int,
    leg_right: int,
    lower_shelf: int | None = None,
    outline: int | None = None,
    highlight: int | None = None,
) -> IsoDeskSlots:
    """Draw a compact 2:1 isometric side table with optional lower shelf."""
    return _draw_table_with_shelf(
        target,
        x,
        y,
        max(6, int(w)),
        max(6, int(d)),
        max(3, int(leg_h)),
        max(2, int(top_h)),
        top=top,
        left=left,
        right=right,
        leg_top=leg_top,
        leg_left=leg_left,
        leg_right=leg_right,
        lower_shelf=lower_shelf,
        inlay_color=None,
        outline=outline,
        highlight=highlight,
    )


def iso_coffee_table(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 22,
    d: int = 14,
    *,
    leg_h: int = 6,
    top_h: int = 3,
    top: int,
    left: int,
    right: int,
    leg_top: int,
    leg_left: int,
    leg_right: int,
    lower_shelf: int | None = None,
    inlay_color: int | None = None,
    outline: int | None = None,
    highlight: int | None = None,
) -> IsoDeskSlots:
    """Draw a low 2:1 isometric coffee table with optional lower shelf and inlay."""
    return _draw_table_with_shelf(
        target,
        x,
        y,
        max(8, int(w)),
        max(8, int(d)),
        max(2, int(leg_h)),
        max(2, int(top_h)),
        top=top,
        left=left,
        right=right,
        leg_top=leg_top,
        leg_left=leg_left,
        leg_right=leg_right,
        lower_shelf=lower_shelf,
        inlay_color=inlay_color,
        outline=outline,
        highlight=highlight,
    )
