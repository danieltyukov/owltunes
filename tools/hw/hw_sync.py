#!/usr/bin/env python3
"""Bring a board's schematic into its PCB (the scripted form of KiCad's Update PCB from Schematic).

Exports the schematic netlist with kicad-cli, then adds every missing footprint from its
library, replaces footprints whose library copy changed (pads, courtyard, rule areas or
drawings), removes footprints the schematic no longer has, and sets each footprint's value,
fields, symbol path, BOM and position-file attributes and pad nets. Footprints that already
exist keep their position, side, rotation and lock, so the tool can run again after a
schematic change without undoing placement or the contract.

Usage: python3 tools/hw/hw_sync.py owl-mainboard
Needs kicad-cli 10.0.6 and KiCad's pcbnew Python module.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

from hw_netlist import ROOT

STOCK = Path("/usr/share/kicad/footprints")
# The Fabrication Toolkit reads its FT offset fields from the footprint.
FIELDS = ("LCSC Part #", "MPN", "Manufacturer", "FT Rotation Offset", "FT Position Offset")


def parse(text: str) -> list:
    """Parse an S-expression into nested lists of strings."""
    stack: list[list] = [[]]
    for tok in re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok[1:-1].replace('\\"', '"') if tok.startswith('"') else tok)
    return stack[0][0]


def child(node: list, name: str):
    return next((c for c in node[1:] if isinstance(c, list) and c and c[0] == name), None)


def children(node: list, name: str) -> list:
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == name]


def value(node: list, name: str, default: str = "") -> str:
    c = child(node, name)
    return c[1] if c is not None and len(c) > 1 else default


def read(board_name: str) -> tuple[dict[str, dict], dict[tuple[str, str], str]]:
    """Return (ref -> component, (ref, pin) -> net name) from the schematic netlist."""
    sch = ROOT / "hardware" / board_name / f"{board_name}.kicad_sch"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "board.net"
        cmd = ["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(sch)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        tree = parse(out.read_text())
    comps = {}
    for c in children(child(tree, "components"), "comp"):
        ref = value(c, "ref")
        fields = {value(f, "name"): (f[2] if len(f) > 2 else "") for f in children(child(c, "fields") or ["fields"], "field")}
        props = {value(p, "name"): value(p, "value") for p in children(c, "property")}
        sheet = child(c, "sheetpath")
        comps[ref] = {
            "value": value(c, "value"),
            "footprint": value(c, "footprint"),
            "fields": fields,
            "props": props,
            "path": value(sheet, "tstamps") + value(c, "tstamps"),
            "sheetname": value(sheet, "names"),
            "sheetfile": props.get("Sheetfile", ""),
        }
    pins = {}
    for n in children(child(tree, "nets"), "net"):
        for node in children(n, "node"):
            pins[(value(node, "ref"), value(node, "pin"))] = value(n, "name")
    return comps, pins


def library(nick: str) -> Path:
    if nick == "owltunes":
        return ROOT / "hardware" / "lib" / "owltunes.pretty"
    return STOCK / f"{nick}.pretty"


def signature(fp) -> tuple:
    """What a library edit changes, in a form that moving, turning or flipping does not: pads,
    courtyard area, rule-area outlines and the number of drawings."""
    fp.BuildCourtyardCaches()
    crt = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    zones = sorted(round(z.Outline().Area() / 1e12, 2) for z in fp.Zones())
    return (sorted(p.GetNumber() for p in fp.Pads()), round(crt.Area() / 1e12, 2), zones, len(fp.GraphicalItems()))


def sync(board_name: str) -> int:
    folder = ROOT / "hardware" / board_name
    path = folder / f"{board_name}.kicad_pcb"
    comps, pins = read(board_name)
    board = pcbnew.LoadBoard(str(path))
    have = {fp.GetReference(): fp for fp in board.GetFootprints()}
    added = removed = 0
    # Delete, not Remove: Remove hands the C++ footprint to its Python wrapper, and once that
    # wrapper is freed pcbnew's bindings return untyped SwigPyObjects for every board (KiCad 10.0.6).
    for ref, fp in have.items():
        if ref not in comps:
            board.Delete(fp)
            removed += 1
    nets: dict[str, pcbnew.NETINFO_ITEM] = {}
    for name in sorted(set(pins.values())):
        net = board.FindNet(name)
        if net is None:
            net = pcbnew.NETINFO_ITEM(board, name)
            board.Add(net)
        nets[name] = net
    refreshed = 0
    for ref, c in sorted(comps.items()):
        fp = have.get(ref)
        nick, name = c["footprint"].split(":", 1)
        lib_fp = pcbnew.FootprintLoad(str(library(nick)), name)
        if lib_fp is None:
            print(f"{ref}: footprint {c['footprint']} not found")
            return 1
        stale = fp is not None and fp.GetFPIDAsString() == c["footprint"] and signature(fp) != signature(lib_fp)
        refreshed += stale
        if fp is not None and (fp.GetFPIDAsString() != c["footprint"] or stale):
            pos, rot, back, locked = fp.GetPosition(), fp.GetOrientationDegrees(), fp.IsFlipped(), fp.IsLocked()
            board.Delete(fp)
            fp = None
        else:
            pos = rot = back = locked = None
        if fp is None:
            fp = lib_fp
            fp.SetFPIDAsString(c["footprint"])
            board.Add(fp)
            added += pos is None
            if pos is not None:
                if back:
                    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
                fp.SetPosition(pos)
                fp.SetOrientationDegrees(rot)
                fp.SetLocked(locked)
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        for name in FIELDS:
            if name in c["fields"]:
                fp.SetField(name, c["fields"][name])
        fp.GetField(pcbnew.FIELD_T_DATASHEET).SetText(c["fields"].get("Datasheet", ""))
        fp.GetField(pcbnew.FIELD_T_DESCRIPTION).SetText(c["fields"].get("Description", ""))
        for name in FIELDS:
            if fp.HasField(name):
                fp.GetField(name).SetVisible(False)
        fp.SetPath(pcbnew.KIID_PATH(c["path"]))
        fp.SetSheetname(c["sheetname"])
        fp.SetSheetfile(c["sheetfile"])
        attrs = fp.GetAttributes() & ~(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_DNP)
        if "exclude_from_bom" in c["props"]:
            attrs |= pcbnew.FP_EXCLUDE_FROM_BOM
        if "exclude_from_pos_files" in c["props"]:
            attrs |= pcbnew.FP_EXCLUDE_FROM_POS_FILES
        if "dnp" in c["props"]:
            attrs |= pcbnew.FP_DNP
        fp.SetAttributes(attrs)
        for pad in fp.Pads():
            net = pins.get((ref, pad.GetNumber()))
            pad.SetNet(nets[net] if net else board.GetNetInfo().OrphanedItem())
    board.BuildConnectivity()
    pcbnew.SaveBoard(str(path), board)
    print(f"{board_name}: {len(comps)} footprints ({added} added, {removed} removed, {refreshed} updated from the library), {len(nets)} nets")
    return 0


if __name__ == "__main__":
    sys.exit(sync(sys.argv[1]))
