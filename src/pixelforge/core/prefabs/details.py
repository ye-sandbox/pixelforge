"""Detail prefab helpers (cables, wall panels, contact shadows, wall posters)."""

from __future__ import annotations

from collections.abc import Sequence

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.plane import Point2D
from pixelforge.core.surface import IndexedSurface
from pixelforge.core.types import TRANSPARENT_INDEX

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
