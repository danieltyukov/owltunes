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


def describe(v: dict, where: str = "") -> str:
    """One line for a KiCad violation: type, description, severity and the first item's position."""
    items = v.get("items") or []
    pos = ""
    if items and "pos" in items[0]:
        pos = f" at ({items[0]['pos']['x']}, {items[0]['pos']['y']}) mm"
    place = f" [{where}]" if where else ""
    return f"{v.get('severity', '?')} {v.get('type', '?')}: {v.get('description', '')}{pos}{place}"


def erc_violations(data: dict) -> list[str]:
    return [describe(v, sheet.get("path", "/")) for sheet in data["sheets"] for v in sheet["violations"]]


def drc_violations(data: dict) -> tuple[list[str], list[str], list[str]]:
    return (
        [describe(v) for v in data["violations"]],
        [describe(v) for v in data["unconnected_items"]],
        [describe(v) for v in data["schematic_parity"]],
    )


def kicad_cli(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(f"kicad-cli failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr}{result.stdout}\n")
        raise SystemExit(2)


def run_erc(schematic: Path, report: Path) -> list[str]:
    kicad_cli(["kicad-cli", "sch", "erc", "--format", "json", "--severity-error", "--severity-warning",
               "-o", str(report), str(schematic)])
    return erc_violations(json.loads(report.read_text()))


def run_drc(pcb: Path, report: Path) -> tuple[list[str], list[str], list[str]]:
    kicad_cli(["kicad-cli", "pcb", "drc", "--format", "json", "--schematic-parity", "--refill-zones",
               "--severity-error", "--severity-warning", "-o", str(report), str(pcb)])
    return drc_violations(json.loads(report.read_text()))


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
        print(f"{name} ERC: {len(erc)} violations")
        for line in erc:
            print(f"  {line}")
        failures += len(erc)
        if board.get("drc", False):
            v, u, p = run_drc(base.with_suffix(".kicad_pcb"), out / "drc.json")
            print(f"{name} DRC: {len(v)} violations, {len(u)} unconnected, {len(p)} parity")
            for line in (*v, *u, *p):
                print(f"  {line}")
            failures += len(v) + len(u) + len(p)
        else:
            print(f"{name} DRC: skipped (drc = false in hardware/boards.toml)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
