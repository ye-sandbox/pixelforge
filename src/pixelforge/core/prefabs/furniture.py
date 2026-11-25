"""Furniture 2:1 isometric prefab helpers (desks, racks, shelves)."""

from __future__ import annotations

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.iso import IsoAnchor

Canvas = Asset | Layer


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
) -> None:
    """Draw a 2:1 isometric desk with side legs, beveled tabletop, and optional desk mat."""
    iw = max(4, int(w))
    id_ = max(4, int(d))
    ileg_h = max(1, int(leg_h))
    itop_h = max(1, int(top_h))

    leg_offset_x = max(2, round(iw * 0.72))
    leg_offset_y = max(2, id_ // 10)
    leg_span = max(2, min(6, iw // 10))

    target.iso_box(
        x - leg_offset_x,
        y + leg_offset_y,
        leg_span,
        leg_span,
        ileg_h,
        top=leg_top,
        left=leg_left,
        right=leg_right,
        anchor="center",
    )
    target.iso_box(
        x + leg_offset_x,
        y + leg_offset_y,
        leg_span,
        leg_span,
        ileg_h,
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
        mw = max(4, int(mat_w) if mat_w is not None else iw)
        target.iso_tile(x - max(0, iw // 11), y, mw, mat_color, height=max(2, mw // 2))


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
) -> None:
    """Draw a 2:1 isometric equipment rack with optional front-left drive bays and LEDs."""
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

    if bay_color is None or bays <= 0 or ih < 6:
        return

    dy_r = iw // 2
    dy_l = id_ // 2
    if anchor == "top":
        tx, ty = round(x), round(y)
    elif anchor == "center":
        tx = round(x - (iw - id_) * 0.5)
        ty = round(y - (dy_r + dy_l) * 0.5)
    elif anchor == "bottom":
        tx = round(x - (iw - id_))
        ty = round(y - (dy_r + dy_l + ih))
    else:
        msg = f"Unsupported iso_rack anchor: {anchor!r}"
        raise ValueError(msg)

    p_left = (tx - id_, ty + dy_l)
    p_front = (tx + iw - id_, ty + dy_r + dy_l)
    p_left_bot = (p_left[0], p_left[1] + ih)

    bay_count = max(1, int(bays))
    with target.plane(p0=p_left, p1=p_front, p2=p_left_bot) as face:
        face.grid(0.15, 0.15, 0.70, 0.70, cols=1, rows=bay_count, color=bay_color, cell_fill=0.55)
        if led_color is not None:
            for idx in range(bay_count):
                v = 0.15 + (idx + 0.45) * (0.70 / bay_count)
                face.dot(0.80, v, led_color)


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
) -> None:
    """Draw a 2:1 isometric open shelving unit with vertical corner posts and stacked tiers."""
    iw = max(4, int(w))
    id_ = max(4, int(d))
    ih = max(4, int(h))
    tier_count = max(1, int(shelves))

    dy_r = iw // 2
    dy_l = id_ // 2
    if anchor == "top":
        tx, ty = round(x), round(y)
    elif anchor == "center":
        tx = round(x - (iw - id_) * 0.5)
        ty = round(y - (dy_r + dy_l) * 0.5)
    elif anchor == "bottom":
        tx = round(x - (iw - id_))
        ty = round(y - (dy_r + dy_l + ih))
    else:
        msg = f"Unsupported iso_shelf anchor: {anchor!r}"
        raise ValueError(msg)

    p_top = (tx, ty)
    p_right = (tx + iw, ty + dy_r)
    p_left = (tx - id_, ty + dy_l)
    p_front = (tx + iw - id_, ty + dy_r + dy_l)

    for px, py in (p_top, p_left, p_right):
        target.line(px, py, px, py + ih, post)

    slab_h = max(2, min(4, ih // (tier_count + 1)))
    for idx in range(tier_count - 1, -1, -1):
        # INVARIANT: Draw lower shelves before upper shelves so upper slabs occlude posts cleanly.
        y_off = round((idx / max(1, tier_count - 1)) * max(0, ih - slab_h)) if tier_count > 1 else 0
        target.iso_box(
            tx,
            ty + y_off,
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
