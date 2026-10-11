#!/usr/bin/env python3
"""Apply or check the enclosure contract (hardware/owl-mainboard/mech/contract.json) on the PCB.

apply: replaces Edge.Cuts with the contract outline, moves the fixed parts and mounting holes to
       their contract positions, side and rotation and locks them, and draws the battery zone
       and the keep-outs on Cmts.User.
check: fails if the outline, a fixed part, a hole or the battery-zone height rule differs from
       the contract, a magnetic part sits within the sensor keep-out of U302, a courtyard
       covers a keep-out on its side (screw bosses, bezel lugs, the ring annulus), or a fixed
       part's library body (F.Fab) is larger than the box the enclosure reserves for it
       (w, h, cu, cv and the knob, all in the footprint frame).

Usage: python3 tools/hw/hw_contract.py apply|check owl-mainboard
Needs KiCad's pcbnew Python module (system python3 with KiCad 10.0.6).
"""

from __future__ import annotations

import json
import math
import sys

import pcbnew

from hw_netlist import ROOT, load_design
from hw_sync import library

TOL = 0.01
BOX_TOL = 0.05  # library body drawing against the contract box
CIRCLE_SEGMENTS = 72


def mm(v: float) -> int:
    return pcbnew.FromMM(v)


def pt(xy) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(xy[0]), mm(xy[1]))


def load(board: str):
    path = ROOT / "hardware" / board / f"{board}.kicad_pcb"
    contract = json.loads((ROOT / "hardware" / board / "mech" / "contract.json").read_text())
    return path, pcbnew.LoadBoard(str(path)), contract


def set_side(fp, side: str) -> None:
    want_back = side == "back"
    if fp.IsFlipped() != want_back:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)


def circle_points(x: float, y: float, r: float) -> list[tuple[float, float]]:
    # Circumscribed polygon, so the keep-out never shrinks below r.
    rr = r / math.cos(math.pi / CIRCLE_SEGMENTS)
    return [(x + rr * math.cos(2 * math.pi * i / CIRCLE_SEGMENTS), y + rr * math.sin(2 * math.pi * i / CIRCLE_SEGMENTS))
            for i in range(CIRCLE_SEGMENTS)]


def keepout_poly(k: dict) -> pcbnew.SHAPE_POLY_SET:
    poly = pcbnew.SHAPE_POLY_SET()
    if k["kind"] == "polygon":
        rings = [k["points"]]
    elif k["kind"] == "circle":
        rings = [circle_points(k["x"], k["y"], k["r"])]
    else:
        rings = [circle_points(k["x"], k["y"], k["r_out"]), circle_points(k["x"], k["y"], k["r_in"])]
    poly.NewOutline()
    for x, y in rings[0]:
        poly.Append(mm(x), mm(y))
    if len(rings) > 1:
        poly.NewHole()
        for x, y in reversed(rings[1]):
            poly.Append(mm(x), mm(y), 0, 0)
    return poly


def courtyard(fp) -> pcbnew.SHAPE_POLY_SET:
    fp.BuildCourtyardCaches()
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    crt = fp.GetCourtyard(layer)
    if crt.OutlineCount():
        return crt
    bb = fp.GetBoundingBox(False)
    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
        poly.Append(x, y)
    return poly


def overlap_mm2(a: pcbnew.SHAPE_POLY_SET, b: pcbnew.SHAPE_POLY_SET) -> float:
    common = pcbnew.SHAPE_POLY_SET(a)
    common.BooleanIntersection(b)
    return common.Area() / 1e12


def body_box(fp) -> tuple[float, float, float, float] | None:
    """Box around the footprint's library F.Fab shapes in the footprint frame (u right, v down)."""
    nick, _, name = fp.GetFPIDAsString().rpartition(":")
    if not nick:
        return None
    lib_fp = pcbnew.FootprintLoad(str(library(nick)), name)
    box = None
    for g in lib_fp.GraphicalItems():
        if g.GetLayer() != pcbnew.F_Fab or g.GetClass() != "PCB_SHAPE":
            continue
        bb, w = g.GetBoundingBox(), pcbnew.ToMM(g.GetWidth()) / 2
        b = (pcbnew.ToMM(bb.GetLeft()) + w, pcbnew.ToMM(bb.GetTop()) + w, pcbnew.ToMM(bb.GetRight()) - w, pcbnew.ToMM(bb.GetBottom()) - w)
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    return box


def draw(board, layer: int, shape: int, width: float, **geom) -> None:
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(shape)
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    if "arc" in geom:
        s.SetArcGeometry(*(pt(p) for p in geom["arc"]))
    elif "points" in geom:
        s.SetPolyPoints([pt(p) for p in geom["points"]])
    elif "radius" in geom:
        s.SetCenter(pt(geom["centre"]))
        s.SetEnd(pt((geom["centre"][0] + geom["radius"], geom["centre"][1])))
    else:
        s.SetStart(pt(geom["start"]))
        s.SetEnd(pt(geom["end"]))
    board.Add(s)


def apply(board_name: str) -> int:
    path, board, c = load(board_name)
    for p in c["placements"]:
        fp = board.FindFootprintByReference(p["ref"])
        if fp is None:
            print(f"missing footprint {p['ref']}")
            return 1
        fp.SetLocked(False)
        set_side(fp, p["side"])
        fp.SetPosition(pt((p["kicad_x"], p["kicad_y"])))
        fp.SetOrientationDegrees(p["rot"])
        fp.SetLocked(True)
    for h in c["mount_holes"]:
        fp = board.FindFootprintByReference(h["ref"])
        if fp is None:
            print(f"missing footprint {h['ref']}")
            return 1
        fp.SetLocked(False)
        fp.SetPosition(pt((h["x"], h["y"])))
        fp.SetLocked(True)
    # Drawings go last: once pcbnew 10.0.6 has removed a drawing, FindFootprintByReference hands
    # back an untyped SWIG object. Keep the removed ones referenced until the board is saved.
    removed = [d for d in board.GetDrawings() if d.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Cmts_User)]
    for d in removed:
        board.Remove(d)
    for seg in c["outline"]:
        if seg["kind"] == "line":
            draw(board, pcbnew.Edge_Cuts, pcbnew.SHAPE_T_SEGMENT, 0.05, start=seg["start"], end=seg["end"])
        else:
            draw(board, pcbnew.Edge_Cuts, pcbnew.SHAPE_T_ARC, 0.05, arc=(seg["start"], seg["mid"], seg["end"]))
    x0, y0, x1, y1 = c["battery_zone"]["kicad"]
    draw(board, pcbnew.Cmts_User, pcbnew.SHAPE_T_RECT, 0.1, start=(x0, y0), end=(x1, y1))
    for k in c.get("keepouts", []):
        if k["kind"] == "circle":
            draw(board, pcbnew.Cmts_User, pcbnew.SHAPE_T_CIRCLE, 0.05, centre=(k["x"], k["y"]), radius=k["r"])
        elif k["kind"] == "polygon":
            draw(board, pcbnew.Cmts_User, pcbnew.SHAPE_T_POLY, 0.05, points=k["points"])
        else:
            for r in (k["r_in"], k["r_out"]):
                draw(board, pcbnew.Cmts_User, pcbnew.SHAPE_T_CIRCLE, 0.05, centre=(k["x"], k["y"]), radius=r)
    pcbnew.SaveBoard(str(path), board)
    print(f"{board_name}: applied {len(c['outline'])} outline segments, {len(c['placements'])} parts, {len(c['mount_holes'])} holes")
    return 0


def check(board_name: str) -> int:
    _, board, c = load(board_name)
    design = {p["ref"]: p for p in load_design(board_name)["part"]}
    errors = []
    edges = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    if len(edges) != len(c["outline"]):
        errors.append(f"outline has {len(edges)} segments, contract has {len(c['outline'])}")

    def ends(a, b):
        return tuple(sorted(((round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2)))))

    have = sorted(
        ends((pcbnew.ToMM(d.GetStart().x), pcbnew.ToMM(d.GetStart().y)), (pcbnew.ToMM(d.GetEnd().x), pcbnew.ToMM(d.GetEnd().y)))
        for d in edges
    )
    want = sorted(ends(s["start"], s["end"]) for s in c["outline"])
    if have != want:
        errors.append("outline segment end points differ from the contract")
    for p in c["placements"]:
        fp = board.FindFootprintByReference(p["ref"])
        if fp is None:
            errors.append(f"{p['ref']} missing")
            continue
        x, y = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
        if math.dist((x, y), (p["kicad_x"], p["kicad_y"])) > TOL:
            errors.append(f"{p['ref']} at ({x:.3f}, {y:.3f}), contract ({p['kicad_x']}, {p['kicad_y']})")
        turn = (fp.GetOrientationDegrees() - p["rot"]) % 360
        if min(turn, 360 - turn) > 0.01:
            errors.append(f"{p['ref']} rotation {fp.GetOrientationDegrees()}, contract {p['rot']}")
        if fp.IsFlipped() != (p["side"] == "back"):
            errors.append(f"{p['ref']} on the wrong side")
        if "w" in p:
            boxes = [(p["cu"] - p["w"] / 2, p["cv"] - p["h"] / 2, p["cu"] + p["w"] / 2, p["cv"] + p["h"] / 2)]
            if p.get("knob"):
                boxes.append(tuple(p["knob"][:4]))
            body = body_box(fp)
            room = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
            if body is not None and (body[0] < room[0] - BOX_TOL or body[1] < room[1] - BOX_TOL
                                     or body[2] > room[2] + BOX_TOL or body[3] > room[3] + BOX_TOL):
                errors.append(f"{p['ref']} body (u {body[0]:.2f} to {body[2]:.2f}, v {body[1]:.2f} to {body[3]:.2f}) "
                              f"is larger than its contract box (u {room[0]:.2f} to {room[2]:.2f}, v {room[1]:.2f} to {room[3]:.2f})")
    for h in c["mount_holes"]:
        fp = board.FindFootprintByReference(h["ref"])
        if fp is None or math.dist((pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)), (h["x"], h["y"])) > TOL:
            errors.append(f"hole {h['ref']} missing or moved")
    x0, y0, x1, y1 = c["battery_zone"]["kicad"]
    limit = c["battery_zone"]["max_back_height"]
    zone = keepout_poly({"kind": "polygon", "points": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]})
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if not fp.IsFlipped() or ref not in design:
            continue
        if overlap_mm2(courtyard(fp), zone) > 0 and design[ref].get("height", 99.0) > limit:
            errors.append(f"{ref} ({design[ref].get('height')} mm) is under the battery (limit {limit} mm)")
    holes = {h["ref"] for h in c["mount_holes"]}
    for k in c.get("keepouts", []):
        area = keepout_poly(k)
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            if ref in holes or fp.IsFlipped() != (k["side"] == "back"):
                continue
            if overlap_mm2(courtyard(fp), area) > 0:
                errors.append(f"{ref} covers the {k['name']} keep-out ({k['side']})")
    hall = board.FindFootprintByReference("U302")
    if hall is not None:
        hx, hy = pcbnew.ToMM(hall.GetPosition().x), pcbnew.ToMM(hall.GetPosition().y)
        for ref, part in design.items():
            fp = board.FindFootprintByReference(ref)
            if part.get("magnetic") and fp is not None:
                d = math.dist((hx, hy), (pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)))
                if d < c["sensor_keepout_mm"]:
                    errors.append(f"{ref} is {d:.1f} mm from U302 (keep-out {c['sensor_keepout_mm']} mm)")
    for e in errors:
        print(e)
    print(f"{board_name}: {len(errors)} contract error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    cmd, name = sys.argv[1], sys.argv[2]
    sys.exit(apply(name) if cmd == "apply" else check(name))
