"""Furniture 2:1 isometric prefab helpers (desks, racks, shelves)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.iso import IsoAnchor
from pixelforge.core.plane import Point2D
from pixelforge.core.prefabs.atmosphere import PlaneRegion

Canvas = Asset | Layer
RackFrontStyle = Literal["bays", "grille", "glass_door"]
ChairFacing = Literal["se", "sw", "nw", "ne"]


def _resolve_box_top_origin(
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    h: int,
    anchor: IsoAnchor,
) -> tuple[int, int]:
    dy_r = w // 2
    dy_l = d // 2
    if anchor == "top":
        return (round(x), round(y))
    if anchor == "center":
        return (round(x - (w - d) * 0.5), round(y - (dy_r + dy_l) * 0.5))
    if anchor == "bottom":
        return (round(x - (w - d)), round(y - (dy_r + dy_l + h)))
    msg = f"Unsupported iso furniture anchor: {anchor!r}"
    raise ValueError(msg)


def _project_diamond(
    p_top: tuple[int, int],
    p_right: tuple[int, int],
    p_left: tuple[int, int],
    u: float,
    v: float,
) -> tuple[int, int]:
    ux = p_right[0] - p_top[0]
    uy = p_right[1] - p_top[1]
    vx = p_left[0] - p_top[0]
    vy = p_left[1] - p_top[1]
    return (round(p_top[0] + u * ux + v * vx), round(p_top[1] + u * uy + v * vy))


@dataclass(frozen=True)
class IsoDeskSlots:
    """Surface projection and item-placement slots for `iso_desk`."""

    center: tuple[int, int]
    p_top: tuple[int, int]
    p_right: tuple[int, int]
    p_left: tuple[int, int]
    p_front: tuple[int, int]

    def top_plane(self) -> PlaneRegion:
        """Return `(p_top, p_right, p_left)` for drawing directly on the desk surface."""
        return (self.p_top, self.p_right, self.p_left)

    def top_point(self, u: float = 0.5, v: float = 0.5) -> tuple[int, int]:
        """Project normalized `(u, v)` onto the tabletop (`u`: top->right, `v`: top->left)."""
        return _project_diamond(self.p_top, self.p_right, self.p_left, u, v)

    def slots(self, count: int = 2, *, v: float = 0.50) -> tuple[tuple[int, int], ...]:
        """Return `count` evenly spaced placement points across the desk width."""
        n = max(1, int(count))
        if n == 1:
            return (self.top_point(0.5, v),)
        return tuple(self.top_point(0.28 + (idx / (n - 1)) * 0.44, v) for idx in range(n))


@dataclass(frozen=True)
class IsoRackSlots:
    """Top surface and front-mount coordinates for `iso_rack`."""

    top_center: tuple[int, int]
    p_top: tuple[int, int]
    p_right: tuple[int, int]
    p_left: tuple[int, int]
    p_front: tuple[int, int]
    p_left_bot: tuple[int, int]
    front_mounts: tuple[tuple[int, int], ...]

    def top_point(self, u: float = 0.5, v: float = 0.5) -> tuple[int, int]:
        """Project normalized `(u, v)` onto the rack top surface."""
        return _project_diamond(self.p_top, self.p_right, self.p_left, u, v)

    def front_plane(self) -> PlaneRegion:
        """Return `(p_left, p_front, p_left_bot)` for the front-left rack face."""
        return (self.p_left, self.p_front, self.p_left_bot)


@dataclass(frozen=True)
class IsoShelfSlots:
    """Tier surface coordinates for `iso_shelf`, ordered top-to-bottom."""

    tiers: tuple[tuple[int, int], ...]
    tier_origins: tuple[tuple[int, int], ...]
    w: int
    d: int

    @property
    def top_center(self) -> tuple[int, int]:
        """Center point of the topmost shelf tier."""
        return self.tiers[0]

    def tier_point(self, tier: int, u: float = 0.5, v: float = 0.5) -> tuple[int, int]:
        """Project normalized `(u, v)` onto the specified `tier` (`0` = top shelf)."""
        if tier < 0 or tier >= len(self.tier_origins):
            msg = f"Shelf tier {tier} out of range [0..{len(self.tier_origins) - 1}]"
            raise IndexError(msg)
        tx, ty = self.tier_origins[tier]
        p_top = (tx, ty)
        p_right = (tx + self.w, ty + self.w // 2)
        p_left = (tx - self.d, ty + self.d // 2)
        return _project_diamond(p_top, p_right, p_left, u, v)


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

    tx, ty = _resolve_box_top_origin(x, y, iw, id_, itop_h, "center")
    p_top = (tx, ty)
    p_right = (tx + iw, ty + iw // 2)
    p_left = (tx - id_, ty + id_ // 2)
    p_front = (tx + iw - id_, ty + iw // 2 + id_ // 2)

    leg_span = max(2, min(4, min(iw, id_) // 6))
    du = min(0.24, max(0.08, (leg_span + 1.5) / float(iw)))
    dv = min(0.24, max(0.10, (leg_span + 1.5) / float(id_)))

    # INVARIANT: Draw all 4 corner legs back-to-front before the tabletop so the slab
    # cleanly occludes leg tops across both square and rectangular desk ratios.
    for lu, lv in (
        (du, dv),
        (du, 1.0 - dv),
        (1.0 - du, dv),
        (1.0 - du, 1.0 - dv),
    ):
        lx, ly = _project_diamond(p_top, p_right, p_left, lu, lv)
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
    )


def iso_rack(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    h: int,
    *,
    top: int,
    left: int,
    right: int,
    outline: int | None = None,
    highlight: int | None = None,
    bay_color: int | None = None,
    led_color: int | None = None,
    bays: int = 3,
    anchor: IsoAnchor = "center",
    front_style: RackFrontStyle = "bays",
    door_color: int | None = None,
) -> IsoRackSlots:
    """Draw a 2:1 isometric equipment rack with optional bays/grille/door and return slots."""
    iw = max(2, int(w))
    id_ = max(2, int(d))
    ih = max(1, int(h))

    target.iso_box(
        x,
        y,
        iw,
        id_,
        ih,
        top=top,
        left=left,
        right=right,
        outline=outline,
        highlight=highlight,
        anchor=anchor,
    )

    tx, ty = _resolve_box_top_origin(x, y, iw, id_, ih, anchor)
    dy_r = iw // 2
    dy_l = id_ // 2
    p_top = (tx, ty)
    p_right = (tx + iw, ty + dy_r)
    p_left = (tx - id_, ty + dy_l)
    p_front = (tx + iw - id_, ty + dy_r + dy_l)
    p_left_bot = (p_left[0], p_left[1] + ih)
    top_center = _project_diamond(p_top, p_right, p_left, 0.5, 0.5)

    bay_count = max(1, int(bays)) if bays > 0 else 0
    front_mounts: list[tuple[int, int]] = []
    if ih >= 6 and (bay_color is not None or door_color is not None):
        with target.plane(p0=p_left, p1=p_front, p2=p_left_bot) as face:
            if front_style == "bays":
                if bay_color is not None and bay_count > 0:
                    face.grid(
                        0.15,
                        0.15,
                        0.70,
                        0.70,
                        cols=1,
                        rows=bay_count,
                        color=bay_color,
                        cell_fill=0.55,
                    )
                    for idx in range(bay_count):
                        v = 0.15 + (idx + 0.45) * (0.70 / bay_count)
                        front_mounts.append(face.project(0.50, v))
                        if led_color is not None:
                            face.dot(0.80, v, led_color)
            elif front_style == "grille":
                grille_col = door_color if door_color is not None else bay_color
                if grille_col is not None:
                    face.rect(0.12, 0.12, 0.76, 0.76, fill=grille_col)
                    vent_cols = max(3, min(6, iw // 4))
                    for col_idx in range(vent_cols):
                        u = 0.20 + (col_idx / max(1, vent_cols - 1)) * 0.60
                        face.line(u, 0.20, u, 0.80, left)
                    if led_color is not None:
                        face.dot(0.80, 0.16, led_color)
            elif front_style == "glass_door":
                frame_col = door_color if door_color is not None else left
                recess_col = bay_color if bay_color is not None else frame_col
                face.rect(0.10, 0.10, 0.80, 0.80, fill=frame_col, outline=outline)
                face.rect(0.18, 0.16, 0.64, 0.68, fill=recess_col)
                if bay_count > 0:
                    for idx in range(bay_count):
                        v = 0.22 + (idx + 0.5) * (0.56 / bay_count)
                        front_mounts.append(face.project(0.50, v))
                        if led_color is not None:
                            face.dot(0.74, v, led_color)
                if highlight is not None:
                    face.line(0.24, 0.22, 0.44, 0.46, highlight)
            else:
                msg = f"Unsupported iso_rack front_style: {front_style!r}"
                raise ValueError(msg)

    return IsoRackSlots(
        top_center=top_center,
        p_top=p_top,
        p_right=p_right,
        p_left=p_left,
        p_front=p_front,
        p_left_bot=p_left_bot,
        front_mounts=tuple(front_mounts),
    )


def iso_shelf(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int,
    d: int,
    h: int,
    *,
    shelves: int = 2,
    top: int,
    left: int,
    right: int,
    post: int,
    outline: int | None = None,
    anchor: IsoAnchor = "center",
) -> IsoShelfSlots:
    """Draw a 2:1 isometric open shelving unit and return `IsoShelfSlots` per tier."""
    iw = max(4, int(w))
    id_ = max(4, int(d))
    ih = max(4, int(h))
    tier_count = max(1, int(shelves))

    tx, ty = _resolve_box_top_origin(x, y, iw, id_, ih, anchor)
    dy_r = iw // 2
    dy_l = id_ // 2

    p_top = (tx, ty)
    p_right = (tx + iw, ty + dy_r)
    p_left = (tx - id_, ty + dy_l)
    p_front = (tx + iw - id_, ty + dy_r + dy_l)

    for px, py in (p_top, p_left, p_right):
        target.line(px, py, px, py + ih, post)

    slab_h = max(2, min(4, ih // (tier_count + 1)))
    tier_origins: list[tuple[int, int]] = []
    tier_centers: list[tuple[int, int]] = []
    for idx in range(tier_count):
        y_off = round((idx / max(1, tier_count - 1)) * max(0, ih - slab_h)) if tier_count > 1 else 0
        tier_origins.append((tx, ty + y_off))
        tier_centers.append(
            _project_diamond(
                (tx, ty + y_off),
                (tx + iw, ty + y_off + dy_r),
                (tx - id_, ty + y_off + dy_l),
                0.5,
                0.5,
            )
        )

    for idx in range(tier_count - 1, -1, -1):
        # INVARIANT: Draw lower shelves before upper shelves so upper slabs occlude posts cleanly.
        ox, oy = tier_origins[idx]
        target.iso_box(
            ox,
            oy,
            iw,
            id_,
            slab_h,
            top=top,
            left=left,
            right=right,
            outline=outline,
            anchor="top",
        )

    target.line(p_front[0], p_front[1], p_front[0], p_front[1] + ih, post)
    return IsoShelfSlots(
        tiers=tuple(tier_centers),
        tier_origins=tuple(tier_origins),
        w=iw,
        d=id_,
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

    tx, ty = _resolve_box_top_origin(icx, icy, sw, sd, sh, "center")
    p_top = (tx, ty)
    p_right = (tx + sw, ty + sw // 2)
    p_left = (tx - sd, ty + sd // 2)

    def _draw_backrest() -> None:
        if facing == "se":
            target.iso_box(
                tx,
                ty - bh,
                2,
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
                2,
                bh,
                top=top,
                left=left,
                right=back,
                outline=outline,
                anchor="top",
            )
        elif facing == "nw":
            target.iso_box(
                p_right[0] - 2,
                p_right[1] - bh,
                2,
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
                2,
                bh,
                top=top,
                left=left,
                right=back,
                outline=outline,
                anchor="top",
            )
        else:
            msg = f"Unsupported chair facing: {facing!r}"
            raise ValueError(msg)

    if facing in ("se", "sw"):
        _draw_backrest()
        target.iso_box(
            icx, icy, sw, sd, sh, top=top, left=left, right=right, outline=outline, anchor="center"
        )
    else:
        target.iso_box(
            icx, icy, sw, sd, sh, top=top, left=left, right=right, outline=outline, anchor="center"
        )
        _draw_backrest()

    return _project_diamond(p_top, p_right, p_left, 0.5, 0.5)


def iso_wall_shelf(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    top: int,
    front: int,
    bracket: int | None = None,
    outline: int | None = None,
    depth: int = 4,
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """Draw a wall-mounted isometric shelf along `(p0, p1, p2)` and return 3 top slots."""
    d = max(2, int(depth))
    dx = -d if p1[1] >= p0[1] else d
    dy = d // 2
    p0_out = (p0[0] + dx, p0[1] + dy)
    p1_out = (p1[0] + dx, p1[1] + dy)

    with target.plane(p0=p0, p1=p1, p2=p0_out) as plank:
        plank.rect(0.0, 0.0, 1.0, 1.0, fill=top, outline=outline)
    with target.plane(p0=p0_out, p1=p1_out, p2=(p0_out[0], p0_out[1] + 2)) as lip:
        lip.rect(0.0, 0.0, 1.0, 1.0, fill=front, outline=outline)

    if bracket is not None:
        for u in (0.18, 0.82):
            bx = round(p0[0] + u * (p1[0] - p0[0]))
            by = round(p0[1] + u * (p1[1] - p0[1])) + 2
            target.line(bx, by, bx, by + 3, bracket)
            target.line(bx, by, round(bx + dx * 0.7), round(by + dy * 0.7), bracket)

    slots: list[tuple[int, int]] = []
    for u in (0.22, 0.50, 0.78):
        sx = round(p0[0] + u * (p1[0] - p0[0]) + dx * 0.5)
        sy = round(p0[1] + u * (p1[1] - p0[1]) + dy * 0.5)
        slots.append((sx, sy))
    return (slots[0], slots[1], slots[2])


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

    tx, ty = _resolve_box_top_origin(x, y, iw, id_, ifh, anchor)
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

    return _project_diamond(p_top, p_right, p_left, 0.5, 0.5)


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


def iso_drawer_unit(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 14,
    d: int = 14,
    h: int = 18,
    *,
    drawers: int = 3,
    top: int,
    left: int,
    right: int,
    drawer_face: int,
    handle: int | None = None,
    outline: int | None = None,
    highlight: int | None = None,
    anchor: IsoAnchor = "center",
) -> tuple[int, int]:
    """Draw a 2:1 isometric drawer cabinet and return its `top_center` `(x, y)` anchor."""
    iw = max(6, int(w))
    id_ = max(6, int(d))
    ih = max(6, int(h))
    count = max(1, int(drawers))

    target.iso_box(
        x,
        y,
        iw,
        id_,
        ih,
        top=top,
        left=left,
        right=right,
        outline=outline,
        highlight=highlight,
        anchor=anchor,
    )

    tx, ty = _resolve_box_top_origin(x, y, iw, id_, ih, anchor)
    p_top = (tx, ty)
    p_right = (tx + iw, ty + iw // 2)
    p_left = (tx - id_, ty + id_ // 2)
    p_front = (tx + iw - id_, ty + iw // 2 + id_ // 2)
    p_left_bot = (p_left[0], p_left[1] + ih)

    with target.plane(p0=p_left, p1=p_front, p2=p_left_bot) as face:
        face.grid(0.12, 0.10, 0.76, 0.80, cols=1, rows=count, color=drawer_face, cell_fill=0.65)
        if handle is not None:
            for idx in range(count):
                v = 0.10 + (idx + 0.5) * (0.80 / count)
                face.line(0.36, v, 0.64, v, handle)

    return _project_diamond(p_top, p_right, p_left, 0.5, 0.5)
