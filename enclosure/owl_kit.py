"""OwlTunes owl v0: the low-cost owl built round the Waveshare ESP32-S3-Touch-AMOLED-1.75 kit.

Six prints (MJF PA12): body, ring, bezel, hub, back cover and beak key. The hub is the chassis:
screwed into the body from behind, it carries the tube the ring turns on, the arms the kit hangs
from by its three M2 standoffs, the TMAG5273 module behind the ring's magnets, and the seats of
the three tact switches. The ring goes in from the front and is held by the bezel, which is glued
onto the tube's front end; the kit then slides in through the bezel. The ear tufts stand on
flexures cut into the head's top wall, each over a switch; the beak key presses the third.

Parts that are bought or come with the kit (the kit, the module, the switches, the battery, the
USB-C plug and the header wiring) are represented by envelopes so the tests can check
clearances. Run `uv run --project enclosure python enclosure/owl_kit.py` to export STEP and STL
files to build/enclosure/kit/. Licence: CERN-OHL-P-2.0 (LICENSE-HARDWARE).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from build123d import Box, Part, Plane, Polyline, Pos, Rot, export_step, export_stl, make_face

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owl_params as P  # noqa: E402
import owl_v1 as V  # noqa: E402
import pcb_contract as C  # noqa: E402
import ring_test as R  # noqa: E402

EPS = 0.01
CLEAR = 0.2  # axial and radial running clearance round the ring, and part-to-part gaps

# Depths (z). The glass front is z = 0; the face, ring and bezel fronts are flush at FRONT_Z.
FRONT_Z = 1.0
FACE_T = 1.6
FACE_BACK_Z = FRONT_Z - FACE_T  # -0.6
# The bezel is glued onto the tube's front end, beside the glass: 2.2 mm thick, as JLC3DP takes no
# part under 2 mm in every direction.
BEZEL_BACK_Z = -1.2
RING_REBATE_Z = BEZEL_BACK_Z - CLEAR  # -1.4: floor of the ring's front rebate, under the bezel
RING_BACK_Z = -4.0  # the magnets' rear faces are flush with it
HUB_FRONT_Z = RING_BACK_Z - CLEAR  # -4.2
HUB_T = 1.85
HUB_BACK_Z = HUB_FRONT_Z - HUB_T  # -6.05
ARM_FRONT_Z = -P.KIT_STANDOFF_DEPTH  # -10.4: the kit's standoffs rest on the arms
ARM_T = 1.5
ARM_BACK_Z = ARM_FRONT_Z - ARM_T  # -11.9
KIT_PCB_BACK_Z = -P.KIT_PCB_BACK_DEPTH
USB_AXIS_Z = KIT_PCB_BACK_Z - P.KIT_USB[2] / 2  # -8.53
BATTERY_FRONT_Z = -10.8  # 0.64 behind the USB-C receptacle, the deepest part over the battery
BATTERY_BACK_Z = BATTERY_FRONT_Z - P.KIT_BATTERY[2]
COVER_IN_Z = BATTERY_BACK_Z - 0.4
COVER_T = 1.5
BACK_Z = COVER_IN_Z - COVER_T  # -18.7: the owl is 19.7 mm deep

# Radii. The ring is the owl's width, as on v1; it shows at the sides for the thumb.
RING_R = C.BODY_W / 2  # 33.0
RING_CLEAR_R = RING_R + CLEAR
GLASS_R = (P.KIT_GLASS_D + P.KIT_GLASS_D_TOL) / 2  # 24.555, the largest glass
TUBE_R_IN = 24.8  # 0.245 round the largest glass
TUBE_R_OUT = 26.0
BEZEL_R_IN = 24.75
BEZEL_R_OUT = 27.2
RING_BORE_R = TUBE_R_OUT + 0.25  # MJF holes print small: 0.25 radial clearance on the tube
RING_REBATE_R = BEZEL_R_OUT + CLEAR
RIDGE_R = (25.25, 25.65)  # centring ridge on the tube's front, in a groove in the bezel
RIDGE_H = 0.3
GROOVE_R = (25.15, 25.75)
GROOVE_DEPTH = RIDGE_H + 0.05
MAG_R = 30.5  # magnet track; the pockets leave 0.95 to the ring's outside
MAG_COUNT = 24
INDEX_GROOVE = (0.6, 0.4, 28.0, 32.4)  # width, depth, from r, to r: the ring's 12 o'clock mark
POLARITY_DIMPLE = (0.6, 0.3, 32.3)  # diameter, depth, radius: beside every other pocket, at the back

# Fasteners: M2 self-tapping screws into 1.7 mm holes in the PA12, M2 x 4 machine screws into the kit.
TAP_D = 1.7
CLEAR_D = 2.4
BOSS_R = 2.8
HEAD_D = 4.4  # counterbore for an M2 pan head (4.0 max)
HEAD_K = 1.6
BODY_BOSSES = ((-26.0, 31.0), (26.0, 31.0), (-21.0, -32.0), (21.0, -32.0))  # hub into the body, M2 x 6
COVER_BOSSES = ((-27.0, 20.0), (27.0, 20.0), (-24.0, -26.0), (24.0, -26.0))  # cover into the hub, M2 x 6
COLLAR_R = 3.4
COLLAR_H = 1.3
HEAD_SEAT = 1.8  # counterbore depth from the back face: the head sits 0.2 below it

# Hub arms to the kit's standoffs: a post outside the kit from the plate back to the arm.
POST_R = (23.7, 27.0)
POST_W = 4.4
USB_CUT_X = P.KIT_USB_MOUTH_X + 0.2  # the plate is cut away outside this, where the plug passes
USB_CUT_HALF_Y = 6.8
USB_OPENING = (13.0, 7.0)  # in the body's left wall: plug overmold 12.35 x 6.5 (owl_params)

# Ear flexures in the head's top wall (both sides mirrored): a tab from the root to the tip, cut
# free by 0.6 mm slots, with the tuft on its tip and a switch under it.
TOP_IN_Y = C.BODY_CY + C.BODY_H / 2 - C.WALL_T  # 43.4
TOP_Y = C.BODY_CY + C.BODY_H / 2  # 45.0
EAR_ROOT_X = 3.0
EAR_TIP_X = 15.4
EAR_SLOT = 0.6
EAR_TAB_Z = (-3.8, -1.2)
EAR_SWITCH_X = 13.4  # plunger centre, 2.0 from the tab's tip
EAR_GAP = 0.15  # plunger top to the tab at rest
SWITCH_POCKET = (P.SWITCH_3X6_LEGS + 0.2, P.SWITCH_3X6[1] + 0.2, 0.4)
EAR_SEAT_BOTTOM_Y = 36.5
# The tuft stands on a stem as wide as the tab; 1.0 above the wall it widens to 5.8 mm, so a press
# (0.4 mm) never brings it onto the fixed wall.
EAR_STEM = (12.0, 15.3, 1.0)  # x from, x to, height over TOP_Y
EAR_TUFT = ((10.5, 1.0), (15.6, 1.0), (17.2, 6.5), (16.1, 6.5), (10.5, 2.8))  # (x, height over TOP_Y)
EAR_TUFT_Z = (-5.4, 0.4)

# Beak key: a cap in a slot under the ring, its flange behind the face, over a switch on the hub.
BEAK_XY = (0.0, -35.4)
BEAK_SLOT = (7.0, 2.4)
BEAK_CLEAR = 0.15
BEAK_PROUD = 0.6
BEAK_FLANGE_OVERLAP = 1.6  # makes the key 10.2 long, over JLC3DP's 10 mm minimum
BEAK_GAP = 0.2  # flange to the switch plunger at rest

WIRE_HOLES = ((-19.0, 38.5), (19.0, 38.5), (6.8, -35.4))
WIRE_HOLE_D = 2.4

BATTERY_C = (0.0, -0.9)  # clear of the lower arms (y -11.6) and the BAT plug (y 12.3)
BATTERY_FENCE = (0.8, 1.2, 30.0)  # wall thickness, height and length along each long side

MARK_PLANE = Plane((0, 0, BACK_Z), x_dir=(-1, 0, 0), z_dir=(0, 0, -1))


def tmag_sensor_xy() -> tuple[float, float]:
    """Sensor centre: the module lies behind the hub at 12 o'clock, long side along x, sensor end
    towards +x at x = -6.4; y is as low as the board's sensor-end corner allows while keeping 0.3
    from the kit's 46 mm board, which puts the sensor 0.5 outside the magnet track."""
    x = -6.4
    corner_x = x + P.TMAG_SENSOR_INSET
    y = P.TMAG_MODULE[1] / 2 + math.sqrt((23.0 + 0.3) ** 2 - corner_x**2)
    return x, y


TMAG_XY = tmag_sensor_xy()
TMAG_BOARD_FRONT_Z = HUB_BACK_Z - P.TMAG_PARTS_H - 0.05  # parts face the hub, 0.05 clear of it
HALL_GAP = RING_BACK_Z - (TMAG_BOARD_FRONT_Z + P.HALL_ELEMENT_H)


def tmag_board_box() -> tuple[float, float, float, float]:
    x, y = TMAG_XY
    length, width, _ = P.TMAG_MODULE
    return (x + P.TMAG_SENSOR_INSET - length, y - width / 2, x + P.TMAG_SENSOR_INSET, y + width / 2)


def tmag_hole_xy() -> tuple[float, float]:
    return TMAG_XY[0] - P.TMAG_HOLE_FROM_SENSOR, TMAG_XY[1]


def box(x0: float, y0: float, x1: float, y1: float, z0: float, z1: float) -> Part:
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def radial_box(angle_deg: float, r0: float, r1: float, width: float, z0: float, z1: float) -> Part:
    return Rot(0, 0, angle_deg) * box(r0, -width / 2, r1, width / 2, z0, z1)


def ear_switch_base_y() -> float:
    return TOP_IN_Y - EAR_GAP - P.SWITCH_3X6[2]


def ear_switch_z() -> float:
    return (EAR_TAB_Z[0] + EAR_TAB_Z[1]) / 2


def beak_switch_top_z() -> float:
    return HUB_FRONT_Z - SWITCH_POCKET[2] + P.SWITCH_3X6[2]


def body() -> Part:
    shell = V.prism(V.silhouette(), BACK_Z, FRONT_Z) - V.prism(V.silhouette(C.WALL_T), BACK_Z - EPS, FACE_BACK_Z)
    shell -= V.by_depth(0, 0, RING_CLEAR_R, FACE_BACK_Z - EPS, FRONT_Z + EPS)
    # side openings for the ring, squared off where the circle meets the side walls (as v1)
    side_y = math.sqrt(RING_CLEAR_R**2 - (C.BODY_W / 2 - C.WALL_T) ** 2)
    for s in (-1, 1):
        x0, x1 = sorted((s * (C.BODY_W / 2 - C.WALL_T - 1.0), s * (C.BODY_W / 2 + 1.0)))
        shell -= box(x0, -side_y, x1, side_y, HUB_FRONT_Z, FRONT_Z + EPS)
    for x, y in BODY_BOSSES:
        shell += V.by_depth(x, y, BOSS_R, HUB_FRONT_Z, FACE_BACK_Z + EPS)
        shell -= V.by_depth(x, y, TAP_D / 2, HUB_FRONT_Z - EPS, FRONT_Z - 1.0)
    shell -= Pos(*BEAK_XY, FRONT_Z - FACE_T / 2) * Box(*BEAK_SLOT, FACE_T + 2 * EPS)
    # USB-C: through the left wall round the receptacle's axis, wide enough for a plug overmold
    wall_x = -(C.BODY_W / 2 - C.WALL_T / 2)
    shell -= Pos(wall_x, 0, USB_AXIS_Z) * Box(C.WALL_T + 1.0, *USB_OPENING)
    # ear flexures: three slots free a tab of the top wall from its root to its tip
    for s in (-1, 1):
        xs = sorted((s * EAR_ROOT_X, s * (EAR_TIP_X + EAR_SLOT)))
        xt = sorted((s * EAR_TIP_X, s * (EAR_TIP_X + EAR_SLOT)))
        z0, z1 = EAR_TAB_Z
        y0, y1 = TOP_IN_Y - EPS, TOP_Y + EPS
        shell -= box(xs[0], y0, xs[1], y1, z1, z1 + EAR_SLOT)
        shell -= box(xs[0], y0, xs[1], y1, z0 - EAR_SLOT, z0)
        shell -= box(xt[0], y0, xt[1], y1, z0 - EAR_SLOT, z1 + EAR_SLOT)
        sx = sorted((s * EAR_STEM[0], s * EAR_STEM[1]))
        shell += box(sx[0], TOP_Y - EPS, sx[1], TOP_Y + EAR_STEM[2] + EPS, z0, z1)
        tuft = make_face(Polyline(*[(s * x, TOP_Y + h) for x, h in EAR_TUFT], close=True))
        shell += V.prism(tuft, *EAR_TUFT_Z)
    return shell


def ring() -> Part:
    out = R.annulus(RING_BORE_R, RING_R, RING_BACK_Z, RING_REBATE_Z)
    out += R.annulus(RING_REBATE_R, RING_R, RING_REBATE_Z - EPS, FRONT_Z)
    for i in range(MAG_COUNT):
        angle = 360.0 * (i + 0.5) / MAG_COUNT  # no pocket on the index mark at 90 degrees
        x, y = R.polar(MAG_R, angle)
        out -= V.by_depth(x, y, P.MAG_POCKET_D / 2, RING_BACK_Z - EPS, RING_BACK_Z + P.MAG_POCKET_DEPTH)
        if i % 2 == 0:
            dx, dy = R.polar(POLARITY_DIMPLE[2], angle)
            out -= V.by_depth(dx, dy, POLARITY_DIMPLE[0] / 2, RING_BACK_Z - EPS, RING_BACK_Z + POLARITY_DIMPLE[1])
    w, d, r0, r1 = INDEX_GROOVE
    out -= radial_box(90.0, r0, r1, w, FRONT_Z - d, FRONT_Z + EPS)
    return out


def bezel() -> Part:
    out = R.annulus(BEZEL_R_IN, BEZEL_R_OUT, BEZEL_BACK_Z, FRONT_Z)
    return out - R.annulus(*GROOVE_R, BEZEL_BACK_Z - EPS, BEZEL_BACK_Z + GROOVE_DEPTH)


def hub() -> Part:
    plate = V.prism(V.silhouette(C.WALL_T + CLEAR), HUB_BACK_Z, HUB_FRONT_Z)
    plate += R.annulus(TUBE_R_IN, TUBE_R_OUT, HUB_FRONT_Z - EPS, BEZEL_BACK_Z)
    plate += R.annulus(*RIDGE_R, BEZEL_BACK_Z - EPS, BEZEL_BACK_Z + RIDGE_H)
    plate -= R.disc(TUBE_R_IN, HUB_BACK_Z - EPS, HUB_FRONT_Z + EPS)
    plate -= box(-C.BODY_W, -USB_CUT_HALF_Y, USB_CUT_X, USB_CUT_HALF_Y, HUB_BACK_Z - EPS, HUB_FRONT_Z + EPS)
    # arms to the kit's standoffs, on posts outside the kit
    for x, y in P.KIT_STANDOFFS:
        angle = math.degrees(math.atan2(y, x))
        r = math.hypot(x, y)
        plate += radial_box(angle, POST_R[0], POST_R[1], POST_W, ARM_BACK_Z, HUB_BACK_Z + EPS)
        plate += radial_box(angle, r - POST_W / 2, POST_R[0] + EPS, POST_W, ARM_BACK_Z, ARM_FRONT_Z)
        plate -= V.by_depth(x, y, CLEAR_D / 2, ARM_BACK_Z - EPS, ARM_FRONT_Z + EPS)
    for x, y in BODY_BOSSES:
        plate -= V.by_depth(x, y, CLEAR_D / 2, HUB_BACK_Z - EPS, HUB_FRONT_Z + EPS)
    for x, y in COVER_BOSSES:
        plate += V.by_depth(x, y, BOSS_R, COVER_IN_Z + COLLAR_H, HUB_BACK_Z + EPS)
        plate -= V.by_depth(x, y, TAP_D / 2, COVER_IN_Z + COLLAR_H - EPS, COVER_IN_Z + COLLAR_H + 5.0)
    # TMAG5273 module: one M2 x 4 screw through its hole into a boss, and two fences
    hx, hy = tmag_hole_xy()
    plate += V.by_depth(hx, hy, 2.2, TMAG_BOARD_FRONT_Z, HUB_BACK_Z + EPS)
    plate -= V.by_depth(hx, hy, TAP_D / 2, TMAG_BOARD_FRONT_Z - EPS, HUB_FRONT_Z - 0.4)
    bx0, by0, bx1, by1 = tmag_board_box()
    fence_z = TMAG_BOARD_FRONT_Z - P.TMAG_MODULE[2] + 0.4
    plate += box(bx1 + CLEAR, by0 + 1.5, bx1 + CLEAR + 0.8, by1 - 1.5, fence_z, HUB_BACK_Z + EPS)
    plate += box(bx0 + 3.0, by1 + CLEAR, bx1 - 3.0, by1 + CLEAR + 0.8, fence_z, HUB_BACK_Z + EPS)
    # ear switch seats in front of the plate, a locating pocket in each top face
    base_y = ear_switch_base_y()
    for s in (-1, 1):
        xs = sorted((s * (EAR_SWITCH_X - 4.0), s * (EAR_SWITCH_X + 4.0)))
        seat_top = base_y + SWITCH_POCKET[2]
        plate += box(xs[0], EAR_SEAT_BOTTOM_Y, xs[1], seat_top, HUB_FRONT_Z - EPS, FACE_BACK_Z - CLEAR)
        pw, pd, ph = SWITCH_POCKET
        plate -= box(s * EAR_SWITCH_X - pw / 2, base_y, s * EAR_SWITCH_X + pw / 2, seat_top + EPS,
                     ear_switch_z() - pd / 2, ear_switch_z() + pd / 2)
    # beak switch: a locating pocket in the plate's front face
    pw, pd, ph = SWITCH_POCKET
    plate -= box(BEAK_XY[0] - pw / 2, BEAK_XY[1] - pd / 2, BEAK_XY[0] + pw / 2, BEAK_XY[1] + pd / 2,
                 HUB_FRONT_Z - ph, HUB_FRONT_Z + EPS)
    for x, y in WIRE_HOLES:
        plate -= V.by_depth(x, y, WIRE_HOLE_D / 2, HUB_BACK_Z - EPS, HUB_FRONT_Z + EPS)
    return plate


def back_cover(mark: bool = True) -> Part:
    plate = V.prism(V.silhouette(C.WALL_T + 0.1), BACK_Z, COVER_IN_Z)
    for x, y in COVER_BOSSES:
        plate += V.by_depth(x, y, COLLAR_R, COVER_IN_Z - EPS, COVER_IN_Z + COLLAR_H)
        plate -= V.by_depth(x, y, CLEAR_D / 2, BACK_Z - EPS, COVER_IN_Z + COLLAR_H + EPS)
        plate -= V.by_depth(x, y, HEAD_D / 2, BACK_Z - EPS, BACK_Z + HEAD_SEAT)
    t, h, length = BATTERY_FENCE
    cx, cy = BATTERY_C
    half = P.KIT_BATTERY[1] / 2 + 0.3
    for s in (-1, 1):
        y0 = cy + s * half
        y1 = cy + s * (half + t)
        plate += box(cx - length / 2, min(y0, y1), cx + length / 2, max(y0, y1), COVER_IN_Z - EPS, COVER_IN_Z + h)
    if mark:
        plate -= V.mark_cut(MARK_PLANE)
    return plate


def beak_key() -> Part:
    cap_w, cap_h = BEAK_SLOT[0] - 2 * BEAK_CLEAR, BEAK_SLOT[1] - 2 * BEAK_CLEAR
    cap = box(BEAK_XY[0] - cap_w / 2, BEAK_XY[1] - cap_h / 2, BEAK_XY[0] + cap_w / 2, BEAK_XY[1] + cap_h / 2,
              FACE_BACK_Z - EPS, FRONT_Z + BEAK_PROUD)
    fw = BEAK_SLOT[0] + 2 * BEAK_FLANGE_OVERLAP
    flange = box(BEAK_XY[0] - fw / 2, BEAK_XY[1] - cap_h / 2, BEAK_XY[0] + fw / 2, BEAK_XY[1] + cap_h / 2,
                 beak_switch_top_z() + BEAK_GAP, FACE_BACK_Z)
    return cap + flange


# Envelopes of the bought parts (not printed), for the clearance tests and the renders.


def kit_envelope() -> Part:
    out = R.disc(GLASS_R, -P.KIT_STACK_T, 0.0)
    out += R.disc(P.KIT_BODY_R, KIT_PCB_BACK_Z, -P.KIT_STACK_T + EPS)
    back = KIT_PCB_BACK_Z
    out += R.disc(P.KIT_BODY_R - 1.0, back - P.KIT_BACK_PARTS_H, back + EPS)
    ul, uw, uh = P.KIT_USB
    out += box(P.KIT_USB_MOUTH_X, -uw / 2, P.KIT_USB_MOUTH_X + ul, uw / 2, back - uh, back + EPS)
    for x, y in P.KIT_STANDOFFS:
        out += V.by_depth(x, y, P.KIT_STANDOFF_OD / 2, -P.KIT_STANDOFF_DEPTH, back + EPS)
    hx, hy, hh = P.KIT_HEADER
    out += box(-hx / 2, P.KIT_HEADER_Y - hy / 2, hx / 2, P.KIT_HEADER_Y + hy / 2, back - hh, back + EPS)
    for x0, x1 in P.KIT_SOCKETS_X:
        out += box(x0, P.KIT_SOCKETS_Y[0], x1, P.KIT_SOCKETS_Y[1], back - P.KIT_SOCKET_H, back + EPS)
    for a in P.KIT_SIDE_BUTTONS_DEG:
        out += radial_box(a, P.KIT_BODY_R - 2.0, P.KIT_BODY_R + 0.4, 3.6, back - 1.6, back + EPS)
    return out


def usb_plug_envelope() -> Part:
    """Largest Type-C plug overmold (owl_params USB_OVERMOLD), 0.3 short of the mouth, out past the wall."""
    w, h = P.USB_OVERMOLD
    x1 = P.KIT_USB_MOUTH_X - P.USB_MATE_GAP
    return box(x1 - 30.0, -w / 2, x1, w / 2, USB_AXIS_Z - h / 2, USB_AXIS_Z + h / 2)


def harness_envelope() -> Part:
    """Right-angle 2.54 mm header in the kit's header with the wires soldered to its legs."""
    hx, hy, hh = P.KIT_HEADER
    top = KIT_PCB_BACK_Z - hh
    return box(-hx / 2, P.KIT_HEADER_Y - 7.5, hx / 2, P.KIT_HEADER_Y + hy / 2, top - 2.9, top)


def battery_plug_envelope() -> Part:
    """MX1.25 plug in the BAT socket and the bend of its wires."""
    x0, x1 = P.KIT_SOCKETS_X[0]
    top = KIT_PCB_BACK_Z - P.KIT_SOCKET_H
    return box(x0 - 0.5, P.KIT_SOCKETS_Y[0] - 0.5, x1 + 0.5, P.KIT_SOCKETS_Y[1] + 0.5, top - 3.0, top)


def battery_envelope() -> Part:
    bx, by, bz = P.KIT_BATTERY
    cx, cy = BATTERY_C
    return box(cx - bx / 2, cy - by / 2, cx + bx / 2, cy + by / 2, BATTERY_BACK_Z, BATTERY_FRONT_Z)


def tmag_envelope() -> Part:
    x0, y0, x1, y1 = tmag_board_box()
    board = box(x0, y0, x1, y1, TMAG_BOARD_FRONT_Z - P.TMAG_MODULE[2], TMAG_BOARD_FRONT_Z)
    hx, hy = tmag_hole_xy()
    parts = box(x0 + 0.5, y0 + 0.5, x1 - 0.5, y1 - 0.5, TMAG_BOARD_FRONT_Z, TMAG_BOARD_FRONT_Z + P.TMAG_PARTS_H)
    parts -= V.by_depth(hx, hy, 2.4, TMAG_BOARD_FRONT_Z - EPS, TMAG_BOARD_FRONT_Z + P.TMAG_PARTS_H + EPS)
    return board + parts


def ear_switch_envelope(s: int) -> Part:
    length, depth, height = P.SWITCH_3X6
    y0 = ear_switch_base_y()
    z = ear_switch_z()
    return box(s * EAR_SWITCH_X - length / 2, y0, s * EAR_SWITCH_X + length / 2, y0 + height, z - depth / 2, z + depth / 2)


def beak_switch_envelope() -> Part:
    length, depth, height = P.SWITCH_3X6
    z0 = HUB_FRONT_Z - SWITCH_POCKET[2]
    return box(BEAK_XY[0] - length / 2, BEAK_XY[1] - depth / 2, BEAK_XY[0] + length / 2, BEAK_XY[1] + depth / 2,
               z0, z0 + height)


def magnets() -> Part:
    out = None
    for i in range(MAG_COUNT):
        x, y = R.polar(MAG_R, 360.0 * (i + 0.5) / MAG_COUNT)
        m = V.by_depth(x, y, P.MAG_D / 2, RING_BACK_Z, RING_BACK_Z + P.MAG_H)
        out = m if out is None else out + m
    return out


def parts() -> dict[str, Part]:
    return {
        "body": body(),
        "ring": ring(),
        "bezel": bezel(),
        "hub": hub(),
        "back_cover": back_cover(),
        "beak_key": beak_key(),
    }


def export_all(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, part in parts().items():
        step, stl = out_dir / f"{name}.step", out_dir / f"{name}.stl"
        export_step(part, str(step))
        export_stl(part, str(stl), tolerance=0.01, angular_tolerance=0.1)
        written += [step, stl]
    return written


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    for path in export_all(root / "build" / "enclosure" / "kit"):
        print(path.relative_to(root))
