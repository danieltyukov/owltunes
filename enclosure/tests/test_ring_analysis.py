"""Ring log analysis on synthetic data."""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ring_analysis as A  # noqa: E402


def synthetic(magnets: int, amp_y: float, amp_z: float, steps: int = 2000) -> list[tuple[float, float, float]]:
    rest = [(0.5, amp_y * 0.0, amp_z) for _ in range(A.STILL_SAMPLES)]
    turn = []
    for i in range(steps + 1):
        theta = 2 * math.pi * i / steps * magnets / 2
        turn.append((0.5, amp_y * math.sin(theta), amp_z * math.cos(theta)))
    return rest + turn


def test_counts_pole_pairs_for_24_magnets():
    r = A.analyse(synthetic(24, 30.0, 45.0), magnets=24)
    assert r.electrical_cycles == pytest.approx(12.0, abs=0.05)
    assert r.peak_mt[2] == pytest.approx(45.0, abs=0.1)
    assert r.noise_mt == pytest.approx(0.0, abs=1e-9)
    assert r.recommendation() == "TMAG5273A2 with the 133 mT range"


def test_strong_field_needs_the_wide_range_or_more_gap():
    assert A.analyse(synthetic(32, 100.0, 150.0), magnets=32).recommendation() == (
        "TMAG5273A2 with the 266 mT range"
    )
    assert A.analyse(synthetic(32, 200.0, 300.0), magnets=32).recommendation() == (
        "field too strong: increase the gap"
    )


def test_wrong_polarity_order_is_reported():
    r = A.analyse(synthetic(24, 30.0, 45.0), magnets=32)
    assert r.recommendation() == "cycle count does not match the magnet count: check polarity order"


def test_parses_sparkfun_text_and_csv():
    lines = [
        "TMAG5273 Example 1",
        "X: 1.25 mT   Y: -3.50 mT   Z: 44.10 mT",
        "120,0.5,-2.0,40.0",
        "t_ms,bx_mT,by_mT,bz_mT",
    ]
    assert A.parse(lines) == [(1.25, -3.5, 44.1), (0.5, -2.0, 40.0)]


def test_too_short_log_is_rejected():
    with pytest.raises(ValueError):
        A.analyse([(0.0, 0.0, 1.0)] * 5, magnets=24)


GOOD_24 = "TMAG5273A2 with the 133 mT range"


def noisy(samples, sigma, seed=1, bias=(0.0, 0.0, 0.0)):
    rng = random.Random(seed)
    return [tuple(v + b + rng.gauss(0.0, sigma) for v, b in zip(s, bias)) for s in samples]


@pytest.mark.parametrize("sigma", [2.0, 8.0])
def test_gaussian_noise_keeps_the_verdict_and_reports_the_noise(sigma):
    r = A.analyse(noisy(synthetic(24, 30.0, 45.0), sigma), magnets=24)
    assert r.recommendation() == GOOD_24
    assert r.electrical_cycles == pytest.approx(12.0, abs=0.25)
    assert r.noise_mt == pytest.approx(sigma, rel=0.35)
    assert r.peak_mt[2] < 45.0 + 3 * sigma


def test_dc_bias_does_not_change_the_cycle_count():
    r = A.analyse(noisy(synthetic(24, 30.0, 45.0), 2.0, bias=(1.0, 14.0, -11.0)), magnets=24)
    assert r.recommendation() == GOOD_24
    assert r.electrical_cycles == pytest.approx(12.0, abs=0.25)


def test_single_glitch_and_nan_are_rejected():
    data = noisy(synthetic(24, 30.0, 45.0), 2.0)
    data[700] = (900.0, 900.0, 900.0)
    data[1200] = (math.nan, 1.0, 2.0)
    r = A.analyse(data, magnets=24)
    assert r.rejected == 2
    assert max(r.peak_mt) < 60.0
    assert r.recommendation() == GOOD_24


@pytest.mark.parametrize("factor", [0.95, 1.05])
@pytest.mark.parametrize("magnets", [24, 32])
def test_over_and_under_rotation_is_reported_as_turn_length(factor, magnets):
    data = noisy(synthetic(magnets, 30.0, 45.0, steps=2000), 2.0)
    kept = A.STILL_SAMPLES + int(2000 * factor) if factor < 1 else None
    if factor < 1:
        data = data[:kept]
    else:
        extra = synthetic(magnets, 30.0, 45.0, steps=2000)[A.STILL_SAMPLES + 1 : A.STILL_SAMPLES + 101]
        data = data + noisy(extra, 2.0, seed=2)
    r = A.analyse(data, magnets=magnets)
    assert r.recommendation() == A.VERDICT_TURN


def test_wrong_magnet_count_is_still_polarity_even_with_noise():
    r = A.analyse(noisy(synthetic(24, 30.0, 45.0), 8.0), magnets=32)
    assert r.recommendation() == A.VERDICT_POLARITY
