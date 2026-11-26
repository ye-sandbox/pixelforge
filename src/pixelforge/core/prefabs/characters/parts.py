"""Compositional StylePack-agnostic character and avatar part primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pixelforge.core.builder import Asset, Layer
from pixelforge.core.palette import PaletteLookup
from pixelforge.core.prefabs.characters.cycles import (
    CharacterCycleState,
    CharacterFacing,
    CharacterPose,
    eval_character_cycle,
)
from pixelforge.core.surface import IndexedSurface

Canvas = Asset[object] | Layer
HairStyle = Literal["short", "parted", "spiky", "bob", "ponytail", "buzz"]
AccessoryKind = Literal["none", "glasses", "visor", "headphones", "headset", "cap", "badge"]


@dataclass(frozen=True)
class CharacterPalette:
    """Resolved StylePack-agnostic integer color indices for modular avatars."""

    skin_light: int
    skin_mid: int
    skin_dark: int
    hair_base: int
    hair_highlight: int
    hair_shadow: int
    shirt_base: int
    shirt_shade: int
    shirt_highlight: int
    pants_base: int
    pants_shade: int
    shoe: int
    eye: int
    outline: int | None = None
    accessory_base: int | None = None
    accessory_accent: int | None = None

    @classmethod
    def from_lookup(
        cls,
        pal: PaletteLookup,
        *,
        skin_light: str,
        skin_mid: str,
        skin_dark: str,
        hair_base: str,
        hair_highlight: str | None = None,
        hair_shadow: str | None = None,
        shirt_base: str,
        shirt_shade: str | None = None,
        shirt_highlight: str | None = None,
        pants_base: str,
        pants_shade: str | None = None,
        shoe: str,
        eye: str,
        outline: str | None = None,
        accessory_base: str | None = None,
        accessory_accent: str | None = None,
    ) -> CharacterPalette:
        """Bind a `CharacterPalette` from any `PaletteLookup` (including `with_overrides`)."""
        return cls(
            skin_light=pal[skin_light],
            skin_mid=pal[skin_mid],
            skin_dark=pal[skin_dark],
            hair_base=pal[hair_base],
            hair_highlight=pal[hair_highlight or hair_base],
            hair_shadow=pal[hair_shadow or hair_base],
            shirt_base=pal[shirt_base],
            shirt_shade=pal[shirt_shade or shirt_base],
            shirt_highlight=pal[shirt_highlight or shirt_base],
            pants_base=pal[pants_base],
            pants_shade=pal[pants_shade or pants_base],
            shoe=pal[shoe],
            eye=pal[eye],
            outline=pal[outline] if outline is not None else None,
            accessory_base=pal[accessory_base] if accessory_base is not None else None,
            accessory_accent=pal[accessory_accent] if accessory_accent is not None else None,
        )


@dataclass(frozen=True)
class LegsAnchors:
    """Connecting coordinates emitted by `avatar_legs`."""

    waist: tuple[int, int]
    foot_left: tuple[int, int]
    foot_right: tuple[int, int]
    ground: tuple[int, int]


@dataclass(frozen=True)
class TorsoAnchors:
    """Connecting coordinates emitted by `avatar_torso`."""

    neck: tuple[int, int]
    hand_left: tuple[int, int]
    hand_right: tuple[int, int]
    waist: tuple[int, int]
    badge: tuple[int, int]


@dataclass(frozen=True)
class HeadAnchors:
    """Connecting coordinates emitted by `avatar_head`."""

    hair_top: tuple[int, int]
    eye_left: tuple[int, int]
    eye_right: tuple[int, int]
    neck: tuple[int, int]
    accessory_slot: tuple[int, int]


@dataclass(frozen=True)
class CharacterAnchors:
    """Full-body coordinates emitted by `avatar_character`."""

    foot: tuple[int, int]
    waist: tuple[int, int]
    neck: tuple[int, int]
    head_top: tuple[int, int]
    hand_left: tuple[int, int]
    hand_right: tuple[int, int]
    accessory: tuple[int, int]
    bbox: tuple[int, int, int, int]


def _render_part(
    target: Canvas,
    outline: int | None,
    draw_fn: Callable[[IndexedSurface], None],
) -> None:
    if outline is None:
        draw_fn(target.surface)
        return
    patch = IndexedSurface(target.surface.width, target.surface.height)
    draw_fn(patch)
    patch.auto_outline(outline)
    target.surface.blit_layer(patch, 0, 0)


def _draw_legs_surface(
    surf: IndexedSurface,
    ix: int,
    iy: int,
    *,
    pants_base: int,
    pants_shade: int,
    shoe: int,
    facing: CharacterFacing,
    stride: int,
    seated: bool,
) -> LegsAnchors:
    clamped_stride = -1 if stride < 0 else (1 if stride > 0 else 0)
    if seated:
        lap_shift = 1 if facing == "iso-se" else (-1 if facing == "iso-sw" else 0)
        surf.rect(ix - 3, iy - 6, 6, 2, pants_base)
        surf.rect(ix - 3 + lap_shift, iy - 4, 6, 2, pants_shade)
        surf.rect(ix - 3 + lap_shift, iy - 2, 2, 2, shoe)
        surf.rect(ix + 1 + lap_shift, iy - 2, 2, 2, shoe)
    elif facing == "front":
        left_dy = -1 if clamped_stride < 0 else 0
        right_dy = -1 if clamped_stride > 0 else 0
        surf.rect(ix - 3, iy - 6, 3, 2, pants_base)
        surf.rect(ix, iy - 6, 3, 2, pants_shade)
        surf.rect(ix - 3, iy - 4 + left_dy, 2, 3, pants_base)
        surf.rect(ix + 1, iy - 4 + right_dy, 2, 3, pants_shade)
        surf.rect(ix - 3, iy - 1 + left_dy, 2, 1, shoe)
        surf.rect(ix + 1, iy - 1 + right_dy, 2, 1, shoe)
    else:
        dir_x = 1 if facing == "iso-se" else -1
        front_dx = dir_x * clamped_stride
        back_dx = -dir_x * clamped_stride
        surf.rect(ix - 3, iy - 6, 6, 2, pants_base)
        surf.rect(ix + 1, iy - 6, 2, 2, pants_shade)
        surf.rect(ix - 3 + back_dx, iy - 5, 2, 3, pants_shade)
        surf.rect(ix - 3 + back_dx, iy - 2, 2, 1, shoe)
        surf.rect(ix + 1 + front_dx, iy - 4, 2, 3, pants_base)
        surf.rect(ix + 1 + front_dx, iy - 1, 2, 1, shoe)

    return LegsAnchors(
        waist=(ix, iy - 6),
        foot_left=(ix - 2, iy - 1),
        foot_right=(ix + 2, iy - 1),
        ground=(ix, iy),
    )


def avatar_legs(
    target: Canvas,
    cx: int | float,
    foot_y: int | float,
    *,
    pants_base: int,
    pants_shade: int,
    shoe: int,
    outline: int | None = None,
    facing: CharacterFacing = "front",
    stride: int = 0,
    seated: bool = False,
) -> LegsAnchors:
    """Draw standing, walking, or seated avatar legs and shoes anchored at `(cx, foot_y)`."""
    ix = round(cx)
    iy = round(foot_y)
    anchors: list[LegsAnchors] = []

    def _draw(surf: IndexedSurface) -> None:
        anchors.append(
            _draw_legs_surface(
                surf,
                ix,
                iy,
                pants_base=pants_base,
                pants_shade=pants_shade,
                shoe=shoe,
                facing=facing,
                stride=stride,
                seated=seated,
            )
        )

    _render_part(target, outline, _draw)
    return anchors[0]


def _draw_torso_surface(
    surf: IndexedSurface,
    ix: int,
    iy: int,
    *,
    shirt_base: int,
    shirt_shade: int,
    shirt_highlight: int,
    skin_light: int,
    skin_mid: int,
    facing: CharacterFacing,
    arm_left_dx: int,
    arm_left_dy: int,
    arm_right_dx: int,
    arm_right_dy: int,
) -> TorsoAnchors:
    top_y = iy - 7
    surf.rect(ix - 4, top_y, 8, 7, shirt_base)
    # Crisp top-left bevel + right-side/hem shadow without splitting torso into stripes
    surf.rect(ix - 4, top_y, 4, 1, shirt_highlight)
    surf.rect(ix + 2, top_y, 2, 7, shirt_shade)
    surf.rect(ix - 4, iy - 1, 8, 1, shirt_shade)

    collar_x = ix - 1 if facing == "front" else (ix if facing == "iso-se" else ix - 2)
    surf.rect(collar_x, top_y, 2, 1, skin_light)

    arm_spread = 6 if facing == "front" else 5
    lx = ix - arm_spread + arm_left_dx
    rx = ix + (arm_spread - 2) + arm_right_dx
    ly = top_y + 1 + arm_left_dy
    ry = top_y + 1 + arm_right_dy

    surf.rect(lx, ly, 2, 3, shirt_base)
    surf.rect(lx, ly, 2, 1, shirt_highlight)
    surf.rect(lx, ly + 3, 2, 2, skin_light)

    surf.rect(rx, ry, 2, 3, shirt_shade)
    surf.rect(rx, ry + 3, 2, 2, skin_mid)

    return TorsoAnchors(
        neck=(ix, top_y),
        hand_left=(lx, ly + 4),
        hand_right=(rx + 1, ry + 4),
        waist=(ix, iy),
        badge=(ix + 1, top_y + 2),
    )


def avatar_torso(
    target: Canvas,
    cx: int | float,
    waist_y: int | float,
    *,
    shirt_base: int,
    shirt_shade: int,
    shirt_highlight: int,
    skin_light: int,
    skin_mid: int,
    outline: int | None = None,
    facing: CharacterFacing = "front",
    arm_left_dx: int = 0,
    arm_left_dy: int = 0,
    arm_right_dx: int = 0,
    arm_right_dy: int = 0,
) -> TorsoAnchors:
    """Draw shaded torso, collar, and articulated arms anchored at `(cx, waist_y)`."""
    ix = round(cx)
    iy = round(waist_y)
    anchors: list[TorsoAnchors] = []

    def _draw(surf: IndexedSurface) -> None:
        anchors.append(
            _draw_torso_surface(
                surf,
                ix,
                iy,
                shirt_base=shirt_base,
                shirt_shade=shirt_shade,
                shirt_highlight=shirt_highlight,
                skin_light=skin_light,
                skin_mid=skin_mid,
                facing=facing,
                arm_left_dx=arm_left_dx,
                arm_left_dy=arm_left_dy,
                arm_right_dx=arm_right_dx,
                arm_right_dy=arm_right_dy,
            )
        )

    _render_part(target, outline, _draw)
    return anchors[0]


def _draw_head_surface(
    surf: IndexedSurface,
    ix: int,
    iy: int,
    *,
    skin_light: int,
    skin_mid: int,
    skin_dark: int,
    eye: int,
    facing: CharacterFacing,
    blink: bool,
) -> HeadAnchors:
    top_y = iy - 8
    if facing == "front":
        eye_lx, eye_rx = ix - 2, ix + 1
    elif facing == "iso-se":
        eye_lx, eye_rx = ix - 1, ix + 2
    else:
        eye_lx, eye_rx = ix - 3, ix
    eye_y = iy - 4

    surf.rect(ix - 3, top_y, 6, 1, skin_light)
    surf.rect(ix - 4, top_y + 1, 8, 6, skin_mid)
    surf.rect(ix - 3, iy - 1, 6, 1, skin_dark)
    surf.rect(ix - 4, top_y + 1, 3, 2, skin_light)
    surf.rect(ix + 2, top_y + 1, 2, 6, skin_dark)

    if facing == "iso-se":
        surf.rect(ix - 5, top_y + 3, 1, 2, skin_dark)
    elif facing == "iso-sw":
        surf.rect(ix + 4, top_y + 3, 1, 2, skin_dark)

    if blink:
        surf.rect(eye_lx, eye_y + 1, 2, 1, skin_dark)
        surf.rect(eye_rx, eye_y + 1, 2, 1, skin_dark)
    else:
        surf.rect(eye_lx, eye_y, 1, 2, eye)
        surf.rect(eye_rx, eye_y, 1, 2, eye)

    return HeadAnchors(
        hair_top=(ix, top_y),
        eye_left=(eye_lx, eye_y),
        eye_right=(eye_rx, eye_y),
        neck=(ix, iy),
        accessory_slot=(ix, eye_y),
    )


def avatar_head(
    target: Canvas,
    cx: int | float,
    neck_y: int | float,
    *,
    skin_light: int,
    skin_mid: int,
    skin_dark: int,
    eye: int,
    outline: int | None = None,
    facing: CharacterFacing = "front",
    blink: bool = False,
) -> HeadAnchors:
    """Draw a directional shaded avatar head with eyes anchored at `(cx, neck_y)`."""
    ix = round(cx)
    iy = round(neck_y)
    anchors: list[HeadAnchors] = []

    def _draw(surf: IndexedSurface) -> None:
        anchors.append(
            _draw_head_surface(
                surf,
                ix,
                iy,
                skin_light=skin_light,
                skin_mid=skin_mid,
                skin_dark=skin_dark,
                eye=eye,
                facing=facing,
                blink=blink,
            )
        )

    _render_part(target, outline, _draw)
    return anchors[0]


def _draw_hair_surface(
    surf: IndexedSurface,
    ix: int,
    ty: int,
    *,
    hair_base: int,
    hair_highlight: int,
    hair_shadow: int,
    style: HairStyle,
    facing: CharacterFacing,
) -> None:
    if style == "buzz":
        surf.rect(ix - 3, ty - 1, 6, 2, hair_base)
        surf.rect(ix - 3, ty - 1, 3, 1, hair_highlight)
        surf.rect(ix - 4, ty + 1, 1, 2, hair_shadow)
        surf.rect(ix + 3, ty + 1, 1, 2, hair_shadow)
        return

    if style == "short":
        surf.rect(ix - 4, ty - 1, 8, 3, hair_base)
        surf.rect(ix - 3, ty - 1, 4, 1, hair_highlight)
        surf.rect(ix + 2, ty, 2, 2, hair_shadow)
        surf.rect(ix - 4, ty + 2, 1, 2, hair_base)
        surf.rect(ix + 3, ty + 2, 1, 2, hair_shadow)
        return

    if style == "parted":
        surf.rect(ix - 4, ty - 2, 8, 3, hair_base)
        surf.rect(ix - 3, ty - 2, 4, 1, hair_highlight)
        if facing == "iso-sw":
            surf.rect(ix - 3, ty + 1, 3, 1, hair_base)
            surf.rect(ix + 2, ty, 2, 3, hair_shadow)
        else:
            surf.rect(ix, ty + 1, 3, 1, hair_base)
            surf.rect(ix - 4, ty + 1, 2, 2, hair_highlight)
        return

    if style == "spiky":
        surf.rect(ix - 4, ty - 1, 8, 2, hair_base)
        surf.rect(ix - 4, ty - 3, 2, 2, hair_highlight)
        surf.rect(ix - 1, ty - 4, 2, 3, hair_highlight)
        surf.rect(ix + 2, ty - 3, 2, 2, hair_shadow)
        return

    if style == "bob":
        surf.rect(ix - 4, ty - 2, 8, 3, hair_base)
        surf.rect(ix - 3, ty - 2, 4, 1, hair_highlight)
        surf.rect(ix - 5, ty, 2, 6, hair_base)
        surf.rect(ix + 3, ty, 2, 6, hair_shadow)
        return

    if style == "ponytail":
        surf.rect(ix - 4, ty - 2, 8, 3, hair_base)
        surf.rect(ix - 3, ty - 2, 4, 1, hair_highlight)
        if facing == "iso-se":
            surf.rect(ix - 6, ty + 1, 2, 5, hair_shadow)
            surf.rect(ix - 6, ty + 1, 1, 3, hair_base)
        else:
            surf.rect(ix + 4, ty + 1, 2, 5, hair_shadow)
            surf.rect(ix + 4, ty + 1, 1, 3, hair_base)
        return

    msg = f"Unsupported hair style: {style!r}"
    raise ValueError(msg)


def avatar_hair(
    target: Canvas,
    cx: int | float,
    head_top_y: int | float,
    *,
    hair_base: int,
    hair_highlight: int,
    hair_shadow: int,
    outline: int | None = None,
    style: HairStyle = "parted",
    facing: CharacterFacing = "front",
) -> None:
    """Draw modular hairstyle geometry anchored at `head_top_y`."""
    ix = round(cx)
    ty = round(head_top_y)

    def _draw(surf: IndexedSurface) -> None:
        _draw_hair_surface(
            surf,
            ix,
            ty,
            hair_base=hair_base,
            hair_highlight=hair_highlight,
            hair_shadow=hair_shadow,
            style=style,
            facing=facing,
        )

    _render_part(target, outline, _draw)


def _draw_accessory_surface(
    surf: IndexedSurface,
    head: HeadAnchors,
    torso: TorsoAnchors,
    *,
    kind: AccessoryKind,
    primary: int,
    accent: int,
    shade: int,
    facing: CharacterFacing,
    alert_indicator: bool,
) -> tuple[int, int]:
    hx, hy = head.accessory_slot
    tx, ty = head.hair_top

    if kind == "glasses":
        lx, ly = head.eye_left
        rx, _ = head.eye_right
        surf.rect(lx - 1, ly, 2, 2, primary)
        surf.rect(rx, ly, 2, 2, primary)
        surf.rect(lx + 1, ly, rx - lx, 1, primary)
        surf.put(lx, ly, accent)
        surf.put(rx, ly, accent)
    elif kind == "visor":
        vx = min(head.eye_left[0], head.eye_right[0]) - 1
        vw = abs(head.eye_right[0] - head.eye_left[0]) + 3
        surf.rect(vx, hy - 1, vw, 3, primary)
        surf.rect(vx, hy, vw, 1, accent)
    elif kind == "headphones":
        surf.rect(tx - 4, ty - 2, 8, 1, primary)
        surf.rect(tx - 5, hy - 1, 2, 3, primary)
        surf.rect(tx + 3, hy - 1, 2, 3, shade)
        surf.put(tx - 5, hy, accent)
        surf.put(tx + 4, hy, accent)
    elif kind == "headset":
        side_x = tx - 5 if facing != "iso-sw" else tx + 3
        surf.rect(tx - 4, ty - 2, 8, 1, primary)
        surf.rect(side_x, hy - 1, 2, 3, primary)
        mic_dir = 1 if facing != "iso-sw" else -1
        surf.rect(side_x + mic_dir, hy + 2, 2, 1, shade)
        surf.put(side_x + mic_dir * 2, hy + 2, accent)
    elif kind == "cap":
        surf.rect(tx - 4, ty - 2, 8, 3, primary)
        brim_x = tx - 3 if facing == "front" else (tx - 1 if facing == "iso-se" else tx - 5)
        surf.rect(brim_x, ty, 6, 1, shade)
        surf.rect(tx - 1, ty - 1, 2, 1, accent)
    elif kind == "badge":
        bx, by = torso.badge
        surf.rect(bx, by, 2, 2, primary)
        surf.put(bx, by, accent)
    elif kind != "none":
        msg = f"Unsupported accessory kind: {kind!r}"
        raise ValueError(msg)

    if alert_indicator:
        # INVARIANT: Use 2px-wide exclamation segments so the floating alert glyph
        # never triggers orphan-pixel (1x1 isolated pixel) guard errors.
        surf.rect(tx - 1, ty - 7, 2, 3, accent)
        surf.rect(tx - 1, ty - 3, 2, 1, accent)

    return (hx, hy)


def avatar_accessory(
    target: Canvas,
    head: HeadAnchors,
    torso: TorsoAnchors,
    *,
    kind: AccessoryKind,
    primary: int,
    accent: int,
    shade: int | None = None,
    outline: int | None = None,
    facing: CharacterFacing = "front",
    alert_indicator: bool = False,
) -> tuple[int, int]:
    """Draw wearable accessories (`glasses`, `visor`, `headphones`, `headset`, `cap`, `badge`)."""
    sh = shade if shade is not None else primary
    slots: list[tuple[int, int]] = []

    def _draw(surf: IndexedSurface) -> None:
        slots.append(
            _draw_accessory_surface(
                surf,
                head,
                torso,
                kind=kind,
                primary=primary,
                accent=accent,
                shade=sh,
                facing=facing,
                alert_indicator=alert_indicator,
            )
        )

    _render_part(target, outline, _draw)
    return slots[0]


def avatar_character(
    target: Canvas,
    cx: int | float,
    foot_y: int | float,
    pal: CharacterPalette,
    *,
    state: CharacterCycleState = "idle",
    frame: int = 0,
    frames: int = 4,
    facing: CharacterFacing = "front",
    hair_style: HairStyle = "parted",
    accessory: AccessoryKind = "none",
    seated: bool = False,
    seed: int = 0,
    pose: CharacterPose | None = None,
    emit_metadata: bool = True,
) -> CharacterAnchors:
    """Compose a full modular character with deterministic cycle pose, outline, and anchors."""
    active_pose = (
        pose
        if pose is not None
        else eval_character_cycle(state, frame, frames, seed=seed, seated=seated)
    )
    ix = round(cx)
    iy = round(foot_y)

    body_surf = IndexedSurface(target.surface.width, target.surface.height)
    legs_a = _draw_legs_surface(
        body_surf,
        ix,
        iy,
        pants_base=pal.pants_base,
        pants_shade=pal.pants_shade,
        shoe=pal.shoe,
        facing=facing,
        stride=active_pose.leg_stride,
        seated=active_pose.seated,
    )
    torso_a = _draw_torso_surface(
        body_surf,
        ix,
        legs_a.waist[1] + active_pose.bob_y,
        shirt_base=pal.shirt_base,
        shirt_shade=pal.shirt_shade,
        shirt_highlight=pal.shirt_highlight,
        skin_light=pal.skin_light,
        skin_mid=pal.skin_mid,
        facing=facing,
        arm_left_dx=active_pose.arm_left_dx,
        arm_left_dy=active_pose.arm_left_dy,
        arm_right_dx=active_pose.arm_right_dx,
        arm_right_dy=active_pose.arm_right_dy,
    )
    head_a = _draw_head_surface(
        body_surf,
        ix,
        torso_a.neck[1] + active_pose.head_dy,
        skin_light=pal.skin_light,
        skin_mid=pal.skin_mid,
        skin_dark=pal.skin_dark,
        eye=pal.eye,
        facing=facing,
        blink=active_pose.blink,
    )
    _draw_hair_surface(
        body_surf,
        ix,
        head_a.hair_top[1],
        hair_base=pal.hair_base,
        hair_highlight=pal.hair_highlight,
        hair_shadow=pal.hair_shadow,
        style=hair_style,
        facing=facing,
    )
    acc_pt = _draw_accessory_surface(
        body_surf,
        head_a,
        torso_a,
        kind=accessory,
        primary=pal.accessory_base if pal.accessory_base is not None else pal.shirt_highlight,
        accent=pal.accessory_accent if pal.accessory_accent is not None else pal.shirt_base,
        shade=pal.pants_shade,
        facing=facing,
        alert_indicator=active_pose.alert_indicator,
    )

    if pal.outline is not None:
        body_surf.auto_outline(pal.outline)
    target.surface.blit_layer(body_surf, 0, 0)

    bx = max(0, ix - 7)
    by = max(0, head_a.hair_top[1] - 5)
    bw = min(target.surface.width - bx, 14)
    bh = min(target.surface.height - by, iy - by + 1)

    if emit_metadata:
        target.anchor("foot", ix, iy, kind="ground")
        target.anchor("head_top", head_a.hair_top[0], head_a.hair_top[1], kind="part")
        target.anchor("hand_left", torso_a.hand_left[0], torso_a.hand_left[1], kind="part")
        target.anchor("hand_right", torso_a.hand_right[0], torso_a.hand_right[1], kind="part")
        target.anchor("accessory", acc_pt[0], acc_pt[1], kind="part")
        if bw > 0 and bh > 0:
            target.hitbox("body", bx, by, bw, bh, kind="character")

    return CharacterAnchors(
        foot=(ix, iy),
        waist=legs_a.waist,
        neck=torso_a.neck,
        head_top=head_a.hair_top,
        hand_left=torso_a.hand_left,
        hand_right=torso_a.hand_right,
        accessory=acc_pt,
        bbox=(bx, by, bw, bh),
    )
