"""Furniture 2:1 isometric prefab helpers (desks, racks, shelves)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.iso import IsoAnchor
from pixelforge.core.prefabs.atmosphere import PlaneRegion

Canvas = Asset | Layer
RackFrontStyle = Literal["bays", "grille", "glass_door"]


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

    tx, ty = _resolve_box_top_origin(x, y, iw, id_, itop_h, "center")
    p_top = (tx, ty)
    p_right = (tx + iw, ty + iw // 2)
    p_left = (tx - id_, ty + id_ // 2)
    p_front = (tx + iw - id_, ty + iw // 2 + id_ // 2)
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
