"""Checks for the ring test prints: valid solids, key fits, no interference, sensor geometry."""

from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path

import pytest
from build123d import Box, Cylinder, Edge, Part, Pos, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import owl_params as P  # noqa: E402
import ring_test as R  # noqa: E402


@pytest.fixture(scope="module")
def parts() -> dict[str, Part]:
    return R.parts()


def inside(part: Part, r: float, z: float, angle_deg: float = 45.0) -> bool:
    x, y = R.polar(r, angle_deg)
    return part.is_inside(Vector(x, y, z))


def sf_box(u0: float, u1: float, v0: float, v1: float, z0: float, z1: float) -> Part:
    """Box given in the SparkFun board frame, placed through the jig mapping."""
    xa, ya = R.sf_to_owl(u0, v0)
    xb, yb = R.sf_to_owl(u1, v1)
    return Pos((xa + xb) / 2, (ya + yb) / 2, (z0 + z1) / 2) * Box(abs(xb - xa), abs(yb - ya), z1 - z0)


def sparkfun_dummy(spacer: float) -> Part:
    """Board plus its two right-angle Qwiic connectors, sensor side facing the ring. Each connector
    body is drawn 0.7 longer at both ends than the footprint's silkscreen, but not past the board
    edge: the silkscreen ends 0.48 inside it, and the jig pocket leaves only JIG_POCKET_CLEAR / 2."""
    top = -(R.jig_pocket_floor_depth() - spacer - P.SF_BOARD_T)
    board = sf_box(0, P.SF_BOARD, 0, P.SF_BOARD, top - P.SF_BOARD_T, top)
    for (u, v), sign in ((P.SF_J1, -1), (P.SF_J2, 1)):
        u_edge = u + sign * P.SF_CONN_L
        board += sf_box(
            max(min(u, u_edge) - 0.7, 0.0), min(max(u, u_edge) + 0.7, P.SF_BOARD),
            v - P.SF_CONN_W / 2, v + P.SF_CONN_W / 2, top, top + P.SF_CONN_H,
        )
    return board


def test_every_part_is_one_valid_solid(parts):
    assert len(parts) == 12
    for name, part in parts.items():
        assert part.is_valid, name
        assert len(part.solids()) == 1, name
        assert part.volume > 100, name


def test_ring_outer_diameter_is_the_owl_width(parts):
    for name in ("ring_a_bearing", "ring_b_bushing"):
        size = parts[name].bounding_box().size
        assert size.X == pytest.approx(P.RING_OD, abs=0.01)
        assert size.Y == pytest.approx(P.RING_OD, abs=0.01)


def glass(d: float, front: float = 0.0) -> Part:
    return Pos(0, 0, front - P.GLASS_T) * Cylinder(d / 2, P.GLASS_T, align=R.BOTTOM)


def test_glass_drops_in_from_the_front_onto_the_ledge_and_cannot_fall_out_the_back(parts):
    bezel = parts["face_bezel"]
    # the ledge is the bezel's front face, flush with the bearing's, one tape thickness behind the
    # glass; the glass front is the reference plane z = 0
    assert P.BRG_FRONT_DEPTH == pytest.approx(P.GLASS_T + P.GLASS_TAPE_T)
    assert bezel.bounding_box().max.Z == pytest.approx(-P.BRG_FRONT_DEPTH)
    assert R.bearing_dummy().bounding_box().max.Z == pytest.approx(-P.BRG_FRONT_DEPTH)
    # the largest glass drops in from the front past the ring lip without touching any part
    largest = P.GLASS_D + P.GLASS_D_TOL
    stack = [bezel, R.bearing_dummy(), parts["bushing_sleeve"], parts["ring_a_bearing"], parts["ring_b_bushing"]]
    for dz in (6.0, 3.0, 1.5, 0.5, 0.0):
        for part in stack:
            overlap = glass(largest, dz) & part
            assert (overlap.volume if overlap is not None else 0.0) < 1e-3, dz
    # pushed back past its tape, the smallest glass meets the ledge: it cannot fall out the back
    overlap = glass(P.GLASS_D - P.GLASS_D_TOL, -P.GLASS_TAPE_T - 0.05) & bezel
    assert overlap is not None and overlap.volume > 0.01
    # the ledge is solid from the panel opening to the seat, and the panel opening stays clear
    for r in (P.PANEL_POCKET_D / 2 + 0.1, P.BRG_SEAT_D / 2 - 0.1):
        assert inside(bezel, r, -P.BRG_FRONT_DEPTH - 0.1)
    assert not inside(bezel, P.PANEL_POCKET_D / 2 - 0.2, -P.BRG_FRONT_DEPTH - 0.1)
    # the glass border covers the ledge and reaches over the inner race face, 0.2 in front of it,
    # but stays inside the race, clear of the shields
    assert (P.GLASS_D - P.GLASS_D_TOL) / 2 > P.BRG_ID / 2
    assert (P.GLASS_D + P.GLASS_D_TOL) / 2 < P.BRG_INNER_RACE_OD / 2


def test_bearing_seat_and_bores(parts):
    bezel = parts["face_bezel"]
    assert inside(bezel, P.BRG_SEAT_D / 2 - 0.05, -3.0)
    assert not inside(bezel, P.BRG_SEAT_D / 2 + 0.05, -3.0)
    ring_a = parts["ring_a_bearing"]
    assert not inside(ring_a, P.RING_A_BORE_D / 2 - 0.05, -3.0)
    assert inside(ring_a, P.RING_A_BORE_D / 2 + 0.05, -3.0)
    ring_b = parts["ring_b_bushing"]
    assert not inside(ring_b, P.RING_B_BORE_D / 2 - 0.05, -3.0)
    assert inside(ring_b, P.RING_B_BORE_D / 2 + 0.05, -3.0)


ASSEMBLY = ("face_bezel", "ring_a_bearing", "ring_b_bushing", "bushing_sleeve", "sensor_jig")


def test_nothing_covers_the_viewing_area(parts):
    # nothing stands in front of the viewing area, and nothing reaches into the largest glass's edge
    for part in [parts[n] for n in ASSEMBLY] + [parts["magnet_carrier_24"]]:
        for angle in range(0, 360, 15):
            assert not inside(part, P.VIEW_D / 2, P.LIP_T / 2, angle)
            assert not inside(part, (P.GLASS_D + P.GLASS_D_TOL) / 2, -P.GLASS_T / 2, angle)


@pytest.mark.parametrize("name", ["ring_a_bearing", "ring_b_bushing"])
def test_ring_lip_clears_the_largest_glass_and_stands_lip_t_proud(parts, name):
    # the lip opening clears the glass edge by 0.4 or more, also at the drawing's +-0.20
    assert (P.RING_LIP_ID - P.GLASS_D - P.GLASS_D_TOL) / 2 >= 0.4
    assert (P.RING_LIP_ID - P.GLASS_D - 0.2) / 2 >= 0.4 - 1e-9
    assert P.RING_CONTACT_R * 2 > P.BRG_OUTER_RACE_ID
    ring = parts[name]
    assert ring.bounding_box().max.Z == pytest.approx(P.LIP_T)
    assert inside(ring, P.RING_LIP_ID / 2 + 0.05, P.LIP_T - 0.05)
    assert not inside(ring, P.RING_LIP_ID / 2 - 0.05, P.LIP_T - 0.05)
    # the contact face rests on the outer race at the bearing's front face; inside RING_CONTACT_R the
    # lip clears the inner race and the shields by LIP_RELIEF
    assert inside(ring, P.RING_CONTACT_R + 0.3, -P.BRG_FRONT_DEPTH + 0.05)
    assert not inside(ring, P.RING_CONTACT_R + 0.3, -P.BRG_FRONT_DEPTH - 0.05)
    relieved = (P.RING_LIP_ID / 2 + P.RING_CONTACT_R) / 2
    assert not inside(ring, relieved, -P.BRG_FRONT_DEPTH + P.LIP_RELIEF - 0.05)
    assert inside(ring, relieved, -P.BRG_FRONT_DEPTH + P.LIP_RELIEF + 0.05)


@pytest.mark.parametrize("count", P.MAGNET_COUNTS)
@pytest.mark.parametrize("variant", ["a", "b"])
def test_assembly_has_no_interference(parts, variant, count):
    if variant == "a":
        stack = [parts["face_bezel"], R.bearing_dummy(), parts["ring_a_bearing"]]
    else:
        stack = [parts["face_bezel"], parts["bushing_sleeve"], parts["ring_b_bushing"]]
    stack += [parts[f"magnet_carrier_{count}"], parts["sensor_jig"], sparkfun_dummy(spacer=3.0)]
    for a, b in itertools.combinations(stack, 2):
        overlap = a & b
        volume = overlap.volume if overlap is not None else 0.0
        assert volume < 1e-3


def test_bearing_and_carrier_slide_on_from_the_back(parts):
    bezel = parts["face_bezel"]
    box = bezel.bounding_box()
    assert P.TUBE_OD < P.BRG_SEAT_D <= P.BRG_ID
    assert P.TUBE_OD < P.CARRIER_ID
    for angle in P.LUG_ANGLES_DEG:
        for da in (-12.0, -6.0, 0.0, 6.0, 12.0):
            z = -P.TUBE_END_DEPTH - P.LUG_T / 2
            assert not inside(bezel, P.BRG_ID / 2 - 0.05, z, angle + da)
    # nothing on the bezel is wider than the seat, and no lip stands in front of the bearing: on a
    # flat plate the bearing (or sleeve) front face comes flush with the bezel's front face
    assert max(box.max.X, box.max.Y, -box.min.X, -box.min.Y) <= P.BRG_SEAT_D / 2 + 1e-6
    for part in (R.bearing_dummy(), parts["bushing_sleeve"]):
        assert part.bounding_box().max.Z == pytest.approx(box.max.Z)


def test_jig_gives_the_planned_gaps():
    floor = R.jig_pocket_floor_depth()
    for spacer, gap in zip((0.0, *P.SPACER_T), P.HALL_GAP_STEPS):
        hall_depth = floor - spacer - P.SF_BOARD_T - P.HALL_ELEMENT_H
        assert hall_depth - P.magnet_face_depth() == pytest.approx(gap)
    # the 2 mm spacer gives the product gap, and the jig floor under the pocket stays 1.3 thick
    assert P.HALL_GAP_STEPS[2] == pytest.approx(P.HALL_GAP_NOMINAL)
    assert P.JIG_FRONT_DEPTH + P.JIG_T - floor == pytest.approx(1.3)


def test_sparkfun_board_seats_in_the_jig_with_every_spacer(parts):
    for spacer in (0.0, *P.SPACER_T):
        overlap = parts["sensor_jig"] & sparkfun_dummy(spacer)
        assert (overlap.volume if overlap is not None else 0.0) < 1e-3, spacer


def test_sensor_position_is_the_pcb_contract():
    x, y = R.sensor_xy()
    assert x == pytest.approx(-P.R_TRACK)
    assert y == pytest.approx(0.0, abs=1e-9)
    assert P.pcb_front_depth() == pytest.approx(10.5)
    carrier_back = P.CARRIER_REAR_DEPTH
    assert carrier_back == pytest.approx(9.5)
    assert P.pcb_front_depth() - carrier_back >= 1.0 - 1e-9
    # the polarity bumps exist on the test carriers only (the product carrier uses bumps=False);
    # they stand behind the rear face but must not reach the board
    bump_back = carrier_back + P.POLARITY_BUMP_H
    assert P.pcb_front_depth() - bump_back >= -1e-9


def test_magnet_face_is_where_a_seated_magnet_sits(parts):
    assert P.magnet_face_depth() == pytest.approx(P.CARRIER_REAR_DEPTH - (P.MAG_POCKET_DEPTH - P.MAG_H))
    assert P.MAG_POCKET_DEPTH >= P.MAG_H
    assert P.magnet_face_depth() == pytest.approx(9.5)
    # the Hall element sits HALL_ELEMENT_H behind the board's back face
    assert P.pcb_front_depth(2.7) + P.PCB_T + P.HALL_ELEMENT_H - P.magnet_face_depth() == pytest.approx(2.7)
    # the pockets open in the rear face with a 1.0 floor in front of them, the ring body ends at the
    # floor, and the flange sits beside the magnets: without bumps nothing stands behind their faces
    carrier = parts["magnet_carrier_24"]
    floor = P.CARRIER_REAR_DEPTH - P.MAG_POCKET_DEPTH
    assert floor - P.CARRIER_FRONT_DEPTH == pytest.approx(P.MJF_STRUCT_WALL)
    assert P.RING_REAR_DEPTH == pytest.approx(floor)
    assert not inside(carrier, P.R_TRACK, -floor - 0.05, 0.0)
    assert inside(carrier, P.R_TRACK, -floor + 0.05, 0.0)
    assert inside(carrier, (P.CARRIER_FLANGE_R_IN + P.RING_OD / 2) / 2, -P.magnet_face_depth() + 0.05, 0.0)
    assert R.magnet_carrier(24, bumps=False).bounding_box().min.Z == pytest.approx(-P.magnet_face_depth())
    for name in ("ring_a_bearing", "ring_b_bushing"):
        assert parts[name].bounding_box().min.Z == pytest.approx(-P.RING_REAR_DEPTH)


def test_carrier_fits_both_rings_with_real_clearance(parts):
    for bore in (P.RING_A_BORE_D, P.RING_B_BORE_D):
        assert (bore - P.CARRIER_OD) / 2 >= P.CARRIER_FIT_CLEARANCE / 2 - 1e-9
    carrier = parts["magnet_carrier_24"]
    assert carrier.bounding_box().size.X == pytest.approx(P.RING_OD, abs=0.01)
    body_z = -(P.CARRIER_FRONT_DEPTH + P.RING_REAR_DEPTH) / 2
    assert inside(carrier, P.CARRIER_OD / 2 - 0.05, body_z, 7.0)
    assert not inside(carrier, P.CARRIER_OD / 2 + 0.05, body_z, 7.0)
    for name in ("ring_a_bearing", "ring_b_bushing"):
        ring = parts[name]
        assert inside(ring, P.CARRIER_OD / 2 + 0.05, body_z, 7.0) is False
        overlap = ring & carrier
        assert (overlap.volume if overlap is not None else 0.0) < 1e-3
        # a 0.1 mm radial gap exists between the carrier body and the ring bore
        assert not inside(ring, P.CARRIER_OD / 2 + 0.05, body_z, 7.0)
        assert not inside(carrier, ring_bore_radius(name) - 0.05, body_z, 7.0)


def ring_bore_radius(name: str) -> float:
    return (P.RING_A_BORE_D if name == "ring_a_bearing" else P.RING_B_BORE_D) / 2


def test_oring_squeeze_and_stretch():
    groove_d = P.SLEEVE_OD - 2 * P.ORING_GROOVE_DEPTH
    stretch = (groove_d - P.ORING_ID) / P.ORING_ID
    gap = (P.RING_B_BORE_D - groove_d) / 2
    squeeze = 1 - gap / P.ORING_CS
    assert 0 <= stretch <= 0.03
    assert 0.15 <= squeeze <= 0.20
    assert P.ORING_ID + 2 * P.ORING_CS == pytest.approx(P.RING_B_BORE_D)
    assert P.ORING_GROOVE_W > P.ORING_CS


def test_jig_pocket_floor_corners_and_board_probes(parts):
    jig = parts["sensor_jig"]
    floor = -R.jig_pocket_floor_depth()
    sx, sy = R.sensor_xy()
    # the chip position is where the PCB sensor goes, and the pocket floor lies right under it
    assert (sx, sy) == (pytest.approx(-28.0), pytest.approx(0.0, abs=1e-9))
    assert jig.is_inside(Vector(sx, sy, floor - 0.1))
    assert not jig.is_inside(Vector(sx, sy, floor + 0.1))
    # the board outline sits inside the pocket: just inside each corner is empty, just outside solid
    for u, v in ((0, 0), (P.SF_BOARD, 0), (0, P.SF_BOARD), (P.SF_BOARD, P.SF_BOARD)):
        cx, cy = R.sf_board_centre()
        x, y = R.sf_to_owl(u, v)
        ix = x + math.copysign(0.1, cx - x)
        iy = y + math.copysign(0.1, cy - y)
        assert not jig.is_inside(Vector(ix, iy, floor + 0.5)), (u, v)
        ox = x + math.copysign(P.JIG_POCKET_CLEAR / 2 + 0.3, x - cx)
        oy = y + math.copysign(P.JIG_POCKET_CLEAR / 2 + 0.3, y - cy)
        assert jig.is_inside(Vector(ox, oy, floor + 0.5)), (u, v)
    # the cable slot lines up with connector J2 and runs out to the plate rim
    j2x, j2y = R.sf_to_owl(*P.SF_J2)
    for x in (-42.0, -44.0, -45.0):
        assert not jig.is_inside(Vector(x, j2y, floor + 0.5)), x
        assert not jig.is_inside(Vector(x, j2y + P.SF_CABLE_SLOT_W / 2 - 0.2, floor + 0.5)), x
        assert jig.is_inside(Vector(x, j2y + P.SF_CABLE_SLOT_W / 2 + 0.3, floor + 0.5)), x
    # the J1 side faces the centre and stays inside the pocket, which is closed towards the centre
    j1x, j1y = R.sf_to_owl(*P.SF_J1)
    assert not jig.is_inside(Vector(j1x + 2.0, j1y, floor + 0.5))
    assert jig.is_inside(Vector(R.sf_board_centre()[0] + P.SF_BOARD / 2 + 1.0, j1y, floor + 0.5))


def test_jig_screw_holes_and_nut_pockets(parts):
    jig = parts["sensor_jig"]
    back = -(P.JIG_FRONT_DEPTH + P.JIG_T)
    circum = (P.M2_NUT_AF + P.M2_NUT_AF_CLEAR) / math.cos(math.radians(30)) / 2
    for angle in P.LUG_ANGLES_DEG:
        x, y = R.polar(P.LUG_HOLE_R, angle)
        # through hole
        assert not jig.is_inside(Vector(x, y, back + P.JIG_T / 2))
        assert jig.is_inside(Vector(x + P.M2_CLEAR_D / 2 + 0.3, y, back + P.JIG_T / 2))
        # hex pocket on the back: open at the corner of the hex, flat-to-flat wider than the nut
        assert not jig.is_inside(Vector(x + circum - 0.1, y, back + 0.5))
        assert jig.is_inside(Vector(x + circum + 0.2, y, back + 0.5))
        flat = (P.M2_NUT_AF + P.M2_NUT_AF_CLEAR) / 2
        assert not jig.is_inside(Vector(x, y + flat - 0.05, back + 0.5))
        assert jig.is_inside(Vector(x, y + flat + 0.2, back + 0.5))
        # pocket depth: nut thickness plus clearance, with solid above it
        depth = P.M2_NUT_T + P.M2_NUT_DEPTH_CLEAR
        assert not jig.is_inside(Vector(x + circum - 0.3, y, back + depth - 0.05))
        assert jig.is_inside(Vector(x + circum - 0.3, y, back + depth + 0.2))
    assert P.M2_NUT_AF_CLEAR >= 0.2 and P.M2_NUT_DEPTH_CLEAR >= 0.2


PROBE_ANGLES = (0.0, 7.0, 45.0, 90.0, 180.0, 215.0, 300.0)
# Per part: (z0, z1) zones that are cosmetic or glass-fit features and are judged against
# MJF_MIN_WALL, and zones that are skipped (engraved lines and bumps are not walls).
PART_ZONES = {
    "magnet_carrier_24": {"min": [], "skip": [(-(P.CARRIER_REAR_DEPTH + 0.5), -P.CARRIER_REAR_DEPTH)]},
    "magnet_carrier_32": {"min": [], "skip": [(-(P.CARRIER_REAR_DEPTH + 0.5), -P.CARRIER_REAR_DEPTH)]},
    "sensor_jig": {"min": [], "skip": [(-P.JIG_FRONT_DEPTH - P.TICK_DEPTH - 0.01, -P.JIG_FRONT_DEPTH + 0.01)]},
}


def chords(part: Part, p0: tuple[float, float, float], p1: tuple[float, float, float]):
    """Solid chords of the line p0 to p1 through the part: (length, z_low, z_high) each."""
    hit = part & Edge.make_line(Vector(*p0), Vector(*p1))
    out = []
    for edge in hit.edges() if hit else []:
        box = edge.bounding_box()
        out.append((edge.length, box.min.Z, box.max.Z))
    return out


def probe_lines(part: Part):
    box = part.bounding_box()
    r_max = max(box.max.X, box.max.Y, -box.min.X, -box.min.Y) + 2.0
    lines = []
    z = box.min.Z + 0.13
    while z < box.max.Z:
        for a in PROBE_ANGLES:
            lines.append(((*R.polar(0.5, a), z), (*R.polar(r_max, a), z)))
        z += 0.5
    r = 12.13
    while r < r_max - 2.0:
        for a in PROBE_ANGLES:
            x, y = R.polar(r, a)
            lines.append(((x, y, box.min.Z - 1.0), (x, y, box.max.Z + 1.0)))
        r += 0.5
    for a in (0.0, 15.0):
        x, y = R.polar(P.R_TRACK, a)
        lines.append(((x, y, box.min.Z - 1.0), (x, y, box.max.Z + 1.0)))
    return lines


def thinnest_wall(name: str, part: Part) -> float:
    """Thinnest chord found over radial and axial probe lines, judged per zone class. Returns the
    smallest margin-corrected value: chord length for the structural class, and chord length plus
    the difference between the two classes for the glass-fit zone, so one threshold fits all."""
    zones = PART_ZONES.get(name, {"min": [], "skip": []})
    worst = float("inf")
    for p0, p1 in probe_lines(part):
        for length, z_low, z_high in chords(part, p0, p1):
            if any(z_high > lo and z_low < hi for lo, hi in zones["skip"]):
                continue
            allowance = 0.0
            if any(z_low >= lo - 1e-6 and z_high <= hi + 1e-6 for lo, hi in zones["min"]):
                allowance = P.MJF_STRUCT_WALL - P.MJF_MIN_WALL
            worst = min(worst, length + allowance)
    return worst


def test_wall_classes_are_ordered():
    assert P.MJF_MIN_WALL == 0.8
    assert P.MJF_STRUCT_WALL == 1.0


@pytest.mark.parametrize(
    "name",
    [
        "face_bezel",
        "ring_a_bearing",
        "ring_b_bushing",
        "bushing_sleeve",
        "magnet_carrier_24",
        "magnet_carrier_32",
        "sensor_jig",
        "jig_spacer_1mm",
        "coupon_shaft",
        "coupon_bore",
    ],
)
def test_walls_meet_the_jlc3dp_mjf_minimum(parts, name):
    assert thinnest_wall(name, parts[name]) >= P.MJF_STRUCT_WALL - 1e-6, name


def test_export_writes_step_and_stl(tmp_path):
    written = R.export_all(tmp_path)
    assert len(written) == 24
    for path in written:
        assert path.stat().st_size > 500, path.name
