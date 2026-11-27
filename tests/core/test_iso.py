"""Unit tests for 2:1 isometric projection, tiles, and extruded boxes."""

from __future__ import annotations

import numpy as np
import pytest

from pixelforge.core.iso import iso_box, iso_cylinder, iso_project, iso_ramp, iso_tile
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import TRANSPARENT_INDEX


def test_iso_project_2_to_1_grid_exactness() -> None:
    """Verify 2:1 integer isometric projection along X, Y, and Z axes."""
    assert iso_project(0, 0, 0, origin=(32, 10)) == (32, 10)
    assert iso_project(1, 0, 0, origin=(32, 10)) == (34, 11)
    assert iso_project(0, 1, 0, origin=(32, 10)) == (30, 11)
    assert iso_project(1, 1, 0, origin=(32, 10)) == (32, 12)
    assert iso_project(0, 0, 5, origin=(32, 10)) == (32, 5)

    # Custom tile grid projection (32x16 tiles)
    assert iso_project(2, 1, 0, origin=(100, 50), tile_w=32.0, tile_h=16.0) == (116, 74)


def test_iso_tile_diamond_and_outline() -> None:
    """Verify 2:1 diamond tile rasterization and isolated outline."""
    surf = IndexedSurface(32, 24)
    iso_tile(surf, 16, 12, width=16, color=3, outline=1)

    # Center is filled with tile color
    assert surf.get(16, 12) == 3
    # Top vertex at (16, 8) gets tile pixel, (16, 7) gets outline
    assert surf.get(16, 8) == 3
    assert surf.get(16, 7) == 1
    assert surf.get(16, 6) == TRANSPARENT_INDEX
    # Left/right vertices at (8, 12) and (24, 12) get tile pixels, +-1 gets outline
    assert surf.get(8, 12) == 3
    assert surf.get(7, 12) == 1
    assert surf.get(24, 12) == 3
    assert surf.get(25, 12) == 1


def test_iso_box_three_faces_highlight_and_anchors() -> None:
    """Verify 3-face iso_box geometry, top-edge highlight, outline, and anchor modes."""
    surf = IndexedSurface(48, 48)
    iso_box(
        surf,
        24,
        8,
        w=10,
        d=8,
        h=10,
        top=2,
        left=3,
        right=4,
        outline=1,
        highlight=5,
        anchor="top",
    )

    # Top vertex is (24, 8), outline directly above at (24, 7)
    assert surf.get(24, 7) == 1
    assert surf.get(24, 8) == 2
    # Front-top vertex is (24 + 10 - 8, 8 + 5 + 4) = (26, 17), highlighted with 5
    assert surf.get(26, 17) == 5
    # Left face sample inside (16..26, 12..27)
    assert surf.get(20, 20) == 3
    # Right face sample inside (26..34, 13..27)
    assert surf.get(30, 20) == 4
    # Bottom-front vertex is (26, 27), outline below at (26, 28)
    assert surf.get(26, 28) == 1
    assert surf.get(26, 29) == TRANSPARENT_INDEX

    # Center and bottom anchor modes match expected vertical footprint
    s_center = IndexedSurface(40, 40)
    iso_box(s_center, 20, 20, w=8, d=8, h=6, top=2, left=3, right=4, anchor="center")
    assert s_center.get(20, 20) == 2

    s_bottom = IndexedSurface(40, 40)
    iso_box(s_bottom, 20, 30, w=8, d=8, h=6, top=2, left=3, right=4, anchor="bottom")
    assert s_bottom.get(20, 30) in (3, 4)
    assert s_bottom.get(20, 31) == TRANSPARENT_INDEX
    assert np.count_nonzero(s_bottom.data == 2) > 0


def test_iso_cylinder_and_iso_ramp() -> None:
    """Verify `iso_cylinder` and `iso_ramp` render crisp 2:1 isometric geometry."""
    s_cyl = IndexedSurface(32, 32, track_maps=True)
    iso_cylinder(
        s_cyl,
        16,
        10,
        6,
        10,
        top=1,
        side=2,
        shade=3,
        highlight=4,
        outline=0,
        anchor="top",
    )
    assert s_cyl.get(16, 10) == 1
    assert np.count_nonzero(s_cyl.data == 2) > 0
    assert np.count_nonzero(s_cyl.data == 3) > 0
    assert np.count_nonzero(s_cyl.data == 4) > 0
    assert np.count_nonzero(s_cyl.data == 0) > 0

    for direction in ("right", "left", "front", "back"):
        s_ramp = IndexedSurface(32, 32, track_maps=True)
        iso_ramp(
            s_ramp,
            16,
            8,
            8,
            8,
            6,
            slope=1,
            left=2,
            right=3,
            direction=direction,
            outline=0,
            highlight=4,
        )
        assert np.count_nonzero(s_ramp.data == 1) > 0
        assert np.count_nonzero(s_ramp.data == 0) > 0

    with pytest.raises(ValueError, match="Unsupported iso_ramp direction"):
        iso_ramp(
            IndexedSurface(16, 16),
            8,
            4,
            4,
            4,
            4,
            slope=1,
            left=2,
            right=3,
            direction="up",  # type: ignore[arg-type]
        )
