"""Export the assembled owl and perch as meshes for the product renders (tools/render/).

Writes one STL per visible part in owl coordinates (mm, X right, Y up, Z out of the glass) and
perch.json with the perch body's file name, the owl's docked placement as a 4 x 4 matrix and the
board's back face (owl Z), so the renders show the parts exactly as built. The battery is its
envelope; the board comes from KiCad (tools/render.sh); the bearing and carrier are left out. Owl v0
(owl_kit) goes to build/render/kit/: its six prints, and the kit and the bought parts drawn from
the envelopes the clearance tests use, split by material. Run
`uv run --project enclosure python enclosure/render_export.py`; output goes to build/render/.
Licence: CERN-OHL-P-2.0 (LICENSE-HARDWARE).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from build123d import export_stl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owl_kit as K  # noqa: E402
import owl_params as P  # noqa: E402
import owl_v1 as V  # noqa: E402
import perch_v1 as PV  # noqa: E402
import ring_test as R  # noqa: E402

KIT_GLASS_T = 0.7  # est.: Waveshare's drawing gives only the glass and panel together (2.05)
KIT_PCB_R = 23.0  # the 46 mm board


def owl_parts() -> dict:
    return {
        "body": V.body(),
        "back_cover": V.back_cover(),
        "bezel": V.bezel(),
        "glass": V.glass_envelope(),
        "ring": R.ring_a(),
        "beak_key": V.beak_key(),
        "ear_key_left": V.ear_key("SW201"),
        "ear_key_right": V.ear_key("SW202"),
        "battery": V.battery_envelope(),
    }


def kit_parts() -> dict:
    pcb_back = K.KIT_PCB_BACK_Z
    pcb_front = pcb_back + P.KIT_PCB_T
    ul, uw, uh = P.KIT_USB
    hx, hy, hh = P.KIT_HEADER
    standoffs = None
    for x, y in P.KIT_STANDOFFS:
        s = V.by_depth(x, y, P.KIT_STANDOFF_OD / 2, -P.KIT_STANDOFF_DEPTH, pcb_back)
        standoffs = s if standoffs is None else standoffs + s
    sockets = None
    for x0, x1 in P.KIT_SOCKETS_X:
        s = K.box(x0, P.KIT_SOCKETS_Y[0], x1, P.KIT_SOCKETS_Y[1], pcb_back - P.KIT_SOCKET_H, pcb_back)
        sockets = s if sockets is None else sockets + s
    return {
        **K.parts(),
        "glass": R.disc(P.KIT_GLASS_D / 2, -KIT_GLASS_T, 0.0),
        "panel": R.disc(P.KIT_BODY_R, pcb_front, -KIT_GLASS_T - 0.1),
        "pcb": R.disc(KIT_PCB_R, pcb_back, pcb_front),
        "usb": K.box(P.KIT_USB_MOUTH_X, -uw / 2, P.KIT_USB_MOUTH_X + ul, uw / 2, pcb_back - uh, pcb_back),
        "header": K.box(-hx / 2, P.KIT_HEADER_Y - hy / 2, hx / 2, P.KIT_HEADER_Y + hy / 2, pcb_back - hh, pcb_back),
        "standoffs": standoffs,
        "sockets": sockets,
        "tmag": K.tmag_envelope(),
        "switches": K.ear_switch_envelope(-1) + K.ear_switch_envelope(1) + K.beak_switch_envelope(),
        "magnets": K.magnets(),
        "battery": K.battery_envelope(),
    }


def main() -> int:
    out = Path(__file__).resolve().parents[1] / "build" / "render"
    (out / "kit").mkdir(parents=True, exist_ok=True)
    parts = owl_parts()
    for name, part in parts.items():
        export_stl(part, str(out / f"{name}.stl"), tolerance=0.005, angular_tolerance=0.05)
    kit = kit_parts()
    for name, part in kit.items():
        export_stl(part, str(out / "kit" / f"{name}.stl"), tolerance=0.005, angular_tolerance=0.05)
    export_stl(PV.perch_body(), str(out / "perch_body.stl"), tolerance=0.005, angular_tolerance=0.05)
    m = PV.owl_location().wrapped.Transformation()
    matrix = [[m.Value(r, c) for c in range(1, 5)] for r in range(1, 4)] + [[0.0, 0.0, 0.0, 1.0]]
    info = {"perch": "perch_body.stl", "owl_docked": matrix, "pcb_back_z": V.PCB_BACK_Z}
    (out / "perch.json").write_text(json.dumps(info, indent=2) + "\n")
    print(f"wrote {len(parts) + 1} meshes, perch.json and {len(kit)} owl v0 meshes to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
