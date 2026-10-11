#!/usr/bin/env python3
"""Hand-route the main board's critical nets (Task 10 Step 1) on B.Cu and lock them.

Each group is a list of (net, width mm, [owl points]) polylines; owl coordinates are x right as
seen from the front, y up, origin at the display centre (KiCad x = 100 + x, y = 100 - y). Widths
neck down to 0.25 or 0.3 mm only where a track leaves a 0.5 mm pitch pin. Running a group again
first removes the tracks it drew before, so a group can be re-routed after a placement change.
GND vias, pours and the rest of the nets are Steps 2 and 3 (Freerouting and planes).

Usage: python3 tools/hw/hw_route.py owl-mainboard tps63802 [charger gauge usb ...]
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
    # Charger (BQ24073): VIN_CHG from pin 13 to C101, on to the D101 and D102 cathodes; VSYS from
    # pins 10 and 11 to C102 and TP102 (the run to the TPS63802 is the In2 VSYS pour); VBAT from
    # pins 2 and 3 to C103, then up between C103 and R103, clear of the H1 boss ring, to J101 pin 1,
    # with TP103 on the way. 0.5 mm except the necks at the 0.5 mm pitch pins and 0.4 mm between
    # C103 and R103.
    "charger": [
        ("VIN_CHG", 0.25, [(25.25, -1.438), (25.25, -2.25)]),
        ("VIN_CHG", 0.5, [(25.25, -2.25), (24.725, -3.2), (24.1, -4.0), (24.1, -5.3), (24.1, -7.9)]),
        ("VSYS", 0.25, [(25.938, 0.25), (25.938, -0.25), (26.7, -0.25)]),
        ("VSYS", 0.5, [(26.7, -0.25), (27.6, -0.775), (28.2, -0.775), (29.3, -0.775), (29.3, 3.0)]),
        ("VBAT", 0.25, [(23.062, 0.25), (23.062, -0.25), (22.1, -0.25)]),
        ("VBAT", 0.5, [(22.1, -0.25), (21.4, -0.775), (20.8, -0.775)]),
        ("VBAT", 0.4, [(21.75, -0.51), (21.75, 4.5)]),
        ("VBAT", 0.4, [(20.6, 3.4), (21.75, 3.4)]),
        ("VBAT", 0.5, [(21.75, 4.5), (22.6, 5.2), (22.6, 14.0), (23.6, 16.0)]),
    ],
    # Fuel gauge Kelvin tap (R37): CELL and VDD (pins 2 and 3) on their own trace to J101 pin 1,
    # apart from the charger's VBAT path, with C104 at pin 3.
    "gauge": [
        ("VBAT", 0.25, [(26.25, 16.0), (26.25, 12.0), (26.25, 10.99)]),
        ("VBAT", 0.2, [(25.75, 10.99), (26.25, 10.99)]),
        ("VBAT", 0.25, [(26.25, 12.0), (27.4, 12.0), (27.4, 10.32), (28.2, 10.32)]),
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
}


def pt(xy) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(100 + xy[0]), pcbnew.FromMM(100 - xy[1]))


def route(board_name: str, groups: list[str]) -> int:
    path = ROOT / "hardware" / board_name / f"{board_name}.kicad_pcb"
    board = pcbnew.LoadBoard(str(path))
    for name in groups:
        if name not in GROUPS:
            print(f"unknown group {name}")
            return 1
        segs = set()
        for _, _, pts in GROUPS[name]:
            for a, b in zip(pts, pts[1:]):
                segs |= {(pt(a).x, pt(a).y, pt(b).x, pt(b).y), (pt(b).x, pt(b).y, pt(a).x, pt(a).y)}
        old = [t for t in board.GetTracks()
               if (t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y) in segs]
        for t in old:
            board.Remove(t)
        length = {}
        for net, width, pts in GROUPS[name]:
            info = board.FindNet(net)
            if info is None:
                print(f"no net {net}")
                return 1
            for a, b in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pt(a))
                t.SetEnd(pt(b))
                t.SetWidth(pcbnew.FromMM(width))
                t.SetLayer(pcbnew.B_Cu)
                t.SetNet(info)
                t.SetLocked(True)
                board.Add(t)
                length[net] = length.get(net, 0.0) + pcbnew.ToMM(t.GetLength())
        print(f"{name}: " + ", ".join(f"{n} {v:.1f} mm" for n, v in sorted(length.items())))
    pcbnew.SaveBoard(str(path), board)
    return 0


if __name__ == "__main__":
    sys.exit(route(sys.argv[1], sys.argv[2:]))
