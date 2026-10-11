"""OwlTunes enclosure v1: body, back cover, product bezel, glass retainer, ring, magnet carrier and
buttons.

v1 is a fit and feel print (MJF PA12): no feather texture yet. The main board, battery and display
glass are represented by envelopes so the tests can check clearances. The glass goes into the bezel
from the front on an adhesive ring, then a retainer ring is glued into the lip opening over the
glass border, so the glass cannot come out even if its adhesive lets go. Run
`uv run --project enclosure python enclosure/owl_v1.py` to export STEP and STL files to
build/enclosure/v1/. Licence: CERN-OHL-P-2.0 (LICENSE-HARDWARE).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from build123d import (
    Box,
    Cylinder,
    Part,
    Polyline,
    Pos,
    RectangleRounded,
    export_step,
    export_stl,
    extrude,
    make_face,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owl_params as P  # noqa: E402
import pcb_contract as C  # noqa: E402
import ring_test as R  # noqa: E402

EPS = 0.01
FRONT_Z = P.LIP_T  # body face is flush with the ring's front lip
FACE_T = 1.6
PCB_FRONT_Z = -P.pcb_front_depth()  # -10.5
PCB_BACK_Z = PCB_FRONT_Z - P.PCB_T  # -11.5
BATTERY_FRONT_Z = PCB_BACK_Z - C.BATTERY_FOAM  # -12.7
BATTERY_BACK_Z = BATTERY_FRONT_Z - C.BATTERY_T  # -20.7
COVER_T = 1.5
BACK_Z = BATTERY_BACK_Z - COVER_T  # -22.2
RING_CLEAR_R = C.RING_CLEAR_R
RING_CLEAR_BACK_Z = PCB_FRONT_Z  # the body is open around the ring down to the board front
BOSS_R = C.BOSS_R
INSERT_D = 3.2  # M2 x 3 heat-set insert hole
INSERT_DEPTH = 4.0
SCREW_HEAD_D = 4.2

# Glass retention (front insertion). The glass rests on the bezel ledge GLASS_GAP below the rim
# plane; the gap takes the adhesive ring. The retainer is a 1.3 mm ring over the glass border,
# outside the viewing area, glued into the lip opening and flush with the lip front. A snap was
# tried and dropped: the lip is 1.3 high with the bearing right behind it, so any dimple or
# groove under it leaves a neck or a ceiling thinner than the 0.8 mm wall floor.
GLASS_GAP = P.GLASS_POCKET_DEPTH - P.GLASS_T  # 0.2
RETAINER_ID = 44.8  # 0.32 outside the 44.16 viewing area
RETAINER_OD = P.BEZEL_LIP_ID - 0.1  # 0.05 radial glue gap in the lip opening

# Beak key: the slot leaves a 1.0 face bar to the ring opening at x = 0. The stem has the cap's
# depth in y, so it ends inside the flange; it is centred on the slot, 0.4 below the switch centre.
BEAK_SLOT = (7.0, 2.4)
BEAK_XY = (0.0, -35.4)
BEAK_CLEAR = 0.15  # per side, cap in the slot
BEAK_PROUD = 0.6
BEAK_FLANGE_T = 1.0
BEAK_FLANGE_OVERLAP = 1.5  # flange reaches past the slot ends; it stops the key on the face
BEAK_STEM = 2.5
BEAK_SWITCH_GAP = 0.2

ALS_WINDOW_D = 1.6
SIDE_OPENING_Y = math.sqrt(RING_CLEAR_R**2 - (C.BODY_W / 2 - C.WALL_T) ** 2)  # where the ring opening meets the inner side wall

# Ear keys run behind the board and press the EVQ-P7A knobs from above.
EAR_KEY = (4.0, 2.0)  # cross-section of the ear plunger (x by z)
EAR_SLOT_CLEAR = 0.15  # per side, plunger in the head wall slot
EAR_KEY_GAP = 0.2  # key end above the knob tip; the knob travels 0.2 more
EAR_RETAINER_W = 1.0  # retainer reaches this far past the plunger on each side
EAR_RETAINER_T = 1.0

USB_SLOT = (9.6, 3.6)  # width by height of the USB-C opening
USB_PLUG_CENTRE_H = 1.63  # receptacle centre above the board (HRO TYPE-C-31-M-12)

DOCK_PAD_PITCH = P.DOCK_PAD_PITCH
DOCK_PAD_Y = P.DOCK_PAD_Y
DOCK_PAD_ORDER = P.DOCK_PAD_ORDER
DOCK_PAD_WINDOW_D = 3.6
DOCK_BOARD = (28.4, 8.4, 0.5)  # recess for the 28 x 8 mm dock-pad board in the cover's inner face
DOCK_BOARD_Y = P.DOCK_PAD_Y - 0.5  # board spans y -35.5 to -27.5, clear of the battery
DOCK_MAGNETS = ((-20.0, -22.0), (20.0, -22.0))  # D6 x 2 mm N52 discs
DOCK_MAGNET_D = 6.1
DOCK_MAGNET_H = 2.1
DOCK_MAGNET_FLOOR = 1.0  # cover skin between each magnet and the perch
DOCK_MAGNET_WALL = 1.2
LRA_XY = (26.0, -14.5)  # LD0832AA-0099F, 8 x 3.25 mm, glued into a cup on the cover
LRA_POCKET_D = 8.3
LRA_CUP_OD = 10.3  # 1.0 wall
LRA_CUP_H = 1.5
ALIGN_RECESSES = ((-20.0, -34.0), (20.0, -34.0))  # outside the dock-pad board recess
ALIGN_D = 4.0
ALIGN_DEPTH = 0.5  # leaves a 1.0 cover floor


def silhouette(inset: float = 0.0):
    w = C.BODY_W - 2 * inset
    h = C.BODY_H - 2 * inset
    return Pos(0, C.BODY_CY) * RectangleRounded(w, h, C.BODY_R - inset)


def prism(face, z0: float, z1: float) -> Part:
    return Pos(0, 0, z0) * extrude(face, z1 - z0)


def by_depth(x: float, y: float, r: float, z0: float, z1: float) -> Part:
    return Pos(x, y, z0) * Cylinder(r, z1 - z0, align=R.BOTTOM)


def placement(ref: str) -> C.Placement:
    return next(p for p in C.PLACEMENTS if p.ref == ref)


def inner_top_y(x: float) -> float:
    """Inside of the head wall at x (the body silhouette inset by WALL_T)."""
    r = C.BODY_R - C.WALL_T
    cx = C.BODY_W / 2 - C.BODY_R
    cy = C.BODY_CY + C.BODY_H / 2 - C.BODY_R
    if abs(x) <= cx:
        return cy + r
    return cy + math.sqrt(r * r - (abs(x) - cx) ** 2)


def ear_key_bottom(ref: str) -> float:
    return C.knob_box(placement(ref))[3] + EAR_KEY_GAP


def ear_retainer_gap(ref: str) -> float:
    """Free travel of an ear key before its retainer meets the head wall."""
    sw = placement(ref)
    reach = abs(sw.x) + EAR_KEY[0] / 2 + EAR_RETAINER_W
    lowest = min(inner_top_y(abs(sw.x) - EAR_KEY[0] / 2 - EAR_RETAINER_W), inner_top_y(reach))
    return lowest - (ear_key_bottom(ref) + EAR_RETAINER_T)


EAR_RETAINER_GAP = min(ear_retainer_gap("SW201"), ear_retainer_gap("SW202"))


def body() -> Part:
    shell = prism(silhouette(), BACK_Z, FRONT_Z) - prism(silhouette(C.WALL_T), BACK_Z - EPS, FRONT_Z - FACE_T)
    shell -= by_depth(0, 0, RING_CLEAR_R, RING_CLEAR_BACK_Z, FRONT_Z + EPS)
    # square the side openings: the circle alone would cut the 1.6 mm side walls to a knife edge
    for s in (-1, 1):
        x0, x1 = C.BODY_W / 2 - C.WALL_T - 1.0, C.BODY_W / 2 + 1.0
        shell -= Pos(s * (x0 + x1) / 2, 0, (RING_CLEAR_BACK_Z + FRONT_Z + EPS) / 2) * Box(
            x1 - x0, 2 * SIDE_OPENING_Y, FRONT_Z + EPS - RING_CLEAR_BACK_Z
        )
    for x, y in C.BODY_HOLES:
        shell += by_depth(x, y, BOSS_R, PCB_FRONT_Z, FRONT_Z - FACE_T + EPS)
        shell -= by_depth(x, y, INSERT_D / 2, PCB_FRONT_Z - EPS, PCB_FRONT_Z + INSERT_DEPTH)
    shell -= Pos(*BEAK_XY, FRONT_Z - FACE_T / 2) * Box(*BEAK_SLOT, FACE_T + 2 * EPS)
    als = placement("U304")
    shell -= by_depth(als.x, als.y, ALS_WINDOW_D / 2, FRONT_Z - FACE_T - EPS, FRONT_Z + EPS)
    usb = placement("J201")
    usb_z = PCB_BACK_Z - USB_PLUG_CENTRE_H
    shell -= Pos(usb.x, C.BODY_CY - C.BODY_H / 2 + C.WALL_T / 2, usb_z) * Box(USB_SLOT[0], C.WALL_T + 1.0, USB_SLOT[1])
    for ref in ("SW201", "SW202"):
        sw = placement(ref)
        slot = (EAR_KEY[0] + 2 * EAR_SLOT_CLEAR, 12.0, EAR_KEY[1] + 2 * EAR_SLOT_CLEAR)
        shell -= Pos(sw.x, sw.y + slot[1] / 2, ear_key_z()) * Box(*slot)
    return shell


def back_cover() -> Part:
    plate = prism(silhouette(C.WALL_T + 0.1), BACK_Z, BATTERY_BACK_Z)
    for x, y in C.MOUNT_HOLES:
        plate += by_depth(x, y, BOSS_R, BATTERY_BACK_Z - EPS, PCB_BACK_Z)
        plate -= by_depth(x, y, INSERT_D / 2, PCB_BACK_Z - INSERT_DEPTH, PCB_BACK_Z + EPS)
    for x, y in C.BODY_HOLES:
        plate += by_depth(x, y, BOSS_R, BATTERY_BACK_Z - EPS, PCB_BACK_Z)
        plate -= by_depth(x, y, P.M2_CLEAR_D / 2, BACK_Z - EPS, PCB_BACK_Z + EPS)
        plate -= by_depth(x, y, SCREW_HEAD_D / 2, BACK_Z - EPS, BACK_Z + 1.0)
    recess_z0 = BATTERY_BACK_Z - DOCK_BOARD[2]
    plate -= Pos(0, DOCK_BOARD_Y, (recess_z0 + BATTERY_BACK_Z + EPS) / 2) * Box(*DOCK_BOARD[:2], DOCK_BOARD[2] + EPS)
    for k in (-1, 0, 1):
        plate -= by_depth(k * DOCK_PAD_PITCH, DOCK_PAD_Y, DOCK_PAD_WINDOW_D / 2, BACK_Z - EPS, BATTERY_BACK_Z)
    magnet_top = BACK_Z + DOCK_MAGNET_FLOOR + DOCK_MAGNET_H
    for x, y in DOCK_MAGNETS:
        plate += by_depth(x, y, DOCK_MAGNET_D / 2 + DOCK_MAGNET_WALL, BATTERY_BACK_Z - EPS, magnet_top)
        plate -= by_depth(x, y, DOCK_MAGNET_D / 2, BACK_Z + DOCK_MAGNET_FLOOR, magnet_top + EPS)
    plate += by_depth(*LRA_XY, LRA_CUP_OD / 2, BATTERY_BACK_Z - EPS, BATTERY_BACK_Z + LRA_CUP_H)
    plate -= by_depth(*LRA_XY, LRA_POCKET_D / 2, BATTERY_BACK_Z, BATTERY_BACK_Z + LRA_CUP_H + EPS)
    for x, y in ALIGN_RECESSES:
        plate -= by_depth(x, y, ALIGN_D / 2, BACK_Z - EPS, BACK_Z + ALIGN_DEPTH)
    return plate


def bezel() -> Part:
    angles = tuple(math.degrees(math.atan2(y, x)) for x, y in C.MOUNT_HOLES)
    hole_r = math.hypot(*C.MOUNT_HOLES[0])
    return R.face_bezel(P.pcb_front_depth() - P.LUG_T, angles, hole_r, lug_w=C.LUG_W)


def glass_retainer() -> Part:
    """Ring over the glass border, from the rim plane to the lip front."""
    return R.annulus(RETAINER_ID / 2, RETAINER_OD / 2, 0.0, P.LIP_T)


def glass_envelope() -> Part:
    """Cover glass resting on the bezel ledge (not printed)."""
    return Pos(0, 0, -GLASS_GAP - P.GLASS_T) * Cylinder(P.GLASS_D / 2, P.GLASS_T, align=R.BOTTOM)


def beak_key() -> Part:
    sw = placement("SW203")
    bottom = PCB_FRONT_Z + sw.height + BEAK_SWITCH_GAP  # 0.2 mm above the switch actuator
    face_back = FRONT_Z - FACE_T
    cap_w, cap_h = BEAK_SLOT[0] - 2 * BEAK_CLEAR, BEAK_SLOT[1] - 2 * BEAK_CLEAR
    cap = Pos(*BEAK_XY, (face_back + FRONT_Z + BEAK_PROUD) / 2) * Box(cap_w, cap_h, FACE_T + BEAK_PROUD)
    flange_back = face_back - BEAK_FLANGE_T
    flange = Pos(*BEAK_XY, face_back - BEAK_FLANGE_T / 2) * Box(BEAK_SLOT[0] + 2 * BEAK_FLANGE_OVERLAP, cap_h, BEAK_FLANGE_T)
    stem = Pos(BEAK_XY[0], BEAK_XY[1], (bottom + flange_back + EPS) / 2) * Box(BEAK_STEM, cap_h, flange_back - bottom + EPS)
    return cap + flange + stem


def ear_key_z() -> float:
    """Centre height of the ear keys: just behind the board, level with the switch knobs."""
    return PCB_BACK_Z - 0.1 - EAR_KEY[1] / 2


def ear_key(ref: str) -> Part:
    sw = placement(ref)
    z = ear_key_z()
    y0 = ear_key_bottom(ref)
    tip_y = P.OWL_TOP_Y + 2.5
    s = 1 if sw.x > 0 else -1
    inner = sw.x - s * EAR_KEY[0] / 2  # the tuft's inner edge continues the plunger's inner face
    base = tip_y - 2.0  # 0.5 above the head at rest
    stem = Pos(sw.x, (y0 + base + 0.5) / 2, z) * Box(EAR_KEY[0], base + 0.5 - y0, EAR_KEY[1])
    tuft = make_face(
        Polyline(
            (inner, base),
            (sw.x + s * 5.0, base),
            (sw.x + s * 3.5, tip_y + 2.5),
            (sw.x + s * 2.5, tip_y + 2.5),
            (inner, base + 1.5),
            close=True,
        )
    )
    retainer = Pos(sw.x, y0 + EAR_RETAINER_T / 2, z) * Box(EAR_KEY[0] + 2 * EAR_RETAINER_W, EAR_RETAINER_T, EAR_KEY[1])
    return stem + retainer + prism(tuft, z - EAR_KEY[1] / 2, z + EAR_KEY[1] / 2)


def _slab(box: tuple[float, float, float, float], z0: float, z1: float) -> Part:
    x0, y0, x1, y1 = box
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def pcb_envelope() -> Part:
    pts = C.outline_polygon(step_deg=3.0)
    board = prism(make_face(Polyline(*pts, close=True)), PCB_BACK_Z, PCB_FRONT_Z)
    for p in C.PLACEMENTS:
        boxes = [(C.body_box(p), p.height)] + ([(C.knob_box(p), p.knob[4])] if p.knob else [])
        for box, h in boxes:
            z0, z1 = (PCB_FRONT_Z, PCB_FRONT_Z + h) if p.side == "front" else (PCB_BACK_Z - h, PCB_BACK_Z)
            board += _slab(box, z0, z1)
    return board


def battery_envelope() -> Part:
    cx, cy = C.BATTERY_CENTRE
    return Pos(cx, cy, (BATTERY_FRONT_Z + BATTERY_BACK_Z) / 2) * Box(C.BATTERY_W, C.BATTERY_L, C.BATTERY_T - 0.1)


def parts() -> dict[str, Part]:
    out = {
        "body": body(),
        "back_cover": back_cover(),
        "bezel": bezel(),
        "glass_retainer": glass_retainer(),
        "ring_a_bearing": R.ring_a(),
        "ring_b_bushing": R.ring_b(),
        "bushing_sleeve": R.bushing_sleeve(),
        "beak_key": beak_key(),
        "ear_key_left": ear_key("SW201"),
        "ear_key_right": ear_key("SW202"),
    }
    for n in P.MAGNET_COUNTS:
        out[f"magnet_carrier_{n}"] = R.magnet_carrier(n, bumps=False)
    return out


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
    for path in export_all(root / "build" / "enclosure" / "v1"):
        print(path.relative_to(root))
