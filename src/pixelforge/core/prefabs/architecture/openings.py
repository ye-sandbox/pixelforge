"""Windows, doors, vents, blinds, and curtain prefabs."""

from __future__ import annotations

from collections.abc import Callable

from pixelforge.core.plane import Point2D
from pixelforge.core.prefabs.architecture.room import Canvas, clamp_unit
from pixelforge.core.prefabs.atmosphere import (
    ClippedPane,
    PlaneRegion,
    RectRegion,
    clipped_pane,
)
from pixelforge.core.surface import IndexedSurface


def iso_window_glass_region(p0: Point2D, p1: Point2D, p2: Point2D) -> PlaneRegion:
    """Return the `(gp0, gp1, gp2)` plane region corresponding to `iso_window` inner glass."""
    u_vec = (float(p1[0]) - float(p0[0]), float(p1[1]) - float(p0[1]))
    v_vec = (float(p2[0]) - float(p0[0]), float(p2[1]) - float(p0[1]))

    def _proj(u: float, v: float) -> Point2D:
        return (
            float(p0[0]) + u * u_vec[0] + v * v_vec[0],
            float(p0[1]) + u * u_vec[1] + v * v_vec[1],
        )

    return (_proj(0.07, 0.08), _proj(0.93, 0.08), _proj(0.07, 0.92))


def front_window_glass_region(
    x: int | float,
    y: int | float,
    w: int | float,
    h: int | float,
    *,
    frame_thickness: int = 2,
) -> RectRegion:
    """Return the `(gx, gy, gw, gh)` rectangle corresponding to `front_window` inner glass."""
    ix = round(x)
    iy = round(y)
    iw = max(3, int(w))
    ih = max(3, int(h))
    t = max(1, min(int(frame_thickness), (iw - 1) // 2, (ih - 1) // 2))
    return (ix + t, iy + t, max(1, iw - 2 * t), max(1, ih - 2 * t))


def iso_window(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    frame: int,
    sky: int,
    outline: int | None = None,
    sky_alt: int | None = None,
    mullion: int | None = None,
    sill: int | None = None,
    cols: int = 1,
    rows: int = 2,
    glint: int | None = None,
    scene: Callable[[ClippedPane], None] | None = None,
) -> None:
    """Draw a skewed isometric window onto `(p0, p1, p2)` with optional clipped vista scene."""
    glass_region = iso_window_glass_region(p0, p1, p2)
    with target.plane(p0=p0, p1=p1, p2=p2) as win:
        win.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        if scene is None:
            win.rect(0.07, 0.08, 0.86, 0.84, fill=sky)
            if sky_alt is not None:
                win.dither(0.07, 0.08, 0.86, 0.45, sky_alt, sky, pattern="bayer4", ratio=0.4)

    if scene is not None or glint is not None:
        with clipped_pane(target, glass_region) as glass_pane:
            if scene is not None:
                scene(glass_pane)
            if glint is not None:
                gx0, gy0 = glass_pane.project(0.14, 0.14)
                gx1, gy1 = glass_pane.project(0.26, 0.28)
                glass_pane.surface.line(gx0, gy0, gx1, gy1, glint)
                sx0, sy0 = glass_pane.project(0.22, 0.13)
                sx1, sy1 = glass_pane.project(0.30, 0.22)
                glass_pane.surface.line(sx0, sy0, sx1, sy1, glint)

    with target.plane(p0=p0, p1=p1, p2=p2) as win:
        if mullion is not None:
            icols = max(1, int(cols))
            irows = max(1, int(rows))
            if icols == 1 and irows == 2:
                # INVARIANT: Preserve exact legacy mullion placement for default 1x2 callers.
                win.rect(0.05, 0.48, 0.90, 0.06, fill=mullion)
            else:
                for r in range(1, irows):
                    vr = 0.08 + (r / float(irows)) * 0.84 - 0.03
                    win.rect(0.05, vr, 0.90, 0.06, fill=mullion)
                for c in range(1, icols):
                    uc = 0.07 + (c / float(icols)) * 0.86 - 0.025
                    win.rect(uc, 0.06, 0.05, 0.88, fill=mullion)
        if sill is not None:
            win.rect(-0.04, 0.94, 1.08, 0.08, fill=sill)


def _draw_front_glint(surface: IndexedSurface, gw: int, gh: int, glint: int) -> None:
    g_len = max(2, min(5, min(gw, gh) // 5))
    surface.line(2, 2, 2 + g_len, 2 + g_len, glint)
    surface.line(5, 2, 5 + max(1, g_len // 2), 2 + max(1, g_len // 2), glint)


def front_window(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int | float,
    h: int | float,
    *,
    frame: int,
    sky: int,
    outline: int | None = None,
    sky_alt: int | None = None,
    mullion: int | None = None,
    sill: int | None = None,
    cols: int = 1,
    rows: int = 2,
    glint: int | None = None,
    frame_thickness: int = 2,
    scene: Callable[[ClippedPane], None] | None = None,
) -> None:
    """Draw a `front-2.5d` rectangular window with clipped glass vista, mullions, and sill."""
    ix = round(x)
    iy = round(y)
    iw = max(3, int(w))
    ih = max(3, int(h))

    target.rect(ix, iy, iw, ih, frame, fill=True)
    if outline is not None:
        target.rect(ix, iy, iw, ih, outline, fill=False)

    glass_region = front_window_glass_region(ix, iy, iw, ih, frame_thickness=frame_thickness)
    gx, gy, gw, gh = (
        round(glass_region[0]),
        round(glass_region[1]),
        int(glass_region[2]),
        int(glass_region[3]),
    )
    if scene is not None:
        with clipped_pane(target, glass_region) as glass_pane:
            scene(glass_pane)
            if glint is not None:
                _draw_front_glint(glass_pane.surface, gw, gh, glint)
    else:
        target.rect(gx, gy, gw, gh, sky, fill=True)
        if sky_alt is not None:
            target.dither(gx, gy, gw, max(1, gh // 2), sky_alt, sky, pattern="bayer4", ratio=0.4)
        if glint is not None:
            with clipped_pane(target, glass_region) as glint_pane:
                _draw_front_glint(glint_pane.surface, gw, gh, glint)

    if mullion is not None:
        icols = max(1, int(cols))
        irows = max(1, int(rows))
        bar_h = 1 if gh < 18 else 2
        bar_w = 1 if gw < 18 else 2
        for r in range(1, irows):
            my = gy + round((r / float(irows)) * gh) - (bar_h // 2)
            target.rect(gx, my, gw, bar_h, mullion, fill=True)
        for c in range(1, icols):
            mx = gx + round((c / float(icols)) * gw) - (bar_w // 2)
            target.rect(mx, gy, bar_w, gh, mullion, fill=True)

    if sill is not None:
        target.rect(ix - 1, iy + ih - 1, iw + 2, 2, sill, fill=True)


def wall_vent(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    frame: int,
    slat: int,
    outline: int | None = None,
    slats: int = 3,
) -> None:
    """Draw a louvered wall vent onto a `(p0, p1, p2)` wall plane."""
    count = max(1, int(slats))
    with target.plane(p0=p0, p1=p1, p2=p2) as vent:
        vent.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        vent.grid(0.15, 0.20, 0.70, 0.60, cols=1, rows=count, color=slat, cell_fill=0.55)


def iso_door(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    frame: int,
    panel: int,
    recess: int | None = None,
    handle: int | None = None,
    outline: int | None = None,
    window: int | None = None,
    threshold: int | None = None,
) -> None:
    """Draw a skewed isometric door onto a `(p0, p1, p2)` wall plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as door:
        door.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        door.rect(0.10, 0.06, 0.80, 0.94, fill=panel)
        if window is not None:
            door.rect(0.24, 0.14, 0.52, 0.26, fill=window, outline=recess)
        elif recess is not None:
            door.rect(0.22, 0.14, 0.56, 0.30, fill=recess)
        if recess is not None:
            door.rect(0.22, 0.54, 0.56, 0.34, fill=recess)
        if handle is not None:
            door.dot(0.78, 0.52, handle)
        if threshold is not None:
            door.rect(-0.04, 0.96, 1.08, 0.06, fill=threshold)


def front_door(
    target: Canvas,
    x: int | float,
    y: int | float,
    w: int | float,
    h: int | float,
    *,
    frame: int,
    panel: int,
    recess: int | None = None,
    handle: int | None = None,
    outline: int | None = None,
    window: int | None = None,
    threshold: int | None = None,
    frame_thickness: int = 2,
) -> None:
    """Draw a `front-2.5d` rectangular door with frame, optional vision glass, and handle."""
    ix = round(x)
    iy = round(y)
    iw = max(5, int(w))
    ih = max(8, int(h))
    t = max(1, min(int(frame_thickness), (iw - 2) // 2, (ih - 2) // 2))

    target.rect(ix, iy, iw, ih, frame, fill=True)
    if outline is not None:
        target.rect(ix, iy, iw, ih, outline, fill=False)

    px, py = ix + t, iy + t
    pw, ph = max(2, iw - 2 * t), max(4, ih - t)
    target.rect(px, py, pw, ph, panel, fill=True)

    inset_x = max(1, pw // 5)
    inner_w = max(1, pw - 2 * inset_x)
    if window is not None:
        win_h = max(2, ph // 4)
        target.rect(px + inset_x, py + max(2, ph // 8), inner_w, win_h, window, fill=True)
        if recess is not None:
            target.rect(px + inset_x, py + max(2, ph // 8), inner_w, win_h, recess, fill=False)
    elif recess is not None:
        target.rect(px + inset_x, py + max(2, ph // 8), inner_w, max(2, ph // 4), recess, fill=True)

    if recess is not None:
        target.rect(
            px + inset_x,
            py + max(4, (ph * 55) // 100),
            inner_w,
            max(2, ph // 3),
            recess,
            fill=True,
        )
    if handle is not None:
        hx = px + max(1, pw - max(2, pw // 5))
        hy = py + ph // 2
        target.rect(hx, hy, 1, 2, handle, fill=True)
    if threshold is not None:
        target.rect(ix - 1, iy + ih - 1, iw + 2, 2, threshold, fill=True)


def window_blinds(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    slat: int,
    shadow: int | None = None,
    cord: int | None = None,
    slats: int = 5,
    open_ratio: float = 0.7,
) -> None:
    """Draw horizontal venetian blinds across a `(p0, p1, p2)` window glass plane."""
    ratio = clamp_unit(open_ratio)
    if ratio <= 0.0:
        return
    count = max(1, int(slats))
    with target.plane(p0=p0, p1=p1, p2=p2) as blinds:
        step_v = ratio / count
        slat_h = max(0.03, step_v * 0.55)
        for idx in range(count):
            v = idx * step_v
            blinds.rect(0.0, v, 1.0, slat_h, fill=slat)
            if shadow is not None:
                blinds.line(0.0, min(1.0, v + slat_h), 1.0, min(1.0, v + slat_h), shadow)
        if cord is not None:
            blinds.line(0.84, 0.0, 0.84, min(1.0, ratio + 0.08), cord)


def window_curtains(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    fabric: int,
    fold: int | None = None,
    rod: int | None = None,
    outline: int | None = None,
    open_ratio: float = 0.35,
) -> None:
    """Draw parted left and right curtains onto a `(p0, p1, p2)` window plane."""
    ratio = clamp_unit(open_ratio)
    panel_w = max(0.12, 0.48 * (1.0 - ratio * 0.72))
    with target.plane(p0=p0, p1=p1, p2=p2) as curtains:
        curtains.rect(0.0, 0.04, panel_w, 0.96, fill=fabric, outline=outline)
        curtains.rect(1.0 - panel_w, 0.04, panel_w, 0.96, fill=fabric, outline=outline)
        if fold is not None:
            curtains.line(panel_w * 0.45, 0.06, panel_w * 0.45, 0.98, fold)
            curtains.line(1.0 - panel_w * 0.45, 0.06, 1.0 - panel_w * 0.45, 0.98, fold)
        if rod is not None:
            curtains.rect(-0.04, 0.0, 1.08, 0.05, fill=rod)
