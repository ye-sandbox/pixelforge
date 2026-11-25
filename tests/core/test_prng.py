"""Unit tests for deterministic uint32 PRNGs and coordinate hashes."""

from __future__ import annotations

from pixelforge.core.prng import hashf, mulberry32, xorshift32


def test_mulberry32_determinism_and_range() -> None:
    """Ensure identical seeds produce identical sequences inside [0, 1)."""
    rng_a = mulberry32(42)
    rng_b = mulberry32(42)
    rng_c = mulberry32(43)

    seq_a = [rng_a() for _ in range(32)]
    seq_b = [rng_b() for _ in range(32)]
    seq_c = [rng_c() for _ in range(32)]

    assert seq_a == seq_b
    assert seq_a != seq_c
    assert all(0.0 <= value < 1.0 for value in seq_a)


def test_xorshift32_zero_seed_guard_and_determinism() -> None:
    """Ensure xorshift32 never locks onto 0 when seeded with 0."""
    rng_zero = xorshift32(0)
    rng_zero_2 = xorshift32(0)
    values = [rng_zero() for _ in range(16)]
    values_2 = [rng_zero_2() for _ in range(16)]

    assert values == values_2
    assert any(v > 0.0 for v in values)
    assert all(0.0 <= v < 1.0 for v in values)


def test_hashf_determinism_and_coordinate_sensitivity() -> None:
    """Ensure hashf is stateless, repeatable, and sensitive to x/y/seed."""
    h1 = hashf(10, 20, 510)
    h2 = hashf(10, 20, 510)
    assert h1 == h2
    assert 0.0 <= h1 < 1.0

    samples = {hashf(x, y, 7) for x in range(-4, 4) for y in range(-4, 4)}
    assert len(samples) == 64
    assert all(0.0 <= val < 1.0 for val in samples)
