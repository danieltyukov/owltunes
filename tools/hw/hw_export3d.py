#!/usr/bin/env python3
"""Export a board's STEP for the enclosure fit check, plus a box for every part without a model.

Runs kicad-cli pcb export step (grid origin at the display centre, STEP substituted for VRML)
and writes <out>.standins.json next to it: for each part kicad-cli could not load a 3D model
for, and each part with a design.toml height above 0 but no model at all, its courtyard outline
in owl coordinates, its side and its design.toml height. enclosure/fit_check.py extrudes these,
so a checkout without the gitignored EasyEDA models (hardware/lib/3dmodels, written by
hw_lib_build.py) gets the same verdict as a full one.

Usage: python3 tools/hw/hw_export3d.py owl-mainboard build/hardware/owl-mainboard.step
Needs kicad-cli 10.0.6 and KiCad's pcbnew Python module.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pcbnew

from hw_netlist import ROOT, load_design


def export(board_name: str, out: Path) -> int:
    pcb = ROOT / "hardware" / board_name / f"{board_name}.kicad_pcb"
    out.parent.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(["kicad-cli", "pcb", "export", "step", "--grid-origin", "--subst-models", "--force",
                          "-o", str(out), str(pcb)], capture_output=True, text=True)
    if run.returncode != 0:
        print(run.stdout + run.stderr)
        return 1
    missing = set(re.findall(r"Could not add 3D model for (\S+?)\.", run.stdout + run.stderr))
    design = {p["ref"]: p for p in load_design(board_name)["part"]}
    board = pcbnew.LoadBoard(str(pcb))
    standins = []
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        ref = fp.GetReference()
        height = design.get(ref, {}).get("height", 0.0)
        if height <= 0 or not (ref in missing or len(fp.Models()) == 0):
            continue
        fp.BuildCourtyardCaches()
        back = fp.IsFlipped()
        crt = fp.GetCourtyard(pcbnew.B_CrtYd if back else pcbnew.F_CrtYd)
        outline = crt.Outline(0)
        pts = [(round(pcbnew.ToMM(outline.CPoint(i).x) - 100, 4), round(100 - pcbnew.ToMM(outline.CPoint(i).y), 4))
               for i in range(outline.PointCount())]
        standins.append({"ref": ref, "side": "back" if back else "front", "height": height, "points": pts})
    path = out.with_suffix(".standins.json")
    path.write_text(json.dumps(standins, indent=1) + "\n")
    print(f"{out}: {len(standins)} part(s) without a 3D model, written as courtyard boxes to {path.name}: "
          + " ".join(s["ref"] for s in standins))
    return 0


if __name__ == "__main__":
    sys.exit(export(sys.argv[1], Path(sys.argv[2])))
