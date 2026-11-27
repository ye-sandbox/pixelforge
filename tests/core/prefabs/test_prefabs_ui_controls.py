"""Hermetic unit tests for extended UI controls, containers, and cursor hotspots."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from pixelforge.core import Asset, prefabs
from pixelforge.core.prefabs import ui as ui_pkg
from pixelforge.core.types import TRANSPARENT_INDEX


def _pal(a: Asset) -> prefabs.UiPalette:
    return prefabs.UiPalette.from_style(a)


def test_ui_package_preserves_public_reexports() -> None:
    """Verify `prefabs` and `prefabs.ui` expose all UI controls and helpers."""
    expected = (
        "UiPalette",
        "ui_panel",
        "ui_panel_margins",
        "ui_button",
        "ui_button_margins",
        "ui_progress_bar",
        "ui_progress_bar_margins",
        "ui_badge",
        "ui_badge_margins",
        "ui_icon_16",
        "ui_slot",
        "ui_slot_margins",
        "ui_dialogue_box",
        "ui_dialogue_box_margins",
        "ui_tabs",
        "ui_divider",
        "ui_slider",
        "ui_toggle",
        "ui_checkbox",
        "ui_scrollbar",
        "ui_scrollbar_margins",
        "ui_cursor",
    )
    for name in expected:
        assert hasattr(prefabs, name), f"Missing {name} on prefabs"
        assert hasattr(ui_pkg, name), f"Missing {name} on prefabs.ui"


def test_ui_slot_states_and_margins_sync(make_asset: Callable[[int, int], Asset]) -> None:
    """Verify `ui_slot` renders distinct states and syncs `NineSliceMargins` + `content`."""
    buffers: dict[prefabs.UiSlotState, np.ndarray] = {}
    for state in ("empty", "hover", "selected", "locked"):
        a = make_asset(24, 24)
        expected = prefabs.ui_slot_margins(
            2, 2, 20, 20, canvas_w=24, canvas_h=24, content_padding=1
        )
        returned = prefabs.ui_slot(
            a,
            2,
            2,
            20,
            20,
            _pal(a),
            state=state,
            emit_content_hitbox=True,
            content_padding=1,
        )
        assert returned == expected
        assert len(a.hitboxes) == 1
        hb = a.hitboxes[0]
        assert hb.name == "content"
        assert hb.x == returned.left
        assert hb.y == returned.top
        assert hb.w == 24 - returned.left - returned.right
        assert hb.h == 24 - returned.top - returned.bottom
        buffers[state] = a.surface.data.copy()

    assert not np.array_equal(buffers["empty"], buffers["hover"])
    assert not np.array_equal(buffers["empty"], buffers["selected"])
    assert not np.array_equal(buffers["empty"], buffers["locked"])
    assert not np.array_equal(buffers["hover"], buffers["selected"])


@pytest.mark.parametrize(
    "tail",
    ["none", "bottom_left", "bottom_center", "bottom_right", "left", "right"],
)
def test_ui_dialogue_box_tails_portrait_and_margins(
    make_asset: Callable[[int, int], Asset],
    tail: prefabs.UiDialogueTail,
) -> None:
    """Verify `ui_dialogue_box` syncs margins, `portrait` hitbox, and `content` hitbox."""
    a = make_asset(64, 32)
    expected = prefabs.ui_dialogue_box_margins(
        2,
        2,
        60,
        28,
        canvas_w=64,
        canvas_h=32,
        tail=tail,
        portrait_size=14,
        content_padding=1,
    )
    returned = prefabs.ui_dialogue_box(
        a,
        2,
        2,
        60,
        28,
        _pal(a),
        tail=tail,
        portrait_size=14,
        emit_content_hitbox=True,
        content_padding=1,
    )
    assert returned == expected
    by_name = {hb.name: hb for hb in a.hitboxes}
    assert set(by_name) == {"portrait", "content"}
    portrait = by_name["portrait"]
    content = by_name["content"]
    assert portrait.w == 14
    assert portrait.h == 14
    assert content.x == returned.left
    assert content.y == returned.top
    assert content.w == 64 - returned.left - returned.right
    assert content.h == 32 - returned.top - returned.bottom
    assert content.x >= portrait.x + portrait.w


def test_ui_tabs_and_divider(make_asset: Callable[[int, int], Asset]) -> None:
    """Verify `ui_tabs` active selection, placements, hitboxes, and `ui_divider`."""
    a_top = make_asset(48, 24)
    prefabs.ui_tabs(
        a_top,
        2,
        2,
        44,
        10,
        _pal(a_top),
        tabs=3,
        active=1,
        placement="top",
        emit_tab_hitboxes=True,
    )
    assert [hb.name for hb in a_top.hitboxes] == ["tab_0", "tab_1", "tab_2"]
    assert sum(hb.w for hb in a_top.hitboxes) == 44

    a_bot = make_asset(48, 24)
    prefabs.ui_tabs(a_bot, 2, 2, 44, 10, _pal(a_bot), tabs=3, active=2, placement="bottom")
    assert not np.array_equal(a_top.surface.data, a_bot.surface.data)

    a_div = make_asset(24, 24)
    prefabs.ui_divider(a_div, 2, 4, 16, _pal(a_div), orientation="horizontal", etched=True)
    prefabs.ui_divider(a_div, 4, 8, 12, _pal(a_div), orientation="vertical", etched=False)
    assert int((a_div.surface.data[4, 2:18] != TRANSPARENT_INDEX).sum()) == 16
    assert int((a_div.surface.data[5, 2:18] != TRANSPARENT_INDEX).sum()) == 16
    assert int((a_div.surface.data[8:20, 4] != TRANSPARENT_INDEX).sum()) == 12


def test_ui_slider_orientations_and_states(make_asset: Callable[[int, int], Asset]) -> None:
    """Verify `ui_slider` renders horizontal/vertical tracks, clamped values, and thumb hitbox."""
    a_low = make_asset(32, 16)
    a_high = make_asset(32, 16)
    prefabs.ui_slider(a_low, 2, 3, 28, 10, _pal(a_low), value=-0.5, emit_thumb_hitbox=True)
    prefabs.ui_slider(a_high, 2, 3, 28, 10, _pal(a_high), value=1.5, emit_thumb_hitbox=True)
    assert len(a_low.hitboxes) == 1
    assert len(a_high.hitboxes) == 1
    assert a_low.hitboxes[0].name == "thumb"
    assert a_high.hitboxes[0].x > a_low.hitboxes[0].x

    a_vert = make_asset(16, 32)
    prefabs.ui_slider(
        a_vert,
        3,
        2,
        10,
        28,
        _pal(a_vert),
        value=0.75,
        orientation="vertical",
        disabled=True,
        emit_thumb_hitbox=True,
    )
    assert len(a_vert.hitboxes) == 1
    assert int((a_vert.surface.data != TRANSPARENT_INDEX).sum()) > 0


def test_ui_toggle_and_checkbox_states(make_asset: Callable[[int, int], Asset]) -> None:
    """Verify `ui_toggle` and `ui_checkbox` render distinct checked/unchecked/disabled states."""
    t_off = make_asset(20, 12)
    t_on = make_asset(20, 12)
    t_dis = make_asset(20, 12)
    prefabs.ui_toggle(t_off, 2, 2, 16, 8, _pal(t_off), checked=False, emit_content_hitbox=True)
    prefabs.ui_toggle(t_on, 2, 2, 16, 8, _pal(t_on), checked=True)
    prefabs.ui_toggle(t_dis, 2, 2, 16, 8, _pal(t_dis), checked=True, disabled=True)
    assert len(t_off.hitboxes) == 1
    assert not np.array_equal(t_off.surface.data, t_on.surface.data)
    assert not np.array_equal(t_on.surface.data, t_dis.surface.data)

    c_off = make_asset(16, 16)
    c_on = make_asset(16, 16)
    c_dis = make_asset(16, 16)
    prefabs.ui_checkbox(c_off, 3, 3, 9, _pal(c_off), checked=False, emit_content_hitbox=True)
    prefabs.ui_checkbox(c_on, 3, 3, 9, _pal(c_on), checked=True)
    prefabs.ui_checkbox(c_dis, 3, 3, 9, _pal(c_dis), checked=True, disabled=True)
    assert len(c_off.hitboxes) == 1
    assert not np.array_equal(c_off.surface.data, c_on.surface.data)
    assert not np.array_equal(c_on.surface.data, c_dis.surface.data)


def test_ui_scrollbar_orientations_and_margins(make_asset: Callable[[int, int], Asset]) -> None:
    """Verify `ui_scrollbar` renders vertical/horizontal tracks and syncs `NineSliceMargins`."""
    a_v0 = make_asset(12, 32)
    a_v1 = make_asset(12, 32)
    expected = prefabs.ui_scrollbar_margins(2, 2, 6, 28, canvas_w=12, canvas_h=32)
    ret = prefabs.ui_scrollbar(
        a_v0,
        2,
        2,
        6,
        28,
        _pal(a_v0),
        value=0.0,
        thumb_ratio=0.3,
        orientation="vertical",
        emit_content_hitbox=True,
    )
    prefabs.ui_scrollbar(
        a_v1,
        2,
        2,
        6,
        28,
        _pal(a_v1),
        value=1.0,
        thumb_ratio=0.3,
        orientation="vertical",
    )
    assert ret == expected
    assert len(a_v0.hitboxes) == 1
    assert not np.array_equal(a_v0.surface.data, a_v1.surface.data)

    a_h = make_asset(32, 12)
    prefabs.ui_scrollbar(
        a_h,
        2,
        2,
        28,
        6,
        _pal(a_h),
        value=0.5,
        thumb_ratio=0.4,
        orientation="horizontal",
    )
    assert int((a_h.surface.data != TRANSPARENT_INDEX).sum()) > 0


@pytest.mark.parametrize(
    ("kind", "expected_offset"),
    [
        ("pointer", (0, 0)),
        ("hand", (4, 0)),
        ("crosshair", (7, 7)),
        ("resize_h", (7, 4)),
        ("resize_v", (4, 7)),
        ("text", (2, 6)),
    ],
)
def test_ui_cursor_kinds_and_hotspot_anchor(
    make_asset: Callable[[int, int], Asset],
    kind: prefabs.UiCursorKind,
    expected_offset: tuple[int, int],
) -> None:
    """Verify `ui_cursor` draws each cursor kind and emits exact `hotspot` anchor."""
    a = make_asset(24, 24)
    hx, hy = prefabs.ui_cursor(a, 3, 4, kind, _pal(a))
    assert (hx, hy) == (3 + expected_offset[0], 4 + expected_offset[1])
    assert len(a.anchors) == 1
    anchor = a.anchors[0]
    assert anchor.name == "hotspot"
    assert anchor.kind == "ui_hotspot"
    assert (anchor.x, anchor.y) == (hx, hy)
    assert int((a.surface.data != TRANSPARENT_INDEX).sum()) > 0
