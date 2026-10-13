#!/usr/bin/env python3
"""Draw each board's own silkscreen (Task 10 Step 4): name, owner, licence, date, the JLC
order-number mark, connector and test pad labels and the pin 1 marks the footprints lack.

Each board's marks are data: (text, side, x, y, height) for a text, or ("dot", side, x, y,
radius) for a filled dot; side is "F" or "B". Coordinates are the owl frame on both boards:
x = KiCad x - 100, y = 100 - KiCad y (on the main board, x right as seen from the front, y up,
origin at the display centre). Texts are centred on (x, y) with a 0.15 mm stroke; back side
texts are mirrored so they read from the back. Everything goes into a KiCad group named
"hw_silk", and a run first deletes what that group holds, so the marks can be moved and drawn
again. tools/hw/hw_place.py keeps the reference designators clear of them. On a board with an
enclosure contract (hardware/<board>/mech/contract.json) a run fails, and saves nothing, if a
mark's strokes reach into a boss keep-out circle on its side (the back cover's bosses on the back,
the body's on the front), where the boss would hide it.

Usage: python3 tools/hw/hw_silk.py owl-mainboard|perch-dock
Needs KiCad's pcbnew Python module.
"""

from __future__ import annotations

import json
import sys

import pcbnew

from hw_contract import keepout_poly, overlap_mm2
from hw_netlist import ROOT
from hw_titleblock import BOARDS, LICENCE

GROUP = "hw_silk"
STROKE = 0.15  # JLC minimum silkscreen line width
DOT_LINE = 0.1  # outline width of a filled dot

MARKS = {
    "owl-mainboard": [
        # Owner, name, licence and the title block's date, on the back in the left strip between
        # the H2 and H3 bosses, above U302: outside the cell, so they stay visible with it fitted.
        # The H2 cover boss (r 3 at (-19, 9)) reaches down to y 6, so the owner mark sits left of
        # it and the board name, the widest line, below it.
        ("Tyukov Inc", "B", -26.0, 7.0, 1.0),
        ("OwlTunes rev A", "B", -22.5, 5.0, 1.0),
        (LICENCE, "B", -22.5, 3.35, 0.8),
        (BOARDS["owl-mainboard"][2], "B", -22.5, 2.15, 0.8),
        # JLC prints the order number here (ordering.md: "Specify a location"); under the cell.
        ("JLCJLCJLCJLC", "B", -6.0, -18.0, 0.8),
        # Connectors and test pads.
        ("DOCK", "B", 14.0, -31.825, 0.8),
        ("EXP", "B", -24.0, -13.6, 0.8),
        ("LRA", "B", 28.3, -20.0, 0.8),
        ("RESET", "B", 18.8, 25.3, 0.8),
        ("BOOT", "B", -16.0, 22.5, 0.8),
        ("TX", "B", -25.7, 22.0, 0.8),
        ("RX", "B", -25.7, 19.0, 0.8),
        # Power test pads for bring-up (their references are hidden): above TP101 (VIN_CHG), TP102
        # (VSYS) and TP103 (VBAT), below TP106 (GND), each nearer its own pad than any other.
        ("VIN", "B", 29.2, -4.1, 0.8),
        ("VSYS", "B", 28.9, 4.4, 0.8),
        ("VBAT", "B", 20.6, 4.8, 0.8),
        ("GND", "B", 29.2, -9.7, 0.8),
        # U201's own pin 1 triangle sits at the module corner over the antenna notch, so the
        # board edge cuts it; this dot beside pin 1 (8.75, 35.61) marks it on the board.
        ("dot", "B", 10.1, 35.85, 0.2),
        # J301 (front): pin 1 (its footprint also has a dot there) and pin 31 at the far end.
        ("1", "F", 4.5, 15.45, 0.8),
        ("31", "F", -4.5, 15.45, 0.8),
    ],
    "perch-dock": [
        # Owner mark on the top, below the pogo pins and clear of the snap-off neck.
        ("Tyukov Inc", "F", -2.0, -6.2, 1.0),
        # Dock-pad section: which way round it goes into the owl (the cover's key takes the notch
        # at the DET end), between the pad rows' tracks and vias.
        ("J2 towards J303 >", "F", -2.5, -17.6, 0.8),
    ],
}


def pt(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(100 + x), pcbnew.FromMM(100 - y))


def remove_old(board: pcbnew.BOARD) -> None:
    """Delete everything in the "hw_silk" group. Delete, not Remove: Remove hands the C++ item to
    its Python wrapper, and once that wrapper is freed the board's lists come back as untyped
    SwigPyObjects (KiCad 10.0.6)."""
    for group in [g for g in board.Groups() if g.GetName() == GROUP]:
        for item in list(group.GetItems()):
            board.Delete(item)
        board.Delete(group)


def draw(board: pcbnew.BOARD, marks: list) -> int:
    remove_old(board)
    group = pcbnew.PCB_GROUP(board)
    group.SetName(GROUP)
    board.Add(group)
    for what, side, x, y, size in marks:
        layer = pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS
        if what == "dot":
            item = pcbnew.PCB_SHAPE(board)
            item.SetShape(pcbnew.SHAPE_T_CIRCLE)
            item.SetFilled(True)
            item.SetWidth(pcbnew.FromMM(DOT_LINE))
            item.SetCenter(pt(x, y))
            item.SetEnd(pt(x + size, y))
        else:
            item = pcbnew.PCB_TEXT(board)
            item.SetText(what)
            item.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
            item.SetTextThickness(pcbnew.FromMM(STROKE))
            item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
            item.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
            item.SetMirrored(side == "B")
            item.SetTextPos(pt(x, y))
        item.SetLayer(layer)
        item.SetLocked(True)
        board.Add(item)
        group.AddItem(item)
    return len(marks)


def boss_clashes(board: pcbnew.BOARD, contract: dict) -> list[str]:
    """The drawn marks whose strokes overlap a boss keep-out circle of the contract on their side."""
    errors = []
    marks = [item for g in board.Groups() if g.GetName() == GROUP for item in g.GetItems()]
    for k in contract.get("keepouts", []):
        if k["kind"] != "circle":
            continue
        layer = pcbnew.B_SilkS if k["side"] == "back" else pcbnew.F_SilkS
        area = keepout_poly(k)
        for item in marks:
            if item.GetLayer() != layer:
                continue
            strokes = pcbnew.SHAPE_POLY_SET()
            item.TransformShapeToPolygon(strokes, layer, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_OUTSIDE)
            if overlap_mm2(strokes, area) > 0:
                name = item.GetText() if isinstance(item, pcbnew.PCB_TEXT) else "dot"
                errors.append(f"{name} on {board.GetLayerName(layer)} reaches into the {k['name']} keep-out "
                              f"(r {k['r']} at owl ({k['x'] - 100:.2f}, {100 - k['y']:.2f}))")
    return errors


def silk(board_name: str) -> int:
    if board_name not in MARKS:
        print(f"no marks for {board_name}")
        return 1
    folder = ROOT / "hardware" / board_name
    path = folder / f"{board_name}.kicad_pcb"
    board = pcbnew.LoadBoard(str(path))
    n = draw(board, MARKS[board_name])
    contract = folder / "mech" / "contract.json"
    if contract.exists():
        errors = boss_clashes(board, json.loads(contract.read_text()))
        if errors:
            print("\n".join(errors))
            print(f"{board_name}: {len(errors)} mark(s) under a boss, nothing saved")
            return 1
    pcbnew.SaveBoard(str(path), board)
    print(f"{board_name}: {n} silkscreen marks")
    return 0


if __name__ == "__main__":
    sys.exit(silk(sys.argv[1]))
