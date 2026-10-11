"""Mechanical contract between enclosure v1 and the owl main board (rev A).

The contract fixes the board outline, the position of every part the enclosure touches, the
keep-low zone under the battery, the keep-outs around the screw bosses and the antenna notch. Owl
coordinates (owl_params.py): X right, Y up, origin at the display centre. KiCad coordinates:
x_k = KICAD_ORIGIN[0] + x, y_k = KICAD_ORIGIN[1] - y, rotation in degrees counter-clockwise as
KiCad shows it. Part boxes are given in the footprint's own frame (u right, v down, as in the
footprint editor) and mapped to the board by local_to_owl(), which follows what pcbnew does to a
footprint placed with Flip(LEFT_RIGHT) and SetOrientationDegrees(rot).

Run `uv run --project enclosure python enclosure/pcb_contract.py` to write
hardware/owl-mainboard/mech/contract.json. Licence: CERN-OHL-P-2.0 (LICENSE-HARDWARE).
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owl_params as P  # noqa: E402

KICAD_ORIGIN = (100.0, 100.0)

# Owl silhouette behind the ring: a rounded rectangle 66 x 84 with 16 mm corners, centred 3 mm
# above the display centre (top of head +45, bottom -39). Ear tufts stand above the corners.
BODY_W = 66.0
BODY_H = 84.0
BODY_R = 16.0
BODY_CY = 3.0
WALL_T = 1.6
PCB_CLEAR = 0.5
PCB_INSET = WALL_T + PCB_CLEAR  # 2.1

# Antenna notch: the module's PCB antenna overhangs the board edge; the board is cut away
# 5 mm either side of the 18 mm module (Espressif PCB layout guide, module placement).
ANT_NOTCH_HALF_W = P.MODULE_W / 2 + 5.0  # 14.0
ANT_BOARD_EDGE_Y = P.ANT_Y_BOTTOM  # 36.6
# No parts within 3 mm either side of the notch edges above y 33, on both sides (GND pour may run
# there; the contract only governs parts).
ANT_STRIP_HALF_W = 3.0
ANT_STRIP_Y0 = 33.0

# Back-side keep-low zone under the battery (803040: 8 x 30 x 40 mm, 0.5 mm margin all round).
BATTERY_W = 30.0
BATTERY_L = 40.0
BATTERY_T = 8.0
BATTERY_CENTRE = (0.0, -7.0)
BATTERY_ZONE = (-15.5, -27.5, 15.5, 13.5)  # x0, y0, x1, y1
BATTERY_ZONE_MAX_H = 1.2  # back-side parts under the battery may not be taller than this
BATTERY_FOAM = 1.2  # gap between the PCB back and the battery

MOUNT_HOLES = ((19.0, 9.0), (-19.0, 9.0), (-19.0, -9.0), (19.0, -9.0))  # M2 through the bezel lugs
BODY_HOLES = ((-27.0, 30.0), (27.0, 30.0), (-25.0, -30.0), (25.0, -30.0))  # M2 from the back into the body
MOUNT_HOLE_D = 2.2

# Screw bosses and bezel lugs that touch the board. Every hole has a back-cover boss behind the
# board; H5 to H8 also have a body boss in front of it, H1 to H4 a bezel lug.
BOSS_R = 2.8
BOSS_CLEAR = 0.2
LUG_W = 6.0  # product bezel lug width (the test bezel uses owl_params.LUG_W)
RING_CLEAR_R = P.RING_OD / 2 + 0.2  # front-side parts stay outside the ring, carrier and bezel tube


@dataclass(frozen=True)
class Placement:
    ref: str
    x: float
    y: float
    rot: float
    side: str  # "front" faces the display and ring, "back" faces the battery
    w: float  # body size along the footprint's u axis
    h: float  # body size along the footprint's v axis
    height: float  # body height above the board surface
    why: str
    cu: float = 0.0  # body centre in the footprint frame, where it is not the footprint origin
    cv: float = 0.0
    knob: tuple[float, ...] = ()  # side actuator in the footprint frame: (u0, v0, u1, v1, top above the board)


# EVQ-P7A (Panasonic EVQP7 catalogue, 01 Sep 2013, p. 2): body 3.5 x 2.9 and 4.7 over the
# terminals, knob 1.7 wide standing 0.65 past the body edge (3.55 overall), knob top 1.1 above the
# board. KiCad's SW_SPST_EVQP7A draws the knob at v +1.45 to +2.1; on the back at rot 0 it faces up.
EVQ_KNOB = (-0.85, 1.45, 0.85, 2.1, 1.1)
EAR_SWITCH_Y = 38.5  # knob tip 2.0 inside the board edge: room for the 1.0 mm key retainer below the wall

# JST SH side entry (SM02B/SM04B-SRSS-TB): 2.95 high, body 4.25 deep centred 0.45 behind the pad
# row's centre line in KiCad's footprints (v -1.675 to +2.575).
SH_CV = 0.45

PLACEMENTS = (
    Placement("U302", -P.R_TRACK, 0.0, 0.0, "back", 3.0, 3.0, 1.45, "TMAG5273 under the magnet track at 9 o clock"),
    Placement("U201", 0.0, P.ANT_Y_TOP - P.MODULE_L / 2, 180.0, "back", P.MODULE_W, P.MODULE_L, 3.1,
              "ESP32-S3-WROOM-1, rot 180 puts the antenna (footprint -v) over the notch at the top"),
    Placement("J201", -12.0, -33.8, 180.0, "back", 8.94, 7.35, 3.26, "USB-C, opening in the bottom wall"),
    Placement("SW203", 0.0, -35.0, 0.0, "front", 4.0, 3.0, 2.0, "beak switch, pressed through the front shell"),
    Placement("SW201", -20.0, EAR_SWITCH_Y, 0.0, "back", 4.7, 2.9, 1.35,
              "left ear switch, knob faces up, key runs behind the board", knob=EVQ_KNOB),
    Placement("SW202", 20.0, EAR_SWITCH_Y, 0.0, "back", 4.7, 2.9, 1.35,
              "right ear switch, knob faces up, key runs behind the board", knob=EVQ_KNOB),
    Placement("U304", 17.0, 31.5, 0.0, "front", 2.1, 2.1, 0.65, "ambient light sensor behind the brow window"),
    # rot 180: the FH26W takes the FPC from footprint +v, which then faces up, so the flex that
    # folds over the panel's top edge runs straight down into it (at rot 0 it would need a fold).
    Placement("J301", 0.0, 12.0, 180.0, "front", 11.5, 5.6, 1.0,
              "display FPC, entry faces the panel's top edge; reach provisional until the paper FPC check", cv=1.0),
    Placement("J101", 22.0, 18.0, 90.0, "back", 9.9, 7.6, 4.8, "battery connector, wires run down to the pack", cv=0.6),
    Placement("J303", 14.0, -32.0, 180.0, "back", 6.0, 4.25, 2.95, "dock link to the dock-pad board", cv=SH_CV),
    Placement("J302", 24.0, -20.0, 90.0, "back", 4.0, 4.25, 2.95, "LRA lead connector, motor on the right", cv=SH_CV),
    Placement("J202", -24.0, -18.0, 270.0, "back", 6.0, 4.25, 2.95, "expansion / encoder fallback", cv=SH_CV),
)


def kicad_xy(x: float, y: float) -> tuple[float, float]:
    return round(KICAD_ORIGIN[0] + x, 4), round(KICAD_ORIGIN[1] - y, 4)


def local_to_owl(p: Placement, u: float, v: float) -> tuple[float, float]:
    """Footprint-frame point (u right, v down) to owl coordinates. A back-side footprint is
    mirrored top to bottom by the flip, so its +v points up at rot 0; then both sides rotate
    counter-clockwise by rot (checked with pcbnew 10.0.6 for 0, 90, 180 and 270 on both sides)."""
    a, b = u, (v if p.side == "back" else -v)
    t = math.radians(p.rot)
    return p.x + a * math.cos(t) - b * math.sin(t), p.y + a * math.sin(t) + b * math.cos(t)


def _box(p: Placement, u0: float, v0: float, u1: float, v1: float) -> tuple[float, float, float, float]:
    pts = [local_to_owl(p, u, v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    return min(xs), min(ys), max(xs), max(ys)


def body_box(p: Placement) -> tuple[float, float, float, float]:
    """Axis-aligned body box (x0, y0, x1, y1) on the board; rot is a multiple of 90 degrees."""
    return _box(p, p.cu - p.w / 2, p.cv - p.h / 2, p.cu + p.w / 2, p.cv + p.h / 2)


def knob_box(p: Placement) -> tuple[float, float, float, float] | None:
    return _box(p, *p.knob[:4]) if p.knob else None


def footprint_box(p: Placement) -> tuple[float, float, float, float]:
    """Box around the body and its actuator, the part's whole outline as the enclosure sees it."""
    boxes = [body_box(p)] + ([knob_box(p)] if p.knob else [])
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _arc(cx: float, cy: float, r: float, a0: float, a1: float) -> dict:
    am = (a0 + a1) / 2
    pt = lambda a: (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))  # noqa: E731
    return {"kind": "arc", "start": pt(a0), "mid": pt(am), "end": pt(a1)}


def outline_segments() -> list[dict]:
    """Closed board outline, counter-clockwise, in owl coordinates."""
    w = BODY_W / 2 - PCB_INSET
    top = BODY_CY + BODY_H / 2 - PCB_INSET
    bot = BODY_CY - BODY_H / 2 + PCB_INSET
    r = BODY_R - PCB_INSET
    n = ANT_NOTCH_HALF_W
    e = ANT_BOARD_EDGE_Y
    seg = []
    line = lambda a, b: seg.append({"kind": "line", "start": a, "end": b})  # noqa: E731
    line((-w + r, bot), (w - r, bot))
    seg.append(_arc(w - r, bot + r, r, -90, 0))
    line((w, bot + r), (w, top - r))
    seg.append(_arc(w - r, top - r, r, 0, 90))
    line((w - r, top), (n, top))
    line((n, top), (n, e))
    line((n, e), (-n, e))
    line((-n, e), (-n, top))
    line((-n, top), (-w + r, top))
    seg.append(_arc(-w + r, top - r, r, 90, 180))
    line((-w, top - r), (-w, bot + r))
    seg.append(_arc(-w + r, bot + r, r, 180, 270))
    return seg


def _circle(arc: dict) -> tuple[float, float, float]:
    (x1, y1), (x2, y2), (x3, y3) = arc["start"], arc["mid"], arc["end"]
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    return ux, uy, math.hypot(x1 - ux, y1 - uy)


def outline_polygon(step_deg: float = 2.0) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for s in outline_segments():
        if s["kind"] == "line":
            pts.append(s["start"])
        else:
            (sx, sy), (ex, ey) = s["start"], s["end"]
            cx, cy, r = _circle(s)
            a0 = math.degrees(math.atan2(sy - cy, sx - cx))
            a1 = math.degrees(math.atan2(ey - cy, ex - cx))
            if a1 < a0:
                a1 += 360
            k = max(2, int((a1 - a0) / step_deg))
            pts += [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / k)),
                     cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / k))) for i in range(k)]
    return pts


def point_in_polygon(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(poly) - 1
    for i, (xi, yi) in enumerate(poly):
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def edge_y_at(x: float) -> float:
    """Top edge of the board outline at x (outside the antenna notch)."""
    w = BODY_W / 2 - PCB_INSET
    r = BODY_R - PCB_INSET
    top = BODY_CY + BODY_H / 2 - PCB_INSET
    cx = w - r
    if abs(x) <= cx:
        return top
    return top - r + math.sqrt(r * r - (abs(x) - cx) ** 2)


def lug_polygon(x: float, y: float, margin: float = BOSS_CLEAR) -> list[tuple[float, float]]:
    """Footprint of the product bezel lug through hole (x, y) on the board front, grown by margin."""
    a = math.atan2(y, x)
    r0, r1, hw = P.LUG_R_IN - margin, P.TUBE_OD / 2 + margin, LUG_W / 2 + margin
    c, s = math.cos(a), math.sin(a)
    return [(r * c - t * s, r * s + t * c) for r, t in ((r0, -hw), (r1, -hw), (r1, hw), (r0, hw))]


def keepouts() -> list[dict]:
    """Board areas no part may cover, in owl coordinates. Back: the cover boss behind every hole.
    Front: the body bosses at H5 to H8, the bezel lugs at H1 to H4, and the annulus under the bezel
    tube, magnet carrier and ring (the carrier flange runs 0.3 mm in front of the board). Both
    sides: the strips beside the antenna notch edges (U201 itself is exempt)."""
    out = []
    holes = [(f"H{i + 1}", xy) for i, xy in enumerate(MOUNT_HOLES + BODY_HOLES)]
    for ref, (x, y) in holes:
        out.append({"name": f"{ref} cover boss", "ref": ref, "side": "back", "kind": "circle",
                    "x": x, "y": y, "r": BOSS_R + BOSS_CLEAR})
    for ref, (x, y) in holes:
        if (x, y) in BODY_HOLES:
            out.append({"name": f"{ref} body boss", "ref": ref, "side": "front", "kind": "circle",
                        "x": x, "y": y, "r": BOSS_R + BOSS_CLEAR})
        else:
            out.append({"name": f"{ref} bezel lug", "ref": ref, "side": "front", "kind": "polygon",
                        "points": lug_polygon(x, y)})
    out.append({"name": "bezel tube, magnet carrier and ring", "side": "front", "kind": "annulus",
                "x": 0.0, "y": 0.0, "r_in": P.PANEL_POCKET_D / 2 - BOSS_CLEAR, "r_out": RING_CLEAR_R})
    top = BODY_CY + BODY_H / 2 - PCB_INSET
    for side in ("front", "back"):
        for sign, where in ((-1, "left"), (1, "right")):
            x0, x1 = sorted((sign * (ANT_NOTCH_HALF_W - ANT_STRIP_HALF_W), sign * (ANT_NOTCH_HALF_W + ANT_STRIP_HALF_W)))
            out.append({"name": f"antenna notch strip {where}", "ref": "U201", "side": side, "kind": "polygon",
                        "points": [(x0, ANT_STRIP_Y0), (x1, ANT_STRIP_Y0), (x1, top), (x0, top)]})
    return out


def _keepout_kicad(k: dict) -> dict:
    out = {key: v for key, v in k.items() if key not in ("x", "y", "points")}
    if "points" in k:
        out["points"] = [kicad_xy(x, y) for x, y in k["points"]]
    else:
        out["x"], out["y"] = kicad_xy(k["x"], k["y"])
    return out


def contract() -> dict:
    zone = BATTERY_ZONE
    return {
        "units": "mm",
        "kicad_origin": KICAD_ORIGIN,
        "board_thickness": P.PCB_T,
        "pcb_front_depth": round(P.pcb_front_depth(), 4),
        "outline": [
            {k: (kicad_xy(*v) if isinstance(v, tuple) else v) for k, v in s.items()} for s in outline_segments()
        ],
        "placements": [
            {**asdict(p), "kicad_x": kicad_xy(p.x, p.y)[0], "kicad_y": kicad_xy(p.x, p.y)[1]} for p in PLACEMENTS
        ],
        "mount_holes": [
            {"ref": f"H{i + 1}", "x": kicad_xy(x, y)[0], "y": kicad_xy(x, y)[1], "d": MOUNT_HOLE_D}
            for i, (x, y) in enumerate(MOUNT_HOLES + BODY_HOLES)
        ],
        "keepouts": [_keepout_kicad(k) for k in keepouts()],
        "battery_zone": {
            "kicad": [*kicad_xy(zone[0], zone[3]), *kicad_xy(zone[2], zone[1])],
            "max_back_height": BATTERY_ZONE_MAX_H,
        },
        "sensor_keepout_mm": 15.0,
        "notes": "Generated by enclosure/pcb_contract.py from enclosure/owl_params.py. Do not edit. "
        "Placement boxes (w, h, cu, cv, knob) are in the footprint frame, u right and v down.",
    }


def write(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    out = root / "hardware" / "owl-mainboard" / "mech" / "contract.json"
    write(out)
    print(out.relative_to(root))
