"""Wall-mounted decor and fixture prefabs."""

from __future__ import annotations

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.plane import Point2D

Canvas = Asset[object] | Layer


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


def wall_light_switch(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    plate: int,
    toggle: int,
    outline: int | None = None,
    led: int | None = None,
    double: bool = False,
) -> None:
    """Draw a wall-mounted single or double light switch onto a `(p0, p1, p2)` wall plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as switch:
        switch.rect(0.0, 0.0, 1.0, 1.0, fill=plate, outline=outline)
        if double:
            switch.rect(0.24, 0.28, 0.20, 0.44, fill=toggle)
            switch.rect(0.56, 0.28, 0.20, 0.44, fill=toggle)
        else:
            switch.rect(0.36, 0.28, 0.28, 0.44, fill=toggle)
        if led is not None:
            switch.dot(0.50, 0.16, led)


def wall_thermostat(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    body: int,
    screen: int,
    readout: int | None = None,
    dial: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a wall-mounted smart thermostat with backlit screen onto a `(p0, p1, p2)` plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as therm:
        therm.rect(0.0, 0.0, 1.0, 1.0, fill=body, outline=outline)
        therm.rect(0.16, 0.16, 0.68, 0.46, fill=screen)
        if readout is not None:
            therm.line(0.28, 0.38, 0.64, 0.38, readout)
        if dial is not None:
            therm.rect(0.30, 0.72, 0.40, 0.16, fill=dial)


def wall_clock(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    frame: int,
    face: int,
    hands: int,
    accent: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a wall-mounted clock onto a `(p0, p1, p2)` wall plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as clock:
        clock.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        clock.rect(0.14, 0.14, 0.72, 0.72, fill=face)
        clock.line(0.50, 0.50, 0.50, 0.24, hands)
        clock.line(0.50, 0.50, 0.72, 0.50, hands)
        if accent is not None:
            clock.dot(0.50, 0.50, accent)


def wall_corkboard(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    frame: int,
    cork: int,
    note: int | None = None,
    note_alt: int | None = None,
    pin: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a framed wall corkboard with pinned notes onto a `(p0, p1, p2)` plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as board:
        board.rect(0.0, 0.0, 1.0, 1.0, fill=frame, outline=outline)
        board.rect(0.08, 0.10, 0.84, 0.80, fill=cork)
        if note is not None:
            board.rect(0.16, 0.20, 0.26, 0.30, fill=note)
            board.rect(0.54, 0.44, 0.28, 0.32, fill=note)
        if note_alt is not None:
            board.rect(0.48, 0.18, 0.24, 0.22, fill=note_alt)
        if pin is not None:
            board.dot(0.28, 0.22, pin)
            board.dot(0.60, 0.20, pin)
            board.dot(0.66, 0.46, pin)


def wall_pegboard(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    board: int,
    hole: int,
    frame: int | None = None,
    hook: int | None = None,
    accent: int | None = None,
    outline: int | None = None,
    cols: int = 4,
    rows: int = 3,
) -> None:
    """Draw a wall-mounted pegboard with perforated grid and optional hooks/gear."""
    with target.plane(p0=p0, p1=p1, p2=p2) as peg:
        peg.rect(0.0, 0.0, 1.0, 1.0, fill=frame if frame is not None else board, outline=outline)
        if frame is not None:
            peg.rect(0.06, 0.08, 0.88, 0.84, fill=board)
        peg.grid(0.16, 0.18, 0.68, 0.64, cols=cols, rows=rows, color=hole)
        if hook is not None:
            peg.line(0.24, 0.36, 0.24, 0.68, hook)
            peg.line(0.72, 0.36, 0.72, 0.62, hook)
        if accent is not None:
            peg.rect(0.42, 0.34, 0.16, 0.32, fill=accent)


def wall_neon_sign(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    glow: int,
    backing: int | None = None,
    accent: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a wall-mounted emissive neon sign onto a `(p0, p1, p2)` wall plane."""
    with target.plane(p0=p0, p1=p1, p2=p2) as sign:
        if backing is not None:
            sign.rect(0.0, 0.0, 1.0, 1.0, fill=backing, outline=outline)
        sign.line(0.14, 0.32, 0.86, 0.32, glow)
        sign.line(0.22, 0.66, 0.78, 0.66, accent if accent is not None else glow)
        sign.dot(0.14, 0.50, glow)
        sign.dot(0.86, 0.50, glow)


def wall_sconce(
    target: Canvas,
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    *,
    bracket: int,
    shade: int,
    bulb: int,
    glow: int | None = None,
    outline: int | None = None,
) -> None:
    """Draw a wall-mounted sconce fixture with emissive bulb and optional uplight glow."""
    with target.plane(p0=p0, p1=p1, p2=p2) as sconce:
        sconce.rect(0.28, 0.54, 0.44, 0.44, fill=bracket, outline=outline)
        sconce.rect(0.16, 0.24, 0.68, 0.36, fill=shade, outline=outline)
        sconce.dot(0.50, 0.22, bulb)
        if glow is not None:
            sconce.line(0.28, 0.08, 0.72, 0.08, glow)


__all__ = [
    "wall_ac_unit",
    "wall_clock",
    "wall_corkboard",
    "wall_light_switch",
    "wall_neon_sign",
    "wall_outlet",
    "wall_panel",
    "wall_pegboard",
    "wall_poster",
    "wall_sconce",
    "wall_thermostat",
    "wall_whiteboard",
]
