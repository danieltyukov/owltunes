"""Export the assembled owl and perch as meshes for the product renders (tools/render/).

Writes one STL per visible part in owl coordinates (mm, X right, Y up, Z out of the glass) and
perch.json with the perch body's file name, the owl's docked placement as a 4 x 4 matrix and the
board's back face (owl Z), so the renders show the parts exactly as built. The battery is its
envelope; the board comes from KiCad (tools/render.sh); the bearing and carrier are left out. Run `uv run --project enclosure python enclosure/render_export.py`; output goes to
build/render/. Licence: CERN-OHL-P-2.0 (LICENSE-HARDWARE).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from build123d import export_stl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owl_v1 as V  # noqa: E402
import perch_v1 as PV  # noqa: E402
import ring_test as R  # noqa: E402


def owl_parts() -> dict:
    return {
        "body": V.body(),
        "back_cover": V.back_cover(),
        "bezel": V.bezel(),
        "glass_retainer": V.glass_retainer(),
        "glass": V.glass_envelope(),
        "ring": R.ring_a(),
        "beak_key": V.beak_key(),
        "ear_key_left": V.ear_key("SW201"),
        "ear_key_right": V.ear_key("SW202"),
        "battery": V.battery_envelope(),
    }


def main() -> int:
    out = Path(__file__).resolve().parents[1] / "build" / "render"
    out.mkdir(parents=True, exist_ok=True)
    parts = owl_parts()
    for name, part in parts.items():
        export_stl(part, str(out / f"{name}.stl"), tolerance=0.005, angular_tolerance=0.05)
    export_stl(PV.perch_body(), str(out / "perch_body.stl"), tolerance=0.005, angular_tolerance=0.05)
    m = PV.owl_location().wrapped.Transformation()
    matrix = [[m.Value(r, c) for c in range(1, 5)] for r in range(1, 4)] + [[0.0, 0.0, 0.0, 1.0]]
    info = {"perch": "perch_body.stl", "owl_docked": matrix, "pcb_back_z": V.PCB_BACK_Z}
    (out / "perch.json").write_text(json.dumps(info, indent=2) + "\n")
    print(f"wrote {len(parts) + 1} meshes and perch.json to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
