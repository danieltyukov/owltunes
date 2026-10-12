"""Check the main board's 3D export against enclosure v1: no board part may overlap the enclosure.

Export first (KiCad 10.0.6, grid origin at the display centre); the export tool also writes
owl-mainboard.standins.json with the courtyard of every part kicad-cli has no 3D model for:
  python3 tools/hw/hw_export3d.py owl-mainboard build/hardware/owl-mainboard.step
then run: uv run --project enclosure python enclosure/fit_check.py build/hardware/owl-mainboard.step

No part is skipped (ruling R45): a part without a model (the EasyEDA models in hardware/lib/3dmodels
are gitignored and exist only after tools/hw/hw_lib_build.py) is its courtyard outline extruded to
its design.toml height plus the 0.1 mm pad stand-off, or, for a part the contract fixes, its contract
box (owl_v1.pcb_envelope, always added); each is named in the output.
Licence: CERN-OHL-P-2.0 (LICENSE-HARDWARE).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from build123d import Compound, Polyline, Pos, import_step, make_face

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owl_v1 as V  # noqa: E402
import ring_test as R  # noqa: E402

TOLERANCE_MM3 = 0.01
STANDOFF = 0.1  # pad and solder under a part, as in tools/hw/hw_contract.py (R44)


def standins(step: Path) -> tuple[list, list[str], list[str]]:
    """Boxes for the parts the export has no 3D model for: a fixed part is already its contract
    box (pcb_envelope; its courtyard margin would run into the wall round its opening, as J201's
    does), every other part is its courtyard extruded."""
    path = step.with_suffix(".standins.json")
    if not path.is_file():
        raise SystemExit(f"{path} missing: export with tools/hw/hw_export3d.py so no part is skipped")
    fixed = {p.ref for p in V.C.PLACEMENTS}
    solids, refs, boxed = [], [], []
    for s in json.loads(path.read_text()):
        if s["ref"] in fixed:
            boxed.append(s["ref"])
            continue
        h = s["height"] + STANDOFF
        z0, z1 = (V.PCB_BACK_Z - h, V.PCB_BACK_Z) if s["side"] == "back" else (V.PCB_FRONT_Z, V.PCB_FRONT_Z + h)
        pts = [tuple(p) for p in s["points"]]
        if pts[0] == pts[-1]:
            pts.pop()
        # KiCad's y points down, so its outlines arrive clockwise in owl coordinates; a clockwise
        # face extrudes to an inside-out solid.
        if sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1])) < 0:
            pts.reverse()
        solids += V.prism(make_face(Polyline(*pts, close=True)), z0, z1).solids()
        refs.append(s["ref"])
    return solids, refs, boxed


def enclosure() -> dict:
    return {
        "body": V.body(),
        "back_cover": V.back_cover(),
        "bezel": V.bezel(),
        "ring": R.ring_a(),
        "bearing": R.bearing_dummy(),
        "carrier": R.magnet_carrier(24, bumps=False),
        "battery": V.battery_envelope(),
        "beak_key": V.beak_key(),
        "ear_key_left": V.ear_key("SW201"),
        "ear_key_right": V.ear_key("SW202"),
    }


def main(argv: list[str]) -> int:
    # Move each solid: a location set on the imported compound is ignored by the booleans.
    solids = [s.moved(Pos(0, 0, V.PCB_BACK_Z)) for s in import_step(argv[0]).solids()]
    boxes, refs, boxed = standins(Path(argv[0]))
    board = Compound(solids + boxes + list(V.pcb_envelope().solids()))
    print(f"board: {len(solids)} exported solids, the contract part boxes and {len(refs)} courtyard boxes")
    print(f"no 3D model, checked as contract boxes: {' '.join(boxed) if boxed else 'none'}")
    print(f"no 3D model, checked as courtyard boxes: {' '.join(refs) if refs else 'none'}")
    clashes = []
    for name, part in enclosure().items():
        common = board & part
        volume = common.volume if common is not None else 0.0
        print(f"{name:14s} overlap {volume:8.3f} mm3")
        if volume > TOLERANCE_MM3:
            clashes.append(name)
    print(f"fit check: {len(clashes)} clash(es)")
    return 1 if clashes else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
