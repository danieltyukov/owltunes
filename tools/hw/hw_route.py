#!/usr/bin/env python3
"""Hand-route the main board's critical nets (Task 10 Step 1) and lock them.

Each group is a list of (net, width mm, [owl points]) polylines on B.Cu, with "F" as a fourth
item for F.Cu, or (net, "via", [owl points]) for through vias; owl coordinates are x right as
seen from the front, y up, origin at the display centre (KiCad x = 100 + x, y = 100 - y). Widths
neck down to 0.25 or 0.3 mm only where a track leaves a 0.5 mm pitch pin. Each group's tracks and
vias go into a KiCad group named "hw_route <group>". Running a group again first removes
everything in that KiCad group, so a group can be re-routed with new coordinates after a
placement change.
GND vias that the planes will tie in are placed here and show as via_dangling in DRC until the
pours exist; the pours and the rest of the nets are Steps 2 and 3 (Freerouting and planes).

Usage: python3 tools/hw/hw_route.py owl-mainboard tps63802 [charger gauge usb usb_fanout crystal dock qspi]
Needs KiCad's pcbnew Python module.
"""

from __future__ import annotations

import sys

import pcbnew

from hw_netlist import ROOT

GROUPS = {
    # TPS63802 (TI datasheet section 11): L1 and L2 straight to L101 (entering its pads on the
    # outer half, clear of the footprint's no-track area under the body), VIN from pin 10 to C106 then
    # C105, EN (pin 1) to VIN below the package, VOUT from pin 6 up through C107 to C108, C109 and
    # the top of the feedback divider fed from C107, FB from pin 4 left to R107 and R108, away from
    # L1 and L2; GND pins 2, 3 and 8 joined between the pad rows.
    "tps63802": [
        ("TPS_L1", 0.3, [(14.75, -3.5), (15.5, -3.5)]),
        ("TPS_L1", 0.5, [(15.5, -3.5), (15.85, -3.75), (16.5, -3.75)]),
        ("TPS_L2", 0.3, [(14.75, -2.5), (15.5, -2.5)]),
        ("TPS_L2", 0.5, [(15.5, -2.5), (15.85, -2.25), (16.5, -2.25)]),
        ("VSYS", 0.25, [(14.75, -4.0), (14.8, -4.45)]),
        ("VSYS", 0.5, [(14.8, -4.45), (14.82, -5.32), (13.825, -6.7)]),
        ("VSYS", 0.25, [(13.1, -4.0), (13.1, -4.6), (14.8, -4.6)]),
        ("+3V3", 0.25, [(14.75, -2.0), (14.75, -1.6)]),
        ("+3V3", 0.5, [(14.75, -1.6), (14.725, -0.2), (14.725, 1.4)]),
        ("+3V3", 0.3, [(14.725, -0.2), (14.2, 0.75), (12.32, 0.75), (12.32, 0.0)]),
        ("+3V3", 0.2, [(12.32, 0.0), (11.0, -1.2), (11.0, -1.99)]),
        ("TPS_FB", 0.15, [(13.1, -2.5), (11.9, -2.5), (11.4, -3.01), (11.0, -3.01), (9.8, -3.01)]),
        ("GND", 0.25, [(13.1, -3.5), (13.1, -3.0), (14.0, -3.0)]),
    ],
    # TPS63802 GND island (review I1): the VSYS and +3V3 runs fence the cap GND pads off from the
    # IC's GND pins on B.Cu, so the input and output loops close through vias into In2 GND (0.21 mm
    # under B.Cu; no VSYS pour under the part) and In1. One via beside each GND pad of C105 to C109,
    # two in the channel between the pad rows (0.2 mm to pins 9 and 7, the FB pin and pad 8's
    # neighbours), two west of pins 2 and 3, and one at R108's GND end of the feedback divider.
    "tps63802_gnd": [
        ("GND", 0.25, [(13.1, -3.5), (13.85, -3.45)]),
        ("GND", 0.25, [(14.0, -3.0), (13.85, -2.55)]),
        ("GND", 0.25, [(13.1, -3.0), (12.3, -3.05)]),
        ("GND", 0.25, [(13.1, -3.5), (12.55, -3.5), (12.3, -3.65)]),
        ("GND", 0.3, [(15.375, -6.7), (16.3, -6.7)]),
        ("GND", 0.3, [(15.78, -5.32), (16.35, -4.75)]),
        ("GND", 0.3, [(16.275, -0.2), (17.2, -0.2)]),
        ("GND", 0.3, [(16.275, 1.4), (17.2, 1.4)]),
        ("GND", 0.25, [(13.28, 0.0), (13.28, -0.7)]),
        ("GND", 0.25, [(9.8, -1.99), (9.8, -1.2)]),
        ("GND", "via", [(13.85, -3.45), (13.85, -2.55), (12.3, -3.05), (12.3, -3.65), (16.3, -6.7), (16.35, -4.75),
                        (17.2, -0.2), (17.2, 1.4), (13.28, -0.7), (9.8, -1.2)]),
    ],
    # Charger (BQ24073): VIN_CHG from pin 13 to C101, on to the D101 and D102 cathodes; VSYS from
    # pins 10 and 11 to C102 and TP102 (the run to the TPS63802 is the In2 VSYS pour); VBAT from
    # pins 2 and 3 to C103, then up between C103 and R103, clear of the H1 boss ring, to J101 pin 1,
    # with TP103 on the way. 0.5 mm except the necks at the 0.5 mm pitch pins; between C103 and
    # R103 the run steps from x 21.75 to 21.65 so the full 0.5 mm keeps 0.2 mm from both (review
    # M1). Branches start at a vertex of the run they leave (review M2).
    "charger": [
        ("VIN_CHG", 0.25, [(25.25, -1.438), (25.25, -2.25)]),
        ("VIN_CHG", 0.5, [(25.25, -2.25), (24.725, -3.2), (24.1, -4.0), (24.1, -5.3), (24.1, -7.9)]),
        ("VSYS", 0.25, [(25.938, 0.25), (25.938, -0.25), (26.7, -0.25)]),
        ("VSYS", 0.5, [(26.7, -0.25), (27.6, -0.775), (28.2, -0.775), (29.3, -0.775), (29.3, 3.0)]),
        ("VBAT", 0.25, [(23.062, 0.25), (23.062, -0.25), (22.1, -0.25)]),
        ("VBAT", 0.5, [(22.1, -0.25), (21.75, -0.5125), (21.4, -0.775), (20.8, -0.775)]),
        ("VBAT", 0.5, [(21.75, -0.5125), (21.75, 1.6), (21.65, 1.7), (21.65, 3.4), (21.65, 4.5)]),
        ("VBAT", 0.5, [(20.6, 3.4), (21.65, 3.4)]),
        ("VBAT", 0.5, [(21.65, 4.5), (22.6, 5.2), (22.6, 14.0), (23.6, 16.0)]),
    ],
    # VIN_CHG taps from the D101/D102 cathode run: east to TP101 above the diode anodes (D101's
    # VBUS_USB anode stays open to the east and south of TP101); and to R103, the CHG_EN2 pull-up,
    # which sits between the VBAT and VSYS runs north of U101, so that tap crosses on F.Cu west of
    # U101 and leaves the ground below U101 pin 1 free for BAT_NTC.
    "vin_chg_taps": [
        ("VIN_CHG", 0.5, [(24.1, -4.0), (24.3, -4.2), (29.3, -4.2), (29.3, -5.5)]),
        ("VIN_CHG", 0.25, [(24.1, -4.0), (23.4, -4.1)]),
        ("VIN_CHG", 0.25, [(23.4, -4.1), (22.5, -3.2), (22.5, 2.2)], "F"),
        ("VIN_CHG", 0.25, [(22.5, 2.2), (22.5, 2.99)]),
        ("VIN_CHG", "via", [(23.4, -4.1), (22.5, 2.2)]),
    ],
    # TPS_PG from U103 pin 5 to R212 on the ESP32 EN network: a via in the pocket west of pin 5
    # (inside the +3V3 and FB runs), F.Cu north, east of the crystal and its load caps (nothing on
    # F.Cu under them), and a via beside R212.
    "tps_pg": [
        ("TPS_PG", 0.15, [(13.1, -2.0), (12.2, -1.5)]),
        ("TPS_PG", 0.15, [(12.2, -1.5), (12.2, 2.0), (16.2, 6.0), (16.2, 28.7), (14.6, 30.3)], "F"),
        ("TPS_PG", 0.15, [(14.6, 30.3), (14.6, 31.19)]),
        ("TPS_PG", "via", [(12.2, -1.5), (14.6, 30.3)]),
    ],
    # Fuel gauge Kelvin tap (R37): CELL and VDD (pins 2 and 3) on their own trace to J101 pin 1,
    # apart from the charger's VBAT path, with C104 at pin 3.
    "gauge": [
        ("VBAT", 0.25, [(26.25, 16.0), (26.25, 12.0), (26.25, 10.99)]),
        ("VBAT", 0.2, [(25.75, 10.99), (26.25, 10.99)]),
        ("VBAT", 0.25, [(26.25, 12.0), (27.4, 12.0), (27.4, 10.32), (28.2, 10.32)]),
    ],
    # GND for the parts routed above whose GND pads a pour cannot reach directly or that need a
    # short path to the planes. U101's GND pins 4 (boxed in by VBAT), 8 and 15 run 0.2 mm into the
    # exposed pad and its four vias, and U102's pins 4 (between the two VBAT runs) and 6 into its
    # pad, which gets a via on its west side, outside the paste. One via beside each GND pad of
    # C101 to C104 and of the crystal load caps C204/C205 (0.225 mm from the TPS_PG run on F.Cu).
    # The ESD parts: U202 pin 2, boxed in by the USB lines, through a via under the body; the
    # D301 TVS through two vias and the D302 ESD diode through one.
    "gnd_vias": [
        ("GND", 0.2, [(23.062, 0.68), (23.9, 0.68)]),
        ("GND", 0.2, [(25.18, 1.438), (25.18, 0.7)]),
        ("GND", 0.2, [(24.25, -1.438), (24.25, -0.7)]),
        ("GND", 0.2, [(26.72, 10.99), (26.72, 10.45), (26.6, 10.3)]),
        ("GND", 0.2, [(26.25, 9.01), (26.25, 9.7)]),
        ("GND", 0.25, [(25.4, 10.0), (24.6, 10.0)]),
        ("GND", 0.3, [(26.275, -3.2), (27.1, -3.45)]),
        ("GND", 0.3, [(28.2, 0.775), (28.2, 1.75)]),
        ("GND", 0.3, [(20.8, 0.775), (20.8, 1.75)]),
        ("GND", 0.25, [(28.2, 11.28), (29.0, 11.28)]),
        ("GND", 0.25, [(14.88, 27.35), (15.65, 27.35)]),
        ("GND", 0.25, [(14.88, 24.85), (15.65, 24.85)]),
        ("GND", 0.25, [(-3.362, -30.0), (-4.5, -30.0)]),
        ("GND", 0.3, [(19.2, -26.4), (20.15, -26.0)]),
        ("GND", 0.3, [(19.2, -26.4), (20.15, -26.8)]),
        ("GND", 0.25, [(12.7, -26.6), (13.5, -26.6)]),
        ("GND", "via", [(24.6, 10.0), (27.1, -3.45), (28.2, 1.75), (20.8, 1.75), (29.0, 11.28), (15.65, 27.35),
                        (15.65, 24.85), (-4.5, -30.0), (20.15, -26.0), (20.15, -26.8), (13.5, -26.6)]),
    ],
    # USB pair, 0.2 mm wide with 0.15 mm gap (USB net class; full speed, no impedance target):
    # through U202 under its body (pins 6 to 1, 4 to 3), then east, up the corridor at x 5.65/6.0
    # between the IMU and the FB divider, east under the module and up into R203/R204 from below,
    # D+ always on the left of travel so nothing crosses; then the short stubs to U201 pins 14
    # and 13. Keep In2 GND unbroken under x 5 to 6.5. The J201-to-U202 fan-out is not routed yet.
    "usb": [
        ("USB_DP_CONN", 0.2, [(-5.64, -29.05), (-3.36, -29.05)]),
        ("USB_DM_CONN", 0.2, [(-5.64, -30.95), (-3.36, -30.95)]),
        ("USB_DP_CONN", 0.2, [(-3.36, -29.05), (-2.6, -29.05), (-2.05, -29.6), (5.65, -29.6), (5.65, 15.2),
                              (10.35, 15.2), (10.35, 16.79)]),
        ("USB_DM_CONN", 0.2, [(-3.36, -30.95), (-2.6, -30.95), (-1.6, -29.95), (6.0, -29.95), (6.0, 14.85),
                              (11.45, 14.85), (11.45, 16.79)]),
        ("USB_DP", 0.2, [(8.75, 19.1), (9.7, 19.1), (10.35, 18.45), (10.35, 17.81)]),
        ("USB_DM", 0.2, [(8.75, 20.37), (10.9, 20.37), (11.45, 19.82), (11.45, 17.81)]),
    ],
    # 32.768 kHz crystal: pins 8 and 9 straight to Y201, load caps on its far side, nothing else
    # between the crystal and the module (pins 7 and 10 must escape elsewhere).
    "crystal": [
        ("XTAL32_P", 0.15, [(8.75, 26.72), (9.9, 26.72), (10.5, 27.35), (12.0, 27.35), (13.92, 27.35)]),
        ("XTAL32_N", 0.15, [(8.75, 25.45), (9.9, 25.45), (10.5, 24.85), (12.0, 24.85), (13.92, 24.85)]),
    ],
    # Dock: VBUS_DOCK from J303 pin 2 through the D301 TVS up the right side, clear of the H4 boss
    # ring and U301, to the D102 anode at 0.5 mm; DOCK_PAD from J303 pin 3 through D302 to R307.
    "dock": [
        ("VBUS_DOCK", 0.5, [(14.5, -30.0), (14.5, -28.0), (16.4, -26.4), (16.4, -24.5), (19.6, -21.3),
                            (19.6, -13.0), (23.5, -10.0), (26.9, -10.0), (26.9, -7.9)]),
        ("DOCK_PAD", 0.25, [(13.5, -30.0), (13.5, -28.2), (11.3, -27.0), (11.3, -26.6), (11.49, -24.8)]),
    ],
    # J201 fan-out to U202: each D+ pad (A6, B6) drops to a via just above the pad row and each D-
    # pad (A7, B7) to a via just below it, the pairs join and run on F.Cu (over the solid In1 GND)
    # to vias beside U202 pins 6 and 4; D- passes below the J201 peg hole and the through-hole shell
    # tab. B.Cu above the pads stays free for CC1, CC2 and VBUS.
    "usb_fanout": [
        ("USB_DP_CONN", 0.2, [(-11.75, -29.755), (-11.75, -28.4)]),
        ("USB_DP_CONN", 0.2, [(-12.75, -29.755), (-12.75, -28.4)]),
        ("USB_DM_CONN", 0.2, [(-12.25, -29.755), (-12.25, -31.05)]),
        ("USB_DM_CONN", 0.2, [(-11.25, -29.755), (-11.25, -31.05)]),
        ("USB_DP_CONN", 0.2, [(-12.75, -28.4), (-11.75, -28.4), (-6.7, -28.75)], "F"),
        ("USB_DM_CONN", 0.2, [(-12.25, -31.05), (-11.25, -31.05), (-10.3, -32.3), (-6.7, -32.3), (-6.7, -31.0)], "F"),
        ("USB_DP_CONN", 0.2, [(-6.7, -28.75), (-5.638, -29.05)]),
        ("USB_DM_CONN", 0.2, [(-6.7, -31.0), (-5.638, -30.95)]),
        ("USB_DP_CONN", "via", [(-11.75, -28.4), (-12.75, -28.4), (-6.7, -28.75)]),
        ("USB_DM_CONN", "via", [(-12.25, -31.05), (-11.25, -31.05), (-6.7, -31.0)]),
    ],
    # QSPI from the module's bottom row (B.Cu; left to right D2 D1 CLK D0 CS D3, the FSPI IO_MUX
    # pins) to J301 on F.Cu (top row CS D1 D3 TE, bottom row D0 CLK D2), Fine class 0.1 mm, one
    # via per net, no track between J301's pads. D2, CLK and D0 turn west, run down the back under
    # J301 and come back east below it, which reverses their order; vias below the bottom row, then
    # F.Cu up into the pads. D1 drops to F.Cu at the module and crosses over the CLK and D0 lanes;
    # CS runs west on B.Cu under D1 to a via just above its pad, D3 likewise to the east of D1. The
    # D1 serpentine (F.Cu) and the CS and D3 trombones (B.Cu, under J301) keep every length within
    # 5 mm of LCD_CLK. TE leaves the module's left column, drops to F.Cu there and comes down into
    # its pad east of D3. GND vias sit beside each layer change (B.Cu returns on In2, F.Cu on In1);
    # the two below J301 also feed its GND pins 10 and 20 and the C301/C302 GND pads.
    "qspi": [
        ("LCD_D2", 0.1, [(-1.905, 17.85), (-1.905, 16.75), (-2.4, 16.255), (-2.4, 8.5), (-2.1, 8.2), (1.2, 8.2)]),
        ("LCD_CLK", 0.1, [(0.635, 17.85), (0.635, 16.0), (-1.75, 16.0), (-2.05, 15.7), (-2.05, 9.0), (-1.7, 8.65),
                          (0.6, 8.65)]),
        ("LCD_D0", 0.1, [(1.905, 17.85), (1.905, 15.65), (-1.4, 15.65), (-1.7, 15.35), (-1.7, 9.4), (-1.4, 9.1),
                         (0.0, 9.1)]),
        ("LCD_D2", 0.1, [(1.2, 8.2), (1.2, 10.562)], "F"),
        ("LCD_CLK", 0.1, [(0.6, 8.65), (0.6, 10.562)], "F"),
        ("LCD_D0", 0.1, [(0.0, 9.1), (0.0, 10.562)], "F"),
        ("LCD_D1", 0.1, [(-0.635, 17.85), (-0.635, 16.55)]),
        ("LCD_D1", 0.1, [(-0.635, 16.55), (1.25, 16.55), (1.25, 16.1), (-0.85, 16.1), (-0.85, 15.75), (1.25, 15.75),
                         (1.25, 15.4), (-0.85, 15.4), (-0.85, 15.05), (0.3, 15.05), (0.3, 13.438)], "F"),
        ("LCD_CS", 0.1, [(3.175, 17.85), (3.175, 15.3), (0.4, 15.3), (0.4, 11.4), (-0.3, 11.4), (-0.3, 14.45)]),
        ("LCD_CS", 0.1, [(-0.3, 14.45), (-0.3, 13.438)], "F"),
        ("LCD_D3", 0.1, [(4.445, 17.85), (4.445, 12.0), (3.85, 12.0), (3.85, 15.0), (0.9, 15.0), (0.9, 14.55)]),
        ("LCD_D3", 0.1, [(0.9, 14.55), (0.9, 13.438)], "F"),
        ("LCD_TE", 0.1, [(-8.75, 24.18), (-10.25, 24.18)]),
        ("LCD_TE", 0.1, [(-10.25, 24.18), (-3.27, 17.2), (1.5, 17.2), (1.5, 13.438)], "F"),
        ("GND", 0.25, [(-1.1, 9.65), (-1.2, 9.95), (-1.2, 10.562)], "F"),
        ("GND", 0.25, [(-1.1, 9.65), (-1.77, 9.1), (-1.77, 8.0)], "F"),
        ("GND", 0.25, [(1.8, 9.6), (1.8, 10.562)], "F"),
        ("LCD_D2", "via", [(1.2, 8.2)]),
        ("LCD_CLK", "via", [(0.6, 8.65)]),
        ("LCD_D0", "via", [(0.0, 9.1)]),
        ("LCD_D1", "via", [(-0.635, 16.55)]),
        ("LCD_CS", "via", [(-0.3, 14.45)]),
        ("LCD_D3", "via", [(0.9, 14.55)]),
        ("LCD_TE", "via", [(-10.25, 24.18)]),
        ("GND", "via", [(-1.35, 16.6), (-1.05, 14.45), (2.1, 14.35), (-1.1, 9.65), (1.8, 9.6), (0.6, 7.65),
                        (-11.0, 24.18)]),
    ],
}


def pt(xy) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(100 + xy[0]), pcbnew.FromMM(100 - xy[1]))


def tag(name: str) -> str:
    """Name of the KiCad group that holds a route group's tracks and vias."""
    return f"hw_route {name}"


def remove_old(board: pcbnew.BOARD, name: str) -> None:
    """Delete what a route group drew before: every item in its KiCad group, so edited coordinates
    leave nothing behind, plus untagged tracks and vias at the group's exact coordinates (copper
    drawn before the tagging, or brought back untagged by a Specctra session import).
    Delete, not Remove: Remove hands the C++ item to its Python wrapper, and once that wrapper is
    freed the board's track list comes back as an untyped SwigPyObject (KiCad 10.0.6)."""
    for group in [g for g in board.Groups() if g.GetName() == tag(name)]:
        for item in list(group.GetItems()):
            board.Delete(item)
        board.Delete(group)
    segs = set()
    for _, width, pts, *_ in GROUPS[name]:
        if width == "via":
            segs |= {(pt(a).x, pt(a).y, pt(a).x, pt(a).y) for a in pts}
        for a, b in zip(pts, pts[1:]):
            segs |= {(pt(a).x, pt(a).y, pt(b).x, pt(b).y), (pt(b).x, pt(b).y, pt(a).x, pt(a).y)}
    for t in [t for t in board.GetTracks() if t.GetParentGroup() is None
              and (t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y) in segs]:
        board.Delete(t)


def route(board_name: str, groups: list[str]) -> int:
    path = ROOT / "hardware" / board_name / f"{board_name}.kicad_pcb"
    board = pcbnew.LoadBoard(str(path))
    for name in groups:
        if name not in GROUPS:
            print(f"unknown group {name}")
            return 1
        remove_old(board, name)
        group = pcbnew.PCB_GROUP(board)
        group.SetName(tag(name))
        board.Add(group)
        length = {}
        for net, width, pts, *layer in GROUPS[name]:
            info = board.FindNet(net)
            if info is None:
                print(f"no net {net}")
                return 1
            if width == "via":
                for a in pts:  # JLC no-fee via: 0.3 mm drill, 0.5 mm pad, through
                    v = pcbnew.PCB_VIA(board)
                    v.SetPosition(pt(a))
                    v.SetWidth(pcbnew.FromMM(0.5))
                    v.SetDrill(pcbnew.FromMM(0.3))
                    v.SetNet(info)
                    v.SetLocked(True)
                    board.Add(v)
                    group.AddItem(v)
                continue
            for a, b in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pt(a))
                t.SetEnd(pt(b))
                t.SetWidth(pcbnew.FromMM(width))
                t.SetLayer(pcbnew.F_Cu if layer == ["F"] else pcbnew.B_Cu)
                t.SetNet(info)
                t.SetLocked(True)
                board.Add(t)
                group.AddItem(t)
                length[net] = length.get(net, 0.0) + pcbnew.ToMM(t.GetLength())
        print(f"{name}: " + ", ".join(f"{n} {v:.1f} mm" for n, v in sorted(length.items())))
    pcbnew.SaveBoard(str(path), board)
    return 0


if __name__ == "__main__":
    sys.exit(route(sys.argv[1], sys.argv[2:]))
