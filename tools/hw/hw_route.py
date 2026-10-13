#!/usr/bin/env python3
"""Hand-route the main board's critical nets (Task 10 Step 1) and lock them.

Each group is a list of (net, width mm, [owl points]) polylines on B.Cu, with "F" as a fourth
item for F.Cu, (net, "via", [owl points]) for through vias, ("", "no pour", [owl polygon],
layer) for a rule area that keeps copper pours out but allows tracks, vias, pads and footprints
(layer "F", "B" or "In2"), ("", "keepout", [owl polygon], layer) for one that also keeps tracks
and vias out (pads and footprints allowed), or (net, "pour", [owl polygon], layer, priority) for a copper pour
(layer "F", "In1", "In2" or "B"; the fill is clipped to the board outline, so a pour may run
past it); owl coordinates are x right as seen from the front, y up, origin at the display centre
(KiCad x = 100 + x, y = 100 - y). Widths neck down to 0.25 or 0.3 mm only where a track leaves a
0.5 mm pitch pin. Each group's tracks, vias, rule areas and pours go into a KiCad group named
"hw_route <group>". Running a group again first removes everything in that KiCad group, so a
group can be re-routed with new coordinates after a placement change. A run that draws a pour
refills every zone before saving.
The planes group is drawn before Freerouting (the Specctra export hands In1 and In2 to it as
planes); the outer GND pours and the stitching vias come after the session import.

Usage: python3 tools/hw/hw_route.py owl-mainboard <group> [<group> ...]
Groups: tps63802 tps63802_gnd charger vin_chg_taps tps_pg gauge gnd_vias usb crystal dock usb_fanout
qspi bat_ntc vsys_link v3v3_feed vbus_usb j301_fanout disp_3v3 touch_shift local_power late_links planes outer_pours
stitching pour_vias.
Needs KiCad's pcbnew Python module.
"""

from __future__ import annotations

import sys

import pcbnew

from hw_netlist import ROOT


def j301_comb() -> list[tuple[float, float]]:
    """F.Cu between J301's pads, as one polygon: the band between its two rows (x -6.0375 to
    -3.8875) and the 0.3 mm gaps between neighbouring pads of each row (odd pins on the west row at
    x -6.4375, even pins on the east row at x -3.5625, pin k at y 8.72 - 0.3 (k - 1); pads 0.3 mm
    tall, the west row out to x -6.8375, the east row to -3.2375). A track may only reach a pad
    from outside the rows: the west row from the west, the east row from the east."""
    odd = [round(8.72 - 0.6 * j, 3) for j in range(16)]
    even = [round(8.42 - 0.6 * j, 3) for j in range(15)]
    w_in, w_out, e_in, e_out = -6.0375, -6.8375, -3.8875, -3.2375
    pts = [(w_in, odd[-1] - 0.15)]
    for lo, hi in zip(odd[::-1], odd[::-1][1:]):
        pts += [(w_in, lo + 0.15), (w_out, lo + 0.15), (w_out, hi - 0.15), (w_in, hi - 0.15)]
    pts += [(w_in, odd[0] + 0.15), (e_in, odd[0] + 0.15)]
    for hi, lo in zip(even, even[1:]):
        pts += [(e_in, hi - 0.15), (e_out, hi - 0.15), (e_out, lo + 0.15), (e_in, lo + 0.15)]
    pts.append((e_in, odd[-1] - 0.15))
    return [(round(x, 4), round(y, 4)) for x, y in pts]


def meander(x0: float, y0: float, xl: float, xr: float, legs: int, pitch: float = 0.25) -> list[tuple[float, float]]:
    """A lane running down at x0 that swings out at y0: legs horizontal legs alternating between xl
    and xr, pitch apart, then back to x0 (it adds about the sum of the legs to the lane's length)."""
    pts, y = [(x0, y0)], y0
    for i in range(legs):
        t = xl if i % 2 == 0 else xr
        pts += [(t, y), (t, round(y - pitch, 3))]
        y = round(y - pitch, 3)
    return pts + [(x0, y)]


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
    # pins 10 and 11 to C102 and TP102 (on to the TPS63802 in part C, with a layer change at each
    # end: In2 stays GND under U101, U103 and their caps, so a VSYS pour only runs between them);
    # VBAT from pins 2 and 3 to C103, then up between C103 and R103, clear of the H1 boss ring, to
    # J101 pin 1, with TP103 on the way. 0.5 mm except the necks at the 0.5 mm pitch pins; between
    # C103 and R103 the run steps from x 21.75 to 21.65 so the full 0.5 mm keeps 0.2 mm from both
    # (review M1). Branches start at a vertex of the run they leave (review M2).
    "charger": [
        ("VIN_CHG", 0.25, [(25.25, -1.438), (25.25, -2.25)]),
        ("VIN_CHG", 0.5, [(25.25, -2.25), (24.725, -3.2), (24.1, -4.0), (24.1, -5.3), (24.1, -7.9)]),
        ("VSYS", 0.25, [(25.938, 0.25), (25.938, -0.25), (26.7, -0.25)]),
        ("VSYS", 0.5, [(26.7, -0.25), (27.6, -0.775), (28.2, -0.775), (29.3, -0.775), (29.3, 3.0)]),
        ("VBAT", 0.25, [(23.062, 0.25), (23.062, -0.25), (22.1, -0.25)]),
        ("VBAT", 0.5, [(22.1, -0.25), (21.75, -0.5125), (21.4, -0.775), (20.8, -0.775)]),
        ("VBAT", 0.5, [(21.75, -0.5125), (21.75, 1.6), (21.65, 1.7), (21.65, 3.4), (21.65, 4.5)]),
        ("VBAT", 0.5, [(20.6, 3.4), (21.65, 3.4)]),
        ("VBAT", 0.5, [(21.65, 4.5), (22.6, 5.2), (22.6, 16.0), (23.6, 17.0)]),
    ],
    # VIN_CHG taps from the D101/D102 cathode run: east to TP101 above the diode anodes (D101's
    # VBUS_USB anode stays open to the east and south of TP101); and to R103, the CHG_EN2 pull-up,
    # which sits between the VBAT and VSYS runs north of U101, so that tap crosses on F.Cu west of
    # U101 and leaves the ground below U101 pin 1 free for BAT_NTC. Its top via sits at y 1.8, low
    # enough for the +3V3 link (late_links) to pass between it and the VSYS F.Cu run at y 3.25.
    "vin_chg_taps": [
        ("VIN_CHG", 0.5, [(24.1, -4.0), (24.3, -4.2), (29.3, -4.2), (29.3, -5.5)]),
        ("VIN_CHG", 0.25, [(24.1, -4.0), (23.4, -4.1)]),
        ("VIN_CHG", 0.25, [(23.4, -4.1), (22.5, -3.2), (22.5, 1.8)], "F"),
        ("VIN_CHG", 0.25, [(22.5, 1.8), (22.5, 2.99)]),
        ("VIN_CHG", "via", [(23.4, -4.1), (22.5, 1.8)]),
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
        ("VBAT", 0.25, [(26.25, 17.0), (26.25, 12.0), (26.25, 10.99)]),
        ("VBAT", 0.2, [(25.75, 10.99), (26.25, 10.99)]),
        ("VBAT", 0.25, [(26.25, 12.0), (27.4, 12.0), (27.4, 10.32), (28.2, 10.32)]),
    ],
    # GND for the parts routed above whose GND pads a pour cannot reach directly or that need a
    # short path to the planes. U101's GND pins 4 (boxed in by VBAT), 8 and 15 run 0.2 mm into the
    # exposed pad and its four vias, and U102's pins 4 (between the two VBAT runs) and 6 into its
    # pad, which gets a via on its west side, outside the paste. One via beside each GND pad of
    # C101 to C104 and of the crystal load caps C204/C205 (0.225 mm from the TPS_PG run on F.Cu).
    # The ESD parts: U202 pin 2, boxed in by the USB lines, through a via under the body; the
    # D301 TVS through two vias and the D302 ESD diode through one. J101 pin 2, the battery return
    # (up to 0.8 A), through two vias beside its pad, just outside the housing (x 25.2).
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
        ("GND", 0.3, [(19.2, -26.2), (20.15, -26.0)]),
        ("GND", 0.3, [(19.2, -26.2), (20.15, -26.8)]),
        ("GND", 0.25, [(12.7, -26.6), (13.5, -26.6)]),
        ("GND", 0.4, [(25.6, 19.0), (25.6, 20.15)]),
        ("GND", 0.4, [(26.4, 19.0), (26.4, 20.15)]),
        ("GND", "via", [(24.6, 10.0), (27.1, -3.45), (28.2, 1.75), (20.8, 1.75), (29.0, 11.28), (15.65, 27.35),
                        (15.65, 24.85), (-4.5, -30.0), (20.15, -26.0), (20.15, -26.8), (13.5, -26.6), (25.6, 20.15),
                        (26.4, 20.15)]),
    ],
    # USB pair, 0.2 mm wide with 0.15 mm gap (USB net class; full speed, no impedance target):
    # through U202 under its body (pins 6 to 1, 4 to 3), then east, up the corridor at x 5.65/6.0
    # between the IMU and the FB divider, east under the module and up into R203/R204 from below,
    # D+ always on the left of travel so nothing crosses; then the short stubs to U201 pins 14
    # and 13. Keep In2 GND unbroken under x 5 to 6.5. The J201-to-U202 fan-out is usb_fanout.
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
        ("VBUS_DOCK", 0.5, [(14.5, -28.825), (14.5, -28.0), (16.4, -26.1), (16.4, -24.5), (19.6, -21.3),
                            (19.6, -13.0), (23.5, -10.0), (26.9, -10.0), (26.9, -7.9)]),
        ("DOCK_PAD", 0.25, [(13.5, -28.825), (13.5, -27.9), (13.0, -27.4), (11.6, -27.4), (11.3, -27.1),
                            (11.3, -26.6), (11.49, -24.8)]),
    ],
    # J201 fan-out to U202: each D+ pad (A6, B6) drops to a via just above the pad row and each D-
    # pad (A7, B7) to a via just below it, the pairs join and run on F.Cu (over the solid In1 GND)
    # to vias beside U202 pins 6 and 4; D- passes below the J201 peg hole and the through-hole shell
    # tab. B.Cu above the pads stays free for CC1, CC2 and VBUS. The pairs change reference
    # between In2 and In1 at every via, so a GND via sits within 1 mm of each: one above the two
    # D+ vias and one below the two D- vias at J201 (Step 1 review M6), one beside each via at
    # U202 (also U202's second ground via).
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
        ("GND", "via", [(-12.25, -27.65), (-11.75, -31.85), (-6.1, -28.2), (-6.1, -31.75)]),
    ],
    # QSPI from the module's bottom row (B.Cu; left to right D2 D1 CLK D0 CS D3, the FSPI IO_MUX
    # pins) to J301 (rotation 270, west row TE D3 D1 CS from y 5.72 down, east row D2 CLK D0 from
    # y 5.42 down), Fine class 0.1 mm, one via per net, no track between J301's pads. The east row
    # nets run down on B.Cu to vias above J301 and come into their pads on F.Cu from the east; the
    # west row nets run down on B.Cu, west under J301 (B.Cu passes under it freely) to vias under
    # the FPC lead-in (tented) and into their pads on F.Cu from the west. D1 drops between the D2
    # and CLK vias, so the two sets never cross. The D2, CLK and D0 trombones (B.Cu, between the
    # module and their vias) keep every length within 5 mm of LCD_CLK. TE leaves the module's left
    # column, drops to F.Cu there and comes down at x -10.25 into its pad. An F.Cu keep-out
    # (j301_comb) holds every other route, Freerouting's included, out from between J301's rows
    # and pads.
    "qspi": [
        ("LCD_D2", 0.1, [(-1.905, 17.85)] + meander(-1.905, 14.5, -2.9, -0.95, 3) + [(-1.905, 11.0)]),
        ("LCD_CLK", 0.1, [(0.635, 17.85)] + meander(0.635, 14.0, -0.33, 1.6, 4) + [(0.635, 11.0)]),
        ("LCD_D0", 0.1, [(1.905, 17.85)] + meander(1.905, 15.4, 0.95, 2.85, 2) + [(1.905, 11.0)]),
        ("LCD_D2", 0.1, [(-1.905, 11.0), (-2.45, 10.45), (-2.45, 5.42), (-3.4, 5.42)], "F"),
        ("LCD_CLK", 0.1, [(0.635, 11.0), (0.635, 10.4), (-2.15, 7.615), (-2.15, 4.82), (-3.4, 4.82)], "F"),
        ("LCD_D0", 0.1, [(1.905, 11.0), (1.905, 10.0), (-1.85, 6.245), (-1.85, 4.22), (-3.4, 4.22)], "F"),
        ("LCD_D1", 0.1, [(-0.635, 17.85), (-0.635, 7.5), (-8.6, 7.5), (-8.6, 4.52)]),
        ("LCD_CS", 0.1, [(3.175, 17.85), (3.175, 7.0), (-8.0, 7.0), (-8.0, 3.92)]),
        ("LCD_D3", 0.1, [(4.445, 17.85), (4.445, 6.5), (-7.4, 6.5), (-7.4, 5.12)]),
        ("LCD_D1", 0.1, [(-8.6, 4.52), (-6.6, 4.52)], "F"),
        ("LCD_CS", 0.1, [(-8.0, 3.92), (-6.6, 3.92)], "F"),
        ("LCD_D3", 0.1, [(-7.4, 5.12), (-6.6, 5.12)], "F"),
        ("LCD_TE", 0.1, [(-8.75, 24.18), (-10.25, 24.18)]),
        ("LCD_TE", 0.1, [(-10.25, 24.18), (-10.25, 6.1), (-9.87, 5.72), (-6.6, 5.72)], "F"),
        ("LCD_D2", "via", [(-1.905, 11.0)]),
        ("LCD_CLK", "via", [(0.635, 11.0)]),
        ("LCD_D0", "via", [(1.905, 11.0)]),
        ("LCD_D1", "via", [(-8.6, 4.52)]),
        ("LCD_CS", "via", [(-8.0, 3.92)]),
        ("LCD_D3", "via", [(-7.4, 5.12)]),
        ("LCD_TE", "via", [(-10.25, 24.18)]),
        ("", "keepout", j301_comb(), "F"),
    ],
    # BAT_NTC from U101 pin 1 (TS) to RT101, the board NTC under the middle of the cell (the pack
    # is 2-wire). B.Cu down at x 22.75 and west at y -2.0 between C103 and R101 (CHG_ISET can pass
    # below at y -2.5) to a via south-west of C103, then F.Cu over In1 GND and across the B.Cu USB
    # pair: diagonally between the C105/C106 GND vias and the H4 hole (under the H4 bezel lug,
    # which only presses on the mask), and west at y -9.5 to a via in RT101's patch. RT101 reads
    # the board under the cell, 30 mm from U101 and 19 mm from U103. What each piece does:
    # - Pad 1 joins a 4.5 x 3 mm patch (a 3 mm wide track) through a 0.6 mm long, 0.3 mm neck.
    #   The thermal gap pad (docs/hardware/rev-a.md, off-board parts) presses the cell onto the
    #   patch, so the patch, and RT101 through the neck, move towards the cell's temperature.
    # - Pad 2 reaches its GND via through a 0.2 mm neck, about 1.5 mm long, so RT101 is not tied
    #   straight into the GND pour that spreads U101's and U103's heat.
    # - The B.Cu rule area keeps every pour off RT101 (0.4 mm round its pads), off the pad 2 neck
    #   (0.3 mm either side, down to 0.05 mm short of the via, where the pour may join it) and
    #   0.4 mm round the patch. A GND pour floods a GND track, so without it the pour takes the
    #   neck right up to pad 2.
    # - The In2 rule area keeps the In2 GND pour from under the patch (only BAT_NTC itself crosses
    #   it): the nearest plane below the patch is then In1, 0.70 mm down, not In2 at 0.21 mm.
    # - The DRU rule "RT101 pads stay off the pours" stops any pour connecting to the two pads,
    #   and each pad of the 0402 sees a narrow neck at reflow.
    # Estimate with a 1.5 W/mK pad (necks 146 and 557 K/W, pad 69 K/W, patch to the planes about
    # 170 K/W with the In2 void, 60 without): RT101 sits about half way from the board's
    # temperature to the cell's; 35 % without the In2 void, 14 % if the pour took the neck.
    "bat_ntc": [
        ("BAT_NTC", 0.2, [(23.062, -0.75), (22.75, -0.75), (22.75, -2.0), (20.0, -2.0)]),
        ("BAT_NTC", 0.2, [(20.0, -2.0), (12.5, -9.5), (0.38, -9.5)], "F"),
        ("BAT_NTC", 3.0, [(-1.12, -9.5), (0.38, -9.5)]),
        ("BAT_NTC", 0.3, [(-3.49, -9.5), (-1.12, -9.5)]),
        ("GND", 0.2, [(-4.51, -9.5), (-4.51, -11.6)]),
        ("BAT_NTC", "via", [(20.0, -2.0), (0.38, -9.5)]),
        ("GND", "via", [(-4.51, -11.6)]),
        ("", "no pour", [(-5.18, -8.78), (-3.02, -8.78), (-3.02, -7.6), (2.28, -7.6), (2.28, -11.4), (-3.02, -11.4),
                         (-3.02, -10.22), (-4.11, -10.22), (-4.11, -11.3), (-4.91, -11.3), (-4.91, -10.22),
                         (-5.18, -10.22)], "B"),
        ("", "no pour", [(-2.62, -8.0), (1.88, -8.0), (1.88, -11.0), (-2.62, -11.0)], "In2"),
    ],
    # VSYS from the charger to the TPS63802 (up to 0.8 A). The charger's VSYS copper is sealed in
    # on B.Cu (VBAT north, VIN_CHG south) and In2 stays GND under U101, U103 and their caps, so
    # the link is F.Cu over the In1 GND plane: two vias beside C105's VSYS pad (the bulk input
    # cap), north at x 13.075 between U103's west and channel GND vias (0.275 mm from each), east
    # at y -1.625 between the channel via and C109's, north at x 16.0 west of the C107/C108 GND
    # vias (not under L101 or the switch pins), east at y 3.25 above the VIN_CHG tap's via, and
    # two vias on the charger's VSYS run below TP102. 0.5 mm all the way.
    "vsys_link": [
        ("VSYS", 0.5, [(13.825, -6.7), (12.85, -6.7), (12.85, -7.55)]),
        ("VSYS", 0.5, [(12.85, -7.55), (12.85, -6.7), (13.075, -6.475), (13.075, -1.625), (15.75, -1.625),
                       (16.0, -1.375), (16.0, 2.5), (16.75, 3.25), (28.35, 3.25), (29.3, 2.3), (29.3, 1.1)], "F"),
        ("VSYS", "via", [(12.85, -6.7), (12.85, -7.55), (29.3, 1.1), (29.3, 1.9)]),
    ],
    # +3V3 from the TPS63802 output to the In2 +3V3 pour under the module (x -9 to 9, above the
    # module's bottom pin row; In2 is GND everywhere else). B.Cu from C108 north-west to two vias
    # west of the TPS_PG F.Cu run, F.Cu north-west and up at x 7.0 (east of J301, over the In1
    # GND plane; the B.Cu USB pair below it is a wall) to two vias under the module, inside its
    # pin ring. Module pin 2 (3V3) reaches the pour through two vias beside it. 0.5 mm.
    "v3v3_feed": [
        ("+3V3", 0.5, [(14.725, 1.4), (14.725, 2.3), (12.4, 4.6), (11.8, 5.2)]),
        ("+3V3", 0.5, [(12.4, 4.6), (11.8, 5.2), (7.0, 10.0), (7.0, 21.0)], "F"),
        ("+3V3", 0.5, [(8.75, 34.34), (7.3, 34.34), (7.3, 33.55)]),
        ("+3V3", "via", [(12.4, 4.6), (11.8, 5.2), (7.0, 20.0), (7.0, 21.0), (7.3, 34.34), (7.3, 33.55)]),
    ],
    # VBUS_USB from both J201 VBUS pads through the D201 TVS to the D101 anode, 0.5 mm. The west
    # pad goes straight up into D201. The east pad cannot cross CC1 (its pull-down R201 sits east
    # of it), so it hooks round R201: up, east, north past R201 and back west above D201's GND pad
    # into D201. CC1 stays inside the hook on B.Cu; CC2 crosses the west leg on F.Cu (via beside
    # its pad, via below R202). D201's and R201's GND pads, inside the hook, share two GND vias.
    # From the hook's north-east corner VBUS drops to F.Cu (the B.Cu USB pair and VBUS_DOCK are
    # walls on B.Cu), runs east at y -24.55 and up the right side at x 29.4 (east of C304, leaving
    # room for U301's and C304's vias) over the In1 GND plane, south of
    # the BAT_NTC run, and comes back to B.Cu through two vias between TP101 and D102, east of
    # D101's anode, which the VIN_CHG tap and VBUS_DOCK box in on B.Cu.
    "vbus_usb": [
        ("VBUS_USB", 0.5, [(-14.45, -29.3), (-14.45, -27.25), (-13.4, -26.3)]),
        ("VBUS_USB", 0.5, [(-9.55, -29.3), (-9.55, -28.3), (-7.6, -28.3), (-7.6, -25.2), (-12.85, -25.2),
                           (-13.4, -25.75), (-13.4, -26.3)]),
        ("VBUS_USB", 0.5, [(-7.6, -25.2), (-7.6, -24.55), (-6.9, -24.55)]),
        ("VBUS_USB", 0.5, [(-7.6, -24.55), (-6.9, -24.55), (26.05, -24.55), (29.4, -21.2), (29.4, -7.9),
                           (28.6, -7.1), (28.0, -6.6)], "F"),
        ("VBUS_USB", 0.5, [(28.6, -7.1), (28.0, -6.6), (26.9, -5.3)]),
        ("VBUS_USB", "via", [(-7.6, -24.55), (-6.9, -24.55), (28.6, -7.1), (28.0, -6.6)]),
        ("USB_CC1", 0.15, [(-10.75, -29.3), (-10.75, -28.05), (-10.4, -27.7), (-8.4, -27.7)]),
        ("USB_CC2", 0.15, [(-13.75, -29.3), (-13.7, -28.3)]),
        ("USB_CC2", 0.15, [(-13.7, -28.3), (-15.6, -28.3)], "F"),
        ("USB_CC2", 0.15, [(-15.6, -28.3), (-15.6, -27.51)]),
        ("USB_CC2", "via", [(-13.7, -28.3), (-15.6, -28.3)]),
        ("GND", 0.3, [(-10.6, -26.3), (-9.4, -26.25), (-8.4, -26.49)]),
        ("GND", 0.3, [(-9.4, -26.25), (-9.4, -26.95)]),
        ("GND", "via", [(-9.4, -26.25), (-9.4, -26.95)]),
    ],
    # J301's other pins, each led out of the connector to a via or its first part, so that nothing
    # (Freerouting included, held off by the qspi group's keep-out) runs between the rows or pads.
    # West row: GND pins 1 and 7 join the top mounting pad, pin 31 the bottom one, each mounting
    # pad and pin 25 a via. East row: GND pins 4 and 10 run north past the unused pins to a via
    # above pin 2, pin 20 to a via in the actuator strip (vias only, no parts there). LCD_RST
    # leaves pin 18 east to a via, runs west under J301 on B.Cu and up between the D1 lane and the
    # DISP_3V3 run to a via below TP105, then on F.Cu north at x -8.9 (east of TE) to a via west
    # of module pin 32.
    "j301_fanout": [
        ("GND", 0.25, [(-6.6, 6.92), (-7.2, 6.92), (-7.2, 8.72), (-6.6, 8.72)], "F"),
        ("GND", 0.25, [(-6.45, 8.72), (-6.45, 9.42), (-5.0, 9.42)], "F"),
        ("GND", 0.25, [(-6.45, -0.28), (-6.45, -0.98), (-5.2, -0.98), (-5.0, -0.75)], "F"),
        ("GND", 0.25, [(-6.6, 1.52), (-8.2, 1.52)], "F"),
        ("GND", 0.2, [(-3.4, 6.02), (-2.9, 6.02), (-2.9, 7.82), (-3.4, 7.82)], "F"),
        ("GND", 0.2, [(-2.9, 7.82), (-2.9, 9.0), (-3.0, 9.4)], "F"),
        ("GND", 0.25, [(-3.4, 3.02), (-2.6, 3.0)], "F"),
        ("GND", "via", [(-5.0, 9.42), (-5.0, -0.75), (-8.2, 1.52), (-3.0, 9.4), (-2.6, 3.0)]),
        ("LCD_RST", 0.1, [(-3.4, 3.62), (-1.45, 3.62), (-1.2, 3.85)], "F"),
        ("LCD_RST", 0.1, [(-1.2, 3.85), (-1.45, 3.6), (-2.9, 3.6), (-3.3, 3.2), (-8.9, 3.2), (-9.2, 3.5),
                          (-9.2, 8.6)]),
        ("LCD_RST", 0.1, [(-9.2, 8.6), (-8.9, 8.9), (-8.9, 25.0), (-9.35, 25.45), (-10.0, 25.45)], "F"),
        ("LCD_RST", 0.1, [(-10.0, 25.45), (-8.75, 25.45)]),
        ("LCD_RST", "via", [(-1.2, 3.85), (-9.2, 8.6), (-10.0, 25.45)]),
    ],
    # DISP_3V3, the panel supply from U104 (TPS22917): J301's west row pins 21 and 23 cannot reach
    # its east row pins 22, 24 and 26 between the rows, so each side has its own via onto one
    # B.Cu run: W west of pins 21 and 23, P in the pocket east of pins 22 to 26 with C302 and C301.
    # The run comes from U104's outputs (pins 5 and 6), C111, C112 and TP105, down at x -10.0 (west
    # of the D1 and LCD_RST lanes) to W and on under J301 to P. 0.4 mm on B.Cu (0.3 mm between C112
    # and R109), 0.3 mm on F.Cu, 0.25 mm at J301's 0.3 mm pads. touch_shift takes it on from P.
    "disp_3v3": [
        ("DISP_3V3", 0.25, [(-6.6, 2.72), (-7.15, 2.72), (-7.15, 2.12), (-6.6, 2.12)], "F"),
        ("DISP_3V3", 0.3, [(-7.15, 2.42), (-7.7, 2.42)], "F"),
        ("DISP_3V3", 0.25, [(-3.4, 2.42), (-2.85, 2.42), (-2.85, 1.22), (-3.4, 1.22)], "F"),
        ("DISP_3V3", 0.25, [(-3.4, 1.82), (-2.85, 1.82)], "F"),
        ("DISP_3V3", 0.3, [(-2.85, 1.25), (-2.35, 1.25), (-1.68, 1.9), (-1.68, 3.0)], "F"),
        ("DISP_3V3", 0.4, [(-7.7, 2.42), (-7.5, 2.2), (-3.0, 2.2), (-2.35, 1.55), (-2.35, 1.25)]),
        ("DISP_3V3", 0.4, [(-7.7, 2.42), (-9.8, 2.42), (-10.0, 2.62), (-10.0, 9.4), (-9.8, 9.6), (-8.6, 9.6)]),
        ("DISP_3V3", 0.4, [(-8.6, 9.6), (-9.2, 10.22), (-11.0, 10.22), (-12.38, 11.6), (-12.38, 12.4)]),
        ("DISP_3V3", 0.4, [(-12.38, 12.4), (-12.38, 13.18), (-12.6, 13.4), (-12.6, 14.56)]),
        ("DISP_3V3", 0.4, [(-12.6, 14.56), (-13.55, 14.56)]),
        ("DISP_3V3", 0.3, [(-13.55, 14.56), (-13.55, 13.2), (-14.68, 13.2), (-14.68, 12.4)]),
        ("DISP_3V3", "via", [(-7.7, 2.42), (-2.35, 1.25)]),
    ],
    # Touch level shift (U305 LSF0204, A side 1.8 V facing J301, B side 3.3 V east; U306 1.8 V LDO):
    # - A side: TP_SDA_1V8 and TP_INT_1V8 straight in from J301's east row (pins 28 and 30);
    #   TP_SCL_1V8 (pin 27, west row) through a via west of J301 and B.Cu under it to a via beside
    #   U305 pin 3 (the one layer change the channel order needs); TP_RST_1V8 (pin 29) round
    #   J301's south end on F.Cu. All four go on under the package to the 1.8 V pull-ups R311 to
    #   R314, turning down at x 3.25, 2.0, 0.5 and 0.15 (SCL keeps 0.2 mm from U303's GND via).
    # - DISP_1V8: U305 pin 8 (EN) to C312, U306 VOUT and R315; pin 1 (refA) from pin 8 under the
    #   package; the pull-up row (R310, R314 to R311) straight along y -6.11 and up past R311 to
    #   C312.
    # - DISP_3V3 on from the disp_3v3 run's pocket via P: B.Cu east (north of U305) to a via that
    #   feeds U305 pin 14 (refB) from above, north at x 4.75 to E (west of the USB pair, leaving
    #   IMU_INT1 a B.Cu lane beside the pair), F.Cu over the pair at y 6.0 and down at x 9.0
    #   through R301 to R303, U306 VIN, C311 and R315 (a few mA).
    # - B side: pins 13 to 11 to the 3.3 V pull-ups R301 to R303. R301 to R303 sit east of the
    #   pins, so only TP_SDA (the top one) can leave north on F.Cu; TP_SCL, TP_INT and TP_RST drop
    #   to B.Cu in the channel east of the USB pair (vias at x 6.6), run north under R301 to R303
    #   and come back up north of R301. All four run west under the DISP_3V3 crossing (y 2.0 to
    #   3.8), north at x 2.4 to 4.2, west above the QSPI vias (y 11.55 to 13.05); SDA, SCL and INT
    #   drop to B.Cu below module pins 24, 25 and 23, TP_RST goes on north on F.Cu (it crosses
    #   DISP_EN's B.Cu run) to a via east of module pin 33.
    # - GND vias at U305 pin 7 with R310, C312, U306 pin 1 and C311.
    "touch_shift": [
        ("TP_SDA_1V8", 0.1, [(-3.4, 0.62), (-2.45, 0.62), (-1.9, 0.07), (-1.9, -0.3), (-1.2, -0.3)], "F"),
        ("TP_INT_1V8", 0.1, [(-3.4, 0.02), (-2.95, 0.02), (-2.95, -1.6), (-1.2, -1.6)], "F"),
        ("TP_SCL_1V8", 0.1, [(-6.6, 0.92), (-7.4, 0.92)], "F"),
        ("TP_SCL_1V8", 0.1, [(-7.4, 0.92), (-7.0, 0.5), (-3.2, 0.5), (-2.15, -0.55), (-2.15, -0.95)]),
        ("TP_SCL_1V8", 0.1, [(-2.15, -0.95), (-1.2, -0.95)], "F"),
        ("TP_RST_1V8", 0.1, [(-6.6, 0.32), (-7.15, 0.32), (-7.15, -2.25), (-1.2, -2.25)], "F"),
        ("TP_SDA_1V8", 0.1, [(-0.5, -0.3), (3.25, -0.3), (3.25, -5.09)], "F"),
        ("TP_SCL_1V8", 0.1, [(-0.5, -0.95), (2.0, -0.95), (2.0, -4.5), (1.7, -4.85), (1.7, -5.09)], "F"),
        ("TP_INT_1V8", 0.1, [(-0.5, -1.6), (0.5, -1.6), (0.5, -5.09)], "F"),
        ("TP_RST_1V8", 0.1, [(-0.5, -2.25), (0.15, -2.25), (0.15, -4.3), (-0.7, -5.0)], "F"),
        ("TP_SCL_1V8", "via", [(-7.4, 0.92), (-2.15, -0.95)]),
        ("DISP_1V8", 0.25, [(5.2, -3.55), (5.2, -4.92), (5.9, -4.92), (6.5, -5.5), (6.862, -5.8),
                            (6.89, -7.35)], "F"),
        ("DISP_1V8", 0.25, [(4.5, -3.55), (3.75, -3.55), (3.75, 0.35), (-0.5, 0.35)], "F"),
        ("DISP_1V8", 0.25, [(-1.88, -5.91), (-1.5, -6.11), (3.25, -6.11), (3.6, -6.11), (4.25, -5.5), (4.25, -4.92),
                            (5.2, -4.92)], "F"),
        ("DISP_3V3", 0.3, [(-2.35, 1.25), (-1.9, 1.6), (4.75, 1.6), (4.75, 6.0)]),
        ("DISP_3V3", 0.3, [(4.6, 1.6), (4.6, 1.0)]),
        ("DISP_3V3", 0.3, [(4.6, 1.0), (4.6, 0.45)], "F"),
        ("DISP_3V3", 0.3, [(4.75, 6.0), (8.6, 6.0), (9.0, 5.6), (9.0, 0.65), (9.0, -0.95), (9.0, -2.55),
                           (9.0, -7.15)], "F"),
        ("DISP_3V3", 0.25, [(8.41, 0.65), (9.0, 0.65)], "F"),
        ("DISP_3V3", 0.25, [(8.41, -0.95), (9.0, -0.95)], "F"),
        ("DISP_3V3", 0.25, [(8.41, -2.55), (9.0, -2.55)], "F"),
        ("DISP_3V3", 0.25, [(8.92, -7.15), (8.4, -7.35), (7.91, -7.35)], "F"),
        ("DISP_3V3", "via", [(4.6, 1.0), (4.75, 6.0)]),
        ("TP_SDA", 0.1, [(5.4, -0.3), (6.35, -0.3), (7.0, 0.35), (7.39, 0.65)], "F"),
        ("TP_SCL", 0.1, [(5.4, -0.95), (7.39, -0.95)], "F"),
        ("TP_INT", 0.1, [(5.4, -1.6), (6.3, -1.6), (7.0, -2.3), (7.39, -2.55)], "F"),
        ("TP_SDA", 0.1, [(7.39, 0.65), (7.39, 1.1), (5.7, 1.1), (5.7, 2.0), (2.4, 2.0), (2.4, 11.55),
                         (-4.445, 11.55)], "F"),
        ("TP_SCL", 0.1, [(6.6, -0.95), (6.6, 1.6)]),
        ("TP_SCL", 0.1, [(6.6, 1.6), (6.6, 2.6), (3.0, 2.6), (3.0, 12.05), (-5.715, 12.05)], "F"),
        ("TP_INT", 0.1, [(6.6, -1.9), (7.85, -1.9), (7.85, 2.0)]),
        ("TP_INT", 0.1, [(7.85, 2.0), (7.85, 3.2), (3.6, 3.2), (3.6, 12.55), (-3.175, 12.55)], "F"),
        ("TP_RST", 0.1, [(5.4, -2.25), (6.1, -2.25), (6.6, -2.75), (6.6, -2.85)], "F"),
        ("TP_RST", 0.1, [(6.6, -2.85), (8.35, -2.85), (8.35, 3.0)]),
        ("TP_RST", 0.1, [(8.35, 3.0), (8.35, 3.8), (4.2, 3.8), (4.2, 13.05), (-6.6, 13.05), (-6.6, 26.0),
                         (-7.32, 26.72)], "F"),
        ("TP_RST", 0.1, [(-7.32, 26.72), (-8.75, 26.72)]),
        ("TP_SDA", 0.1, [(-4.445, 11.55), (-4.445, 17.85)]),
        ("TP_SCL", 0.1, [(-5.715, 12.05), (-5.715, 17.85)]),
        ("TP_INT", 0.1, [(-3.175, 12.55), (-3.175, 17.85)]),
        ("TP_SDA", "via", [(-4.445, 11.55)]),
        ("TP_SCL", "via", [(6.6, -0.95), (6.6, 1.6), (-5.715, 12.05)]),
        ("TP_INT", "via", [(6.6, -1.9), (7.85, 2.0), (-3.175, 12.55)]),
        ("TP_RST", "via", [(6.6, -2.85), (8.35, 3.0), (-7.32, 26.72)]),
        ("GND", 0.25, [(-1.2, -3.55), (-2.0, -3.55), (-2.75, -3.4)], "F"),
        ("GND", 0.25, [(-1.88, -4.89), (-1.88, -4.3), (-2.75, -3.4)], "F"),
        ("GND", 0.25, [(5.2, -5.88), (4.75, -6.3), (4.4, -6.4)], "F"),
        ("GND", 0.25, [(6.862, -3.9), (6.862, -4.6)], "F"),
        ("GND", 0.25, [(9.88, -7.15), (10.6, -7.15)], "F"),
        ("GND", "via", [(-2.75, -3.4), (4.4, -6.4), (6.862, -4.6), (10.6, -7.15)]),
    ],
    # Fine-pitch power pins Freerouting left open (the Power class's 0.2 mm clearance does not fit
    # its tracks between 0.5 mm pitch pads):
    # - U303 (LGA-12): pad 2 to R309's +3V3 pad and straight across under the package (0.225 mm
    #   from pads 8 and 12) to pads 9 and 10 and on to C307 (C307 and C308 are joined already).
    # - U301 (TSSOP-10): pin 8 (GND) to C304's GND pad and a via above it, pin 10 (+3V3) to C304's
    #   other pad and a via below it, F.Cu west to the +3V3 run over the package; pins 6 and 5 (+3V3)
    #   joined under the package between the pin rows; pin 4 (GND) to a via west of the package.
    # - C202 (module decoupling): its GND pad to module pin 1 (GND); tracks round it leave the B.Cu
    #   pour one spoke, so the DRU keeps the pour off that pad and this track is its GND path.
    "local_power": [
        ("+3V3", 0.2, [(-2.0, -5.26), (-0.763, -5.25), (0.763, -5.25), (0.763, -5.75), (2.0, -5.73)]),
        ("GND", 0.25, [(27.15, -14.0), (28.75, -14.02), (28.55, -13.3)]),
        ("GND", 0.25, [(22.85, -13.5), (21.85, -13.5), (21.6, -13.35)]),
        ("+3V3", 0.25, [(27.15, -13.0), (22.85, -13.0)]),
        ("+3V3", 0.25, [(27.15, -15.0), (28.75, -14.98), (28.6, -15.75)]),
        ("+3V3", 0.25, [(28.6, -15.75), (24.0, -15.75)], "F"),
        ("GND", 0.25, [(10.3, 34.78), (9.75, 35.33), (8.75, 35.61)]),
        ("GND", 0.25, [(0.763, -4.25), (1.4, -4.3)]),
        ("GND", "via", [(28.55, -13.3), (21.6, -13.35), (1.4, -4.3)]),
        ("+3V3", "via", [(28.6, -15.75)]),
    ],
    # Links Freerouting could not make in the routed board (hand copper after the import):
    # - +3V3, west group (U104 pin 1, C110, R206, R207, R210, R211, R304 to R306, R309, U302, U303,
    #   C306 to C308, J202): a via beside R306's +3V3 pad (west of I2C_SCL's hook under R306), F.Cu
    #   east at y 27.5 over the module's left column (below DOCK_DET's F.Cu run), a via into the In2
    #   +3V3 pour under the module.
    # - +3V3, U301 group (U301, C304, C305, R105, R106, R308): F.Cu from that group's via at
    #   (26.28, 2.22) west at y 2.5, between the VIN_CHG tap's via and the VSYS F.Cu run, to a via
    #   beside TP104 on the TPS63802 output.
    # - I2C_SDA, U304 pin 6 (boxed in by the antenna rule area above y 33, U304's own pins and
    #   the +3V3 F.Cu runs): F.Cu west at y 32.8 above ESP_EN's run, north-west beside its
    #   diagonal and west at y 35.2 over the +3V3 vias at x 7.3, a via inside the module's pin
    #   ring and B.Cu under the module to the SDA run from pin 35. The Freerouting GND diagonals
    #   under the module that crossed this path are gone; the B.Cu pour joins those pads.
    # - I2C_SDA, U102 pin 8: a via below the pin, F.Cu north round CHG_PGOOD's via at
    #   (21.65, 13.3) and south at x 20.5, a B.Cu hop under the VSYS and +3V3 F.Cu runs (between
    #   the +3V3 via beside TP104 and TP103), F.Cu south at x 20.55 to the bus via at
    #   (19.929, -11.292) on the U301 side.
    # - IMU_INT1 (since the touch level shift took its old F.Cu path): from U303 pin 12 east at
    #   y -6.33 (above I2C_SCL), up a 0.1 mm B.Cu lane at x 5.3 between DISP_3V3's run to E and the
    #   USB pair, past U305 and the QSPI lanes, a via below module pin 16 and F.Cu on to its run
    #   from module pin 6.
    "late_links": [
        ("+3V3", 0.25, [(-11.41, 27.99), (-12.1, 27.75)]),
        ("+3V3", 0.25, [(-12.1, 27.75), (-11.85, 27.5), (-6.3, 27.5)], "F"),
        ("+3V3", "via", [(-12.1, 27.75), (-6.3, 27.5)]),
        ("+3V3", 0.25, [(18.3, 2.6), (19.25, 2.5)]),
        ("+3V3", 0.25, [(19.25, 2.5), (25.95, 2.5), (26.28, 2.22)], "F"),
        ("+3V3", "via", [(19.25, 2.5)]),
        ("I2C_SDA", 0.15, [(16.35, 32.45), (16.0, 32.8), (10.15, 32.8), (7.75, 35.2), (5.6, 35.2)], "F"),
        ("I2C_SDA", 0.15, [(5.6, 35.2), (1.5, 31.1), (-6.2, 31.1), (-7.0, 30.3), (-7.0, 28.5)]),
        ("I2C_SDA", 0.15, [(25.25, 9.01), (25.25, 8.1)]),
        ("I2C_SDA", 0.15, [(25.25, 8.1), (25.25, 12.9), (24.15, 14.0), (21.2, 14.0), (20.5, 13.3),
                           (20.5, 5.0), (19.8, 4.3)], "F"),
        ("I2C_SDA", 0.15, [(19.8, 4.3), (19.8, 1.6)]),
        ("I2C_SDA", 0.15, [(19.8, 1.6), (20.55, 0.85), (20.55, -10.67), (19.929, -11.292)], "F"),
        ("I2C_SDA", "via", [(5.6, 35.2), (25.25, 8.1), (19.8, 4.3), (19.8, 1.6)]),
        ("IMU_INT1", 0.15, [(-0.25, -5.763), (-0.25, -6.177), (-0.093, -6.334), (3.7, -6.334), (4.3, -5.73)]),
        ("IMU_INT1", 0.1, [(4.3, -5.73), (5.3, -4.73), (5.3, 16.4)]),
        ("IMU_INT1", 0.15, [(5.3, 16.4), (5.3, 20.6), (6.416, 21.244)], "F"),
        ("IMU_INT1", "via", [(5.3, 16.4)]),
    ],
    # Inner planes. In1 is solid GND. In2 is GND too (the reference for the B.Cu parts: U101,
    # U103 and their caps, the crystal, the QSPI block and the USB corridor) except for a +3V3
    # pour under the module, inside its pin ring: x -8.4 to 8.4, from y 18.8 (above the bottom pin
    # row, so the QSPI and USB stubs leaving the pins stay over GND) up to the antenna rule area at
    # y 36.6. Y201 (x 11 to 15) keeps GND under it. The GND pour on In2 is notched round the +3V3
    # pour rather than under it, so the Specctra export gives Freerouting two planes that do not
    # overlap. The module's antenna rule area, RT101's In2 rule area and the board outline clip
    # the fills.
    "planes": [
        ("GND", "pour", [(-32.0, -38.0), (32.0, -38.0), (32.0, 44.0), (-32.0, 44.0)], "In1", 0),
        ("GND", "pour", [(-32.0, -38.0), (32.0, -38.0), (32.0, 44.0), (8.4, 44.0), (8.4, 18.8), (-8.4, 18.8),
                         (-8.4, 44.0), (-32.0, 44.0)], "In2", 0),
        ("+3V3", "pour", [(-8.4, 18.8), (8.4, 18.8), (8.4, 37.0), (-8.4, 37.0)], "In2", 1),
    ],
    # GND stitching vias round the board edge, about every 3 mm on a line 0.75 mm inside it (ruling
    # R5: at least 0.7 mm), and along the antenna notch's lower edge under the module (the strips
    # beside the notch are the antenna rule area: no vias). Spots that would come within the class
    # clearance of other copper or 0.2 mm of any pad, within 1.6 mm of a mounting hole or under
    # J201 are left out: the right edge beside the charger's test pads and VBUS_USB's F.Cu run, the
    # bottom edge under J201 and at SW203, the left edge at U302. Placed after the Freerouting
    # import (tools/hw: scratch generator, coordinates kept here as data).
    "stitching": [
        ("GND", "via", [(-10.12, 35.85), (-6.09, 35.85), (-3.06, 35.85), (-0.03, 35.85), (3.0, 35.85),
                        (6.03, 35.85), (18.22, 42.09), (21.18, 41.47), (23.92, 40.18), (26.29, 38.31),
                        (28.17, 35.94), (29.46, 33.21), (30.09, 30.25), (30.15, 27.23), (30.15, 24.2),
                        (30.15, 21.17), (30.15, 18.14), (30.15, 6.02), (30.15, -6.1), (30.15, -9.13),
                        (30.15, -12.16), (30.15, -15.19), (30.15, -18.22), (30.15, -21.24), (30.09, -24.27),
                        (29.45, -27.23), (28.16, -29.96), (26.28, -32.32), (23.9, -34.19), (21.16, -35.47),
                        (18.21, -36.09), (15.18, -36.15), (12.15, -36.15), (9.12, -36.15), (6.09, -36.15),
                        (3.56, -36.15), (-3.5, -36.15), (-6.03, -36.15), (-18.14, -36.1), (-21.1, -35.49),
                        (-23.85, -34.22), (-26.23, -32.37), (-28.13, -30.01), (-29.43, -27.28),
                        (-30.08, -24.33), (-30.15, -21.31), (-30.15, -18.28), (-30.15, -15.25),
                        (-30.15, -12.22), (-30.15, -9.19), (-30.15, -6.16), (-30.15, -3.13), (-30.15, 2.93),
                        (-30.15, 5.96), (-30.15, 8.99), (-30.15, 12.02), (-30.15, 15.05), (-30.15, 18.08),
                        (-30.15, 21.1), (-30.15, 24.13), (-30.15, 27.16), (-30.1, 30.19), (-29.48, 33.15),
                        (-28.2, 35.89), (-26.33, 38.27), (-23.97, 40.15), (-21.24, 41.45), (-18.29, 42.09)]),
    ],
    # Outer GND pours, drawn after the Freerouting import: F.Cu and B.Cu flood every free area with
    # GND (0.2 mm from other nets, thermal spokes to GND pads), joined to In1 and In2 by the GND vias
    # and the edge stitching. The antenna rule area, J301's keep-out and RT101's no-pour areas stay
    # empty.
    "outer_pours": [
        ("GND", "pour", [(-32.0, -38.0), (32.0, -38.0), (32.0, 44.0), (-32.0, 44.0)], "F", 0),
        ("GND", "pour", [(-32.0, -38.0), (32.0, -38.0), (32.0, 44.0), (-32.0, 44.0)], "B", 0),
    ],
    # One GND via in each region of the outer pours that the tracks round it enclose (review M2):
    # without a via the filler drops the region as an island. Each sits at the deepest spot of its
    # region that is outside every courtyard (for the region beside the module's exposed pad,
    # under the module) and clear of other copper on both outer layers. The first three are for
    # F.Cu regions, the rest for B.Cu regions; regions under 4 mm2 or too thin for a via stay empty.
    "pour_vias": [
        ("GND", "via", [(10.05, 13.99), (21.75, 5.6), (6.67, -6.7), (11.6, -16.82), (-16.47, -9.59),
                        (-21.36, -3.33), (3.54, 21.57), (-1.38, -6.45), (-9.56, 15.61), (25.35, -6.5)]),
    ],
}


LAYERS = {"F": pcbnew.F_Cu, "In1": pcbnew.In1_Cu, "In2": pcbnew.In2_Cu, "B": pcbnew.B_Cu}

# Copper pours (Task 10 Step 3): 0.2 mm clearance (net classes may ask for more), solid fill no
# thinner than 0.2 mm, thermal reliefs with a 0.3 mm gap and 0.3 mm spokes unless a pad says
# otherwise, and islands that reach no pad of their net removed.
POUR_CLEARANCE = 0.2
POUR_MIN_WIDTH = 0.2
POUR_THERMAL_GAP = 0.3
POUR_SPOKE = 0.3


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
        if width in ("no pour", "keepout", "pour"):
            continue
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
    poured = False
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
            if width in ("no pour", "keepout"):
                area = pcbnew.ZONE(board)
                area.SetIsRuleArea(True)
                area.SetDoNotAllowZoneFills(True)
                area.SetDoNotAllowTracks(width == "keepout")
                area.SetDoNotAllowVias(width == "keepout")
                area.SetDoNotAllowPads(False)
                area.SetDoNotAllowFootprints(False)
                area.SetLayer(LAYERS[layer[0]])
                area.SetZoneName(f"{tag(name)} {width}")
                outline = area.Outline()
                outline.NewOutline()
                for a in pts:
                    outline.Append(pt(a))
                area.SetLocked(True)
                board.Add(area)
                group.AddItem(area)
                continue
            info = board.FindNet(net)
            if info is None:
                print(f"no net {net}")
                return 1
            if width == "pour":
                zone = pcbnew.ZONE(board)
                zone.SetLayer(LAYERS[layer[0]])
                zone.SetNet(info)
                zone.SetAssignedPriority(layer[1])
                zone.SetZoneName(f"{tag(name)} {net} {layer[0]}")
                zone.SetLocalClearance(pcbnew.FromMM(POUR_CLEARANCE))
                zone.SetMinThickness(pcbnew.FromMM(POUR_MIN_WIDTH))
                zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
                zone.SetThermalReliefGap(pcbnew.FromMM(POUR_THERMAL_GAP))
                zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(POUR_SPOKE))
                zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
                outline = zone.Outline()
                outline.NewOutline()
                for a in pts:
                    outline.Append(pt(a))
                zone.SetLocked(True)
                board.Add(zone)
                group.AddItem(zone)
                poured = True
                continue
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
    if poured:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(path), board)
    return 0


if __name__ == "__main__":
    sys.exit(route(sys.argv[1], sys.argv[2:]))
