"""Unit tests for the affine `(u, v)` `Plane` context manager."""

from __future__ import annotations

import numpy as np

from pixelforge.core.plane import Plane
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import TRANSPARENT_INDEX, AnchorPoint


def test_plane_projection_rect_bevel_and_anchors() -> None:
    """Verify `(u, v)` projection, filled rect, top-left bevel, and anchor emission."""
    surf = IndexedSurface(40, 40)
    recorded: list[AnchorPoint] = []

    def emit(name: str, x: int, y: int) -> AnchorPoint:
        pt = AnchorPoint(name=name, x=x, y=y)
        recorded.append(pt)
        return pt

    with Plane(surf, p0=(10, 5), p1=(30, 5), p2=(10, 25), emit_anchor=emit) as p:
        p.rect(0.0, 0.0, 1.0, 1.0, fill=2, bevel=(8, 9))
        p.rect(0.25, 0.25, 0.5, 0.5, fill=4)
        p.dot(0.5, 0.5, 7, anchor="center")
        p.anchor("top_left", 0.0, 0.0)

    # Top/left rim gets bevel highlight (8), bottom/right gets bevel shadow (9)
    assert surf.get(15, 5) == 8
    assert surf.get(10, 15) == 8
    assert surf.get(20, 25) == 9
    assert surf.get(30, 15) == 9
    # Inner rect and center dot
    assert surf.get(16, 11) == 4
    assert surf.get(20, 15) == 7
    assert recorded == [
        AnchorPoint(name="center", x=20, y=15),
        AnchorPoint(name="top_left", x=10, y=5),
    ]


def test_plane_angled_extrude_y_grid_line_quad_and_dither() -> None:
    """Verify tilted plane `extrude_y`, `grid`, `line`, `quad`, and clipped `dither`."""
    surf = IndexedSurface(64, 64)
    recorded: list[AnchorPoint] = []

    def emit(name: str, x: int, y: int) -> AnchorPoint:
        pt = AnchorPoint(name=name, x=x, y=y)
        recorded.append(pt)
        return pt

    with Plane(surf, p0=(17, 32), p1=(52, 41), p2=(5, 49), emit_anchor=emit) as deck:
        deck.rect(0.0, 0.0, 1.0, 1.0, fill=3, extrude_y=4, side_left=6, side_right=7)
        deck.grid(0.1, 0.1, 0.8, 0.5, cols=6, rows=3, color=1)
        deck.dot(0.45, 0.29, 5, anchor="trackpoint")

    # Extruded downward-facing walls must extend below front-bottom edge (40, 58) down to y=62
    assert surf.get(40, 58) == 3
    assert surf.get(40, 62) in (6, 7)
    # Left wall sample below (5, 49) -> (20, 55)
    assert surf.get(20, 56) == 6
    # Right wall sample below (52, 41)..(40, 58)
    assert surf.get(46, 52) == 7
    # Back-top edge (17, 32)->(52, 41) must NOT extrude upward or outside
    assert surf.get(34, 35) == TRANSPARENT_INDEX
    # Keycaps painted in index 1
    assert np.count_nonzero(surf.data == 1) > 0
    assert recorded[0].name == "trackpoint"

    # Clipped dither on tilted plane must never leak outside the projected quad
    dither_surf = IndexedSurface(32, 32)
    with Plane(dither_surf, p0=(16, 4), p1=(28, 16), p2=(4, 16), emit_anchor=emit) as diamond:
        diamond.dither(0.0, 0.0, 1.0, 1.0, 1, 2, pattern="checker", ratio=0.5, mask="all")
    # Bounding box corner (4, 4) is outside the diamond so it must remain transparent
    assert dither_surf.get(4, 4) == TRANSPARENT_INDEX
    assert dither_surf.get(28, 4) == TRANSPARENT_INDEX
    assert dither_surf.get(16, 16) in (1, 2)

    # Lines mode grid + quad + line
    line_surf = IndexedSurface(20, 20)
    with Plane(line_surf, p0=(2, 2), p1=(14, 2), p2=(2, 14), emit_anchor=emit) as p:
        p.grid(0.0, 0.0, 1.0, 1.0, cols=2, rows=2, color=5, mode="lines")
        p.line(0.0, 0.0, 1.0, 1.0, 8)
        p.quad((0.2, 0.2), (0.4, 0.2), (0.4, 0.4), (0.2, 0.4), 9)
    assert line_surf.get(8, 2) == 5
    assert line_surf.get(2, 8) == 5
    assert line_surf.get(14, 14) == 8
    assert line_surf.get(5, 5) == 9
