"""Deterministic part-based animation cycles for modular character prefabs."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from pixelforge.core.prng import mulberry32

CharacterCycleState = Literal["idle", "walk", "typing", "alert"]
CharacterFacing = Literal["front", "iso-se", "iso-sw"]


@dataclass(frozen=True)
class CharacterPose:
    """Deterministic integer pose offsets driving modular character parts."""

    bob_y: int = 0
    head_dy: int = 0
    arm_left_dx: int = 0
    arm_left_dy: int = 0
    arm_right_dx: int = 0
    arm_right_dy: int = 0
    leg_stride: int = 0
    blink: bool = False
    alert_indicator: bool = False
    typing_pulse: bool = False
    seated: bool = False


def _wrap_phase(phase: float) -> float:
    return float(phase) % 1.0


def eval_character_cycle(
    state: CharacterCycleState,
    frame: int = 0,
    frames: int = 4,
    *,
    seed: int = 0,
    seated: bool = False,
) -> CharacterPose:
    """Evaluate a deterministic `CharacterPose` for `(state, frame, frames)`."""
    safe_frames = max(1, int(frames))
    safe_frame = int(frame) % safe_frames
    phase = _wrap_phase(safe_frame / float(safe_frames))

    # Deterministic per-character blink phase offset derived from seed.
    rng = mulberry32(int(seed) ^ 0xA7A7A901)
    blink_slot = int(rng() * safe_frames)

    if state == "idle":
        bob_y = 1 if (safe_frames >= 2 and math.sin(math.tau * phase) < -0.2) else 0
        blink = safe_frames >= 4 and safe_frame == blink_slot
        return CharacterPose(bob_y=bob_y, blink=blink, seated=seated)

    if state == "walk":
        # 4-beat gait: left-step (-1), pass (0), right-step (+1), pass (0)
        step_idx = (safe_frame * 4) // safe_frames if safe_frames >= 4 else safe_frame % 4
        stride_table = (-1, 0, 1, 0)
        bob_table = (-1, 0, -1, 0)
        stride = stride_table[step_idx % 4]
        bob_y = bob_table[step_idx % 4]
        return CharacterPose(
            bob_y=bob_y,
            arm_left_dy=stride,
            arm_right_dy=-stride,
            leg_stride=stride,
            seated=False,
        )

    if state == "typing":
        # Alternating finger/hand taps with subtle rhythmic head nod.
        left_tap = -1 if safe_frame % 2 == 0 else 0
        right_tap = 0 if safe_frame % 2 == 0 else -1
        head_dy = 1 if (safe_frames >= 4 and safe_frame % 4 >= 2) else 0
        return CharacterPose(
            bob_y=0,
            head_dy=head_dy,
            arm_left_dx=1,
            arm_left_dy=left_tap,
            arm_right_dx=-1,
            arm_right_dy=right_tap,
            typing_pulse=safe_frame % 2 == 0,
            seated=seated,
        )

    if state == "alert":
        perked = safe_frame % 2 == 0
        return CharacterPose(
            bob_y=-1 if perked else 0,
            head_dy=0,
            arm_left_dy=-1,
            arm_right_dy=-2 if perked else -1,
            alert_indicator=perked or safe_frames == 1,
            seated=seated,
        )

    msg = f"Unsupported character cycle state: {state!r}"
    raise ValueError(msg)
