"""Enclosure v1: every part builds, the assembly has no interference, key dimensions hold."""

from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path

import pytest
from build123d import Cylinder, Edge, Pos, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import owl_params as P  # noqa: E402
import owl_v1 as V  # noqa: E402
import pcb_contract as C  # noqa: E402
import ring_test as R  # noqa: E402


@pytest.fixture(scope="module")
def parts():
    return V.parts()


def overlap_volume(a, b) -> float:
    common = a & b
    return common.volume if common is not None else 0.0


def chords(part, p0, p1) -> list[float]:
    """Lengths of the solid chords of the line p0 to p1 through the part."""
    hit = part & Edge.make_line(Vector(*p0), Vector(*p1))
    return [e.length for e in hit.edges()] if hit else []


def placement(ref):
    return next(q for q in C.PLACEMENTS if q.ref == ref)


def test_every_part_is_one_valid_solid(parts):
    assert len(parts) == 12
    for name, part in parts.items():
        assert part.is_valid, name
        assert len(part.solids()) == 1, name


def test_outside_size(parts):
    size = parts["body"].bounding_box().size
    assert size.X == pytest.approx(C.BODY_W)
    assert size.Y == pytest.approx(C.BODY_H)
    assert size.Z == pytest.approx(V.FRONT_Z - V.BACK_Z)  # 23.5 mm front lip to back
    assert V.FRONT_Z - V.BACK_Z <= 23.5 + 1e-9


@pytest.mark.parametrize("ring", ["ring_a_bearing", "ring_b_bushing"])
def test_assembly_has_no_interference(parts, ring):
    middle = R.bearing_dummy() if ring == "ring_a_bearing" else parts["bushing_sleeve"]
    stack = {
        "body": parts["body"],
        "back_cover": parts["back_cover"],
        "bezel": parts["bezel"],
        "glass_retainer": parts["glass_retainer"],
        "glass": V.glass_envelope(),
        "middle": middle,
        "ring": parts[ring],
        "carrier": parts["magnet_carrier_24"],
        "beak_key": parts["beak_key"],
        "ear_key_left": parts["ear_key_left"],
        "ear_key_right": parts["ear_key_right"],
        "pcb": V.pcb_envelope(),
        "battery": V.battery_envelope(),
    }
    clashes = []
    for (na, a), (nb, b) in itertools.combinations(stack.items(), 2):
        v = overlap_volume(a, b)
        if v > 1e-3:
            clashes.append((na, nb, round(v, 3)))
    assert clashes == []


def test_ring_sides_are_exposed_for_the_thumb(parts):
    body = parts["body"]
    for z in (0.0, -4.0, -8.0):
        assert not body.is_inside(Vector(-P.RING_OD / 2 - 0.1, 0.0, z))
        assert not body.is_inside(Vector(P.RING_OD / 2 + 0.1, 0.0, z))


def test_glass_drops_in_from_the_front_and_the_retainer_holds_it(parts):
    bezel, retainer = parts["bezel"], parts["glass_retainer"]
    seated = V.glass_envelope()
    # with the retainer off, the glass drops in from the front without touching the bezel
    for dz in (6.0, 3.0, 1.5, 0.5, 0.0):
        assert overlap_volume(Pos(0, 0, dz) * seated, bezel) < 1e-3, dz
    # the retainer follows it into the lip opening, over the glass border
    for dz in (4.0, 2.0, 0.5, 0.0):
        assert overlap_volume(Pos(0, 0, dz) * retainer, bezel) < 1e-3, dz
    assert overlap_volume(retainer, seated) < 1e-3
    assert not retainer.is_inside(Vector(0.0, -(P.BEZEL_LIP_ID / 2 - 0.02), 0.5))  # glue gap
    # the glass cannot leave without moving the retainer: it covers the glass edge all round
    assert overlap_volume(Pos(0, 0, V.GLASS_GAP + 0.05) * seated, retainer) > 0.01
    assert V.RETAINER_ID < P.GLASS_D - 2.0
    # the retainer stays out of the viewing area, is flush with the lip and meets the wall rule
    for angle in range(0, 360, 15):
        x, y = R.polar(P.VIEW_D / 2 + 0.05, angle)
        assert not retainer.is_inside(Vector(x, y, 0.5))
    assert V.RETAINER_ID / 2 - P.VIEW_D / 2 >= 0.2
    assert retainer.bounding_box().max.Z == pytest.approx(P.LIP_T)
    assert (V.RETAINER_OD - V.RETAINER_ID) / 2 >= P.MJF_STRUCT_WALL
    assert P.LIP_T >= P.MJF_STRUCT_WALL


def test_back_cover_windows_line_up_with_the_dock_pads(parts):
    cover = parts["back_cover"]
    for k in (-1, 0, 1):
        assert not cover.is_inside(Vector(k * V.DOCK_PAD_PITCH, V.DOCK_PAD_Y, V.BACK_Z + 0.5))
    assert cover.is_inside(Vector(2.25, V.DOCK_PAD_Y, V.BACK_Z + 0.5))


def test_lra_cup_is_clear_of_the_battery_and_magnets():
    x, y = V.LRA_XY
    r = V.LRA_CUP_OD / 2
    assert x - r > C.BATTERY_ZONE[2]
    magnet_boss = V.DOCK_MAGNET_D / 2 + V.DOCK_MAGNET_WALL
    for (mx, my), other in (
        [(m, magnet_boss) for m in V.DOCK_MAGNETS]
        + [(h, V.BOSS_R) for h in C.MOUNT_HOLES]
        + [(h, V.SCREW_COLLAR_R) for h in C.BODY_HOLES]
    ):
        assert ((x - mx) ** 2 + (y - my) ** 2) ** 0.5 > r + other
    assert x + r < C.BODY_W / 2 - C.WALL_T
    hall = placement("U302")
    assert ((x - hall.x) ** 2 + (y - hall.y) ** 2) ** 0.5 > 40.0


def button_head(x: float, y: float, seat: float, towards: int):
    """ISO 7380 M2 head as a cylinder dk x k (it encloses the dome), its bearing face at z = seat
    and the head on the side opposite to the shank direction `towards` (+1 or -1 in z)."""
    z0 = seat - P.M2_BUTTON_K if towards > 0 else seat
    return Pos(x, y, z0) * Cylinder(P.M2_BUTTON_DK / 2, P.M2_BUTTON_K, align=R.BOTTOM)


def shank(x: float, y: float, seat: float, length: float, towards: int):
    z0 = seat if towards > 0 else seat - length
    return Pos(x, y, z0) * Cylinder(1.0, length, align=R.BOTTOM)


@pytest.mark.parametrize("hole", C.BODY_HOLES)
def test_back_screw_heads_sit_inside_the_cover(parts, hole):
    # P.SCREW_BACK from the back: head in the counterbore, through the cover standoff and the
    # board into the insert in the body boss.
    x, y = hole
    seat = V.BACK_Z + V.SCREW_HEAD_DEPTH
    head, body_of_screw = button_head(x, y, seat, +1), shank(x, y, seat, P.SCREW_BACK_L, +1)
    assert head.bounding_box().min.Z >= V.BACK_Z - 1e-9  # flush or recessed: the owl stays 23.5 deep
    assert V.FRONT_Z - head.bounding_box().min.Z <= 23.5 + 1e-9
    for name in ("back_cover", "body"):
        assert overlap_volume(head, parts[name]) < 1e-3, name
        assert overlap_volume(body_of_screw, parts[name]) < 1e-3, name
    tip = seat + P.SCREW_BACK_L
    assert V.PCB_FRONT_Z + P.M2_INSERT_L - 1e-6 <= tip <= V.PCB_FRONT_Z + V.INSERT_DEPTH + 1e-6


@pytest.mark.parametrize("hole", C.MOUNT_HOLES)
def test_front_screws_clear_the_ring_parts_and_reach_the_inserts(parts, hole):
    # P.SCREW_FRONT from the front: head on the bezel lug, through the board into the insert in
    # the cover standoff.
    x, y = hole
    seat = V.PCB_FRONT_Z + P.LUG_T
    head, body_of_screw = button_head(x, y, seat, -1), shank(x, y, seat, P.SCREW_FRONT_L, -1)
    for name in ("bezel", "back_cover", "magnet_carrier_24", "ring_a_bearing", "bushing_sleeve"):
        assert overlap_volume(head, parts[name]) < 1e-3, name
        assert overlap_volume(body_of_screw, parts[name]) < 1e-3, name
    tip = seat - P.SCREW_FRONT_L
    assert V.PCB_BACK_Z - V.INSERT_DEPTH - 1e-6 <= tip <= V.PCB_BACK_Z - P.M2_INSERT_L + 1e-6


def test_counterbore_edge_keeps_a_structural_wall():
    # from the counterbore's top edge to the nearest outside surface: the boss above the collar
    # and the collar's rim
    edge = (V.SCREW_HEAD_D / 2, V.SCREW_HEAD_DEPTH)
    boss = (V.BOSS_R, V.COVER_T + V.SCREW_COLLAR_H)
    rim = (V.SCREW_COLLAR_R, V.COVER_T)
    assert min(math.dist(edge, boss), math.dist(edge, rim)) >= P.MJF_STRUCT_WALL
    assert V.SCREW_HEAD_D / 2 - P.M2_BUTTON_DK / 2 >= 0.3


def test_dock_magnets_stay_away_from_the_ring_sensor():
    # Spec 7.3: as far from the TMAG5273 as the cover allows. At 20 mm a D6 x 2 N52 disc adds
    # well under 1 mT at the sensor, against about 46 mT from the ring magnets at the 3.0 mm gap.
    hall = placement("U302")
    for mx, my in V.DOCK_MAGNETS:
        assert math.dist((mx, my), (hall.x, hall.y)) >= 20.0


def test_dock_pad_board_clears_the_battery_and_the_alignment_recesses():
    w, h, _ = V.DOCK_BOARD  # recess size: the board is 0.4 mm smaller
    board_top = V.DOCK_BOARD_Y + (h - 0.4) / 2
    assert board_top <= C.BATTERY_CENTRE[1] - C.BATTERY_L / 2 - 0.4
    for x, _y in V.ALIGN_RECESSES:
        assert abs(x) - V.ALIGN_D / 2 >= w / 2 + 1.0
    for k in (-1, 1):
        assert abs(V.DOCK_BOARD_Y - V.DOCK_PAD_Y) + V.DOCK_PAD_WINDOW_D / 2 < h / 2
        assert k * V.DOCK_PAD_PITCH + V.DOCK_PAD_WINDOW_D / 2 < w / 2


def test_battery_fits_between_board_and_cover():
    assert V.BATTERY_FRONT_Z - V.BATTERY_BACK_Z == pytest.approx(C.BATTERY_T)
    assert V.PCB_BACK_Z - V.BATTERY_FRONT_Z == pytest.approx(C.BATTERY_FOAM)
    assert V.PCB_FRONT_Z == pytest.approx(-P.pcb_front_depth())


@pytest.mark.parametrize("ref, name", [("SW201", "ear_key_left"), ("SW202", "ear_key_right")])
def test_ear_key_meets_the_knob_and_the_wall_stops_it(parts, ref, name):
    key, body = parts[name], parts["body"]
    sw = placement(ref)
    kx0, _ky0, kx1, tip = C.knob_box(sw)
    box = key.bounding_box()
    # the key's end face sits 0.2 mm above the knob tip and covers the knob in x and in height
    assert box.min.Y == pytest.approx(tip + V.EAR_KEY_GAP)
    assert box.min.X < kx0 and box.max.X > kx1
    assert V.ear_key_z() - V.EAR_KEY[1] / 2 < V.PCB_BACK_Z - sw.knob[4]
    # the retainer catches on the head wall before the key can leave, and pressing the key far
    # enough to work the switch (gap plus 0.2 mm travel) keeps the tuft off the head
    assert V.EAR_RETAINER_GAP >= 0.2
    assert overlap_volume(Pos(0, V.EAR_RETAINER_GAP + 0.2, 0) * key, body) > 0.01
    assert overlap_volume(Pos(0, -(V.EAR_KEY_GAP + 0.2), 0) * key, body) < 1e-3
    assert V.EAR_RETAINER_T >= P.MJF_STRUCT_WALL


def test_beak_key_meets_the_switch_and_the_face_stops_it(parts):
    key, body = parts["beak_key"], parts["body"]
    sw = placement("SW203")
    assert key.bounding_box().min.Z == pytest.approx(V.PCB_FRONT_Z + sw.height + 0.2)
    assert key.bounding_box().max.Z == pytest.approx(V.FRONT_Z + V.BEAK_PROUD)
    assert overlap_volume(Pos(0, 0, 0.1) * key, body) > 0.01
    assert V.BEAK_FLANGE_T >= P.MJF_STRUCT_WALL


def test_thin_spots_meet_the_wall_classes(parts):
    body, cover = parts["body"], parts["back_cover"]
    face_z = V.FRONT_Z - V.FACE_T / 2
    # face bar between the beak slot and the ring opening, and below the slot
    top = V.BEAK_XY[1] + V.BEAK_SLOT[1] / 2
    bottom = V.BEAK_XY[1] - V.BEAK_SLOT[1] / 2
    assert chords(body, (0, top - 0.01, face_z), (0, -RING_Y, face_z)) == [pytest.approx(1.0)]
    assert min(chords(body, (0, bottom + 0.01, face_z), (0, -45.0, face_z))) >= P.MJF_STRUCT_WALL
    # the side walls end square where the ring opening cuts them, not in a knife edge
    for z in (-1.0, -6.0):
        for y in (V.SIDE_OPENING_Y + 0.05, -V.SIDE_OPENING_Y - 0.05):
            assert chords(body, (29.0, y, z), (35.0, y, z)) == [pytest.approx(C.WALL_T)]
    # bars between the dock pad windows and the cover floor under the dock magnets
    z = V.BACK_Z + 0.5
    lengths = chords(cover, (-V.DOCK_PAD_PITCH, V.DOCK_PAD_Y, z), (V.DOCK_PAD_PITCH, V.DOCK_PAD_Y, z))
    assert min(lengths) >= P.MJF_MIN_WALL
    for mx, my in V.DOCK_MAGNETS:
        assert chords(cover, (mx, my, V.BACK_Z - 1.0), (mx, my, V.BACK_Z + 1.5))[0] >= P.MJF_STRUCT_WALL - 1e-6
    # LRA cup wall, recess floors and the cover plate
    x, y = V.LRA_XY
    z = V.BATTERY_BACK_Z + V.LRA_CUP_H / 2
    assert chords(cover, (x + V.LRA_POCKET_D / 2 - 0.5, y, z), (x + 6.0, y, z))[0] >= P.MJF_STRUCT_WALL - 1e-6
    for ax, ay in V.ALIGN_RECESSES:
        assert chords(cover, (ax, ay, V.BACK_Z - 1.0), (ax, ay, V.BATTERY_BACK_Z + 0.01))[0] >= P.MJF_STRUCT_WALL - 1e-6
    for value in (C.WALL_T, V.FACE_T, V.COVER_T - V.DOCK_BOARD[2], (V.LRA_CUP_OD - V.LRA_POCKET_D) / 2):
        assert value >= P.MJF_STRUCT_WALL


RING_Y = C.RING_CLEAR_R - 0.5  # just inside the ring opening at x = 0


def test_export_writes_step_and_stl(tmp_path):
    written = V.export_all(tmp_path)
    assert len(written) == 24
    assert all(p.stat().st_size > 500 for p in written)


def test_glass_envelope_matches_the_panel_data():
    glass = V.glass_envelope()
    box = glass.bounding_box()
    assert box.size.X == pytest.approx(P.GLASS_D)
    assert box.max.Z == pytest.approx(-V.GLASS_GAP)
