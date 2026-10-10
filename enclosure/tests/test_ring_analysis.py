"""Ring log analysis on synthetic data."""

from __future__ import annotations

import math
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
    assert r.peak_mt[2] == pytest.approx(45.0, abs=0.01)
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
