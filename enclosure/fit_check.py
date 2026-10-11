"""Check the main board's 3D export against enclosure v1: no board part may overlap the enclosure.

Export first (KiCad 10.0.6, grid origin at the display centre):
  kicad-cli pcb export step --grid-origin --subst-models --force \
    -o build/hardware/owl-mainboard.step hardware/owl-mainboard/owl-mainboard.kicad_pcb
then run: uv run --project enclosure python enclosure/fit_check.py build/hardware/owl-mainboard.step

The contract part boxes (owl_v1.pcb_envelope) are added to the exported solids, so a fixed part
whose KiCad 3D model is missing from the local library (kicad-cli says "Could not add 3D model")
is still checked at the size the enclosure reserves for it.
Licence: CERN-OHL-P-2.0 (LICENSE-HARDWARE).
"""

from __future__ import annotations

import sys
from pathlib import Path

from build123d import Compound, Pos, import_step

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owl_v1 as V  # noqa: E402
import ring_test as R  # noqa: E402

TOLERANCE_MM3 = 0.01


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
    board = Compound(solids + list(V.pcb_envelope().solids()))
    print(f"board: {len(solids)} exported solids plus the contract part boxes")
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
