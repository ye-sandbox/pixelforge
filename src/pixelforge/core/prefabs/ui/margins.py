"""Shared UI border geometry, 9-slice margin synchronization, and content hitboxes."""

from __future__ import annotations

from typing import Literal

from pixelforge.core.prefabs.ui.palette import UiTarget
from pixelforge.core.types import NineSliceMargins

UiDialogueTail = Literal["none", "bottom_left", "bottom_center", "bottom_right", "left", "right"]


def cut_rect_corners(a: UiTarget, x: int, y: int, w: int, h: int, cut: int) -> None:
    """Erase `cut` pixels on each outer corner for chamfered pixel UI frames."""
    if cut <= 0 or w < cut * 2 + 2 or h < cut * 2 + 2:
        return
    for dy in range(cut):
        span = cut - dy
        for dx in range(span):
            a.erase(x + dx, y + dy)
            a.erase(x + w - 1 - dx, y + dy)
            a.erase(x + dx, y + h - 1 - dy)
            a.erase(x + w - 1 - dx, y + h - 1 - dy)


def draw_chamfer_border(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    color: int,
    cut: int,
) -> None:
    """Draw a 1px outer border respecting optional 1px corner chamfers."""
    if cut <= 0 or w < 4 or h < 4:
        a.rect(x, y, w, 1, color)
        a.rect(x, y + h - 1, w, 1, color)
        a.rect(x, y, 1, h, color)
        a.rect(x + w - 1, y, 1, h, color)
        return

    # INVARIANT: Chamfered 1px corners sit at (x+1, y+1) etc. so diagonal edges
    # stay 45-degree pixel-clean without 2px L-clusters.
    a.rect(x + 1, y, w - 2, 1, color)
    a.rect(x + 1, y + h - 1, w - 2, 1, color)
    a.rect(x, y + 1, 1, h - 2, color)
    a.rect(x + w - 1, y + 1, 1, h - 2, color)
    a.put(x + 1, y + 1, color)
    a.put(x + w - 2, y + 1, color)
    a.put(x + 1, y + h - 2, color)
    a.put(x + w - 2, y + h - 2, color)


def build_nine_slice_margins(
    x: int,
    y: int,
    w: int,
    h: int,
    frame_left: int,
    frame_right: int,
    frame_top: int,
    frame_bottom: int,
    *,
    canvas_w: int | None = None,
    canvas_h: int | None = None,
    content_padding: int = 0,
) -> NineSliceMargins:
    if content_padding < 0:
        msg = f"content_padding must be >= 0 (got {content_padding})"
        raise ValueError(msg)
    pad_left = max(0, x)
    pad_top = max(0, y)
    pad_right = pad_left if canvas_w is None else max(0, canvas_w - (x + w))
    pad_bottom = pad_top if canvas_h is None else max(0, canvas_h - (y + h))
    return NineSliceMargins(
        left=pad_left + frame_left + content_padding,
        right=pad_right + frame_right + content_padding,
        top=pad_top + frame_top + content_padding,
        bottom=pad_bottom + frame_bottom + content_padding,
    )


def maybe_emit_content_hitbox(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    frame_left: int,
    frame_right: int,
    frame_top: int,
    frame_bottom: int,
    *,
    emit_content_hitbox: bool,
    content_padding: int,
) -> None:
    if not emit_content_hitbox:
        return
    cx = x + frame_left + content_padding
    cy = y + frame_top + content_padding
    cw = w - frame_left - frame_right - (content_padding * 2)
    ch = h - frame_top - frame_bottom - (content_padding * 2)
    if cw > 0 and ch > 0:
        a.hitbox("content", cx, cy, cw, ch, kind="ui_content")


def panel_frame_insets(
    w: int,
    h: int,
    *,
    title_bar_h: int = 0,
    beveled: bool = True,
    corner_cut: int = 1,
) -> tuple[int, int, int, int]:
    if w < 4 or h < 4:
        return (0, 0, 0, 0)
    has_bevel = beveled and w >= 6 and h >= 6
    has_chamfer = corner_cut > 0
    # INVARIANT: Chamfered 1px corners occupy (x+1, y+1); slicing at inset < 2
    # would stretch the corner pixel.
    side = 2 if (has_bevel or has_chamfer) else 1
    top = side
    if title_bar_h > 0 and h > title_bar_h + 4:
        bar_h = min(title_bar_h, h - 4)
        top = 3 + bar_h
    return (side, side, top, side)


def button_frame_insets(
    w: int,
    h: int,
    *,
    corner_cut: int = 1,
) -> tuple[int, int, int, int]:
    if w < 4 or h < 4:
        return (0, 0, 0, 0)
    has_chamfer = corner_cut > 0
    has_edges = w >= 6 and h >= 5
    lr = 2 if has_chamfer else 1
    tb = 2 if (has_chamfer or has_edges) else 1
    return (lr, lr, tb, tb)


def progress_bar_frame_insets(w: int, h: int) -> tuple[int, int, int, int]:
    if w < 4 or h < 3:
        return (0, 0, 0, 0)
    return (1, 1, 1, 1)


def badge_frame_insets(w: int, h: int, *, pill: bool = True) -> tuple[int, int, int, int]:
    if w < 4 or h < 3:
        return (0, 0, 0, 0)
    cut = 1 if (pill and w >= 6 and h >= 5) else 0
    margin = 2 if cut > 0 else 1
    return (margin, margin, margin, margin)


def slot_frame_insets(
    w: int,
    h: int,
    *,
    corner_cut: int = 1,
) -> tuple[int, int, int, int]:
    if w < 4 or h < 4:
        return (0, 0, 0, 0)
    side = 2 if (corner_cut > 0 or (w >= 6 and h >= 6)) else 1
    return (side, side, side, side)


def dialogue_box_frame_insets(
    w: int,
    h: int,
    *,
    tail: UiDialogueTail = "none",
    portrait_size: int = 0,
    corner_cut: int = 1,
) -> tuple[int, int, int, int]:
    if w < 6 or h < 6:
        return (0, 0, 0, 0)
    side = 2 if (corner_cut > 0 or (w >= 8 and h >= 8)) else 1
    fl = side
    fr = side
    ft = side
    fb = side
    tail_b = 3 if (tail in ("bottom_left", "bottom_center", "bottom_right") and h >= 10) else 0
    tail_l = 3 if (tail == "left" and w >= 10) else 0
    tail_r = 3 if (tail == "right" and w >= 10) else 0
    fl += tail_l
    fr += tail_r
    fb += tail_b
    body_w = w - tail_l - tail_r
    body_h = h - tail_b
    if portrait_size > 0 and body_w >= portrait_size + side * 2 + 6 and body_h >= portrait_size + 4:
        # INVARIANT: Portrait box is (portrait_size + 2) wide with a 1px gap before text content.
        fl += portrait_size + 3
    return (fl, fr, ft, fb)


def scrollbar_frame_insets(w: int, h: int) -> tuple[int, int, int, int]:
    if w < 3 or h < 3:
        return (0, 0, 0, 0)
    return (1, 1, 1, 1)


def ui_panel_margins(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    canvas_w: int | None = None,
    canvas_h: int | None = None,
    title_bar_h: int = 0,
    beveled: bool = True,
    corner_cut: int = 1,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Compute synchronized `NineSliceMargins` for a `ui_panel` call."""
    fl, fr, ft, fb = panel_frame_insets(
        w,
        h,
        title_bar_h=title_bar_h,
        beveled=beveled,
        corner_cut=corner_cut,
    )
    return build_nine_slice_margins(
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        content_padding=content_padding,
    )


def ui_button_margins(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    canvas_w: int | None = None,
    canvas_h: int | None = None,
    corner_cut: int = 1,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Compute synchronized `NineSliceMargins` for a `ui_button` call."""
    fl, fr, ft, fb = button_frame_insets(w, h, corner_cut=corner_cut)
    return build_nine_slice_margins(
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        content_padding=content_padding,
    )


def ui_progress_bar_margins(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    canvas_w: int | None = None,
    canvas_h: int | None = None,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Compute synchronized `NineSliceMargins` for a `ui_progress_bar` call."""
    fl, fr, ft, fb = progress_bar_frame_insets(w, h)
    return build_nine_slice_margins(
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        content_padding=content_padding,
    )


def ui_badge_margins(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    canvas_w: int | None = None,
    canvas_h: int | None = None,
    pill: bool = True,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Compute synchronized `NineSliceMargins` for a `ui_badge` call."""
    fl, fr, ft, fb = badge_frame_insets(w, h, pill=pill)
    return build_nine_slice_margins(
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        content_padding=content_padding,
    )


def ui_slot_margins(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    canvas_w: int | None = None,
    canvas_h: int | None = None,
    corner_cut: int = 1,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Compute synchronized `NineSliceMargins` for a `ui_slot` call."""
    fl, fr, ft, fb = slot_frame_insets(w, h, corner_cut=corner_cut)
    return build_nine_slice_margins(
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        content_padding=content_padding,
    )


def ui_dialogue_box_margins(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    canvas_w: int | None = None,
    canvas_h: int | None = None,
    tail: UiDialogueTail = "none",
    portrait_size: int = 0,
    corner_cut: int = 1,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Compute synchronized `NineSliceMargins` for a `ui_dialogue_box` call."""
    fl, fr, ft, fb = dialogue_box_frame_insets(
        w,
        h,
        tail=tail,
        portrait_size=portrait_size,
        corner_cut=corner_cut,
    )
    return build_nine_slice_margins(
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        content_padding=content_padding,
    )


def ui_scrollbar_margins(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    canvas_w: int | None = None,
    canvas_h: int | None = None,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Compute synchronized `NineSliceMargins` for a `ui_scrollbar` call."""
    fl, fr, ft, fb = scrollbar_frame_insets(w, h)
    return build_nine_slice_margins(
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        content_padding=content_padding,
    )
