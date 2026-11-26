"""Shared drawing, scatter, recolor, and metadata helpers for `Asset` and `Layer`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

import numpy as np

from pixelforge.core.font import draw_indexed_text
from pixelforge.core.iso import IsoAnchor, iso_box, iso_tile
from pixelforge.core.plane import Plane, Point2D
from pixelforge.core.surface import (
    DitherMask,
    DitherPattern,
    IndexedSurface,
    MirrorSource,
)
from pixelforge.core.surface_maps import Normal3D
from pixelforge.core.types import (
    TRANSPARENT_INDEX,
    AnchorPoint,
    BitmapFontPreset,
    HitboxRect,
)

ScatterMask = Literal["all", "opaque", "transparent"]
SelOutSpec = int | tuple[int, int] | tuple[int, int, int]
AnchorAlign = Literal["center", "bottom-center", "top-left"]


class DrawingMixin:
    """Shared drawing, scatter, recolor, and metadata helpers for `Asset` and `Layer`."""

    @property
    def surface(self) -> IndexedSurface:
        raise NotImplementedError

    def _next_rng(self) -> float:
        raise NotImplementedError

    def _emit_anchor(
        self,
        name: str,
        x: int | float,
        y: int | float,
        *,
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> AnchorPoint:
        raise NotImplementedError

    def _emit_hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        *,
        kind: str | None = None,
    ) -> HitboxRect:
        raise NotImplementedError

    def _resolve_pal_index(self, token_or_idx: str | int) -> int:
        raise NotImplementedError

    def _make_plane(
        self,
        p0: Point2D,
        p1: Point2D,
        p2: Point2D,
        *,
        normal: Normal3D | None = None,
    ) -> Plane:
        return Plane(self.surface, p0, p1, p2, self._emit_anchor, normal=normal)

    def plane(
        self,
        p0: Point2D,
        p1: Point2D,
        p2: Point2D,
        *,
        normal: Normal3D | None = None,
    ) -> Plane:
        """Open a normalized `(u, v)` affine `Plane` context onto the active surface."""
        return self._make_plane(p0, p1, p2, normal=normal)

    def put(self, x: int | float, y: int | float, color: int) -> None:
        """Write a single integer-grid pixel (1px surgical escape hatch)."""
        self.surface.put(x, y, color)

    def erase(self, x: int | float, y: int | float) -> None:
        """Erase a single integer-grid pixel back to `TRANSPARENT_INDEX`."""
        self.surface.erase(x, y)

    def get(self, x: int | float, y: int | float) -> int:
        """Read palette index at `(x, y)` or `TRANSPARENT_INDEX` when out of bounds."""
        return self.surface.get(x, y)

    def clear(self, color: int = TRANSPARENT_INDEX) -> None:
        """Fill the active surface with `color`."""
        self.surface.clear(color)

    def rect(
        self,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw an axis-aligned rectangle onto the active surface."""
        self.surface.rect(x, y, w, h, color, fill=fill)

    def rounded_rect(
        self,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        radius: int,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw a pixel-crisp rounded rectangle onto the active surface."""
        self.surface.rounded_rect(x, y, w, h, radius, color, fill=fill)

    def line(
        self,
        x0: int | float,
        y0: int | float,
        x1: int | float,
        y1: int | float,
        color: int,
    ) -> None:
        """Draw an integer Bresenham line onto the active surface."""
        self.surface.line(x0, y0, x1, y1, color)

    def circle(
        self,
        cx: int | float,
        cy: int | float,
        radius: int,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw an integer midpoint circle onto the active surface."""
        self.surface.circle(cx, cy, radius, color, fill=fill)

    def ellipse(
        self,
        cx: int | float,
        cy: int | float,
        rx: int,
        ry: int,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw an integer midpoint ellipse onto the active surface."""
        self.surface.ellipse(cx, cy, rx, ry, color, fill=fill)

    def polygon(
        self,
        points: Sequence[Point2D],
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw a polygon onto the active surface."""
        self.surface.polygon(points, color, fill=fill)

    def quad(
        self,
        p0: Point2D,
        p1: Point2D,
        p2: Point2D,
        p3: Point2D,
        color: int,
        *,
        fill: bool = True,
    ) -> None:
        """Draw a quadrilateral onto the active surface."""
        self.surface.quad(p0, p1, p2, p3, color, fill=fill)

    def fill(self, x: int | float, y: int | float, color: int) -> None:
        """Scanline 4-connected flood fill on the active surface."""
        self.surface.fill(x, y, color)

    def dither(
        self,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        color_a: int | None,
        color_b: int | None,
        *,
        pattern: DitherPattern = "bayer4",
        ratio: float = 0.5,
        mask: DitherMask = "all",
    ) -> None:
        """Apply ordered Bayer 2x2/4x4 or checker dithering onto the active surface."""
        self.surface.dither(x, y, w, h, color_a, color_b, pattern=pattern, ratio=ratio, mask=mask)

    def spr(
        self,
        grid: Sequence[str],
        x: int | float,
        y: int | float,
        color_map: Mapping[str, int],
    ) -> None:
        """Stamp an ASCII sprite grid onto the active surface."""
        self.surface.spr(grid, x, y, color_map)

    def mirror_x(self, source: MirrorSource = "left") -> None:
        """Mirror one horizontal half of the active surface onto the other."""
        self.surface.mirror_x(source)

    def flip_x(self) -> None:
        """Flip the active surface horizontally."""
        self.surface.flip_x()

    def flip_y(self) -> None:
        """Flip the active surface vertically."""
        self.surface.flip_y()

    def auto_outline(self, outline_color: int) -> None:
        """Add a 1px 4-connected outline onto transparent border pixels."""
        self.surface.auto_outline(outline_color)

    def sel_out(
        self,
        top_color: int,
        bottom_color: int | None = None,
        *,
        side_color: int | None = None,
    ) -> None:
        """Apply directional selective outlining around opaque pixels."""
        self.surface.sel_out(top_color, bottom_color, side_color=side_color)

    def edge_mask(
        self,
        top_color: int | None = None,
        bottom_color: int | None = None,
    ) -> None:
        """Recolor top/bottom exposed opaque edge pixels for bevels and rims."""
        self.surface.edge_mask(top_color, bottom_color)

    def text(
        self,
        text: str,
        x: int | float,
        y: int | float,
        color: int,
        *,
        font: BitmapFontPreset = "4x6",
        scale: int = 1,
        shadow: int | None = None,
        letter_spacing: int | None = None,
        line_height: int | None = None,
    ) -> None:
        """Render crisp 1x bitmap text onto the active surface using palette indices."""
        draw_indexed_text(
            self.surface,
            text,
            round(x),
            round(y),
            color,
            font=font,
            scale=scale,
            shadow=shadow,
            letter_spacing=letter_spacing,
            line_height=line_height,
        )

    def iso_tile(
        self,
        cx: int | float,
        cy: int | float,
        width: int,
        color: int,
        *,
        height: int | None = None,
        fill: bool = True,
        outline: int | None = None,
    ) -> None:
        """Draw a 2:1 isometric diamond tile onto the active surface."""
        iso_tile(self.surface, cx, cy, width, color, height=height, fill=fill, outline=outline)

    def iso_box(
        self,
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
        anchor: IsoAnchor = "top",
    ) -> None:
        """Draw a 2:1 isometric 3-face box onto the active surface."""
        iso_box(
            self.surface,
            x,
            y,
            w,
            d,
            h,
            top=top,
            left=left,
            right=right,
            outline=outline,
            highlight=highlight,
            anchor=anchor,
        )

    def scatter(
        self,
        count: int,
        colors: Sequence[int] | int,
        *,
        mask: ScatterMask = "opaque",
        bounds: tuple[int, int, int, int] | None = None,
        only_colors: Sequence[int] | None = None,
    ) -> int:
        """Deterministically place `count` pixels onto masked coordinates using `rng`."""
        if count <= 0:
            return 0
        palette_choices = (
            (int(colors),) if isinstance(colors, int) else tuple(int(c) for c in colors)
        )
        if not palette_choices:
            msg = "scatter requires at least one color"
            raise ValueError(msg)

        surf = self.surface
        if bounds is None:
            x0, y0, x1, y1 = 0, 0, surf.width, surf.height
        else:
            bx, by, bw, bh = bounds
            x0 = max(0, int(bx))
            y0 = max(0, int(by))
            x1 = min(surf.width, int(bx) + int(bw))
            y1 = min(surf.height, int(by) + int(bh))
        if x0 >= x1 or y0 >= y1:
            return 0

        patch = surf.data[y0:y1, x0:x1]
        if mask == "opaque":
            eligible = patch != TRANSPARENT_INDEX
        elif mask == "transparent":
            eligible = patch == TRANSPARENT_INDEX
        elif mask == "all":
            eligible = np.ones_like(patch, dtype=bool)
        else:
            msg = f"Unsupported scatter mask: {mask!r}"
            raise ValueError(msg)

        if only_colors is not None:
            allowed = np.isin(patch, np.array([int(c) for c in only_colors], dtype=np.uint8))
            eligible &= allowed

        coords = np.argwhere(eligible)
        total = len(coords)
        if total == 0:
            return 0

        picks = min(int(count), total)
        indices = list(range(total))
        # INVARIANT: Partial Fisher-Yates driven solely by the asset's mulberry32 stream
        # guarantees exact `count` placement and bit-determinism without numpy.random.
        for i in range(picks):
            j = i + int(self._next_rng() * (total - i))
            indices[i], indices[j] = indices[j], indices[i]
            ry, rx = int(coords[indices[i], 0]), int(coords[indices[i], 1])
            color = palette_choices[int(self._next_rng() * len(palette_choices))]
            surf.put(x0 + rx, y0 + ry, color)
        return picks

    def recolor(self, mapping: Mapping[str | int, str | int]) -> None:
        """Atomically remap palette indices on the active surface without swap collisions."""
        if not mapping:
            return
        surf = self.surface
        resolved_pairs = [
            (self._resolve_pal_index(src), self._resolve_pal_index(dst))
            for src, dst in mapping.items()
        ]
        snapshot = surf.data.copy()
        for src_idx, dst_idx in resolved_pairs:
            surf.data[snapshot == src_idx] = dst_idx

    def anchor(
        self,
        name: str,
        x: int | float,
        y: int | float,
        *,
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> AnchorPoint:
        """Register a named `AnchorPoint` automatically shifted by active layer offsets."""
        return self._emit_anchor(name, x, y, kind=kind, dir=dir)

    def anchor_slots(
        self,
        prefix: str,
        points: Sequence[Point2D],
        *,
        start: int = 0,
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> tuple[AnchorPoint, ...]:
        """Register sequential scene slot anchors (e.g. `hw_slot_0..N`)."""
        return tuple(
            self._emit_anchor(f"{prefix}{start + idx}", pt[0], pt[1], kind=kind, dir=dir)
            for idx, pt in enumerate(points)
        )

    def hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        *,
        kind: str | None = None,
    ) -> HitboxRect:
        """Register a named `HitboxRect` automatically shifted by active layer offsets."""
        return self._emit_hitbox(name, x, y, w, h, kind=kind)

    def anchor_hitbox(
        self,
        name: str,
        x: int | float,
        y: int | float,
        w: int | float,
        h: int | float,
        *,
        anchor_at: AnchorAlign = "bottom-center",
        kind: str | None = None,
        dir: tuple[int, int] | None = None,
    ) -> tuple[AnchorPoint, HitboxRect]:
        """Register a coupled `HitboxRect` and `AnchorPoint` from one geometry block."""
        hb = self._emit_hitbox(name, x, y, w, h, kind=kind)
        ix = round(x)
        iy = round(y)
        iw = round(w)
        ih = round(h)
        if anchor_at == "bottom-center":
            ax, ay = ix + (iw // 2), iy + ih
        elif anchor_at == "center":
            ax, ay = ix + (iw // 2), iy + (ih // 2)
        elif anchor_at == "top-left":
            ax, ay = ix, iy
        else:
            msg = f"Unsupported anchor_at alignment: {anchor_at!r}"
            raise ValueError(msg)
        pt = self._emit_anchor(name, ax, ay, kind=kind, dir=dir)
        return (pt, hb)
