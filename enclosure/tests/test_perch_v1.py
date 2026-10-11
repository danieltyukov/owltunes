"""Perch v1: builds, holds the owl without interference, pins and magnets meet the owl's."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from build123d import Pos, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import owl_v1 as V  # noqa: E402
import perch_v1 as Q  # noqa: E402


@pytest.fixture(scope="module")
def perch():
    return Q.perch_body()


@pytest.fixture(scope="module")
def owl():
    return Q.owl_location() * (V.body() + V.back_cover())


def common_volume(a, b) -> float:
    c = a & b
    return c.volume if c is not None else 0.0


def rest_point(x: float, along: float, into: float) -> Vector:
    return Vector(*Q.owl_to_perch(x, Q.Y_BOT + along, into))


def test_perch_is_one_valid_solid(perch):
    assert perch.is_valid
    assert len(perch.solids()) == 1


def test_owl_back_points_land_on_the_rest_face():
    loc = Q.owl_location()
    for x, y in ((0.0, V.DOCK_PAD_Y), (20.0, -22.0), (-12.0, -34.0)):
        p = (loc * Pos(x, y, V.BACK_Z)).position
        q = Vector(*Q.owl_to_perch(x, y, 0.0))
        assert (p - q).length < 1e-6


def test_docked_owl_does_not_collide_with_the_perch(perch, owl):
    assert common_volume(perch, owl) < 1e-2


def test_seat_carries_the_owl(perch, owl):
    # R21: the owl's bottom bears on the seat; 0.1 mm further down it would cut into it
    t = Q.math.radians(Q.TILT_DEG)
    lowered = Pos(0, -0.1 * Q.math.sin(t), -0.1 * Q.math.cos(t)) * owl  # along the owl's -Y, parallel to the rest
    assert common_volume(perch, lowered) > 1.0


def test_pin_window_and_magnet_pockets_are_open(perch):
    for x in (-V.DOCK_PAD_PITCH, 0.0, V.DOCK_PAD_PITCH):
        assert not perch.is_inside(Vector(*Q.owl_to_perch(x, V.DOCK_PAD_Y, 1.0)))
    for x, y in V.DOCK_MAGNETS:
        assert not perch.is_inside(Vector(*Q.owl_to_perch(x, y, 1.6)))
        assert perch.is_inside(Vector(*Q.owl_to_perch(x, y, 0.3)))


def test_perch_board_fits_without_interference(perch):
    # R4: the board, its parts and the free pins sit in the pocket, cavity and pin window
    assert common_volume(perch, Q.board_envelope()) < 1e-3


def test_board_rests_on_bosses_with_screw_holes(perch):
    # R20: H1 and H2 meet bosses at the board top with a blind pilot hole for an M2 screw
    for hx, ha in Q.HOLES:
        along = Q.PAD_UP + ha
        assert perch.is_inside(rest_point(hx + 1.6, along, Q.BOARD_TOP_INTO - 0.3))
        assert not perch.is_inside(rest_point(hx, along, Q.BOARD_TOP_INTO - 2.0))
        assert perch.is_inside(rest_point(hx, along, 0.5))
        assert not perch.is_inside(rest_point(hx, along, Q.BOARD_TOP_INTO + 1.0))  # open behind


def test_usb_channel_runs_from_j1_to_the_side(perch):
    plug = Q.BOARD_TOP_INTO - Q.J1_PLUG_H
    for x in (Q.PERCH_BOARD[0] / 2 + 0.5, 30.0, Q.REST[0] / 2 - 0.5):
        assert not perch.is_inside(rest_point(x, Q.PAD_UP, plug))


def test_steel_weight_pocket_holds_200_g():
    w, d, h = Q.WEIGHT_POCKET
    assert (w - 2) * (d - 2) * (h - 0.2) / 1000 * 7.85 >= 195.0


def test_pins_use_the_drawing_stroke_and_stand_two_mm_proud():
    # R29: 7.0 mm free above the board, 1.0 mm working stroke
    assert Q.PIN_FREE_LEN == pytest.approx(7.0)
    assert Q.PIN_FREE_LEN - Q.PIN_WORK_LEN == pytest.approx(1.0)
    assert Q.PIN_PROUD == pytest.approx(2.0)
    # docked: the pad face sits PAD_RECESS past the rest face, so each pin is at its working height
    assert Q.BOARD_TOP_INTO + Q.PAD_RECESS == pytest.approx(Q.PIN_WORK_LEN)
