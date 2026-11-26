"""Isometric rack, shelf, drawer, and cabinet storage prefabs."""

from __future__ import annotations

from pixelforge.core.iso import IsoAnchor
from pixelforge.core.plane import Point2D
from pixelforge.core.prefabs.furniture._common import (
    Canvas,
    IsoRackSlots,
    IsoShelfSlots,
    RackFrontStyle,
    project_diamond,
    resolve_box_top_origin,
)


def _draw_rack_front(
    target: Canvas,
    p_left: tuple[int, int],
    p_front: tuple[int, int],
    p_left_bot: tuple[int, int],
    iw: int,
    left: int,
    outline: int | None,
    highlight: int | None,
    bay_color: int | None,
    led_color: int | None,
    bay_count: int,
    front_style: RackFrontStyle,
    door_color: int | None,
) -> list[tuple[int, int]]:
    front_mounts: list[tuple[int, int]] = []
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
    return front_mounts


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

    tx, ty = resolve_box_top_origin(x, y, iw, id_, ih, anchor)
    dy_r = iw // 2
    dy_l = id_ // 2
    p_top = (tx, ty)
    p_right = (tx + iw, ty + dy_r)
    p_left = (tx - id_, ty + dy_l)
    p_front = (tx + iw - id_, ty + dy_r + dy_l)
    p_left_bot = (p_left[0], p_left[1] + ih)
    top_center = project_diamond(p_top, p_right, p_left, 0.5, 0.5)

    bay_count = max(1, int(bays)) if bays > 0 else 0
    front_mounts: list[tuple[int, int]] = []
    if ih >= 6 and (bay_color is not None or door_color is not None):
        front_mounts = _draw_rack_front(
            target,
            p_left,
            p_front,
            p_left_bot,
            iw,
            left,
            outline,
            highlight,
            bay_color,
            led_color,
            bay_count,
            front_style,
            door_color,
        )

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

    tx, ty = resolve_box_top_origin(x, y, iw, id_, ih, anchor)
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
            project_diamond(
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

    tx, ty = resolve_box_top_origin(x, y, iw, id_, ih, anchor)
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

    return project_diamond(p_top, p_right, p_left, 0.5, 0.5)


def iso_nightstand(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 12,
    d: int = 12,
    h: int = 14,
    *,
    drawers: int = 2,
    top: int,
    left: int,
    right: int,
    drawer_face: int,
    handle: int | None = None,
    outline: int | None = None,
    highlight: int | None = None,
    anchor: IsoAnchor = "center",
) -> tuple[int, int]:
    """Draw a compact 2:1 isometric bedside nightstand and return `top_center` `(x, y)`."""
    return iso_drawer_unit(
        target,
        x,
        y,
        max(6, int(w)),
        max(6, int(d)),
        max(6, int(h)),
        drawers=max(1, int(drawers)),
        top=top,
        left=left,
        right=right,
        drawer_face=drawer_face,
        handle=handle,
        outline=outline,
        highlight=highlight,
        anchor=anchor,
    )


def iso_filing_cabinet(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 12,
    d: int = 14,
    h: int = 24,
    *,
    drawers: int = 3,
    top: int,
    left: int,
    right: int,
    drawer_face: int,
    handle: int | None = None,
    label_color: int | None = None,
    outline: int | None = None,
    highlight: int | None = None,
    anchor: IsoAnchor = "center",
) -> tuple[int, int]:
    """Draw a tall 2:1 isometric filing cabinet with optional label tabs and return `top_center`."""
    iw = max(6, int(w))
    id_ = max(6, int(d))
    ih = max(10, int(h))
    count = max(2, int(drawers))
    top_center = iso_drawer_unit(
        target,
        x,
        y,
        iw,
        id_,
        ih,
        drawers=count,
        top=top,
        left=left,
        right=right,
        drawer_face=drawer_face,
        handle=handle,
        outline=outline,
        highlight=highlight,
        anchor=anchor,
    )
    if label_color is not None:
        tx, ty = resolve_box_top_origin(x, y, iw, id_, ih, anchor)
        p_left = (tx - id_, ty + id_ // 2)
        p_front = (tx + iw - id_, ty + iw // 2 + id_ // 2)
        p_left_bot = (p_left[0], p_left[1] + ih)
        with target.plane(p0=p_left, p1=p_front, p2=p_left_bot) as face:
            for idx in range(count):
                v = 0.10 + (idx + 0.25) * (0.80 / count)
                face.line(0.40, v, 0.60, v, label_color)
    return top_center


def _draw_cabinet_box(
    target: Canvas,
    x: int | float,
    y: int | float,
    iw: int,
    id_: int,
    ih: int,
    *,
    top: int,
    left: int,
    right: int,
    outline: int | None,
    highlight: int | None,
    anchor: IsoAnchor,
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]]:
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
    tx, ty = resolve_box_top_origin(x, y, iw, id_, ih, anchor)
    p_top = (tx, ty)
    p_right = (tx + iw, ty + iw // 2)
    p_left = (tx - id_, ty + id_ // 2)
    p_front = (tx + iw - id_, ty + iw // 2 + id_ // 2)
    p_left_bot = (p_left[0], p_left[1] + ih)
    top_center = project_diamond(p_top, p_right, p_left, 0.5, 0.5)
    return (top_center, p_left, p_front, p_left_bot)


def iso_wardrobe(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 18,
    d: int = 12,
    h: int = 30,
    *,
    top: int,
    left: int,
    right: int,
    door: int,
    seam: int | None = None,
    handle: int | None = None,
    outline: int | None = None,
    highlight: int | None = None,
    anchor: IsoAnchor = "center",
) -> tuple[int, int]:
    """Draw a tall 2:1 isometric double-door wardrobe and return `top_center` `(x, y)`."""
    iw = max(8, int(w))
    id_ = max(6, int(d))
    ih = max(12, int(h))
    top_center, p_left, p_front, p_left_bot = _draw_cabinet_box(
        target,
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
    with target.plane(p0=p_left, p1=p_front, p2=p_left_bot) as face:
        face.rect(0.10, 0.08, 0.80, 0.84, fill=door)
        seam_col = seam if seam is not None else (outline if outline is not None else left)
        face.line(0.50, 0.08, 0.50, 0.92, seam_col)
        if handle is not None:
            face.line(0.42, 0.42, 0.42, 0.56, handle)
            face.line(0.58, 0.42, 0.58, 0.56, handle)
    return top_center


def iso_locker(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 12,
    d: int = 12,
    h: int = 30,
    *,
    top: int,
    left: int,
    right: int,
    door: int,
    vent: int | None = None,
    handle: int | None = None,
    badge_color: int | None = None,
    outline: int | None = None,
    highlight: int | None = None,
    anchor: IsoAnchor = "center",
) -> tuple[int, int]:
    """Draw a tall 2:1 isometric metal locker with vents and return `top_center` `(x, y)`."""
    iw = max(6, int(w))
    id_ = max(6, int(d))
    ih = max(12, int(h))
    top_center, p_left, p_front, p_left_bot = _draw_cabinet_box(
        target,
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
    with target.plane(p0=p_left, p1=p_front, p2=p_left_bot) as face:
        face.rect(0.14, 0.08, 0.72, 0.84, fill=door)
        vent_col = vent if vent is not None else (outline if outline is not None else left)
        for v in (0.14, 0.20, 0.80, 0.86):
            face.line(0.24, v, 0.76, v, vent_col)
        if handle is not None:
            face.line(0.74, 0.45, 0.74, 0.57, handle)
        if badge_color is not None:
            face.line(0.38, 0.30, 0.62, 0.30, badge_color)
    return top_center


def iso_mini_fridge(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int = 12,
    d: int = 12,
    h: int = 18,
    *,
    top: int,
    left: int,
    right: int,
    door: int,
    handle: int | None = None,
    vent: int | None = None,
    led_color: int | None = None,
    outline: int | None = None,
    highlight: int | None = None,
    anchor: IsoAnchor = "center",
) -> tuple[int, int]:
    """Draw a compact 2:1 isometric mini-fridge and return `top_center` `(x, y)`."""
    iw = max(6, int(w))
    id_ = max(6, int(d))
    ih = max(8, int(h))
    top_center, p_left, p_front, p_left_bot = _draw_cabinet_box(
        target,
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
    with target.plane(p0=p_left, p1=p_front, p2=p_left_bot) as face:
        face.rect(0.12, 0.08, 0.76, 0.72, fill=door)
        if handle is not None:
            face.line(0.76, 0.24, 0.76, 0.56, handle)
        if vent is not None:
            face.line(0.18, 0.86, 0.82, 0.86, vent)
            face.line(0.18, 0.92, 0.82, 0.92, vent)
        if led_color is not None:
            face.dot(0.24, 0.16, led_color)
    return top_center
