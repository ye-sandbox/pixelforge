"""Shared types, slot dataclasses, and projection helpers for isometric furniture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.iso import IsoAnchor
from pixelforge.core.prefabs.atmosphere import PlaneRegion

Canvas = Asset | Layer
RackFrontStyle = Literal["bays", "grille", "glass_door"]
ChairFacing = Literal["se", "sw", "nw", "ne"]


def resolve_box_top_origin(
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


def project_diamond(
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
        return project_diamond(self.p_top, self.p_right, self.p_left, u, v)

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
        return project_diamond(self.p_top, self.p_right, self.p_left, u, v)

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
        return project_diamond(p_top, p_right, p_left, u, v)
