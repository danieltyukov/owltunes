"""Analyse TMAG5273 logs from the ring test jig.

Input: the serial output of SparkFun's TMAG5273 Arduino library Example1 ("X: 1.23 mT ...")
or CSV lines "t_ms,bx_mT,by_mT,bz_mT". On the jig the board's X axis is radial, Y is tangential
and Z is axial (towards the magnets).

Usage: uv run --project enclosure python enclosure/ring_analysis.py LOG [--magnets 24]
Start the log with the ring still for at least 2 seconds, then turn it exactly one revolution
(index notch from the 0 tick back to the 0 tick). Licence: MIT (LICENSE).
"""

from __future__ import annotations

import argparse
import math
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

TEXT_RE = re.compile(r"X:\s*(-?[\d.]+).*?Y:\s*(-?[\d.]+).*?Z:\s*(-?[\d.]+)")
RANGES_MT = {"A1 40": 40.0, "A1 80": 80.0, "A2 133": 133.0, "A2 266": 266.0}
STILL_SAMPLES = 20  # minimum rest window; the real window is found from the data
PEAK_PERCENTILE = 98.0  # peaks use a high percentile, so a stray sample cannot set the range
GLITCH_WINDOW = 5  # Hampel filter: compare each sample with the median of its neighbours
GLITCH_SIGMAS = 10.0  # of the residual MAD, which understates the noise by about half
GLITCH_FLOOR_MT = 5.0  # never reject a deviation smaller than this
TURN_TOLERANCE = 0.5  # cycles of difference allowed to the expected count
TURN_REL_LIMIT = 0.10  # a miss this small (relative) points at the turn, not the polarity order
CLOSURE_LIMIT = 0.10  # cycles away from a whole number mean the log did not close one revolution

VERDICT_POLARITY = "cycle count does not match the magnet count: check polarity order"
VERDICT_TURN = "turn length does not match one revolution: repeat the log with exactly one turn"


@dataclass
class Report:
    samples: int
    peak_mt: tuple[float, float, float]
    noise_mt: float
    electrical_cycles: float
    expected_cycles: float
    axis_ratio: float
    fits: dict[str, bool]
    rest_samples: int = STILL_SAMPLES
    rejected: int = 0
    closed: bool = True

    def recommendation(self) -> str:
        peak = max(self.peak_mt)
        miss = abs(self.electrical_cycles - self.expected_cycles)
        if miss > TURN_TOLERANCE:
            if miss / self.expected_cycles <= TURN_REL_LIMIT and not self.closed:
                return VERDICT_TURN
            return VERDICT_POLARITY
        for name in ("A2 133", "A2 266"):
            if self.fits[name] and peak > 10.0:
                return f"TMAG5273{name.split()[0]} with the {name.split()[1]} mT range"
        if peak <= 10.0:
            return "field too weak: reduce the gap"
        return "field too strong: increase the gap"


def parse(lines: list[str]) -> list[tuple[float, float, float]]:
    out = []
    for line in lines:
        m = TEXT_RE.search(line)
        if m:
            out.append(tuple(float(v) for v in m.groups()))
            continue
        parts = line.strip().split(",")
        if len(parts) == 4:
            try:
                out.append(tuple(float(v) for v in parts[1:]))
            except ValueError:
                continue
    return out


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * pct / 100.0
    lo = math.floor(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def median(values: list[float]) -> float:
    return percentile(values, 50.0)


def mad_sigma(values: list[float]) -> float:
    centre = median(values)
    return 1.4826 * median([abs(v - centre) for v in values])


def smooth(values: list[float], width: int = 9) -> list[float]:
    """Centred moving average (shorter at the ends); keeps the phase, cuts the noise."""
    half = width // 2
    return [
        sum(values[max(0, i - half) : i + half + 1]) / len(values[max(0, i - half) : i + half + 1])
        for i in range(len(values))
    ]


def clean(samples: list[tuple[float, float, float]]) -> tuple[list[tuple[float, float, float]], int]:
    """Drop non-finite samples and isolated glitches. Returns the kept samples and how many went."""
    finite = [s for s in samples if all(math.isfinite(v) for v in s)]
    drop = [False] * len(finite)
    half = GLITCH_WINDOW // 2
    for axis in range(3):
        column = [s[axis] for s in finite]
        residual = [
            column[i] - median(column[max(0, i - half) : i + half + 1]) for i in range(len(column))
        ]
        limit = max(GLITCH_SIGMAS * mad_sigma(residual), GLITCH_FLOOR_MT)
        for i, r in enumerate(residual):
            if abs(r) > limit:
                drop[i] = True
    kept = [s for s, bad in zip(finite, drop) if not bad]
    return kept, len(samples) - len(kept)


def rest_window(samples: list[tuple[float, float, float]]) -> int:
    """Length of the leading still part: a 10 sample moving mean stays near the starting level."""
    base = [median([s[a] for s in samples[:STILL_SAMPLES]]) for a in range(3)]
    spread = [mad_sigma([s[a] for s in samples[:STILL_SAMPLES]]) for a in range(3)]
    avg = 10
    limit = [max(5.0 * sd / math.sqrt(avg), 0.5) for sd in spread]
    for end in range(STILL_SAMPLES, len(samples) - avg):
        window = samples[end : end + avg]
        mean = [sum(s[a] for s in window) / avg for a in range(3)]
        if any(abs(mean[a] - base[a]) > limit[a] for a in range(3)):
            return end
    return STILL_SAMPLES


def analyse(samples: list[tuple[float, float, float]], magnets: int) -> Report:
    kept, rejected = clean(samples)
    if len(kept) < STILL_SAMPLES + 10:
        raise ValueError(f"need at least {STILL_SAMPLES + 10} usable samples, got {len(kept)}")
    rest = rest_window(kept)
    noise = statistics.pstdev([math.dist((0, 0, 0), s) for s in kept[:rest]])
    peaks = tuple(percentile([abs(s[i]) for s in kept], PEAK_PERCENTILE) for i in range(3))
    turn = kept[rest:] if len(kept) - rest >= 10 else kept[STILL_SAMPLES:]
    mid = [
        0.5 * (percentile([s[a] for s in turn], 100 - PEAK_PERCENTILE) + percentile([s[a] for s in turn], PEAK_PERCENTILE))
        for a in range(3)
    ]
    ys = smooth([s[1] - mid[1] for s in kept])
    zs = smooth([s[2] - mid[2] for s in kept])
    phase = [math.atan2(z, y) for y, z in zip(ys, zs)]
    total = 0.0
    for a, b in zip(phase, phase[1:]):
        d = b - a
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        total += d
    cycles = abs(total) / (2 * math.pi)
    ratio = peaks[2] / peaks[1] if peaks[1] > 0 else float("inf")
    fits = {name: max(peaks) < 0.9 * limit for name, limit in RANGES_MT.items()}
    closed = abs(cycles - round(cycles)) <= CLOSURE_LIMIT
    return Report(len(kept), peaks, noise, cycles, magnets / 2, ratio, fits, rest, rejected, closed)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log", type=Path)
    ap.add_argument("--magnets", type=int, default=24)
    args = ap.parse_args(argv)
    report = analyse(parse(args.log.read_text().splitlines()), args.magnets)
    print(f"samples            {report.samples} ({report.rejected} rejected, rest window {report.rest_samples})")
    print(f"peak X Y Z (mT)    {report.peak_mt[0]:.1f} {report.peak_mt[1]:.1f} {report.peak_mt[2]:.1f}")
    print(f"noise at rest (mT) {report.noise_mt:.3f}")
    print(f"electrical cycles  {report.electrical_cycles:.2f} (expected {report.expected_cycles:.1f})")
    print(f"Z to Y amplitude   {report.axis_ratio:.2f}")
    for name, ok in report.fits.items():
        print(f"fits {name:7s} mT  {'yes' if ok else 'no'}")
    print(f"recommendation     {report.recommendation()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
