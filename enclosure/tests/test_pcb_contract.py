"""The board outline and fixed placements that enclosure v1 hands to the PCB layout."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import owl_params as P  # noqa: E402
import pcb_contract as C  # noqa: E402

POLY = C.outline_polygon()
OVERHANG = {"U201": ("top", P.ANTENNA_L + 0.01), "J201": ("bottom", 1.0)}
EAR_SWITCHES = ("SW201", "SW202")


def corners(box):
    x0, y0, x1, y1 = box
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def placement(ref):
    return next(q for q in C.PLACEMENTS if q.ref == ref)


def test_outline_is_closed():
    segs = C.outline_segments()
    for a, b in zip(segs, segs[1:] + segs[:1]):
        assert math.dist(a["end"], b["start"]) < 1e-9


def test_outline_fits_inside_the_body_walls():
    for x, y in POLY:
        assert abs(x) <= C.BODY_W / 2 - C.PCB_INSET + 1e-9
        assert C.BODY_CY - C.BODY_H / 2 + C.PCB_INSET - 1e-9 <= y <= C.BODY_CY + C.BODY_H / 2 - C.PCB_INSET + 1e-9


def test_antenna_overhangs_the_notch():
    assert not C.point_in_polygon(0.0, C.ANT_BOARD_EDGE_Y + 0.5, POLY)
    assert not C.point_in_polygon(C.ANT_NOTCH_HALF_W - 0.5, C.ANT_BOARD_EDGE_Y + 3.0, POLY)
    assert C.point_in_polygon(C.ANT_NOTCH_HALF_W + 0.5, C.ANT_BOARD_EDGE_Y + 3.0, POLY)


def test_footprint_frame_matches_kicad():
    # Checked with pcbnew 10.0.6 (Flip LEFT_RIGHT, then SetOrientationDegrees): a back-side
    # footprint at rot 0 keeps +u to the right and puts its +v (down in the footprint editor) up.
    back = C.Placement("X", 10.0, 20.0, 0.0, "back", 1.0, 1.0, 1.0, "")
    assert C.local_to_owl(back, 1.0, 2.0) == pytest.approx((11.0, 22.0))
    front = C.Placement("X", 10.0, 20.0, 90.0, "front", 1.0, 1.0, 1.0, "")
    assert C.local_to_owl(front, 1.0, 0.0) == pytest.approx((10.0, 21.0))
    assert C.local_to_owl(front, 0.0, 1.0) == pytest.approx((11.0, 20.0))
    back90 = C.Placement("X", 0.0, 0.0, 90.0, "back", 1.0, 1.0, 1.0, "")
    assert C.local_to_owl(back90, 0.0, 1.0) == pytest.approx((-1.0, 0.0))


def test_module_antenna_points_into_the_notch():
    # The WROOM-1 footprint draws its antenna at negative v ("Antenna" text at v = -9.44).
    u201 = placement("U201")
    _, y = C.local_to_owl(u201, 0.0, -9.44)
    assert y > C.ANT_BOARD_EDGE_Y
    assert C.footprint_box(u201)[3] == pytest.approx(P.ANT_Y_TOP)


@pytest.mark.parametrize("p", C.PLACEMENTS, ids=lambda p: p.ref)
def test_every_fixed_part_sits_on_the_board(p):
    x0, y0, x1, y1 = C.footprint_box(p)
    if p.ref in OVERHANG:
        edge, allowed = OVERHANG[p.ref]
        if edge == "top":
            y1 -= allowed
        else:
            y0 += allowed
    for x, y in corners((x0, y0, x1, y1)):
        assert C.point_in_polygon(x, y, POLY), (p.ref, x, y)


@pytest.mark.parametrize("ref", EAR_SWITCHES)
def test_ear_switch_actuators_face_up(ref):
    # EVQ-P7A (Panasonic EVQP7 catalogue, 01 Sep 2013, p. 2): body 3.5 x 2.9, 4.7 over the
    # terminals, knob 1.7 wide standing 0.65 past the body (3.55 overall), knob top 1.1 above the board.
    p = placement(ref)
    kx0, ky0, kx1, ky1 = C.knob_box(p)
    bx0, by0, bx1, by1 = C.body_box(p)
    assert kx1 - kx0 == pytest.approx(1.7)
    assert ky0 == pytest.approx(by1)
    assert ky1 - by0 == pytest.approx(3.55)
    assert ky1 == pytest.approx(p.y + 2.1)
    assert p.knob[4] == pytest.approx(1.1)


@pytest.mark.parametrize("ref", EAR_SWITCHES)
def test_ear_switches_leave_room_for_the_key_retainer(ref):
    p = placement(ref)
    x0, y0, x1, y1 = C.footprint_box(p)
    assert y1 == pytest.approx(C.knob_box(p)[3])
    assert 1.0 <= C.edge_y_at(p.x) - y1 <= 2.5
    assert min(abs(x0), abs(x1)) >= C.ANT_NOTCH_HALF_W + 3.0


def test_parts_on_the_same_side_do_not_overlap():
    for i, a in enumerate(C.PLACEMENTS):
        for b in C.PLACEMENTS[i + 1 :]:
            through_hole = "J201" in (a.ref, b.ref)
            if a.side == b.side or through_hole:
                assert not overlap(C.footprint_box(a), C.footprint_box(b)), (a.ref, b.ref)


def test_tall_back_parts_stay_out_of_the_battery_zone():
    for p in C.PLACEMENTS:
        if p.side == "back" and p.height > C.BATTERY_ZONE_MAX_H:
            assert not overlap(C.footprint_box(p), C.BATTERY_ZONE), p.ref


def test_battery_zone_is_on_the_board():
    for x, y in corners(C.BATTERY_ZONE):
        assert C.point_in_polygon(x, y, POLY)


def test_mount_holes_clear_battery_edges_and_sensor():
    for x, y in C.MOUNT_HOLES:
        assert C.point_in_polygon(x, y, POLY)
        assert min(math.dist((x, y), q) for q in POLY) >= 2.5
        assert abs(x) - 2.5 >= C.BATTERY_ZONE[2]  # standoff of 5 mm diameter clears the battery
        assert P.TUBE_OD / 2 > math.hypot(x, y) + C.MOUNT_HOLE_D / 2 > 15.0  # inside the bezel lugs


def test_body_screws_clear_the_ring_parts_and_antenna():
    for x, y in C.BODY_HOLES:
        assert C.point_in_polygon(x, y, POLY)
        assert min(math.dist((x, y), q) for q in POLY) >= 2.5
        assert math.hypot(x, y) - C.BOSS_R > P.RING_OD / 2 + 0.2  # 5.6 mm boss clears the ring
        assert math.dist((x, y), (min(max(x, -P.MODULE_W / 2), P.MODULE_W / 2), P.ANT_Y_BOTTOM)) > 15.0
        for p in C.PLACEMENTS:
            x0, y0, x1, y1 = C.footprint_box(p)
            assert not (x0 - C.BOSS_R < x < x1 + C.BOSS_R and y0 - C.BOSS_R < y < y1 + C.BOSS_R), p.ref


def rect_hits_keepout(box, k) -> bool:
    x0, y0, x1, y1 = box
    if k["kind"] == "circle":
        nx, ny = min(max(k["x"], x0), x1), min(max(k["y"], y0), y1)
        return math.dist((nx, ny), (k["x"], k["y"])) < k["r"]
    if k["kind"] == "annulus":
        nx, ny = min(max(k["x"], x0), x1), min(max(k["y"], y0), y1)
        nearest = math.dist((nx, ny), (k["x"], k["y"]))
        farthest = max(math.dist(c, (k["x"], k["y"])) for c in corners(box))
        return nearest < k["r_out"] and farthest > k["r_in"]
    # convex polygon against the box: separating axis test
    poly = k["points"]
    rect = corners(box)
    for shape in (rect, poly):
        for (ax, ay), (bx, by) in zip(shape, shape[1:] + shape[:1]):
            nx, ny = by - ay, ax - bx
            pa = [nx * px + ny * py for px, py in rect]
            pb = [nx * px + ny * py for px, py in poly]
            if max(pa) <= min(pb) or max(pb) <= min(pa):
                return False
    return True


def test_keepouts_surround_every_hole_on_the_sides_with_a_boss():
    ko = C.keepouts()
    holes = dict(zip((f"H{i + 1}" for i in range(8)), C.MOUNT_HOLES + C.BODY_HOLES))
    for ref, (x, y) in holes.items():
        back = [k for k in ko if k["side"] == "back" and k.get("ref") == ref]
        assert len(back) == 1 and back[0]["r"] >= C.BOSS_R + 0.2, ref
        assert (back[0]["x"], back[0]["y"]) == (x, y)
        front = [k for k in ko if k["side"] == "front" and k.get("ref") == ref]
        assert len(front) == 1, ref
        assert rect_hits_keepout((x - 0.1, y - 0.1, x + 0.1, y + 0.1), front[0])
    ring = next(k for k in ko if k["kind"] == "annulus")
    assert ring["side"] == "front"
    assert ring["r_in"] < P.PANEL_POCKET_D / 2 and ring["r_out"] >= P.RING_OD / 2 + 0.2


def test_antenna_notch_strips_cover_3_mm_either_side_of_both_notch_edges_on_both_sides():
    strips = [k for k in C.keepouts() if k["name"].startswith("antenna notch strip")]
    assert sorted((k["side"], k["name"]) for k in strips) == [
        (side, f"antenna notch strip {where}") for side in ("back", "front") for where in ("left", "right")]
    for k in strips:
        xs = sorted({x for x, _ in k["points"]})
        assert sorted(abs(x) for x in (xs[0], xs[-1])) == [11.0, 17.0]
        assert min(y for _, y in k["points"]) == 33.0
        assert k["ref"] == "U201"


@pytest.mark.parametrize("p", C.PLACEMENTS, ids=lambda p: p.ref)
def test_fixed_parts_stay_out_of_the_keepouts(p):
    for k in C.keepouts():
        if k["side"] == p.side and k.get("ref") != p.ref:
            assert not rect_hits_keepout(C.footprint_box(p), k), (p.ref, k["name"])


def test_front_parts_clear_the_ring_and_the_display_fpc_reaches():
    for ref in ("SW203", "U304"):
        p = placement(ref)
        assert min(math.hypot(x, y) for x, y in corners(C.footprint_box(p))) > P.RING_OD / 2 + 0.2, ref
    fpc = placement("J301")
    assert max(math.hypot(x, y) for x, y in corners(C.footprint_box(fpc))) < P.PANEL_POCKET_D / 2 - 1.0


def test_sensor_and_ambient_light_positions():
    hall = placement("U302")
    assert (hall.x, hall.y, hall.side) == (-P.R_TRACK, 0.0, "back")
    als = placement("U304")
    assert abs(als.x) - 1.05 >= C.ANT_NOTCH_HALF_W + 1.0


def test_jst_sh_heights_follow_the_datasheet():
    for ref in ("J202", "J302", "J303"):
        assert placement(ref).height == pytest.approx(2.95), ref


def test_contract_json_is_up_to_date():
    path = Path(__file__).resolve().parents[2] / "hardware" / "owl-mainboard" / "mech" / "contract.json"
    if not path.exists():
        pytest.skip("contract.json not generated yet")
    assert json.loads(path.read_text()) == json.loads(json.dumps(C.contract(), sort_keys=True))
