"""Pixel UI interactive control primitives (buttons, bars, badges, sliders, toggles, scrollbars)."""

from __future__ import annotations

from typing import Literal

from pixelforge.core.prefabs.ui.containers import UiOrientation
from pixelforge.core.prefabs.ui.margins import (
    badge_frame_insets,
    build_nine_slice_margins,
    button_frame_insets,
    cut_rect_corners,
    draw_chamfer_border,
    maybe_emit_content_hitbox,
    progress_bar_frame_insets,
    scrollbar_frame_insets,
)
from pixelforge.core.prefabs.ui.palette import UiPalette, UiTarget
from pixelforge.core.types import NineSliceMargins

UiButtonState = Literal["normal", "hover", "pressed", "disabled"]
UiBadgeTone = Literal["neutral", "info", "success", "warning", "danger"]


def ui_button(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    state: UiButtonState = "normal",
    accent: bool = False,
    corner_cut: int = 1,
    emit_content_hitbox: bool = False,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Draw a tactile pixel UI button across normal, hover, pressed, and disabled states."""
    fl, fr, ft, fb = button_frame_insets(w, h, corner_cut=corner_cut)
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

    if state == "disabled":
        fill = pal.bg_dark
        border = pal.border_shadow
        top_edge = pal.bg
        bot_edge = pal.bg_dark
    elif state == "pressed":
        fill = pal.accent if accent else pal.bg_dark
        border = pal.border_outer
        top_edge = pal.border_shadow
        bot_edge = fill
    elif state == "hover":
        fill = pal.accent_bright if accent else pal.bg_light
        border = pal.border_outer
        top_edge = pal.text if accent else pal.accent_bright
        bot_edge = pal.accent if accent else pal.border_shadow
    else:
        fill = pal.accent if accent else pal.bg_light
        border = pal.border_outer
        top_edge = pal.accent_bright if accent else pal.border_highlight
        bot_edge = pal.border_shadow

    a.rect(x, y, w, h, fill)
    draw_chamfer_border(a, x, y, w, h, border, corner_cut)

    if w >= 6 and h >= 5:
        inset = 2 if corner_cut > 0 else 1
        span_w = max(1, w - inset * 2)
        a.rect(x + inset, y + 1, span_w, 1, top_edge)
        a.rect(x + inset, y + h - 2, span_w, 1, bot_edge)

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


def ui_progress_bar(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    value: float = 0.5,
    fill_color: int | None = None,
    segments: int = 0,
    show_specular: bool = True,
    emit_content_hitbox: bool = False,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Draw a recessed pixel progress bar with optional specular strip and segments."""
    fl, fr, ft, fb = progress_bar_frame_insets(w, h)
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
    if w < 4 or h < 3:
        return margins

    clamped = max(0.0, min(1.0, value))
    a.rect(x, y, w, h, pal.border_outer)
    inner_x = x + 1
    inner_y = y + 1
    inner_w = w - 2
    inner_h = h - 2
    a.rect(inner_x, inner_y, inner_w, inner_h, pal.bg_dark)

    fill_w = round(inner_w * clamped)
    if fill_w > 0:
        bar_color = pal.accent if fill_color is None else fill_color
        a.rect(inner_x, inner_y, fill_w, inner_h, bar_color)
        if show_specular and inner_h >= 2:
            spec_color = pal.accent_bright if fill_color is None else pal.border_highlight
            a.rect(inner_x, inner_y, fill_w, 1, spec_color)

    if segments > 1 and inner_w >= segments * 2:
        for idx in range(1, segments):
            div_x = inner_x + (inner_w * idx) // segments
            if inner_x < div_x < inner_x + inner_w:
                a.rect(div_x, inner_y, 1, inner_h, pal.border_outer)

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


def ui_badge(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    tone: UiBadgeTone = "neutral",
    pill: bool = True,
    emit_content_hitbox: bool = False,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Draw a compact status badge or pill tag using semantic tone colors."""
    fl, fr, ft, fb = badge_frame_insets(w, h, pill=pill)
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
    if w < 4 or h < 3:
        return margins

    tone_colors: dict[UiBadgeTone, tuple[int, int]] = {
        "neutral": (pal.bg_light, pal.text_muted),
        "info": (pal.bg_dark, pal.accent_bright),
        "success": (pal.bg_dark, pal.success),
        "warning": (pal.bg_dark, pal.warning),
        "danger": (pal.bg_dark, pal.danger),
    }
    fill_color, dot_color = tone_colors[tone]
    cut = 1 if (pill and w >= 6 and h >= 5) else 0

    a.rect(x, y, w, h, fill_color)
    draw_chamfer_border(a, x, y, w, h, pal.border_outer, cut)
    if w >= 8 and h >= 5:
        a.put(x + 2, y + h // 2, dot_color)
        if w >= 12:
            a.rect(x + 4, y + h // 2, w - 7, 1, dot_color)
    cut_rect_corners(a, x, y, w, h, cut)
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


def ui_slider(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    value: float = 0.5,
    orientation: UiOrientation = "horizontal",
    disabled: bool = False,
    emit_thumb_hitbox: bool = False,
) -> None:
    """Draw a pixel UI slider with recessed track, active fill, and tactile thumb."""
    if w < 6 or h < 5:
        return
    clamped = max(0.0, min(1.0, value))
    fill_c = pal.text_muted if disabled else pal.accent
    border_c = pal.border_shadow if disabled else pal.border_outer
    thumb_c = pal.bg_dark if disabled else pal.bg_light

    if orientation == "horizontal":
        track_h = min(4, max(3, h // 2))
        ty = y + (h - track_h) // 2
        a.rect(x, ty, w, track_h, border_c)
        a.rect(x + 1, ty + 1, w - 2, track_h - 2, pal.bg_dark)
        thumb_w = min(5, max(3, h - 2))
        thumb_h = min(h, 7)
        knob_y = y + (h - thumb_h) // 2
        travel = max(0, w - thumb_w)
        knob_x = x + round(travel * clamped)
        fill_w = max(0, (knob_x + thumb_w // 2) - (x + 1))
        if fill_w > 0:
            a.rect(x + 1, ty + 1, min(w - 2, fill_w), track_h - 2, fill_c)
    else:
        track_w = min(4, max(3, w // 2))
        tx = x + (w - track_w) // 2
        a.rect(tx, y, track_w, h, border_c)
        a.rect(tx + 1, y + 1, track_w - 2, h - 2, pal.bg_dark)
        thumb_w = min(w, 7)
        thumb_h = min(5, max(3, w - 2))
        knob_x = x + (w - thumb_w) // 2
        travel = max(0, h - thumb_h)
        knob_y = y + round(travel * (1.0 - clamped))
        fill_start = knob_y + thumb_h // 2
        fill_h = max(0, (y + h - 1) - fill_start)
        if fill_h > 0:
            a.rect(tx + 1, max(y + 1, fill_start), track_w - 2, min(h - 2, fill_h), fill_c)

    a.rect(knob_x, knob_y, thumb_w, thumb_h, thumb_c)
    draw_chamfer_border(a, knob_x, knob_y, thumb_w, thumb_h, border_c, 0)
    if thumb_w >= 3 and thumb_h >= 3 and not disabled:
        a.rect(knob_x + 1, knob_y + 1, thumb_w - 2, 1, pal.border_highlight)
    if emit_thumb_hitbox:
        a.hitbox("thumb", knob_x, knob_y, thumb_w, thumb_h, kind="ui_thumb")


def ui_toggle(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    checked: bool = False,
    disabled: bool = False,
    emit_content_hitbox: bool = False,
) -> None:
    """Draw a pill-shaped pixel toggle switch."""
    if w < 8 or h < 5:
        return
    border_c = pal.border_shadow if disabled else pal.border_outer
    if disabled:
        track_c = pal.bg_dark
        knob_c = pal.text_muted
    elif checked:
        track_c = pal.accent
        knob_c = pal.text
    else:
        track_c = pal.bg_dark
        knob_c = pal.bg_light

    a.rect(x, y, w, h, track_c)
    draw_chamfer_border(a, x, y, w, h, border_c, 1)
    cut_rect_corners(a, x, y, w, h, 1)

    knob_s = max(3, h - 4)
    knob_y = y + (h - knob_s) // 2
    knob_x = (x + w - 2 - knob_s) if checked else (x + 2)
    a.rect(knob_x, knob_y, knob_s, knob_s, knob_c)
    if knob_s >= 3 and not disabled:
        a.rect(knob_x, knob_y, knob_s, 1, pal.border_highlight)
    if emit_content_hitbox:
        a.hitbox("content", x, y, w, h, kind="ui_toggle")


def ui_checkbox(
    a: UiTarget,
    x: int,
    y: int,
    size: int,
    pal: UiPalette,
    *,
    checked: bool = False,
    disabled: bool = False,
    emit_content_hitbox: bool = False,
) -> None:
    """Draw a crisp square pixel checkbox with optional checkmark glyph."""
    if size < 5:
        return
    border_c = pal.border_shadow if disabled else pal.border_outer
    fill_c = pal.bg_dark if (disabled or not checked) else pal.accent
    tick_c = pal.text_muted if disabled else pal.text

    a.rect(x, y, size, size, fill_c)
    draw_chamfer_border(a, x, y, size, size, border_c, 0)

    if checked and size >= 7:
        # Draw a crisp 3-segment pixel checkmark centered inside the box.
        cx = x + size // 2
        cy = y + size // 2 + 1
        a.put(cx - 2, cy - 1, tick_c)
        a.put(cx - 1, cy, tick_c)
        a.put(cx, cy - 1, tick_c)
        a.put(cx + 1, cy - 2, tick_c)
        if size >= 9:
            a.put(cx + 2, cy - 3, tick_c)
    elif checked:
        a.rect(x + 2, y + 2, size - 4, size - 4, tick_c)

    if emit_content_hitbox:
        a.hitbox("content", x, y, size, size, kind="ui_checkbox")


def ui_scrollbar(
    a: UiTarget,
    x: int,
    y: int,
    w: int,
    h: int,
    pal: UiPalette,
    *,
    value: float = 0.0,
    thumb_ratio: float = 0.25,
    orientation: UiOrientation = "vertical",
    emit_content_hitbox: bool = False,
    content_padding: int = 0,
) -> NineSliceMargins:
    """Draw a recessed pixel scrollbar track with a proportional thumb."""
    fl, fr, ft, fb = scrollbar_frame_insets(w, h)
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
    if w < 3 or h < 3:
        return margins

    clamped_val = max(0.0, min(1.0, value))
    clamped_ratio = max(0.05, min(1.0, thumb_ratio))
    a.rect(x, y, w, h, pal.border_outer)
    a.rect(x + 1, y + 1, w - 2, h - 2, pal.bg_dark)

    if orientation == "vertical":
        inner_h = h - 2
        thumb_h = min(inner_h, max(3, round(inner_h * clamped_ratio)))
        travel = max(0, inner_h - thumb_h)
        ty = y + 1 + round(travel * clamped_val)
        a.rect(x + 1, ty, w - 2, thumb_h, pal.bg_light)
        if w >= 4:
            a.rect(x + 1, ty, 1, thumb_h, pal.border_highlight)
            a.rect(x + w - 2, ty, 1, thumb_h, pal.border_shadow)
        else:
            a.rect(x + 1, ty, w - 2, 1, pal.border_highlight)
    else:
        inner_w = w - 2
        thumb_w = min(inner_w, max(3, round(inner_w * clamped_ratio)))
        travel = max(0, inner_w - thumb_w)
        tx = x + 1 + round(travel * clamped_val)
        a.rect(tx, y + 1, thumb_w, h - 2, pal.bg_light)
        if h >= 4:
            a.rect(tx, y + 1, thumb_w, 1, pal.border_highlight)
            a.rect(tx, y + h - 2, thumb_w, 1, pal.border_shadow)
        else:
            a.rect(tx, y + 1, 1, h - 2, pal.border_highlight)

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
