"""OwlTunes perch v1: weighted desk dock with a tilted back rest, pogo pins and magnets.

Perch coordinates: X to the right as seen from the front (same as the owl's X), Y towards the
back of the desk, Z up. The owl stands on a seat whose top is square to the back rest and leans
back by TILT_DEG against the rest; its dock pads meet the perch board's pogo pins and its two
magnets meet the perch magnets.

Rest frame (rest_location): local X is the perch X, local Y points into the rest (away from the
owl) and local Z runs up the tilt, so a Box(width, depth into the rest, height along the tilt).

The perch board goes in from the back of the rest, components first, into a pocket whose front
wall holds the pins' window, a cavity for the parts and two bosses at H1 and H2; two M2 x 5
self-tapping screws from the back hold it against the bosses. The base's back face continues the
rest's back face so nothing behind the rest is in the way. The USB-C plug enters from the right side of the
rest (see USB_SLOT). Run `uv run --project enclosure python enclosure/perch_v1.py` to export to
build/enclosure/perch-v1/. Licence: CERN-OHL-P-2.0 (LICENSE-HARDWARE).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from build123d import Align, Box, Cylinder, Location, Part, Pos, Rot, export_step, export_stl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owl_v1 as V  # noqa: E402
import pcb_contract as C  # noqa: E402

CENTRE = (Align.CENTER, Align.CENTER, Align.CENTER)
TILT_DEG = 17.5  # owl leans back by this angle from vertical (spec 7.3: 15 to 20 degrees)
Y_BOT = C.BODY_CY - C.BODY_H / 2  # the owl's bottom edge, owl y
BASE = (96.0, 56.0, 12.0)  # width, depth, height
BASE_BACK_Y = 9.5  # base back, then trimmed flush with the rest back so the board can go in from behind
WEIGHT_POCKET = (72.0, 42.0, 9.2)  # 200 g steel insert 70 x 40 x 9 mm (7.85 g/cm3), from below
LEDGE_Y = 0.0  # where the owl's back meets the base top
REST = (80.0, 9.0, 70.0)  # back rest width, thickness, height along the tilt
SEAT = (34.0, 12.0)  # seat under the owl's flat bottom (x -17 to 17): width, depth below the owl

# Pogo pins YZ71215080P-02 (R29): 7.0 mm free above the board, 6.0 mm at the 1.0 mm working
# stroke. The owl's pads sit PAD_RECESS inside its back surface, so the board top sits
# PIN_WORK_LEN - PAD_RECESS behind the rest face and the free pins stand PIN_PROUD proud of it.
PIN_FREE_LEN = 7.0
PIN_WORK_LEN = 6.0
PIN_D = 2.0  # flange diameter
PAD_RECESS = V.COVER_T - V.DOCK_BOARD[2]  # 1.0
BOARD_TOP_INTO = PIN_WORK_LEN - PAD_RECESS  # 5.0
PIN_PROUD = PIN_FREE_LEN - BOARD_TOP_INTO  # 2.0
PIN_WINDOW = (16.0, 6.0)  # width by height along the tilt

# Perch board (hardware/perch-dock, KiCad x = 100 + x, y = 100 - along offset from the pins)
PERCH_BOARD = (34.0, 16.0, 1.6)
BOARD_CLEAR = 0.2  # per side in the pocket
HOLES = ((-14.0, 5.0), (-14.0, -5.0))  # H1, H2: x, along offset from the pin row
BOSS_D = 4.6  # inside the 2.5 mm keep-out ring of each hole
PILOT_D = 1.6  # M2 self-tapping screw into the boss
PILOT_DEPTH = 4.0  # from the board top towards the face; leaves 1.0 at the rest face
PARTS_H = 1.4  # cavity for the small parts (tallest 1.1 mm, D1)
PARTS_X = (-11.0, 9.8)  # LED1 and R4 courtyards start at x -10.5; J1 starts at 8.5
J1_BOX = (7.9, 17.6, 5.6, 3.6)  # x from (joins the pin window), x to, half height along the tilt, depth (3.26 mm part)
J1_PLUG_H = 1.63  # receptacle centre above the board top (HRO TYPE-C-31-M-12)
USB_SLOT = (10.0, 0.8)  # plug opening along the tilt; front skin left at the rest face
PERCH_MAGNET_D = 6.1  # D6 x 2 mm N52 discs, opposite pole to the owl's magnets
PERCH_MAGNET_H = 2.1
MAGNET_SKIN = 0.8  # rest face over each magnet (R7: 0.8 mm non-critical wall)
BUMP_D = 3.6  # alignment bumps that sit in the owl's 4.0 mm recesses
BUMP_H = 0.5


def owl_to_perch(x: float, y: float, z_owl_back: float = 0.0) -> tuple[float, float, float]:
    """Map a point on the owl's back plane (owl X, Y; z_owl_back mm behind it) to perch space."""
    t = math.radians(TILT_DEG)
    up = y - Y_BOT  # distance above the owl's bottom edge
    py = LEDGE_Y + up * math.sin(t) + z_owl_back * math.cos(t)
    pz = BASE[2] + up * math.cos(t) - z_owl_back * math.sin(t)
    return x, py, pz


def rest_location(along: float = 0.0, into: float = 0.0, x: float = 0.0) -> Location:
    """Location on the back rest's front face, `along` mm up the tilt, `into` mm into the rest."""
    px, py, pz = owl_to_perch(x, Y_BOT + along, into)
    return Location((px, py, pz), (-TILT_DEG, 0, 0))


def owl_location() -> Location:
    """Where the owl (owl_v1 coordinates) sits when docked."""
    t = math.radians(TILT_DEG)
    ty = LEDGE_Y - Y_BOT * math.sin(t) + V.BACK_Z * math.cos(t)
    tz = BASE[2] - Y_BOT * math.cos(t) - V.BACK_Z * math.sin(t)
    return Location((0, ty, tz), (90.0 - TILT_DEG, 0, 0))


def rest_box(x: float, along: float, into: float, size: tuple[float, float, float]) -> Part:
    """Box centred at (x, along, into) in the rest frame; size is (width, into, along)."""
    return rest_location(along, into, x) * Box(*size)


def rest_rod(x: float, along: float, into0: float, into1: float, d: float) -> Part:
    """Cylinder along the rest normal from into0 to into1."""
    return rest_location(along, (into0 + into1) / 2, x) * Rot(90, 0, 0) * Cylinder(d / 2, into1 - into0, align=CENTRE)


PAD_UP = V.DOCK_PAD_Y - Y_BOT  # pin row, mm up the tilt from the owl's bottom edge


def board_envelope() -> Part:
    """The assembled perch board: PCB, the parts on its top side and the free pogo pins."""
    w, h, t = PERCH_BOARD
    env = rest_box(0, PAD_UP, BOARD_TOP_INTO + t / 2, (w, t, h))
    top = BOARD_TOP_INTO
    env += rest_box(sum(PARTS_X) / 2, PAD_UP, top - 0.55, (PARTS_X[1] - PARTS_X[0] - 0.4, 1.1, h - 0.4))
    env += rest_box(13.0, PAD_UP, top - J1_PLUG_H, (9.0, 3.26, 8.94))  # J1 shell, x 8.5 to 17.5
    for x in (-V.DOCK_PAD_PITCH, 0.0, V.DOCK_PAD_PITCH):
        env += rest_rod(x, PAD_UP, top - PIN_FREE_LEN, top, PIN_D)
    return env


def perch_body() -> Part:
    body = Pos(0, BASE_BACK_Y - BASE[1] / 2, BASE[2] / 2) * Box(*BASE)
    body -= rest_box(0, -25.0, REST[1] + 30.0, (BASE[0] + 2, 60.0, 70.0))  # base back flush with the rest back
    body += rest_box(0, REST[2] / 2, REST[1] / 2, (REST[0], REST[1], REST[2]))
    # seat: square to the rest under the owl's flat bottom, so the owl bears on it along its depth
    depth = V.FRONT_Z - V.BACK_Z
    body += owl_location() * Pos(0, Y_BOT - SEAT[1] / 2, (V.BACK_Z + V.FRONT_Z) / 2) * Box(SEAT[0], SEAT[1], depth)
    body -= Pos(0, BASE_BACK_Y - BASE[1] / 2, WEIGHT_POCKET[2] / 2 - 0.01) * Box(*WEIGHT_POCKET)

    w, h, th = PERCH_BOARD
    top = BOARD_TOP_INTO
    # board pocket, open through the back of the rest (and the base edge behind it)
    back = REST[1] + 8.0
    body -= rest_box(0, PAD_UP, (top + back) / 2, (w + 2 * BOARD_CLEAR, back - top, h + 2 * BOARD_CLEAR))
    # cavity for the small parts and for J1, leaving bosses at H1 and H2
    cavity = rest_box(sum(PARTS_X) / 2, PAD_UP, top - PARTS_H / 2, (PARTS_X[1] - PARTS_X[0], PARTS_H + 0.02, h + 2 * BOARD_CLEAR))
    x0, x1, half, deep = J1_BOX
    cavity += rest_box((x0 + x1) / 2, PAD_UP, top - deep / 2, (x1 - x0, deep + 0.02, 2 * half))
    body -= cavity
    body -= rest_box(0, PAD_UP, top / 2, (PIN_WINDOW[0], top + 0.2, PIN_WINDOW[1]))  # pin window
    for hx, ha in HOLES:
        body -= rest_rod(hx, PAD_UP + ha, top - PILOT_DEPTH, top + 0.01, PILOT_D)
    # USB-C plug channel from J1 out of the right side of the rest, open to the back
    usb_x0 = w / 2 - 0.3
    usb_len = REST[0] / 2 - usb_x0 + 1.0
    skin = USB_SLOT[1]
    body -= rest_box(usb_x0 + usb_len / 2, PAD_UP, (skin + back) / 2, (usb_len, back - skin, USB_SLOT[0]))
    for mx, my in V.DOCK_MAGNETS:
        body -= rest_rod(mx, my - Y_BOT, MAGNET_SKIN, MAGNET_SKIN + PERCH_MAGNET_H, PERCH_MAGNET_D)
    for bx, by in V.ALIGN_RECESSES:
        body += rest_rod(bx, by - Y_BOT, -BUMP_H, 0.01, BUMP_D)
    return body


def parts() -> dict[str, Part]:
    return {"perch_body": perch_body()}


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
    for path in export_all(root / "build" / "enclosure" / "perch-v1"):
        print(path.relative_to(root))
