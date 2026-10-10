"""Checks for the ring test prints: valid solids, key fits, no interference, sensor geometry."""

from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path

import pytest
from build123d import Box, Part, Pos, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import owl_params as P  # noqa: E402
import ring_test as R  # noqa: E402


@pytest.fixture(scope="module")
def parts() -> dict[str, Part]:
    return R.parts()


def inside(part: Part, r: float, z: float, angle_deg: float = 45.0) -> bool:
    x, y = R.polar(r, angle_deg)
    return part.is_inside(Vector(x, y, z))


def sparkfun_dummy(spacer: float) -> Part:
    """Board plus its two right-angle Qwiic connectors, sensor side facing the ring."""
    top = -(R.jig_pocket_floor_depth() - spacer - P.SF_BOARD_T)
    sx, sy = R.sensor_xy()
    board = Pos(sx, sy, top - P.SF_BOARD_T / 2) * Box(P.SF_BOARD, P.SF_BOARD, P.SF_BOARD_T)
    for dx in (5.08 - 12.7, 20.32 - 12.7):
        board += Pos(sx + dx, sy, top + P.SF_CONN_H / 2) * Box(4.3, 6.0, P.SF_CONN_H)
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
    for part in [parts[n] for n in ASSEMBLY] + [parts["magnet_carrier_24"]]:
        for angle in range(0, 360, 15):
            assert not inside(part, P.VIEW_D / 2, P.LIP_T / 2, angle)


def test_bezel_lip_stays_inside_the_inner_race_and_ring_lip_clears_it(parts):
    assert P.BEZEL_LIP_OD < P.BRG_INNER_RACE_OD
    assert P.RING_CONTACT_R * 2 > P.BRG_OUTER_RACE_ID
    ring = parts["ring_a_bearing"]
    assert not inside(ring, (P.RING_LIP_ID / 2 + P.RING_CONTACT_R) / 2, P.LIP_RELIEF / 2)
    assert inside(ring, P.RING_CONTACT_R + 0.3, P.LIP_T / 2)


@pytest.mark.parametrize("variant", ["a", "b"])
def test_assembly_has_no_interference(parts, variant):
    if variant == "a":
        stack = [parts["face_bezel"], R.bearing_dummy(), parts["ring_a_bearing"]]
    else:
        stack = [parts["face_bezel"], parts["bushing_sleeve"], parts["ring_b_bushing"]]
    stack += [parts["magnet_carrier_24"], parts["sensor_jig"], sparkfun_dummy(spacer=3.0)]
    for a, b in itertools.combinations(stack, 2):
        overlap = a & b
        volume = overlap.volume if overlap is not None else 0.0
        assert volume < 1e-3


def test_bearing_and_carrier_slide_on_from_the_back(parts):
    bezel = parts["face_bezel"]
    behind_seat = bezel.bounding_box()
    assert P.TUBE_OD < P.BRG_SEAT_D <= P.BRG_ID
    assert P.TUBE_OD < P.CARRIER_ID
    for angle in P.LUG_ANGLES_DEG:
        for da in (-12.0, -6.0, 0.0, 6.0, 12.0):
            z = -P.TUBE_END_DEPTH - P.LUG_T / 2
            assert not inside(bezel, P.BRG_ID / 2 - 0.05, z, angle + da)
    assert behind_seat.max.X <= P.BEZEL_LIP_OD / 2 + 1e-6


def test_jig_gives_the_planned_gaps():
    floor = R.jig_pocket_floor_depth()
    for spacer, gap in zip((0.0, *P.SPACER_T), P.HALL_GAP_STEPS):
        hall_depth = floor - spacer - P.SF_BOARD_T - P.HALL_ELEMENT_H
        assert hall_depth - P.magnet_face_depth() == pytest.approx(gap)


def test_sensor_position_is_the_pcb_contract():
    x, y = R.sensor_xy()
    assert x == pytest.approx(-P.R_TRACK)
    assert y == pytest.approx(0.0, abs=1e-9)
    assert P.pcb_front_depth() == pytest.approx(10.5)
    carrier_back = P.RING_REAR_DEPTH + P.CARRIER_FLANGE_T
    assert P.pcb_front_depth() - carrier_back >= 0.5 - 1e-9


def test_thin_walls_meet_the_mjf_minimum():
    min_wall = 0.8
    assert (P.BRG_SEAT_D - P.GLASS_POCKET_D) / 2 >= min_wall - 1e-9
    assert P.BRG_SEAT_D / 2 - P.FPC_NOTCH_R >= min_wall - 1e-9
    assert P.R_TRACK - P.MAG_POCKET_D / 2 - P.CARRIER_ID / 2 >= min_wall
    assert P.RING_REAR_DEPTH - P.CARRIER_FRONT_DEPTH - P.MAG_POCKET_DEPTH >= min_wall - 1e-9
    assert P.LIP_T - P.LIP_RELIEF >= min_wall
    assert P.RING_A_BORE_D / 2 - 0.05 - (P.R_TRACK + P.MAG_POCKET_D / 2) >= min_wall
    for count in P.MAGNET_COUNTS:
        pitch = 2 * math.pi * P.R_TRACK / count
        assert pitch - P.MAG_POCKET_D >= min_wall


def test_export_writes_step_and_stl(tmp_path):
    written = R.export_all(tmp_path)
    assert len(written) == 24
    for path in written:
        assert path.stat().st_size > 500, path.name
