"""Windows, doors, vents, blinds, and curtain prefabs."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from pixelforge.core.builder import Asset
from pixelforge.core.plane import Point2D
from pixelforge.core.prefabs.architecture.room import (
    Canvas,
    IsoRoomGeometry,
    WallSide,
    clamp_unit,
)
from pixelforge.core.prefabs.atmosphere import (
    ClippedPane,
    PlaneRegion,
    RectRegion,
    clipped_pane,
    window_light_spill,
)
from pixelforge.core.surface import IndexedSurface, compute_dither_thresholds


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


def _outer_perimeter_mask(in_outer: NDArray[np.bool_]) -> NDArray[np.bool_]:
    padded = np.pad(in_outer, 1, mode="constant", constant_values=False)
    has_outside_neighbor = (
        ~padded[:-2, 1:-1] | ~padded[2:, 1:-1] | ~padded[1:-1, :-2] | ~padded[1:-1, 2:]
    )
    return in_outer & has_outside_neighbor


def _paint_shaped_iso_window(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    in_outer: NDArray[np.bool_],
    in_glass: NDArray[np.bool_],
    frame: int,
    sky: int,
    outline: int | None,
    sky_alt: int | None,
    glint: int | None,
    scene: Callable[[ClippedPane], None] | None,
) -> None:
    with clipped_pane(target, (p0, p1, p2)) as frame_pane:
        frame_pane.mask = in_outer
        frame_pane.surface.data[in_outer & ~in_glass] = frame
        if outline is not None:
            frame_pane.surface.data[_outer_perimeter_mask(in_outer)] = outline

    with clipped_pane(target, (p0, p1, p2)) as glass_pane:
        glass_pane.mask = in_glass
        if scene is not None:
            scene(glass_pane)
        else:
            glass_pane.surface.data[in_glass] = sky
            if sky_alt is not None:
                thresholds = compute_dither_thresholds(
                    glass_pane.ox,
                    glass_pane.oy,
                    glass_pane.ox + glass_pane.width,
                    glass_pane.oy + glass_pane.height,
                    pattern="bayer4",
                )
                upper_glass = in_glass & (glass_pane.v_grid < 0.52) & (thresholds < 0.4)
                glass_pane.surface.data[upper_glass] = sky_alt
        if glint is not None:
            gx0, gy0 = glass_pane.project(0.24, 0.24)
            gx1, gy1 = glass_pane.project(0.36, 0.36)
            glass_pane.surface.line(gx0, gy0, gx1, gy1, glint)
            sx0, sy0 = glass_pane.project(0.32, 0.22)
            sx1, sy1 = glass_pane.project(0.40, 0.30)
            glass_pane.surface.line(sx0, sy0, sx1, sy1, glint)


def iso_arched_window(
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
    glint: int | None = None,
    scene: Callable[[ClippedPane], None] | None = None,
) -> None:
    """Draw an arched isometric window onto `(p0, p1, p2)` with optional clipped vista scene."""
    with clipped_pane(target, (p0, p1, p2)) as probe:
        u = probe.u_grid
        v = probe.v_grid
        arch_v = 0.38
        in_arch_outer = ((u - 0.5) / 0.5) ** 2 + ((v - arch_v) / arch_v) ** 2 <= 1.0
        in_outer = probe.mask & ((v >= arch_v) | in_arch_outer)
        in_arch_glass = ((u - 0.5) / 0.41) ** 2 + ((v - arch_v) / 0.30) ** 2 <= 1.0
        in_rect_glass = (u >= 0.09) & (u <= 0.91) & (v >= arch_v) & (v <= 0.92)
        in_glass = probe.mask & (in_rect_glass | ((v < arch_v) & in_arch_glass))
        # Prevent probe commit from blitting an empty buffer.
        probe.mask = np.zeros_like(probe.mask)

    _paint_shaped_iso_window(
        target,
        p0,
        p1,
        p2,
        in_outer=in_outer,
        in_glass=in_glass,
        frame=frame,
        sky=sky,
        outline=outline,
        sky_alt=sky_alt,
        glint=glint,
        scene=scene,
    )

    if mullion is not None or sill is not None:
        with target.plane(p0=p0, p1=p1, p2=p2) as win:
            if mullion is not None:
                win.rect(0.07, 0.52, 0.86, 0.06, fill=mullion)
                win.rect(0.475, 0.08, 0.05, 0.84, fill=mullion)
            if sill is not None:
                win.rect(-0.04, 0.94, 1.08, 0.08, fill=sill)


def iso_porthole_window(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    frame: int,
    sky: int,
    outline: int | None = None,
    sky_alt: int | None = None,
    rivet: int | None = None,
    glint: int | None = None,
    scene: Callable[[ClippedPane], None] | None = None,
) -> None:
    """Draw a circular porthole isometric window onto `(p0, p1, p2)` with optional vista."""
    with clipped_pane(target, (p0, p1, p2)) as probe:
        u = probe.u_grid
        v = probe.v_grid
        in_outer = probe.mask & ((((u - 0.5) / 0.5) ** 2 + ((v - 0.5) / 0.5) ** 2) <= 1.0)
        in_glass = probe.mask & ((((u - 0.5) / 0.34) ** 2 + ((v - 0.5) / 0.34) ** 2) <= 1.0)
        probe.mask = np.zeros_like(probe.mask)

    _paint_shaped_iso_window(
        target,
        p0,
        p1,
        p2,
        in_outer=in_outer,
        in_glass=in_glass,
        frame=frame,
        sky=sky,
        outline=outline,
        sky_alt=sky_alt,
        glint=glint,
        scene=scene,
    )

    if rivet is not None:
        with target.plane(p0=p0, p1=p1, p2=p2) as bezel:
            for ru, rv in ((0.5, 0.08), (0.5, 0.92), (0.08, 0.5), (0.92, 0.5)):
                bezel.dot(ru, rv, rivet)


def iso_room_window(
    target: Canvas,
    room: IsoRoomGeometry,
    wall: WallSide = "left",
    *,
    u0: float = 0.25,
    u1: float = 0.65,
    v0: float = 0.18,
    v1: float = 0.62,
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
    blinds_slat: int | None = None,
    blinds_shadow: int | None = None,
    blinds_cord: int | None = None,
    blinds_slats: int = 5,
    blinds_open_ratio: float = 0.7,
    curtain_fabric: int | None = None,
    curtain_fold: int | None = None,
    curtain_rod: int | None = None,
    curtain_open_ratio: float = 0.35,
    spill_color: int | None = None,
    spill_secondary: int | None = None,
    spill_depth: float = 0.35,
    spill_near_ratio: float = 0.70,
    spill_far_ratio: float = 0.18,
) -> PlaneRegion:
    """Draw a wall-mounted `iso_window` with optional blinds, curtains, and floor light spill."""
    if wall not in ("left", "right"):
        msg = f"Unsupported wall side: {wall!r}"
        raise ValueError(msg)
    p0, p1, p2 = (
        room.left_wall_plane(u0, v0, u1, v1)
        if wall == "left"
        else room.right_wall_plane(u0, v0, u1, v1)
    )
    iso_window(
        target,
        p0,
        p1,
        p2,
        frame=frame,
        sky=sky,
        outline=outline,
        sky_alt=sky_alt,
        mullion=mullion,
        sill=sill,
        cols=cols,
        rows=rows,
        glint=glint,
        scene=scene,
    )
    if blinds_slat is not None:
        gp0, gp1, gp2 = iso_window_glass_region(p0, p1, p2)
        window_blinds(
            target,
            gp0,
            gp1,
            gp2,
            slat=blinds_slat,
            shadow=blinds_shadow,
            cord=blinds_cord,
            slats=blinds_slats,
            open_ratio=blinds_open_ratio,
        )
    if curtain_fabric is not None:
        window_curtains(
            target,
            p0,
            p1,
            p2,
            fabric=curtain_fabric,
            fold=curtain_fold,
            rod=curtain_rod,
            outline=outline,
            open_ratio=curtain_open_ratio,
        )
    if spill_color is not None:
        quad = room.window_spill_quad(u0, u1, wall=wall, depth=spill_depth)
        window_light_spill(
            target,
            points=quad,
            color=spill_color,
            secondary_color=spill_secondary,
            near_ratio=spill_near_ratio,
            far_ratio=spill_far_ratio,
            mask="opaque",
        )
    return (p0, p1, p2)


def iso_portal_door(
    target: Canvas,
    room: IsoRoomGeometry,
    wall: WallSide = "left",
    *,
    u0: float = 0.65,
    u1: float = 0.85,
    v0: float = 0.25,
    v1: float = 1.0,
    frame: int,
    panel: int,
    recess: int | None = None,
    handle: int | None = None,
    outline: int | None = None,
    window: int | None = None,
    threshold: int | None = None,
    anchor_name: str | None = None,
    clearance_hitbox: bool = True,
) -> tuple[int, int]:
    """Draw an isometric doorway on `room`'s `wall` and return its `(x, y)` portal anchor."""
    if wall not in ("left", "right"):
        msg = f"Unsupported wall side: {wall!r}"
        raise ValueError(msg)
    p0, p1, p2 = (
        room.left_wall_plane(u0, v0, u1, v1)
        if wall == "left"
        else room.right_wall_plane(u0, v0, u1, v1)
    )
    iso_door(
        target,
        p0,
        p1,
        p2,
        frame=frame,
        panel=panel,
        recess=recess,
        handle=handle,
        outline=outline,
        window=window,
        threshold=threshold,
    )
    with target.plane(p0=p0, p1=p1, p2=p2) as door_plane:
        ax, ay = door_plane.project(0.5, 0.92)
    ax = max(0, min(target.surface.width - 1, ax))
    ay = max(0, min(target.surface.height - 1, ay))
    if isinstance(target, Asset):
        if anchor_name is not None:
            target.anchor(anchor_name, ax, ay)
        if clearance_hitbox:
            depth = 0.12
            if wall == "left":
                fv0 = 1.0 - clamp_unit(u1)
                fv1 = 1.0 - clamp_unit(u0)
                pts = (
                    room.floor_point(0.0, fv0),
                    room.floor_point(0.0, fv1),
                    room.floor_point(depth, fv0),
                    room.floor_point(depth, fv1),
                )
            else:
                fu0 = clamp_unit(u0)
                fu1 = clamp_unit(u1)
                pts = (
                    room.floor_point(fu0, 0.0),
                    room.floor_point(fu1, 0.0),
                    room.floor_point(fu0, depth),
                    room.floor_point(fu1, depth),
                )
            min_x = max(0, min(px for px, _ in pts))
            min_y = max(0, min(py for _, py in pts))
            max_x = min(target.surface.width, max(px for px, _ in pts))
            max_y = min(target.surface.height, max(py for _, py in pts))
            hb_w = max(1, min(target.surface.width - min_x, max_x - min_x))
            hb_h = max(1, min(target.surface.height - min_y, max_y - min_y))
            hb_suffix = anchor_name if anchor_name is not None else f"{wall}_{round(u0 * 100)}"
            target.hitbox(
                f"door_clearance_{hb_suffix}",
                min_x,
                min_y,
                hb_w,
                hb_h,
                kind="door_clearance",
            )
    return (ax, ay)
