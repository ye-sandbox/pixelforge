"""Deterministic 32-bit PRNGs and coordinate hashes for pixelforge v2."""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

_UINT32_MASK: Final[int] = 0xFFFFFFFF
_UINT32_RANGE: Final[float] = 4294967296.0


def mulberry32(seed: int) -> Callable[[], float]:
    """Return a deterministic 32-bit mulberry32 generator yielding floats in [0, 1)."""
    state = int(seed) & _UINT32_MASK

    def _next() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & _UINT32_MASK
        t = ((state ^ (state >> 15)) * (1 | state)) & _UINT32_MASK
        t = (((t + ((t ^ (t >> 7)) * (61 | t))) & _UINT32_MASK) ^ t) & _UINT32_MASK
        return ((t ^ (t >> 14)) & _UINT32_MASK) / _UINT32_RANGE

    return _next


def xorshift32(seed: int) -> Callable[[], float]:
    """Return a deterministic 32-bit xorshift generator yielding floats in [0, 1)."""
    # INVARIANT: xorshift32 degenerates to an all-zero sequence if state == 0.
    state = (int(seed) & _UINT32_MASK) or 0x9E3779B9

    def _next() -> float:
        nonlocal state
        state = (state ^ ((state << 13) & _UINT32_MASK)) & _UINT32_MASK
        state = (state ^ (state >> 17)) & _UINT32_MASK
        state = (state ^ ((state << 5) & _UINT32_MASK)) & _UINT32_MASK
        return state / _UINT32_RANGE

    return _next


def hashf(x: int, y: int, seed: int = 0) -> float:
    """Return a stateless deterministic float in [0, 1) from integer (x, y, seed)."""
    ix = int(x) & _UINT32_MASK
    iy = int(y) & _UINT32_MASK
    iz = int(seed) & _UINT32_MASK
    h = ((ix * 374761393) + (iy * 668265263) + (iz * 1442695041)) & _UINT32_MASK
    h = ((h ^ (h >> 13)) * 1274126177) & _UINT32_MASK
    return ((h ^ (h >> 16)) & _UINT32_MASK) / _UINT32_RANGE
