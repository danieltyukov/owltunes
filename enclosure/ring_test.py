"""Ring test prints for OwlTunes (spec section 7.2).

Parts: the face bezel, ring A (6710ZZ bearing), ring B (printed bushing with an O-ring), the
bushing sleeve, magnet carriers with 24 and 32 pockets, a sensor jig that holds the SparkFun
TMAG5273 board where the main PCB's sensor will be, spacers for the jig, and two fit coupons.

Run `uv run --project enclosure python enclosure/ring_test.py` to export STEP and STL files to
build/enclosure/ring-test/. All dimensions come from owl_params.py.
Licence: CERN-OHL-P-2.0 (LICENSE-HARDWARE).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from build123d import (
    Align,
    Box,
    Cylinder,
    Part,
    Pos,
    RegularPolygon,
    Rot,
    export_step,
    export_stl,
    extrude,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owl_params as P  # noqa: E402

BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
EPS = 0.01


def disc(r: float, z0: float, z1: float) -> Part:
    """Solid cylinder of radius r between heights z0 < z1, on the Z axis."""
    return Pos(0, 0, z0) * Cylinder(r, z1 - z0, align=BOTTOM)


def annulus(r_in: float, r_out: float, z0: float, z1: float) -> Part:
    """Tube between radii r_in < r_out and heights z0 < z1, on the Z axis."""
    return disc(r_out, z0, z1) - disc(r_in, z0 - EPS, z1 + EPS)


def polar(r: float, angle_deg: float) -> tuple[float, float]:
    a = math.radians(angle_deg)
    return r * math.cos(a), r * math.sin(a)


def bearing_dummy() -> Part:
    """Envelope of the 6710ZZ bearing, for interference checks only (not printed)."""
    return annulus(P.BRG_ID / 2, P.BRG_OD / 2, -P.BRG_W, 0)


def face_bezel(
    tube_end_depth: float = P.TUBE_END_DEPTH,
    lug_angles: tuple[float, ...] = P.LUG_ANGLES_DEG,
    lug_hole_r: float = P.LUG_HOLE_R,
    lug_w: float = P.LUG_W,
) -> Part:
    """Stationary bezel: glass seat, bearing seat, tube and screw lugs behind the ring."""
    lip = annulus(P.BEZEL_LIP_ID / 2, P.BEZEL_LIP_OD / 2, 0, P.LIP_T)
    seat = annulus(P.PANEL_POCKET_D / 2, P.BRG_SEAT_D / 2, -P.BRG_W, 0)
    tube = annulus(P.PANEL_POCKET_D / 2, P.TUBE_OD / 2, -tube_end_depth, -P.BRG_W)
    body = lip + seat + tube
    for angle in lug_angles:
        length = P.TUBE_OD / 2 - P.LUG_R_IN
        lug = Pos(P.LUG_R_IN + length / 2, 0, -tube_end_depth - P.LUG_T / 2) * Box(length, lug_w, P.LUG_T)
        hole = Pos(lug_hole_r, 0, -tube_end_depth - P.LUG_T / 2) * Cylinder(
            P.M2_CLEAR_D / 2, P.LUG_T + 2 * EPS
        )
        lug = (lug - hole) & disc(P.TUBE_OD / 2, -tube_end_depth - P.LUG_T - EPS, 0)
        body += Rot(0, 0, angle) * lug
    body -= disc(P.GLASS_POCKET_D / 2, -P.GLASS_POCKET_DEPTH, 0)
    notch_depth = P.FPC_NOTCH_END_DEPTH - P.GLASS_T
    notch_box = Pos(0, P.FPC_NOTCH_R / 2, -P.GLASS_T - notch_depth / 2) * Box(
        P.FPC_NOTCH_W, P.FPC_NOTCH_R, notch_depth
    )
    body -= notch_box & disc(P.FPC_NOTCH_R, -P.FPC_NOTCH_END_DEPTH, -P.GLASS_T)
    return body


def ring_front(bore_d: float) -> Part:
    body = annulus(bore_d / 2, P.RING_OD / 2, -P.RING_REAR_DEPTH, 0)
    lip_contact = annulus(P.RING_CONTACT_R, P.RING_OD / 2, 0, P.LIP_T)
    lip_relieved = annulus(P.RING_LIP_ID / 2, P.RING_CONTACT_R + EPS, P.LIP_RELIEF, P.LIP_T)
    ring = body + lip_contact + lip_relieved
    notch = Pos(0, P.RING_OD / 2, P.LIP_T - P.INDEX_NOTCH_L / 2) * Box(
        P.INDEX_NOTCH_W, 2 * P.INDEX_NOTCH_D, P.INDEX_NOTCH_L + EPS
    )
    return ring - notch


def ring_a() -> Part:
    return ring_front(P.RING_A_BORE_D)


def ring_b() -> Part:
    return ring_front(P.RING_B_BORE_D)


def bushing_sleeve() -> Part:
    sleeve = annulus(P.SLEEVE_ID / 2, P.SLEEVE_OD / 2, -P.BRG_W, 0)
    z_mid = -P.BRG_W / 2
    groove = annulus(
        P.SLEEVE_OD / 2 - P.ORING_GROOVE_DEPTH,
        P.SLEEVE_OD / 2 + 1.0,
        z_mid - P.ORING_GROOVE_W / 2,
        z_mid + P.ORING_GROOVE_W / 2,
    )
    return sleeve - groove


def magnet_carrier(count: int, bumps: bool = True) -> Part:
    front = -P.CARRIER_FRONT_DEPTH
    back = -P.RING_REAR_DEPTH
    body = annulus(P.CARRIER_ID / 2, P.RING_A_BORE_D / 2 - 0.05, back, front)
    flange = annulus(P.CARRIER_FLANGE_R_IN, P.RING_OD / 2, back - P.CARRIER_FLANGE_T, back)
    carrier = body + flange
    for i in range(count):
        angle = 360.0 * i / count
        x, y = polar(P.R_TRACK, angle)
        carrier -= Pos(x, y, back - EPS) * Cylinder(
            P.MAG_POCKET_D / 2, P.MAG_POCKET_DEPTH + EPS, align=BOTTOM
        )
        if bumps and i % 2 == 0:
            bx, by = polar(P.POLARITY_BUMP_R, angle)
            bump_z = back - P.CARRIER_FLANGE_T - P.POLARITY_BUMP_H
            carrier += Pos(bx, by, bump_z) * Cylinder(
                P.POLARITY_BUMP_D / 2, P.POLARITY_BUMP_H + EPS, align=BOTTOM
            )
    return carrier


def jig_pocket_floor_depth() -> float:
    """Depth of the jig pocket floor: with no spacer the gap is the largest step."""
    return P.magnet_face_depth() + max(P.HALL_GAP_STEPS) + P.HALL_ELEMENT_H + P.SF_BOARD_T


def sensor_xy() -> tuple[float, float]:
    return polar(P.R_TRACK, P.SENSOR_ANGLE_DEG)


def sensor_jig() -> Part:
    front = -P.JIG_FRONT_DEPTH
    back = front - P.JIG_T
    jig = disc(P.JIG_D / 2, back, front)
    jig += Pos(0, (30.0 + P.ANT_TAB_TOP) / 2, (back + front) / 2) * Box(
        P.ANT_TAB_W, P.ANT_TAB_TOP - 30.0, P.JIG_T
    )
    jig -= disc(P.JIG_CENTRE_HOLE_D / 2, back - EPS, front + EPS)
    nut_d = P.M2_NUT_AF / math.cos(math.radians(30))
    for angle in P.LUG_ANGLES_DEG:
        x, y = polar(P.LUG_HOLE_R, angle)
        jig -= Pos(x, y, back - EPS) * Cylinder(P.M2_CLEAR_D / 2, P.JIG_T + 2 * EPS, align=BOTTOM)
        nut = extrude(RegularPolygon(nut_d / 2, 6), P.M2_NUT_T + EPS)
        jig -= Pos(x, y, back - EPS) * nut
    sx, sy = sensor_xy()
    pocket_w = P.SF_BOARD + P.JIG_POCKET_CLEAR
    floor = -jig_pocket_floor_depth()
    jig -= Pos(sx, sy, (floor + front) / 2 + EPS) * Box(pocket_w, pocket_w, front - floor + 2 * EPS)
    slot_len = P.JIG_D / 2 - (abs(sx) + pocket_w / 2) + 1.0
    jig -= Pos(sx - pocket_w / 2 - slot_len / 2 + 0.5, sy, (floor + front) / 2 + EPS) * Box(
        slot_len + 1.0, 8.0, front - floor + 2 * EPS
    )
    for k in range(36):
        angle = 10.0 * k
        if abs(angle - P.SENSOR_ANGLE_DEG) < P.TICK_SKIP_DEG or abs(angle - 90.0) < P.TICK_SKIP_TOP_DEG:
            continue
        r_out = P.TICK_R_OUT_LONG if k % 3 == 0 else P.TICK_R_OUT
        length = r_out - P.TICK_R_IN
        tick = Pos(P.TICK_R_IN + length / 2, 0, front - P.TICK_DEPTH / 2 + EPS) * Box(
            length, P.TICK_W, P.TICK_DEPTH + EPS
        )
        jig -= Rot(0, 0, angle) * tick
    ant_cx = 0.0
    ant_cy = (P.ANT_Y_TOP + P.ANT_Y_BOTTOM) / 2
    outline = Box(P.MODULE_W + 1.0, P.ANTENNA_L + 1.0, P.TICK_DEPTH + EPS) - Box(
        P.MODULE_W, P.ANTENNA_L, P.TICK_DEPTH + 2 * EPS
    )
    jig -= Pos(ant_cx, ant_cy, front - P.TICK_DEPTH / 2 + EPS) * outline
    return jig


def jig_spacer(thickness: float) -> Part:
    side = P.SF_BOARD
    spacer = Pos(0, 0, thickness / 2) * Box(side, side, thickness)
    corner = Pos(side / 2, side / 2, thickness / 2) * Rot(0, 0, 45) * Box(4.0, 4.0, thickness + EPS)
    return spacer - corner


def coupon_shaft() -> Part:
    """Stepped shaft: slide the bearing on from the top; it stops on the step that fits."""
    steps = (49.80, 49.90, 50.00, 50.10)  # top to bottom
    step_h = 2.0
    shaft = annulus(22.0, 27.0, -1.5, 0)  # handling flange, OD 54
    for i, d in enumerate(reversed(steps)):
        shaft += annulus(22.0, d / 2, i * step_h - EPS, (i + 1) * step_h)
    return shaft


def coupon_bore() -> Part:
    """Stepped bore: press the bearing in from the top; it stops on the step that fits.
    The top face also carries magnet pockets of 2.95, 3.05, 3.15 and 3.25 mm."""
    bores = (62.20, 62.10, 62.00, 61.90)  # top to bottom
    step_h = 2.0
    height = step_h * len(bores)
    part = disc(37.0, 0, height)
    for i, d in enumerate(bores):
        z1 = height - i * step_h + EPS
        part -= disc(d / 2, z1 - step_h - 2 * EPS, z1)
    for k, d in enumerate((2.95, 3.05, 3.15, 3.25)):
        x, y = polar(34.3, 45.0 + 90.0 * k)
        part -= Pos(x, y, height - P.MAG_POCKET_DEPTH) * Cylinder(d / 2, P.MAG_POCKET_DEPTH + EPS, align=BOTTOM)
    return part


def parts() -> dict[str, Part]:
    out = {
        "face_bezel": face_bezel(),
        "ring_a_bearing": ring_a(),
        "ring_b_bushing": ring_b(),
        "bushing_sleeve": bushing_sleeve(),
        "sensor_jig": sensor_jig(),
        "coupon_shaft": coupon_shaft(),
        "coupon_bore": coupon_bore(),
    }
    for n in P.MAGNET_COUNTS:
        out[f"magnet_carrier_{n}"] = magnet_carrier(n)
    for t in P.SPACER_T:
        out[f"jig_spacer_{t:.0f}mm"] = jig_spacer(t)
    return out


def export_all(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, part in parts().items():
        step = out_dir / f"{name}.step"
        stl = out_dir / f"{name}.stl"
        export_step(part, str(step))
        export_stl(part, str(stl), tolerance=0.01, angular_tolerance=0.1)
        written += [step, stl]
    return written


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    for path in export_all(root / "build" / "enclosure" / "ring-test"):
        print(path.relative_to(root))
