"""Pixel UI container primitives (panels, slots, dialogue boxes, tabs, dividers)."""

from __future__ import annotations

from typing import Literal

from pixelforge.core.prefabs.ui.margins import (
    UiDialogueTail,
    build_nine_slice_margins,
    cut_rect_corners,
    dialogue_box_frame_insets,
    draw_chamfer_border,
    maybe_emit_content_hitbox,
    panel_frame_insets,
    slot_frame_insets,
)
from pixelforge.core.prefabs.ui.palette import UiPalette, UiTarget
from pixelforge.core.types import NineSliceMargins

UiSlotState = Literal["empty", "hover", "selected", "locked"]
UiTabPlacement = Literal["top", "bottom"]
UiOrientation = Literal["horizontal", "vertical"]


def ui_panel(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    title_bar_h: int = 0,
    beveled: bool = True,
    corner_cut: int = 1,
    recessed: bool = False,
    emit_content_hitbox: bool = False,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Draw a 9-slice-ready beveled pixel UI panel with optional title bar."""
    fl, fr, ft, fb = panel_frame_insets(
        w,
        h,
        title_bar_h=title_bar_h,
        beveled=beveled,
        corner_cut=corner_cut,
    )
    margins = build_nine_slice_margins(
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        canvas_w=a.surface.width,
        canvas_h=a.surface.height,
        content_padding=content_padding,
    )
    if w < 4 or h < 4:
        return margins

    fill_color = pal.bg_dark if recessed else pal.bg
    a.rect(x, y, w, h, fill_color)
    draw_chamfer_border(a, x, y, w, h, pal.border_outer, corner_cut)

    if beveled and w >= 6 and h >= 6:
        top_bevel = pal.border_shadow if recessed else pal.border_highlight
        bot_bevel = pal.border_highlight if recessed else pal.border_shadow
        inset = 2 if corner_cut > 0 else 1
        span_w = max(1, w - inset * 2)
        span_h = max(1, h - inset * 2)
        a.rect(x + inset, y + 1, span_w, 1, top_bevel)
        a.rect(x + 1, y + inset, 1, span_h, top_bevel)
        a.rect(x + inset, y + h - 2, span_w, 1, bot_bevel)
        a.rect(x + w - 2, y + inset, 1, span_h, bot_bevel)

    if title_bar_h > 0 and h > title_bar_h + 4:
        bar_y = y + 2
        bar_h = min(title_bar_h, h - 4)
        a.rect(x + 2, bar_y, w - 4, bar_h, pal.bg_light)
        a.rect(x + 1, bar_y + bar_h, w - 2, 1, pal.border_outer)
        if w >= 12 and bar_h >= 2:
            a.put(x + 3, bar_y + 1, pal.accent)

    cut_rect_corners(a, x, y, w, h, min(corner_cut, 1))
    maybe_emit_content_hitbox(
        a,
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        emit_content_hitbox=emit_content_hitbox,
        content_padding=content_padding,
    )
    return margins


def ui_slot(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    state: UiSlotState = "empty",
    corner_cut: int = 1,
    emit_content_hitbox: bool = False,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Draw an inventory/equipment slot across empty, hover, selected, and locked states."""
    fl, fr, ft, fb = slot_frame_insets(w, h, corner_cut=corner_cut)
    margins = build_nine_slice_margins(
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        canvas_w=a.surface.width,
        canvas_h=a.surface.height,
        content_padding=content_padding,
    )
    if w < 4 or h < 4:
        return margins

    fill = pal.bg if state == "hover" else pal.bg_dark
    outer = pal.border_shadow if state == "locked" else pal.border_outer
    a.rect(x, y, w, h, fill)
    draw_chamfer_border(a, x, y, w, h, outer, corner_cut)

    if w >= 6 and h >= 6:
        inset = 2 if corner_cut > 0 else 1
        span_w = max(1, w - inset * 2)
        span_h = max(1, h - inset * 2)
        if state == "hover":
            top_c, bot_c = pal.accent_bright, pal.accent
        elif state == "selected":
            top_c, bot_c = pal.accent, pal.accent
        elif state == "locked":
            top_c, bot_c = pal.bg, pal.bg_dark
        else:
            top_c, bot_c = pal.border_shadow, pal.border_highlight
        a.rect(x + inset, y + 1, span_w, 1, top_c)
        a.rect(x + 1, y + inset, 1, span_h, top_c)
        a.rect(x + inset, y + h - 2, span_w, 1, bot_c)
        a.rect(x + w - 2, y + inset, 1, span_h, bot_c)

    if state == "selected" and w >= 8 and h >= 8:
        # Crisp 2px corner selection brackets inside the outer border.
        for cx, cy, dx, dy in (
            (x + 1, y + 1, 1, 1),
            (x + w - 2, y + 1, -1, 1),
            (x + 1, y + h - 2, 1, -1),
            (x + w - 2, y + h - 2, -1, -1),
        ):
            a.put(cx, cy, pal.accent_bright)
            a.put(cx + dx, cy, pal.accent_bright)
            a.put(cx, cy + dy, pal.accent_bright)
    elif state == "locked" and w >= 9 and h >= 9:
        mx = x + w // 2
        my = y + h // 2
        a.rect(mx - 1, my - 2, 3, 2, pal.text_muted)
        a.put(mx, my - 1, pal.bg_dark)
        a.rect(mx - 2, my, 5, 3, pal.text_muted)
        a.put(mx, my + 1, pal.bg_dark)

    cut_rect_corners(a, x, y, w, h, min(corner_cut, 1))
    maybe_emit_content_hitbox(
        a,
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        emit_content_hitbox=emit_content_hitbox,
        content_padding=content_padding,
    )
    return margins


def _draw_dialogue_tail(
    a: UiTarget,
    bx: int,
    by: int,
    bw: int,
    bh: int,
    pal: UiPalette,
    tail: UiDialogueTail,
) -> None:
    """Draw a 3px pixel-clean speech tail attached to the dialogue box body."""
    if tail == "none":
        return
    if tail in ("bottom_left", "bottom_center", "bottom_right"):
        if tail == "bottom_left":
            tx = bx + min(5, max(2, bw // 5))
        elif tail == "bottom_right":
            tx = bx + bw - min(9, max(5, bw // 5))
        else:
            tx = bx + bw // 2 - 2
        base_y = by + bh - 1
        a.rect(tx + 1, base_y, 3, 1, pal.bg)
        a.rect(tx + 1, base_y + 1, 2, 1, pal.bg)
        a.put(tx, base_y + 1, pal.border_outer)
        a.put(tx + 3, base_y + 1, pal.border_outer)
        a.put(tx + 1, base_y + 2, pal.border_outer)
        a.put(tx + 2, base_y + 2, pal.border_outer)
        return

    ty = by + bh // 2 - 2
    if tail == "left":
        base_x = bx
        a.rect(base_x, ty + 1, 1, 3, pal.bg)
        a.rect(base_x - 1, ty + 1, 1, 2, pal.bg)
        a.put(base_x - 1, ty, pal.border_outer)
        a.put(base_x - 1, ty + 3, pal.border_outer)
        a.put(base_x - 2, ty + 1, pal.border_outer)
        a.put(base_x - 2, ty + 2, pal.border_outer)
    elif tail == "right":
        base_x = bx + bw - 1
        a.rect(base_x, ty + 1, 1, 3, pal.bg)
        a.rect(base_x + 1, ty + 1, 1, 2, pal.bg)
        a.put(base_x + 1, ty, pal.border_outer)
        a.put(base_x + 1, ty + 3, pal.border_outer)
        a.put(base_x + 2, ty + 1, pal.border_outer)
        a.put(base_x + 2, ty + 2, pal.border_outer)


def ui_dialogue_box(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    tail: UiDialogueTail = "none",
    portrait_size: int = 0,
    corner_cut: int = 1,
    emit_content_hitbox: bool = False,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Draw a pixel dialogue box with optional speech tail and portrait frame."""
    fl, fr, ft, fb = dialogue_box_frame_insets(
        w,
        h,
        tail=tail,
        portrait_size=portrait_size,
        corner_cut=corner_cut,
    )
    margins = build_nine_slice_margins(
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        canvas_w=a.surface.width,
        canvas_h=a.surface.height,
        content_padding=content_padding,
    )
    if w < 6 or h < 6:
        return margins

    tail_b = 3 if (tail in ("bottom_left", "bottom_center", "bottom_right") and h >= 10) else 0
    tail_l = 3 if (tail == "left" and w >= 10) else 0
    tail_r = 3 if (tail == "right" and w >= 10) else 0
    bx = x + tail_l
    by = y
    bw = w - tail_l - tail_r
    bh = h - tail_b

    a.rect(bx, by, bw, bh, pal.bg)
    draw_chamfer_border(a, bx, by, bw, bh, pal.border_outer, corner_cut)
    if bw >= 8 and bh >= 8:
        inset = 2 if corner_cut > 0 else 1
        a.rect(bx + inset, by + 1, max(1, bw - inset * 2), 1, pal.border_highlight)
        a.rect(bx + inset, by + bh - 2, max(1, bw - inset * 2), 1, pal.border_shadow)
    cut_rect_corners(a, bx, by, bw, bh, min(corner_cut, 1))
    _draw_dialogue_tail(a, bx, by, bw, bh, pal, tail)

    side = 2 if (corner_cut > 0 or (w >= 8 and h >= 8)) else 1
    if portrait_size > 0 and bw >= portrait_size + side * 2 + 6 and bh >= portrait_size + 4:
        px = bx + side
        py = by + (bh - (portrait_size + 2)) // 2
        a.rect(px, py, portrait_size + 2, portrait_size + 2, pal.border_outer)
        a.rect(px + 1, py + 1, portrait_size, portrait_size, pal.bg_dark)
        if emit_content_hitbox:
            a.hitbox("portrait", px + 1, py + 1, portrait_size, portrait_size, kind="ui_portrait")

    maybe_emit_content_hitbox(
        a,
        x,
        y,
        w,
        h,
        fl,
        fr,
        ft,
        fb,
        emit_content_hitbox=emit_content_hitbox,
        content_padding=content_padding,
    )
    return margins


def ui_tabs(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    tabs: int = 3,
    active: int = 0,
    placement: UiTabPlacement = "top",
    corner_cut: int = 1,
    emit_tab_hitboxes: bool = False,
) -> None:
    """Draw a horizontal tab strip with an active tab highlight."""
    if tabs < 1 or w < tabs * 4 or h < 4:
        return
    active_idx = max(0, min(tabs - 1, active))
    base_w = w // tabs
    rem = w % tabs
    cur_x = x
    for idx in range(tabs):
        tw = base_w + (1 if idx < rem else 0)
        is_active = idx == active_idx
        fill = pal.bg_light if is_active else pal.bg_dark
        a.rect(cur_x, y, tw, h, fill)
        draw_chamfer_border(a, cur_x, y, tw, h, pal.border_outer, corner_cut)
        if is_active:
            accent_y = y + 1 if placement == "top" else y + h - 2
            span_w = max(1, tw - 4)
            a.rect(cur_x + 2, accent_y, span_w, 1, pal.accent_bright)
            open_y = y + h - 1 if placement == "top" else y
            a.rect(cur_x + 1, open_y, max(1, tw - 2), 1, fill)
        elif h >= 5:
            shade_y = y + h - 2 if placement == "top" else y + 1
            a.rect(cur_x + 1, shade_y, max(1, tw - 2), 1, pal.border_shadow)

        if corner_cut > 0 and tw >= 4 and h >= 4:
            if placement == "top":
                a.erase(cur_x, y)
                a.erase(cur_x + tw - 1, y)
            else:
                a.erase(cur_x, y + h - 1)
                a.erase(cur_x + tw - 1, y + h - 1)
        if emit_tab_hitboxes:
            a.hitbox(f"tab_{idx}", cur_x, y, tw, h, kind="ui_tab")
        cur_x += tw


def ui_divider(
    a: UiTarget,
    x: int,
    y: int,
    length: int,
    pal: UiPalette,
    *,
    orientation: UiOrientation = "horizontal",
    etched: bool = True,
) -> None:
    """Draw a crisp 1px or 2px etched UI divider line."""
    if length <= 0:
        return
    if orientation == "horizontal":
        a.rect(x, y, length, 1, pal.border_shadow)
        if etched:
            a.rect(x, y + 1, length, 1, pal.border_highlight)
    else:
        a.rect(x, y, 1, length, pal.border_shadow)
        if etched:
            a.rect(x + 1, y, 1, length, pal.border_highlight)
