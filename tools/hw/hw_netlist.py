#!/usr/bin/env python3
"""Check a board's KiCad connectivity against hardware/<board>/design.toml.

design.toml lists every part with its symbol, footprint, value, LCSC number and a pin to net
map. The check exports the schematic netlist with kicad-cli and fails when a part is missing or
extra, a pin sits on the wrong net, a net has pins the design does not list, or a pin marked nc
is connected. Restrict the check to some sheets with --sheets while a board is being drawn.

Usage: python3 tools/hw/hw_netlist.py owl-mainboard [--sheets power,mcu_usb]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_design(board: str) -> dict:
    return tomllib.loads((ROOT / "hardware" / board / "design.toml").read_text())


def export_netlist(schematic: Path, out: Path) -> Path:
    cmd = ["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml", "-o", str(out), str(schematic)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out


def read_netlist(xml_text: str) -> tuple[dict[str, set[str]], dict[str, dict]]:
    """Return (net name -> {"REF.PIN"}, ref -> component info)."""
    root = ET.fromstring(xml_text)
    comps: dict[str, dict] = {}
    for c in root.iter("comp"):
        lib = c.find("libsource")
        fields = {f.get("name"): (f.text or "").strip() for f in c.iter("field")}
        props = {p.get("name"): p.get("value") or "" for p in c.findall("property")}
        comps[c.get("ref")] = {
            "value": (c.findtext("value") or "").strip(),
            "footprint": (c.findtext("footprint") or "").strip(),
            "symbol": f"{lib.get('lib')}:{lib.get('part')}" if lib is not None else "",
            "fields": fields,
            "sheet": props.get("Sheetname", ""),
            "dnp": "dnp" in props,
        }
    nets: dict[str, set[str]] = {}
    for n in root.iter("net"):
        nets[n.get("name")] = {f"{node.get('ref')}.{node.get('pin')}" for node in n.iter("node")}
    return nets, comps


def expected_pins(design: dict, sheets: set[str] | None) -> tuple[dict[str, str], set[str], dict[str, dict]]:
    """Return ("REF.PIN" -> net, {"REF.PIN" that must stay unconnected}, ref -> part)."""
    pins: dict[str, str] = {}
    nc: set[str] = set()
    parts: dict[str, dict] = {}
    for part in design["part"]:
        if sheets and part["sheet"] not in sheets:
            continue
        parts[part["ref"]] = part
        for pin, net in part.get("pins", {}).items():
            pins[f"{part['ref']}.{pin}"] = net
        for pin in part.get("nc", []):
            nc.add(f"{part['ref']}.{pin}")
    return pins, nc, parts


def check(design: dict, nets: dict[str, set[str]], comps: dict[str, dict], sheets: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    want, nc, parts = expected_pins(design, sheets)
    have = {pin: name for name, members in nets.items() for pin in members}
    in_scope = {ref for ref, c in comps.items() if not sheets or c["sheet"] in sheets}
    for ref in sorted(set(parts) - set(comps)):
        errors.append(f"missing part {ref}")
    for ref in sorted(in_scope - set(parts)):
        errors.append(f"part {ref} is not in design.toml")
    for ref, part in sorted(parts.items()):
        comp = comps.get(ref)
        if comp is None:
            continue
        for key in ("symbol", "footprint", "value"):
            if part[key] != comp[key]:
                errors.append(f"{ref} {key} is {comp[key]!r}, design says {part[key]!r}")
    for pin, net in sorted(want.items()):
        ref = pin.split(".")[0]
        if ref not in comps:
            continue
        actual = have.get(pin)
        if actual != net:
            errors.append(f"{pin} is on {actual!r}, design says {net!r}")
    for pin in sorted(nc):
        if pin.split(".")[0] in comps and len(nets.get(have.get(pin, ""), set())) > 1:
            errors.append(f"{pin} must be unconnected but is on {have[pin]!r}")
    declared = set(want) | nc
    for name, members in sorted(nets.items()):
        for pin in sorted(members):
            if pin.split(".")[0] in parts and pin not in declared:
                errors.append(f"{pin} is on {name!r} but design.toml does not list the pin")
    return errors


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Check KiCad connectivity against design.toml")
    ap.add_argument("board")
    ap.add_argument("--sheets", default="", help="comma-separated sheet names to check")
    args = ap.parse_args(argv)
    design = load_design(args.board)
    schematic = ROOT / "hardware" / args.board / f"{args.board}.kicad_sch"
    sheets = {s for s in args.sheets.split(",") if s} or None
    with tempfile.TemporaryDirectory() as tmp:
        xml_text = export_netlist(schematic, Path(tmp) / "net.xml").read_text()
    nets, comps = read_netlist(xml_text)
    errors = check(design, nets, comps, sheets)
    for e in errors:
        print(e)
    scope = ",".join(sorted(sheets)) if sheets else "all sheets"
    print(f"{args.board}: {len(errors)} connectivity error(s) ({scope})")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
