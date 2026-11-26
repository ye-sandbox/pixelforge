"""Isometric seating and bed prefabs (task chair, sofa, armchair, bed)."""

from __future__ import annotations

from typing import Literal

from pixelforge.core.iso import IsoAnchor
from pixelforge.core.prefabs.furniture._common import (
    Canvas,
    ChairFacing,
    project_diamond,
    resolve_box_top_origin,
)


def _draw_seat_backrest(
    target: Canvas,
    tx: int,
    ty: int,
    p_right: tuple[int, int],
    p_left: tuple[int, int],
    sw: int,
    sd: int,
    bh: int,
    thick: int,
    *,
    top: int,
    left: int,
    right: int,
    back: int,
    outline: int | None,
    facing: ChairFacing,
) -> None:
    if facing == "se":
        target.iso_box(
            tx,
            ty - bh,
            thick,
            sd,
            bh,
            top=top,
            left=back,
            right=right,
            outline=outline,
            anchor="top",
        )
    elif facing == "sw":
        target.iso_box(
            tx,
            ty - bh,
            sw,
            thick,
            bh,
            top=top,
            left=left,
            right=back,
            outline=outline,
            anchor="top",
        )
    elif facing == "nw":
        target.iso_box(
            p_right[0] - thick,
            p_right[1] - bh,
            thick,
            sd,
            bh,
            top=top,
            left=back,
            right=right,
            outline=outline,
            anchor="top",
        )
    elif facing == "ne":
        target.iso_box(
            p_left[0],
            p_left[1] - bh,
            sw,
            thick,
            bh,
            top=top,
            left=left,
            right=back,
            outline=outline,
            anchor="top",
        )
    else:
        msg = f"Unsupported seat facing: {facing!r}"
        raise ValueError(msg)


def _draw_seat_arm(
    target: Canvas,
    which: Literal["near", "far"],
    tx: int,
    ty: int,
    p_right: tuple[int, int],
    p_left: tuple[int, int],
    sw: int,
    sd: int,
    sh: int,
    ah: int,
    arm_thick: int,
    *,
    arm_top: int,
    left: int,
    right: int,
    outline: int | None,
    facing: ChairFacing,
) -> None:
    if facing in ("se", "nw"):
        ax, ay = (tx, ty) if which == "far" else (p_left[0], p_left[1] - arm_thick // 2)
        target.iso_box(
            ax,
            ay - ah + sh,
            sw,
            arm_thick,
            ah,
            top=arm_top,
            left=left,
            right=right,
            outline=outline,
            anchor="top",
        )
        return

    ax, ay = (tx, ty) if which == "far" else (p_right[0] - arm_thick, p_right[1] + arm_thick // 2)
    target.iso_box(
        ax,
        ay - ah + sh,
        arm_thick,
        sd,
        ah,
        top=arm_top,
        left=left,
        right=right,
        outline=outline,
        anchor="top",
    )


def iso_chair(
    target: Canvas,
    x: int | float,
    y: int | float,
    *,
    seat_w: int = 12,
    seat_d: int = 12,
    seat_h: int = 3,
    back_h: int = 11,
    leg_h: int = 6,
    top: int,
    left: int,
    right: int,
    back: int,
    leg: int,
    outline: int | None = None,
    facing: ChairFacing = "se",
) -> tuple[int, int]:
    """Draw a 2:1 isometric task chair and return the seat-center `(x, y)` anchor."""
    sw = max(4, int(seat_w))
    sd = max(4, int(seat_d))
    sh = max(2, int(seat_h))
    bh = max(3, int(back_h))
    lh = max(2, int(leg_h))
    icx = round(x)
    icy = round(y)

    # Central pedestal + 4-way caster base
    base_y = icy + (sw + sd) // 4 + sh + lh
    target.line(icx, icy + sh, icx, base_y, leg)
    target.line(icx - sw // 2, base_y - 1, icx + sw // 2, base_y - 1, leg)
    target.line(icx - 2, base_y, icx + 2, base_y, leg)

    tx, ty = resolve_box_top_origin(icx, icy, sw, sd, sh, "center")
    p_top = (tx, ty)
    p_right = (tx + sw, ty + sw // 2)
    p_left = (tx - sd, ty + sd // 2)

    if facing in ("se", "sw"):
        _draw_seat_backrest(
            target,
            tx,
            ty,
            p_right,
            p_left,
            sw,
            sd,
            bh,
            2,
            top=top,
            left=left,
            right=right,
            back=back,
            outline=outline,
            facing=facing,
        )
        target.iso_box(
            icx, icy, sw, sd, sh, top=top, left=left, right=right, outline=outline, anchor="center"
        )
    else:
        target.iso_box(
            icx, icy, sw, sd, sh, top=top, left=left, right=right, outline=outline, anchor="center"
        )
        _draw_seat_backrest(
            target,
            tx,
            ty,
            p_right,
            p_left,
            sw,
            sd,
            bh,
            2,
            top=top,
            left=left,
            right=right,
            back=back,
            outline=outline,
            facing=facing,
        )

    return project_diamond(p_top, p_right, p_left, 0.5, 0.5)


def iso_bed(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 28,
    d: int = 16,
    *,
    frame_h: int = 6,
    headboard_h: int = 11,
    frame: int,
    frame_left: int,
    frame_right: int,
    mattress: int,
    blanket: int,
    blanket_shade: int | None = None,
    pillow: int | None = None,
    outline: int | None = None,
    anchor: IsoAnchor = "center",
) -> tuple[int, int]:
    """Draw a 2:1 isometric bed with headboard, mattress, blanket, and optional pillow."""
    iw = max(8, int(w))
    id_ = max(6, int(d))
    ifh = max(2, int(frame_h))
    ihb = max(3, int(headboard_h))

    tx, ty = resolve_box_top_origin(x, y, iw, id_, ifh, anchor)
    target.iso_box(
        tx,
        ty - ihb,
        3,
        id_,
        ihb,
        top=frame,
        left=frame_left,
        right=frame_right,
        outline=outline,
        anchor="top",
    )
    target.iso_box(
        tx,
        ty,
        iw,
        id_,
        ifh,
        top=mattress,
        left=frame_left,
        right=frame_right,
        outline=outline,
        anchor="top",
    )

    p_top = (tx, ty)
    p_right = (tx + iw, ty + iw // 2)
    p_left = (tx - id_, ty + id_ // 2)
    with target.plane(p0=p_top, p1=p_right, p2=p_left) as top_plane:
        top_plane.rect(0.36, 0.04, 0.62, 0.92, fill=blanket)
        if blanket_shade is not None:
            top_plane.rect(0.36, 0.04, 0.08, 0.92, fill=blanket_shade)
        if pillow is not None:
            top_plane.rect(0.10, 0.16, 0.20, 0.68, fill=pillow, outline=outline)

    return project_diamond(p_top, p_right, p_left, 0.5, 0.5)


def _draw_upholstered_seat(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    seat_h: int,
    back_h: int,
    arm_h: int,
    *,
    top: int,
    left: int,
    right: int,
    back: int,
    arm: int | None,
    cushion_seam: int | None,
    seats: int,
    outline: int | None,
    facing: ChairFacing,
) -> tuple[int, int]:
    sw, sd = max(8, int(w)), max(8, int(d))
    sh, bh, ah = max(3, int(seat_h)), max(4, int(back_h)), max(3, int(arm_h))
    arm_top = arm if arm is not None else top
    tx, ty = resolve_box_top_origin(x, y, sw, sd, sh, "center")
    p_top, p_right, p_left = (tx, ty), (tx + sw, ty + sw // 2), (tx - sd, ty + sd // 2)
    arm_thick = max(2, min(4, min(sw, sd) // 4))

    def _back() -> None:
        _draw_seat_backrest(
            target,
            tx,
            ty,
            p_right,
            p_left,
            sw,
            sd,
            bh,
            3,
            top=top,
            left=left,
            right=right,
            back=back,
            outline=outline,
            facing=facing,
        )

    def _arm(which: Literal["near", "far"]) -> None:
        _draw_seat_arm(
            target,
            which,
            tx,
            ty,
            p_right,
            p_left,
            sw,
            sd,
            sh,
            ah,
            arm_thick,
            arm_top=arm_top,
            left=left,
            right=right,
            outline=outline,
            facing=facing,
        )

    if facing in ("se", "sw"):
        _back()
    _arm("far")
    target.iso_box(
        tx, ty, sw, sd, sh, top=top, left=left, right=right, outline=outline, anchor="top"
    )
    if cushion_seam is not None and seats > 1:
        with target.plane(p0=p_top, p1=p_right, p2=p_left) as seat_plane:
            for idx in range(1, seats):
                t = idx / float(seats)
                if facing in ("se", "nw"):
                    seat_plane.line(0.15, t, 0.90, t, cushion_seam)
                else:
                    seat_plane.line(t, 0.15, t, 0.90, cushion_seam)
    _arm("near")
    if facing in ("nw", "ne"):
        _back()

    return project_diamond(p_top, p_right, p_left, 0.5, 0.5)


def iso_sofa(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 28,
    d: int = 14,
    *,
    seat_h: int = 5,
    back_h: int = 9,
    arm_h: int = 6,
    seats: int = 3,
    top: int,
    left: int,
    right: int,
    back: int,
    arm: int | None = None,
    cushion_seam: int | None = None,
    outline: int | None = None,
    facing: ChairFacing = "sw",
) -> tuple[int, int]:
    """Draw a 2:1 isometric multi-seat sofa and return its seat-center `(x, y)`."""
    return _draw_upholstered_seat(
        target,
        x,
        y,
        w,
        d,
        seat_h,
        back_h,
        arm_h,
        top=top,
        left=left,
        right=right,
        back=back,
        arm=arm,
        cushion_seam=cushion_seam,
        seats=max(2, int(seats)),
        outline=outline,
        facing=facing,
    )


def iso_armchair(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 14,
    d: int = 14,
    *,
    seat_h: int = 5,
    back_h: int = 9,
    arm_h: int = 6,
    top: int,
    left: int,
    right: int,
    back: int,
    arm: int | None = None,
    outline: int | None = None,
    facing: ChairFacing = "se",
) -> tuple[int, int]:
    """Draw a 2:1 isometric cushioned armchair and return its seat-center `(x, y)`."""
    return _draw_upholstered_seat(
        target,
        x,
        y,
        w,
        d,
        seat_h,
        back_h,
        arm_h,
        top=top,
        left=left,
        right=right,
        back=back,
        arm=arm,
        cushion_seam=None,
        seats=1,
        outline=outline,
        facing=facing,
    )
