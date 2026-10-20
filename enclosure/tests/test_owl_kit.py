"""Owl v0 on the Waveshare kit: every part builds, nothing collides, the ring turns, key gaps hold."""

from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path

import pytest
from build123d import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import owl_kit as K  # noqa: E402
import owl_params as P  # noqa: E402
import pcb_contract as C  # noqa: E402


@pytest.fixture(scope="module")
def parts():
    return K.parts()


@pytest.fixture(scope="module")
def stack(parts):
    out = dict(parts)
    out.update(
        kit=K.kit_envelope(),
        usb_plug=K.usb_plug_envelope(),
        harness=K.harness_envelope(),
        battery_plug=K.battery_plug_envelope(),
        battery=K.battery_envelope(),
        tmag=K.tmag_envelope(),
        ear_switch_left=K.ear_switch_envelope(-1),
        ear_switch_right=K.ear_switch_envelope(1),
        beak_switch=K.beak_switch_envelope(),
        magnets=K.magnets(),
    )
    return out


def overlap_volume(a, b) -> float:
    common = a & b
    return common.volume if common is not None else 0.0


def test_every_part_is_one_valid_solid(parts):
    assert set(parts) == {"body", "ring", "bezel", "hub", "back_cover", "beak_key"}
    for name, part in parts.items():
        assert part.is_valid, name
        assert len(part.solids()) == 1, name


def test_every_part_meets_jlc3dp_minimum_size(parts):
    # JLC3DP's quote rejects a part smaller than 2 x 2 x 10 mm (MJF and resin, 20 October 2026)
    for name, part in parts.items():
        s = part.bounding_box().size
        size = sorted((s.X, s.Y, s.Z))
        assert size[0] >= 2.0 and size[1] >= 2.0 and size[2] >= 10.0, name


def test_outside_size(parts):
    size = parts["body"].bounding_box().size
    assert size.X == pytest.approx(C.BODY_W)
    assert size.Z == pytest.approx(K.FRONT_Z - K.BACK_Z)
    assert K.FRONT_Z - K.BACK_Z <= 20.0
    top = parts["body"].bounding_box().max.Y
    assert top == pytest.approx(K.TOP_Y + max(h for _, h in K.EAR_TUFT), abs=0.02)
    # a pressed tuft (the tab moves EAR_GAP plus the switch travel) stays clear of the fixed wall
    assert min(h for _, h in K.EAR_TUFT) > K.EAR_GAP + P.SWITCH_3X6_TRAVEL + 0.2


def test_nothing_collides(stack):
    clashes = []
    for (na, a), (nb, b) in itertools.combinations(stack.items(), 2):
        v = overlap_volume(a, b)
        if v > 1e-3:
            clashes.append((na, nb, round(v, 3)))
    assert clashes == []


def test_ring_turns_freely(stack):
    ring = stack["ring"]
    for name in ("body", "bezel", "hub", "kit", "beak_switch", "beak_key", "usb_plug"):
        assert ring.distance_to(stack[name]) >= K.CLEAR - 0.01, name


def test_ring_is_held_by_the_bezel_and_the_hub():
    assert K.BEZEL_R_OUT > K.RING_BORE_R + 0.8  # the bezel overlaps the ring's rebate
    assert K.RING_REBATE_Z < K.BEZEL_BACK_Z < K.FRONT_Z
    assert K.HUB_FRONT_Z == pytest.approx(K.RING_BACK_Z - K.CLEAR)


def test_ring_sides_are_exposed_for_the_thumb(parts):
    for s in (-1, 1):
        x = s * (K.RING_R - 0.3)
        assert parts["ring"].is_inside(Vector(x, 0, -2.0))
        assert not parts["body"].is_inside(Vector(s * (C.BODY_W / 2 - 0.1), 0, -2.0))


def test_kit_goes_in_through_the_bezel_and_tube():
    assert K.BEZEL_R_IN - K.GLASS_R >= 0.19
    assert K.TUBE_R_IN - K.GLASS_R >= 0.24


def test_kit_rests_on_the_arms(stack):
    for x, y in P.KIT_STANDOFFS:
        assert stack["hub"].is_inside(Vector(x + 1.5, y, K.ARM_FRONT_Z - 0.5))
    assert stack["kit"].distance_to(stack["hub"]) < 0.01


def test_hall_gap_matches_the_ring_test_design():
    assert 2.3 <= K.HALL_GAP <= 3.0
    r = math.hypot(*K.TMAG_XY)
    assert abs(r - K.MAG_R) <= 1.0


def test_magnet_pockets_leave_mjf_walls():
    outer = K.RING_R - (K.MAG_R + P.MAG_POCKET_D / 2)
    inner = (K.MAG_R - P.MAG_POCKET_D / 2) - K.RING_BORE_R
    assert outer >= P.MJF_MIN_WALL
    assert inner >= P.MJF_STRUCT_WALL


def test_usb_plug_reaches_the_kit(stack):
    plug = stack["usb_plug"]
    for name in ("body", "hub", "ring", "back_cover"):
        assert plug.distance_to(stack[name]) > 0.1, name


def test_ear_flexures_are_free_and_reach_their_switches(parts):
    body = parts["body"]
    z = K.ear_switch_z()
    for s in (-1, 1):
        tip = s * (K.EAR_TIP_X + K.EAR_SLOT / 2)
        assert not body.is_inside(Vector(tip, K.TOP_IN_Y + 0.8, z))
        assert body.is_inside(Vector(s * K.EAR_SWITCH_X, K.TOP_IN_Y + 0.8, z))
        gap = K.TOP_IN_Y - (K.ear_switch_base_y() + P.SWITCH_3X6[2])
        assert gap == pytest.approx(K.EAR_GAP)


def test_beak_key_rests_just_above_its_switch():
    assert K.beak_switch_top_z() + K.BEAK_GAP < K.FACE_BACK_Z
    assert K.BEAK_GAP + P.SWITCH_3X6_TRAVEL < 0.6


def test_battery_sits_behind_the_kit_and_in_front_of_the_cover():
    usb_back = K.KIT_PCB_BACK_Z - P.KIT_USB[2]
    assert K.BATTERY_FRONT_Z < usb_back - 0.5
    assert K.COVER_IN_Z < K.BATTERY_BACK_Z
