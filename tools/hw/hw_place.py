#!/usr/bin/env python3
"""Place the main board's free parts (everything the enclosure contract does not fix).

Positions are owl coordinates (x right as seen from the front, y up, origin at the display
centre); KiCad x = 100 + x, y = 100 - y. Rotation is what KiCad shows. Run it after
hw_sync.py and hw_contract.py apply; it skips locked parts, so the contract wins.

Usage: python3 tools/hw/hw_place.py owl-mainboard
Needs KiCad's pcbnew Python module.
"""

from __future__ import annotations

import sys

import pcbnew

from hw_netlist import ROOT

# ref: (x, y, rot, side). Groups follow task 8 of the rev A plan; comments say what each sits next to.
PLACE = {
    # Module support: C202 and C201 at the 3V3 pin (pin 2) inside the 3 mm strip beside the notch,
    # the EN network (R205 pull-up, C203, R212 from TPS63802 PG) just below, BOOT pull-up at pin 27.
    "C202": (10.3, 34.3, 90, "back"),
    "C201": (10.55, 31.45, 270, "back"),
    "C203": (12.2, 31.7, 90, "back"),
    "R205": (13.4, 31.7, 90, "back"),
    "R212": (14.6, 31.7, 90, "back"),
    "R206": (-10.9, 19.1, 0, "back"),
    "TP201": (18.8, 27.0, 0, "back"),
    "TP202": (-13.2, 22.5, 0, "back"),
    "TP203": (-13.2, 25.6, 0, "back"),
    # 32 kHz crystal at pins 8 and 9, load caps on its outer side.
    "Y201": (12.0, 26.1, 90, "back"),
    "C204": (14.4, 27.35, 0, "back"),
    "C205": (14.4, 24.85, 0, "back"),
    # USB: series resistors just below pins 13 and 14, standing with their connector pads (pad 1)
    # at the bottom, D+ on the left; ESD, VBUS TVS and CC resistors at the receptacle. U202 at
    # rot 180 has D+ (pins 1, 6) above D- (pins 3, 4) on both sides, so the pair leaves J201, runs
    # through U202 and turns up into R203 and R204 without crossing (checked on the airwires).
    "R203": (10.35, 17.3, 90, "back"),
    "R204": (11.45, 17.3, 90, "back"),
    "U202": (-4.5, -30.0, 180, "back"),
    "D201": (-12.0, -26.3, 0, "back"),
    "R201": (-8.4, -27.0, 90, "back"),
    "R202": (-15.6, -27.0, 90, "back"),
    # Charger in the right strip, outside the battery: C101 at IN, C102 at OUT, C103 at BAT.
    "U101": (24.5, 0.0, 0, "back"),
    "C101": (25.5, -3.2, 0, "back"),
    "C102": (28.2, 0.0, 90, "back"),
    "C103": (20.8, 0.0, 90, "back"),
    "R101": (22.4, -3.3, 0, "back"),
    "R102": (28.4, -2.6, 0, "back"),
    "R103": (22.5, 3.5, 90, "back"),
    "R104": (23.7, 3.5, 90, "back"),
    "R105": (24.9, 3.5, 90, "back"),
    "R106": (26.1, 3.5, 90, "back"),
    "D101": (25.5, -5.3, 0, "back"),
    "D102": (25.5, -7.9, 0, "back"),
    "TP101": (29.3, -5.5, 0, "back"),
    "TP102": (29.3, 3.0, 0, "back"),
    "TP103": (20.6, 3.4, 0, "back"),
    "TP106": (29.3, -8.2, 0, "back"),
    # Board NTC on TS (the pack is 2-wire): on the cell-facing side under the cell, 4.7 mm from its
    # centre (0, -7) and as far from the heat as the cell allows (U101 30 mm, U103 19 mm, L101 22 mm);
    # pad 1 (BAT_NTC) faces east onto its copper patch, pad 2 (GND) west (hw_route.py bat_ntc).
    "RT101": (-4.0, -9.5, 180, "back"),
    # Fuel gauge below J101: CELL and VDD (pins 2 and 3) face J101 pin 1, C104 at pin 3.
    "U102": (26.0, 10.0, 0, "back"),
    "C104": (28.2, 10.8, 90, "back"),
    "TP107": (29.0, 8.0, 0, "back"),
    # 3.3 V buck-boost at the right edge of the battery: C106 (100 nF) right at VIN pin 10 with C105
    # behind it, VOUT caps above, L101 across L1 and L2, feedback divider at FB. L101 (1.2 mm) sits
    # with its courtyard outside the battery zone (R44: under the cell only 1.1 mm parts). It is
    # about 44 mm from U302.
    "U103": (14.0, -3.0, 0, "back"),
    "L101": (16.75, -3.0, 90, "back"),
    "C106": (15.3, -5.32, 0, "back"),
    "C105": (14.6, -6.7, 0, "back"),
    "C107": (15.5, -0.2, 0, "back"),
    "C108": (15.5, 1.4, 0, "back"),
    "C109": (12.8, 0.0, 0, "back"),
    "R107": (11.0, -2.5, 270, "back"),
    "R108": (9.8, -2.5, 90, "back"),
    "TP104": (18.3, 2.6, 0, "back"),
    # Display switch left of the module, above the battery (U104 is 1.45 mm) and clear of the H2 boss.
    "U104": (-12.6, 15.7, 270, "back"),
    "C110": (-15.0, 16.6, 90, "back"),
    "R109": (-15.0, 14.4, 90, "back"),
    "C111": (-11.6, 12.4, 0, "back"),
    "C112": (-14.2, 12.4, 0, "back"),
    "TP105": (-8.6, 9.6, 0, "back"),
    # Display FPC decoupling on the front, east of J301's DISP_3V3 pins 22, 24 and 26 (J301 sits at
    # (-5.0, 4.22) rot 270 with its rows along y and the flex entering from the west), pad 1
    # towards J301 and outside the strip x -3.7 to -2.4 where J301's back-flip actuator opens.
    "C301": (-1.2, 3.0, 0, "front"),
    "C302": (-1.2, 1.9, 0, "front"),
    # Touch pull-ups east of J301, outside the actuator strip x -3.7 to -2.4, pad 2 (TP_*) towards
    # J301's touch pins with room between for the vias of the touch runs, 1.6 mm apart so each
    # reference fits beside its part. On the front they leave the back free for the QSPI lanes
    # between the module and J301. No pad may cover a via that has no tracks (the pour vias):
    # saving the board gives such a via the net of the pad over it.
    "R301": (7.9, 0.65, 180, "front"),
    "R302": (7.9, -0.95, 180, "front"),
    "R303": (7.9, -2.55, 180, "front"),
    # Haptics next to J302: LRA_P and LRA_N (pins 7 and 9) face the connector; C304 spans VDD
    # pin 10 and GND pin 8 on the outer side, C303 at REG.
    "U301": (25.0, -14.0, 0, "back"),
    "C303": (22.6, -16.4, 0, "back"),
    "C304": (28.75, -14.5, 90, "back"),
    "C305": (25.2, -11.5, 0, "back"),
    # Ring sensor support beside U302.
    "C306": (-24.6, 1.0, 0, "back"),
    "R304": (-24.6, -0.4, 0, "back"),
    # IMU at the board centre, C307 at pin 9, C308 beside it, SA0 pull-up at pin 3.
    "U303": (0.0, -5.0, 0, "back"),
    "C307": (2.0, -5.25, 90, "back"),
    "C308": (3.2, -5.25, 90, "back"),
    "R309": (-2.0, -4.75, 90, "back"),
    # Light sensor decoupling beside U304, outside the ring.
    "C309": (19.2, 31.2, 90, "front"),
    # Sensor bus pull-ups at pins 34 (SCL) and 35 (SDA).
    "R306": (-10.9, 27.99, 0, "back"),
    "R305": (-10.9, 29.26, 0, "back"),
    # Dock link: TVS on VBUS_DOCK and ESD on DOCK_PAD at the connector, then the divider.
    "D301": (17.8, -26.2, 0, "back"),
    "D302": (12.0, -26.6, 0, "back"),
    "R307": (12.0, -24.8, 0, "back"),
    "R308": (14.2, -24.8, 0, "back"),
    "C310": (14.2, -23.6, 0, "back"),
    # Buttons: ear pull-ups and filter caps below each ear switch, beak pair right of the module.
    "R207": (-19.0, 35.0, 0, "back"),
    "C206": (-21.2, 35.0, 0, "back"),
    "R208": (19.0, 35.0, 0, "back"),
    "C207": (21.2, 35.0, 0, "back"),
    "R209": (18.5, 31.5, 90, "back"),
    "C208": (19.7, 31.5, 90, "back"),
    # Expansion pull-ups next to J202.
    "R210": (-19.3, -19.0, 90, "back"),
    "R211": (-18.1, -19.0, 90, "back"),
    # UART pads in the left strip, reachable with the battery out.
    "TP204": (-27.5, 22.0, 0, "back"),
    "TP205": (-27.5, 19.0, 0, "back"),
}


REF_SIZE = 0.8  # JLC minimum silkscreen text height (owl-mainboard.kicad_dru)
REF_THICKNESS = 0.15
SILK_GAP = 0.15

# Reference spots set by hand, placed before the search below: owl (x, y) of the text, then
# "left" for text that starts there, or 90 for text that runs up the board (centred otherwise).
# On the front east of J301 the search found no room for C302's reference; C301 and R301 to R303
# are pinned here to the spots the search first gave them. DRC checks these spots (silk to pad, silk overlap) on the
# glyphs themselves.
REF_AT = {
    "C301": (0.16, 3.0, "left"),
    "C302": (0.16, 1.9, "left"),
    "R301": (9.28, 0.65, "left"),
    "R302": (9.28, -0.95, "left"),
    "R303": (9.28, -2.55, "left"),
}


def box(item) -> tuple[float, float, float, float]:
    bb = item.BBox() if isinstance(item, pcbnew.SHAPE_POLY_SET) else item.GetBoundingBox()
    return pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())


def hits(a, b, gap: float = SILK_GAP) -> bool:
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def place_references(board) -> list[str]:
    """Put each reference designator on its side's silkscreen next to the part, clear of every
    pad, hole, other reference, footprint silkscreen drawing and board silkscreen text or mark
    (tools/hw/hw_silk.py, the J101 marks); hide it (the F.Fab or B.Fab copy stays) where nothing
    fits. The references in REF_AT go first, at their own spots, unchecked."""
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    copper = {False: [], True: []}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            for back in (False, True):
                if pad.IsOnLayer(pcbnew.B_Cu if back else pcbnew.F_Cu) or pad.HasHole():
                    copper[back].append(box(pad))
    taken = {False: [], True: []}
    silk = {pcbnew.F_SilkS: False, pcbnew.B_SilkS: True}
    drawings = list(board.GetDrawings()) + [g for fp in board.GetFootprints() for g in fp.GraphicalItems()]
    for d in drawings:
        if d.GetLayer() in silk:
            taken[silk[d.GetLayer()]].append(box(d))
    hidden = []
    for fp in sorted(board.GetFootprints(), key=lambda f: (f.GetReference() not in REF_AT, f.GetReference())):
        ref, back = fp.Reference(), fp.IsFlipped()
        fp.BuildCourtyardCaches()
        ref.SetLayer(pcbnew.B_SilkS if back else pcbnew.F_SilkS)
        ref.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(REF_SIZE), pcbnew.FromMM(REF_SIZE)))
        ref.SetTextThickness(pcbnew.FromMM(REF_THICKNESS))
        ref.SetVisible(True)
        pads = [box(p) for p in fp.Pads()]
        cx0, cy0 = min(b[0] for b in pads) - 0.2, min(b[1] for b in pads) - 0.2
        cx1, cy1 = max(b[2] for b in pads) + 0.2, max(b[3] for b in pads) + 0.2
        mx, my = (cx0 + cx1) / 2, (cy0 + cy1) / 2
        spots = [(mx, cy0 - 0.6), (mx, cy1 + 0.6), (cx0 - 0.4, my, "right"), (cx1 + 0.4, my, "left"),
                 (cx0 - 0.6, my, 90), (cx1 + 0.6, my, 90),
                 (cx0 - 0.4, cy0 - 0.6, "right"), (cx1 + 0.4, cy0 - 0.6, "left"),
                 (cx0 - 0.4, cy1 + 0.6, "right"), (cx1 + 0.4, cy1 + 0.6, "left"), (mx, my), (mx, my, 90)]
        fixed = REF_AT.get(fp.GetReference())
        if fixed:
            spots = [(100 + fixed[0], 100 - fixed[1], *fixed[2:])]
        for spot in spots:
            ref.SetTextAngleDegrees(spot[2] if len(spot) == 3 and spot[2] == 90 else 0)
            ref.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
            if len(spot) == 3 and spot[2] != 90:
                # Mirrored text on the back flips which edge is the start of the line.
                left = (spot[2] == "left") != back
                ref.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if left else pcbnew.GR_TEXT_H_ALIGN_RIGHT)
            ref.SetTextPos(pcbnew.VECTOR2I(pcbnew.FromMM(spot[0]), pcbnew.FromMM(spot[1])))
            t = box(ref)
            inside = all(outline.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
                         for x, y in ((t[0] - 0.3, t[1] - 0.3), (t[2] + 0.3, t[1] - 0.3), (t[2] + 0.3, t[3] + 0.3), (t[0] - 0.3, t[3] + 0.3)))
            if fixed or (inside and not any(hits(t, c) for c in copper[back])
                         and not any(hits(t, o, 0.1) for o in taken[back])):
                taken[back].append(t)
                break
        else:
            ref.SetVisible(False)
            hidden.append(fp.GetReference())
    return hidden


# Battery connector polarity on the back silkscreen beside J101's pins (pin 1 VBAT at y 17,
# pin 2 GND at y 19), with a dot marking pin 1. The board has no reverse-polarity protection on
# J101, so this is what the person plugging the pack in checks.
J101_MARKS = (("+", 28.4, 17.0), ("-", 28.4, 19.0))
J101_PIN1_DOT = (27.35, 17.0, 0.2)
# What the 3-pin J101 had ("+ NTC -" for pins 1 to 3 at y 16, 18 and 20, the dot at y 16), and the
# area round both sets of marks (owl x0, y0, x1, y1). Only these marks are cleared, and only there.
J101_OLD_TEXTS = ("NTC",)
J101_OLD_DOT_Y = 16.0
J101_MARK_AREA = (26.9, 15.0, 29.6, 21.0)


def clear_j101_marks(board) -> None:
    """Delete the marks this tool drew beside J101's pins on the back silkscreen: the texts of
    J101_MARKS and J101_OLD_TEXTS inside J101_MARK_AREA, and the pin 1 dots of the 2-pin and the
    3-pin J101. Other silkscreen there stays. Delete, not Remove: Remove hands the C++ item to
    its Python wrapper, and once that wrapper is freed pcbnew's bindings return untyped
    SwigPyObjects for every board (KiCad 10.0.6)."""
    x0, y0, x1, y1 = J101_MARK_AREA
    texts = {m[0] for m in J101_MARKS} | set(J101_OLD_TEXTS)
    dots = {(pcbnew.FromMM(100 + J101_PIN1_DOT[0]), pcbnew.FromMM(100 - y)) for y in (J101_PIN1_DOT[1], J101_OLD_DOT_Y)}

    def beside(p) -> bool:
        x, y = pcbnew.ToMM(p.x) - 100, 100 - pcbnew.ToMM(p.y)
        return x0 <= x <= x1 and y0 <= y <= y1

    old = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.B_SilkS
           and ((isinstance(d, pcbnew.PCB_TEXT) and d.GetText() in texts and beside(d.GetTextPos()))
                or (isinstance(d, pcbnew.PCB_SHAPE) and d.GetShape() == pcbnew.SHAPE_T_CIRCLE
                    and (d.GetCenter().x, d.GetCenter().y) in dots))]
    for d in old:
        board.Delete(d)


def mark_j101(board) -> None:
    clear_j101_marks(board)
    for text, x, y in J101_MARKS:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(pcbnew.B_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(REF_SIZE), pcbnew.FromMM(REF_SIZE)))
        t.SetTextThickness(pcbnew.FromMM(REF_THICKNESS))
        t.SetMirrored(True)
        t.SetTextPos(pcbnew.VECTOR2I(pcbnew.FromMM(100 + x), pcbnew.FromMM(100 - y)))
        board.Add(t)
    x, y, r = J101_PIN1_DOT
    dot = pcbnew.PCB_SHAPE(board)
    dot.SetShape(pcbnew.SHAPE_T_CIRCLE)
    dot.SetLayer(pcbnew.B_SilkS)
    dot.SetFilled(True)
    dot.SetWidth(pcbnew.FromMM(0.1))
    dot.SetCenter(pcbnew.VECTOR2I(pcbnew.FromMM(100 + x), pcbnew.FromMM(100 - y)))
    dot.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(100 + x + r), pcbnew.FromMM(100 - y)))
    board.Add(dot)


def place(board_name: str) -> int:
    path = ROOT / "hardware" / board_name / f"{board_name}.kicad_pcb"
    board = pcbnew.LoadBoard(str(path))
    moved = 0
    for ref, (x, y, rot, side) in PLACE.items():
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            print(f"{ref}: not on the board")
            return 1
        if fp.IsLocked():
            continue
        if fp.IsFlipped() != (side == "back"):
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(100 + x), pcbnew.FromMM(100 - y)))
        fp.SetOrientationDegrees(rot)
        moved += 1
    hidden = place_references(board)
    unplaced = [fp.GetReference() for fp in board.GetFootprints() if not fp.IsLocked() and fp.GetReference() not in PLACE]
    mark_j101(board)
    pcbnew.SaveBoard(str(path), board)
    print(f"{board_name}: placed {moved} parts, {len(hidden)} references hidden (no room on the silkscreen): {' '.join(hidden)}")
    if unplaced:
        print(f"not in the table: {' '.join(sorted(unplaced))}")
    return 1 if unplaced else 0


if __name__ == "__main__":
    sys.exit(place(sys.argv[1]))
