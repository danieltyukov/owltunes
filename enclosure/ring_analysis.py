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
STILL_SAMPLES = 20


@dataclass
class Report:
    samples: int
    peak_mt: tuple[float, float, float]
    noise_mt: float
    electrical_cycles: float
    expected_cycles: float
    axis_ratio: float
    fits: dict[str, bool]

    def recommendation(self) -> str:
        peak = max(self.peak_mt)
        if abs(self.electrical_cycles - self.expected_cycles) > 0.5:
            return "cycle count does not match the magnet count: check polarity order"
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


def analyse(samples: list[tuple[float, float, float]], magnets: int) -> Report:
    if len(samples) < STILL_SAMPLES + 10:
        raise ValueError(f"need at least {STILL_SAMPLES + 10} samples, got {len(samples)}")
    still = [math.dist((0, 0, 0), s) for s in samples[:STILL_SAMPLES]]
    noise = statistics.pstdev(still)
    peaks = tuple(max(abs(s[i]) for s in samples) for i in range(3))
    phase = [math.atan2(s[2], s[1]) for s in samples]
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
    return Report(len(samples), peaks, noise, cycles, magnets / 2, ratio, fits)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log", type=Path)
    ap.add_argument("--magnets", type=int, default=24)
    args = ap.parse_args(argv)
    report = analyse(parse(args.log.read_text().splitlines()), args.magnets)
    print(f"samples            {report.samples}")
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
