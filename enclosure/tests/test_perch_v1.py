"""Perch v1: builds, holds the owl without interference, pins and magnets meet the owl's."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest
from build123d import Box, Pos, Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import owl_params as P  # noqa: E402
import owl_v1 as V  # noqa: E402
import perch_v1 as Q  # noqa: E402


@pytest.fixture(scope="module")
def perch():
    return Q.perch_body()


@pytest.fixture(scope="module")
def plain_perch():
    return Q.perch_body(mark=False)


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
        assert not perch.is_inside(rest_point(x, Q.PAD_UP + Q.J1_ALONG, plug))


def test_usb_channel_takes_the_largest_type_c_overmold(perch):
    # R48: 12.35 x 6.5 mm overmold, slot at least 13.0 x 7.0, from J1's face out of the side
    assert Q.USB_SLOT[0] >= 13.0 and Q.USB_SLOT[1] >= 7.0
    x0 = Q.PERCH_BOARD[0] / 2 + 0.5
    length = Q.BASE[0] / 2 + 2.0 - x0
    plug = Q.rest_box(x0 + length / 2, Q.PAD_UP + Q.J1_ALONG, Q.BOARD_TOP_INTO - Q.J1_PLUG_H,
                      (length, Q.OVERMOLD[1], Q.OVERMOLD[0]))
    assert common_volume(perch, plug) < 1e-3


def test_neck_nub_has_relief_in_both_pockets(perch):
    # R46: the board envelope carries a 0.6 mm nub (zero-interference test above); the owl's
    # dock-pad recess has the same relief at the board's top edge, clear of the battery margin
    cover = V.back_cover()
    rw, rd = V.DOCK_NECK_RELIEF
    y = V.DOCK_BOARD_Y + V.DOCK_BOARD[1] / 2 + Q.NUB - 0.05
    z = V.BATTERY_BACK_Z - V.DOCK_BOARD[2] / 2
    assert rd >= Q.NUB + 0.2 and rw >= Q.NECK + 0.8
    assert not cover.is_inside(Vector(0.0, y, z))
    assert cover.is_inside(Vector(rw / 2 + 0.3, y, z))


def test_steel_weight_pocket_holds_200_g():
    w, d, h = Q.WEIGHT_POCKET
    assert (w - 2) * (d - 2) * (h - 0.2) / 1000 * 7.85 >= 195.0


def test_pins_use_the_drawing_stroke_and_stand_two_mm_proud():
    # R29: 7.0 mm free above the board (design.toml height), 1.0 mm working stroke
    design = tomllib.loads((ROOT / "hardware" / "perch-dock" / "design.toml").read_text())
    pins = [p for p in design["part"] if p["ref"] in ("P1", "P2", "P3")]
    assert [p["height"] for p in pins] == [Q.PIN_FREE_LEN] * 3
    assert Q.PIN_FREE_LEN - Q.PIN_WORK_LEN == pytest.approx(1.0)
    assert Q.PIN_PROUD == pytest.approx(2.0)


def test_docked_owl_compresses_each_pin_to_its_working_height():
    # the pad face is the back cover's recess floor, seen through the pad window; measure where it
    # lands in the docked owl and how long each pin is when it touches it
    t = Q.math.radians(Q.TILT_DEG)
    n = Vector(0, Q.math.cos(t), -Q.math.sin(t))  # into the rest
    cover = V.back_cover()
    face_z = V.BATTERY_BACK_Z - V.DOCK_BOARD[2]
    for x in (-V.DOCK_PAD_PITCH, 0.0, V.DOCK_PAD_PITCH):
        assert not cover.is_inside(Vector(x, V.DOCK_PAD_Y, face_z - 0.5))  # window open to the pin
        assert cover.is_inside(Vector(x + 2.5, V.DOCK_PAD_Y, face_z - 0.5))
        pad = (Q.owl_location() * Pos(x, V.DOCK_PAD_Y, face_z)).position
        into = (pad - Vector(*Q.owl_to_perch(x, V.DOCK_PAD_Y, 0.0))).dot(n)
        length = Q.BOARD_TOP_INTO - into
        assert length == pytest.approx(Q.PIN_WORK_LEN, abs=0.05)
        assert Q.PIN_FREE_LEN - length >= 0.95


def test_mark_is_debossed_into_the_underside(perch, plain_perch):
    area = sum(f.area for f in V.mark_faces())
    assert plain_perch.volume - perch.volume == pytest.approx(area * P.MARK_DEPTH, rel=1e-3)
    cut = (plain_perch - perch).bounding_box()
    assert cut.min.Z == pytest.approx(0.0, abs=1e-3)
    assert cut.max.Z == pytest.approx(P.MARK_DEPTH, abs=1e-3)
    # on the left strip, inside the 1.0 walls to the base's side and the weight pocket, and clear
    # of the feet at both ends
    x0, x1 = Q.STRIP_X
    assert cut.min.X - x0 >= P.MJF_STRUCT_WALL and x1 - cut.max.X >= P.MJF_STRUCT_WALL
    y0, y1 = Q.underside_y()
    assert cut.min.Y - y0 >= Q.FOOT_ZONE and y1 - cut.max.Y >= Q.FOOT_ZONE
    # it reads front to back from the left side: the T comes first, its bar towards the pocket
    x, y, z = cut.max.X - 0.3, cut.min.Y + 0.3, P.MARK_DEPTH / 2
    assert not perch.is_inside(Vector(x, y, z))
    assert perch.is_inside(Vector(x - 2.0, y, z))


def test_mark_keeps_solid_material_round_it(perch, plain_perch):
    # the unmarked perch is solid within 1.0 of the mark and 1.0 above its floor: the mark is clear
    # of the weight pocket, the base's edges and the USB channel
    cut = (plain_perch - perch).bounding_box()
    m = P.MJF_STRUCT_WALL
    size = (cut.size.X + 2 * m, cut.size.Y + 2 * m, P.MARK_DEPTH + m)
    block = Pos(cut.center().X, cut.center().Y, size[2] / 2) * Box(*size)
    assert common_volume(plain_perch, block) == pytest.approx(block.volume, rel=1e-6)
