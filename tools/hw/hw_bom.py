#!/usr/bin/env python3
"""Check the sourcing fields of every part against hardware/<board>/design.toml.

Each part that is assembled (assembled = true, the default) must carry the fields
"LCSC Part #" and "MPN" in the schematic, equal to design.toml, and the LCSC number must look
like C followed by digits. Test points, mounting holes and fiducials set assembled = false.

Usage: python3 tools/hw/hw_bom.py owl-mainboard [--sheets power,mcu_usb]
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

from hw_netlist import ROOT, export_netlist, load_design, read_netlist

LCSC_RE = re.compile(r"^C\d+$")


def check(design: dict, comps: dict[str, dict], sheets: set[str] | None = None) -> list[str]:
    errors = []
    for part in design["part"]:
        if not part.get("assembled", True) or (sheets and part["sheet"] not in sheets):
            continue
        ref = part["ref"]
        if not LCSC_RE.match(part.get("lcsc", "")):
            errors.append(f"{ref}: design.toml lcsc {part.get('lcsc')!r} is not an LCSC number")
        comp = comps.get(ref)
        if comp is None:
            errors.append(f"{ref}: not in the schematic")
            continue
        for field, key in (("LCSC Part #", "lcsc"), ("MPN", "mpn")):
            if comp["fields"].get(field, "") != part.get(key, ""):
                errors.append(f"{ref}: field {field!r} is {comp['fields'].get(field)!r}, design says {part.get(key)!r}")
    return errors


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Check LCSC and MPN fields against design.toml")
    ap.add_argument("board")
    ap.add_argument("--sheets", default="")
    args = ap.parse_args(argv)
    board = args.board
    sheets = {s for s in args.sheets.split(",") if s} or None
    with tempfile.TemporaryDirectory() as tmp:
        xml_text = export_netlist(ROOT / "hardware" / board / f"{board}.kicad_sch", Path(tmp) / "n.xml").read_text()
    _, comps = read_netlist(xml_text)
    errors = check(load_design(board), comps, sheets)
    for e in errors:
        print(e)
    print(f"{board}: {len(errors)} sourcing error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
