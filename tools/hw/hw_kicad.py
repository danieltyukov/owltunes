#!/usr/bin/env python3
"""Run KiCad ERC and DRC (kicad-cli 10.0.6) for the boards listed in hardware/boards.toml.

Every board must have zero ERC violations (errors and warnings). Boards with drc = true must
also have zero DRC violations, zero unconnected items and zero schematic parity issues. JSON
reports go to build/hardware/<board>/.

Usage: python3 tools/hw/hw_kicad.py [board ...]
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def boards() -> list[dict]:
    return tomllib.loads((ROOT / "hardware" / "boards.toml").read_text())["board"]


def run_erc(schematic: Path, report: Path) -> int:
    cmd = ["kicad-cli", "sch", "erc", "--format", "json", "--severity-error", "--severity-warning",
           "-o", str(report), str(schematic)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    data = json.loads(report.read_text())
    return sum(len(sheet["violations"]) for sheet in data["sheets"])


def run_drc(pcb: Path, report: Path) -> tuple[int, int, int]:
    cmd = ["kicad-cli", "pcb", "drc", "--format", "json", "--schematic-parity", "--refill-zones",
           "--severity-error", "--severity-warning", "-o", str(report), str(pcb)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    data = json.loads(report.read_text())
    return len(data["violations"]), len(data["unconnected_items"]), len(data["schematic_parity"])


def main(argv: list[str]) -> int:
    failures = 0
    for board in boards():
        name = board["name"]
        if argv and name not in argv:
            continue
        out = ROOT / "build" / "hardware" / name
        out.mkdir(parents=True, exist_ok=True)
        base = ROOT / "hardware" / name / name
        erc = run_erc(base.with_suffix(".kicad_sch"), out / "erc.json")
        print(f"{name} ERC: {erc} violations")
        failures += erc
        if board.get("drc", False):
            v, u, p = run_drc(base.with_suffix(".kicad_pcb"), out / "drc.json")
            print(f"{name} DRC: {v} violations, {u} unconnected, {p} parity")
            failures += v + u + p
        else:
            print(f"{name} DRC: skipped (drc = false in hardware/boards.toml)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
