#!/usr/bin/env python3
"""Set or check the title blocks of a board's schematics and PCB.

Every KiCad file of a board carries a title block with the board and sheet title, Rev A, the
company, comment 1 (the hardware licence) and the date. The blocks are written by editing the
(title_block ...) S-expression directly, because KiCad has no command line for it. The PCB title
also names the Fabrication Toolkit zip.

Usage: python3 tools/hw/hw_titleblock.py [--check] owl-mainboard
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from hw_netlist import ROOT

BOARDS = {
    "owl-mainboard": ("OwlTunes main board", ["power", "mcu_usb", "periph"]),
    "perch-dock": ("OwlTunes perch board", ["perch", "owl_pads"]),
}
REV = "A"
COMPANY = "OwlTunes"
LICENCE = "CERN-OHL-P-2.0"
DATE = "2026-10-11"

BLOCK_RE = re.compile(r"[ \t]*\(title_block\b.*?\n[ \t]*\)[ \t]*\n", re.S)
BLOCK_ONE_LINE_RE = re.compile(r"[ \t]*\(title_block\b[^\n]*\)[ \t]*\n")
PAPER_RE = re.compile(r"(\(paper\b[^\n]*\)[ \t]*\n)")


def block(title: str) -> str:
    return (
        "\t(title_block\n"
        f'\t\t(title "{title}")\n'
        f'\t\t(date "{DATE}")\n'
        f'\t\t(rev "{REV}")\n'
        f'\t\t(company "{COMPANY}")\n'
        f'\t\t(comment 1 "{LICENCE}")\n'
        "\t)\n"
    )


def strip_block(text: str) -> str:
    text = BLOCK_RE.sub("", text, count=1)
    return BLOCK_ONE_LINE_RE.sub("", text, count=1)


def apply(text: str, title: str) -> str:
    text = strip_block(text)
    new, n = PAPER_RE.subn(lambda m: m.group(1) + block(title), text, count=1)
    if n != 1:
        raise ValueError("no (paper ...) line to anchor the title block")
    return new


def read_block(text: str) -> dict[str, str]:
    m = BLOCK_RE.search(text) or BLOCK_ONE_LINE_RE.search(text)
    if not m:
        return {}
    body = m.group(0)
    out = {k: v for k, v in re.findall(r'\((title|date|rev|company)\s+"([^"]*)"\)', body)}
    c1 = re.search(r'\(comment 1 "([^"]*)"\)', body)
    if c1:
        out["comment1"] = c1.group(1)
    return out


def check_text(text: str, title: str) -> list[str]:
    got = read_block(text)
    want = {"title": title, "date": DATE, "rev": REV, "company": COMPANY, "comment1": LICENCE}
    return [f"title block {k} is {got.get(k)!r}, expected {v!r}" for k, v in want.items() if got.get(k) != v]


def targets(board: str) -> list[tuple[Path, str]]:
    name, sheets = BOARDS[board]
    folder = ROOT / "hardware" / board
    out = [(folder / f"{board}.kicad_sch", name), (folder / f"{board}.kicad_pcb", name)]
    out += [(folder / f"{s}.kicad_sch", f"{name}: {s}") for s in sheets]
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Set or check KiCad title blocks")
    ap.add_argument("board")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    errors = []
    for path, title in targets(args.board):
        text = path.read_text()
        if args.check:
            errors += [f"{path.name}: {e}" for e in check_text(text, title)]
        else:
            path.write_text(apply(text, title))
    if args.check:
        for e in errors:
            print(e)
        print(f"{args.board}: {len(errors)} title block error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
