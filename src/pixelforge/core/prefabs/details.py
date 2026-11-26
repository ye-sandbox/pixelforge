"""Detail prefab helpers (cables, wall panels, shadows, reflections, wall posters)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.palette import build_reflection_lut
from pixelforge.core.plane import Point2D
from pixelforge.core.surface import (
    DitherMask,
    DitherPattern,
    IndexedSurface,
    compute_dither_thresholds,
)
from pixelforge.core.types import TRANSPARENT_INDEX, LightingAngle, StylePack

Canvas = Asset | Layer


def iso_cable_run(
    target: Canvas,
    points: Sequence[Point2D],
    *,
    color: int,
    highlight: int | None = None,
) -> None:
    """Draw a deterministic pixel-crisp cable polyline across 2D surface coordinates."""
    if len(points) < 2:
        return
    for idx in range(len(points) - 1):
        x0, y0 = round(points[idx][0]), round(points[idx][1])
        x1, y1 = round(points[idx + 1][0]), round(points[idx + 1][1])
        target.line(x0, y0, x1, y1, color)
        if highlight is not None:
            target.line(x0, y0 - 1, x1, y1 - 1, highlight)


def wall_panel(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    frame: int,
    recess: int,
    slot: int,
    outline: int | None = None,
    cols: int = 2,
    rows: int = 3,
    status_led: int | None = None,
) -> None:
    """Draw an isometric wall-mounted breaker/control panel onto a `(p0, p1, p2)` plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as panel:
        panel.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        panel.rect(0.22, 0.25, 0.56, 0.45, fill=recess)
        panel.grid(0.28, 0.30, 0.44, 0.35, cols=cols, rows=rows, color=slot)
        if status_led is not None:
            panel.dot(0.75, 0.18, status_led)


def contact_shadow(
    target: Canvas,
    cx: int | float,
    cy: int | float,
    rx: int,
    ry: int,
    *,
    color: int,
    dither_ratio: float = 0.5,
) -> None:
    """Draw a grounded elliptical contact shadow with optional ordered checker/Bayer dithering."""
    irx = max(1, int(rx))
    iry = max(1, int(ry))
    icx = round(cx)
    icy = round(cy)

    if dither_ratio >= 1.0:
        target.ellipse(icx, icy, irx, iry, color, fill=True)
        return
    if dither_ratio <= 0.0:
        return

    w = irx * 2 + 1
    h = iry * 2 + 1
    patch = IndexedSurface(w, h)
    patch.ellipse(irx, iry, irx, iry, color, fill=True)
    # INVARIANT: Use TRANSPARENT_INDEX as color_a so unselected pixels become transparent
    # rather than overwriting surrounding floor pixels on blit.
    patch.dither(
        0,
        0,
        w,
        h,
        TRANSPARENT_INDEX,
        color,
        pattern="checker" if abs(dither_ratio - 0.5) < 1e-6 else "bayer4",
        ratio=dither_ratio,
        mask="opaque",
    )
    target.surface.blit_layer(patch, icx - irx, icy - iry)


def wall_poster(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    border: int,
    fill: int,
    accent: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a skewed isometric framed wall poster onto a `(p0, p1, p2)` wall plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as poster:
        poster.rect(0.0, 0.0, 1.0, 1.0, fill=border, outline=outline)
        poster.rect(0.12, 0.12, 0.76, 0.76, fill=fill)
        if accent is not None:
            poster.rect(0.22, 0.28, 0.56, 0.18, fill=accent)
            poster.line(0.22, 0.58, 0.72, 0.58, accent)


def cast_shadow(
    target: Canvas,
    cx: int | float,
    cy: int | float,
    rx: int,
    ry: int,
    *,
    color: int,
    length: int = 8,
    lighting_angle: LightingAngle | None = None,
    dither_ratio: float = 0.5,
    mask: DitherMask = "all",
) -> None:
    """Draw a directional cast shadow aligned away from `StylePack.lighting_angle`."""
    if dither_ratio <= 0.0:
        return
    irx = max(1, int(rx))
    iry = max(1, int(ry))
    icx = round(cx)
    icy = round(cy)
    span = max(0, int(length))
    angle: LightingAngle = (
        lighting_angle
        if lighting_angle is not None
        else (target.style.lighting_angle if isinstance(target, Asset) else "top-left")
    )

    dy = max(1, round(span * 0.5)) if span > 0 else 0
    if angle == "top-left":
        dx = span
    elif angle == "top-right":
        dx = -span
    elif angle == "top":
        dx = 0
    else:
        msg = f"Unsupported lighting_angle: {angle!r}"
        raise ValueError(msg)

    tip_x = icx + dx
    tip_y = icy + dy
    min_x = min(icx, tip_x) - irx
    min_y = min(icy, tip_y) - iry
    max_x = max(icx, tip_x) + irx
    max_y = max(icy, tip_y) + iry
    w = max_x - min_x + 1
    h = max_y - min_y + 1

    patch = IndexedSurface(w, h)
    lx0, ly0 = icx - min_x, icy - min_y
    lx1, ly1 = tip_x - min_x, tip_y - min_y
    patch.ellipse(lx0, ly0, irx, iry, color, fill=True)
    patch.ellipse(lx1, ly1, irx, iry, color, fill=True)
    if dx != 0 or dy != 0:
        patch.quad(
            (lx0, ly0 - iry),
            (lx1, ly1 - iry),
            (lx1, ly1 + iry),
            (lx0, ly0 + iry),
            color,
            fill=True,
        )
        patch.quad(
            (lx0 - irx, ly0),
            (lx1 - irx, ly1),
            (lx1 + irx, ly1),
            (lx0 + irx, ly0),
            color,
            fill=True,
        )

    if dither_ratio < 1.0:
        patch.dither(
            0,
            0,
            w,
            h,
            TRANSPARENT_INDEX,
            color,
            pattern="checker" if abs(dither_ratio - 0.5) < 1e-6 else "bayer4",
            ratio=dither_ratio,
            mask="opaque",
        )

    if mask == "all":
        target.surface.blit_layer(patch, min_x, min_y)
        return

    x0 = max(0, min_x)
    y0 = max(0, min_y)
    x1 = min(target.surface.width, min_x + w)
    y1 = min(target.surface.height, min_y + h)
    if x0 >= x1 or y0 >= y1:
        return
    dst = target.surface.data[y0:y1, x0:x1]
    src = patch.data[y0 - min_y : y1 - min_y, x0 - min_x : x1 - min_x]
    write_mask = (src != TRANSPARENT_INDEX) & (dst != TRANSPARENT_INDEX)
    dst[write_mask] = src[write_mask]


def floor_reflection(
    target: Canvas,
    region: tuple[int, int, int, int],
    *,
    y_floor: int | None = None,
    style: StylePack | None = None,
    dither_ratio: float = 0.5,
    pattern: DitherPattern = "checker",
    mask: DitherMask = "opaque",
    max_height: int | None = None,
) -> None:
    """Render a vertically flipped floor reflection preview using `StylePack.reflections`."""
    if dither_ratio <= 0.0:
        return
    resolved_style = (
        style if style is not None else (target.style if isinstance(target, Asset) else None)
    )
    if resolved_style is None:
        msg = "style is required when calling floor_reflection on a Layer"
        raise ValueError(msg)
    if not resolved_style.reflections:
        return

    rx, ry, rw, rh = region
    if rw <= 0 or rh <= 0:
        return
    sx0 = max(0, int(rx))
    sy0 = max(0, int(ry))
    sx1 = min(target.surface.width, int(rx) + int(rw))
    sy1 = min(target.surface.height, int(ry) + int(rh))
    if sx0 >= sx1 or sy0 >= sy1:
        return

    flipped = target.surface.data[sy0:sy1, sx0:sx1][::-1, :]
    if max_height is not None:
        if max_height <= 0:
            return
        flipped = flipped[: int(max_height), :]

    lut = build_reflection_lut(resolved_style)
    mapped = lut[flipped]
    dest_y = int(y_floor) if y_floor is not None else sy1
    dy0 = max(0, dest_y)
    dy1 = min(target.surface.height, dest_y + mapped.shape[0])
    if dy0 >= dy1:
        return

    src_slice = mapped[dy0 - dest_y : dy1 - dest_y, :]
    dst_slice = target.surface.data[dy0:dy1, sx0:sx1]
    active = src_slice != TRANSPARENT_INDEX
    if mask == "opaque":
        active &= dst_slice != TRANSPARENT_INDEX
    if not np.any(active):
        return

    if dither_ratio < 1.0:
        thresholds = compute_dither_thresholds(sx0, dy0, sx1, dy1, pattern=pattern)
        active &= thresholds < float(dither_ratio)

    dst_slice[active] = src_slice[active]


def wall_ac_unit(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    body: int,
    shade: int,
    vent: int,
    outline: int | None = None,
    led: int | None = None,
) -> None:
    """Draw a wall-mounted split AC unit onto a `(p0, p1, p2)` wall plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as ac:
        ac.rect(0.0, 0.0, 1.0, 1.0, fill=body, outline=outline)
        ac.rect(0.06, 0.62, 0.88, 0.28, fill=shade)
        ac.line(0.10, 0.72, 0.90, 0.72, vent)
        ac.line(0.10, 0.82, 0.90, 0.82, vent)
        if led is not None:
            ac.dot(0.84, 0.28, led)


def wall_whiteboard(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    frame: int,
    board: int,
    marker: int | None = None,
    accent: int | None = None,
    tray: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a framed wall whiteboard with optional diagram strokes and marker tray."""
    with target.plane(p0=p0, p1=p1, p2=p2) as wb:
        wb.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        wb.rect(0.07, 0.09, 0.86, 0.82, fill=board)
        if marker is not None:
            wb.line(0.15, 0.26, 0.56, 0.26, marker)
            wb.line(0.15, 0.42, 0.46, 0.42, marker)
            wb.line(0.15, 0.58, 0.64, 0.58, marker)
        if accent is not None:
            wb.rect(0.66, 0.22, 0.18, 0.20, fill=accent)
        if tray is not None:
            wb.rect(0.16, 0.92, 0.68, 0.08, fill=tray)


def power_strip(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    *,
    body: int,
    socket: int,
    switch: int | None = None,
    outline: int | None = None,
    outlets: int = 4,
) -> None:
    """Draw a floor or desk power strip along `(p0, p1)` with outlets and power switch."""
    x0, y0 = round(p0[0]), round(p0[1])
    x1, y1 = round(p1[0]), round(p1[1])
    count = max(1, int(outlets))

    if outline is not None:
        target.line(x0, y0 - 2, x1, y1 - 2, outline)
        target.line(x0, y0 + 2, x1, y1 + 2, outline)
    for dy in (-1, 0, 1):
        target.line(x0, y0 + dy, x1, y1 + dy, body)

    if switch is not None:
        sx = round(x0 + 0.12 * (x1 - x0))
        sy = round(y0 + 0.12 * (y1 - y0))
        target.put(sx, sy, switch)

    start_t = 0.28 if switch is not None else 0.18
    span_t = 0.66 if switch is not None else 0.64
    for idx in range(count):
        t = start_t + (idx / max(1, count - 1)) * span_t if count > 1 else 0.5
        ox = round(x0 + t * (x1 - x0))
        oy = round(y0 + t * (y1 - y0))
        target.put(ox, oy, socket)


def wall_outlet(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    plate: int,
    socket: int,
    outline: int | None = None,
    dual: bool = True,
) -> None:
    """Draw a wall-mounted electrical or network outlet onto a `(p0, p1, p2)` wall plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as outlet:
        outlet.rect(0.0, 0.0, 1.0, 1.0, fill=plate, outline=outline)
        if dual:
            outlet.dot(0.50, 0.34, socket)
            outlet.dot(0.50, 0.68, socket)
        else:
            outlet.dot(0.50, 0.50, socket)


def iso_cable_catenary(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    *,
    color: int,
    sag: int = 6,
    highlight: int | None = None,
    segments: int = 8,
) -> None:
    """Draw a sagging catenary cable arc between `p0` and `p1`."""
    segs = max(2, int(segments))
    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    drop = float(sag)
    points: list[Point2D] = []
    for idx in range(segs + 1):
        t = idx / segs
        px = x0 + t * (x1 - x0)
        py = y0 + t * (y1 - y0) + 4.0 * t * (1.0 - t) * drop
        points.append((round(px), round(py)))
    iso_cable_run(target, points, color=color, highlight=highlight)


__all__ = [
    "cast_shadow",
    "contact_shadow",
    "floor_reflection",
    "iso_cable_catenary",
    "iso_cable_run",
    "power_strip",
    "wall_ac_unit",
    "wall_outlet",
    "wall_panel",
    "wall_poster",
    "wall_whiteboard",
]
