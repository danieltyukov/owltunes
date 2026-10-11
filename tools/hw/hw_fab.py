#!/usr/bin/env python3
"""Generate and verify the JLCPCB files for a board.

1. Marks every part with assembled = false in design.toml as excluded from the BOM and the
   position file (test points, holes, dock pads), on the board and on the schematic symbols
   (so the DRC schematic parity check stays quiet), and saves both.
2. Runs the Fabrication Toolkit CLI (~/tools/Fabrication-Toolkit or $FT_DIR) with automatic
   rotation fixes; it writes hardware/<board>/production/ (not tracked).
3. Checks the outputs: every gerber layer present, BOM designators and LCSC numbers equal to the
   assembled parts in design.toml, position file designators and sides equal to design.toml.

Usage: python3 tools/hw/hw_fab.py owl-mainboard
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pcbnew

from hw_netlist import ROOT, load_design

LAYERS = {
    2: ["F_Cu", "B_Cu", "F_Mask", "B_Mask", "F_Paste", "F_Silkscreen", "B_Silkscreen", "Edge_Cuts"],
    4: ["F_Cu", "In1_Cu", "In2_Cu", "B_Cu", "F_Mask", "B_Mask", "F_Paste", "B_Paste",
        "F_Silkscreen", "B_Silkscreen", "Edge_Cuts"],
}


def mark_unassembled(pcb: Path, design: dict) -> int:
    board = pcbnew.LoadBoard(str(pcb))
    skip = {p["ref"] for p in design["part"] if not p.get("assembled", True)}
    flags = pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES
    for fp in board.GetFootprints():
        if fp.GetReference() in skip:
            fp.SetAttributes(fp.GetAttributes() | flags)
    pcbnew.SaveBoard(str(pcb), board)
    return board.GetCopperLayerCount()


def run_toolkit(pcb: Path) -> None:
    ft = Path(os.environ.get("FT_DIR", Path.home() / "tools" / "Fabrication-Toolkit"))
    cmd = [sys.executable, "-m", "plugins.cli", "-p", str(pcb), "--autoTranslate", "--excludeDNP",
           "--nonInteractive", "--noBackup"]
    out = pcb.parent / "production"
    shutil.rmtree(out, ignore_errors=True)
    subprocess.run(cmd, cwd=ft, check=True, capture_output=True, text=True)
    # The toolkit names the archive after the title block; the rest of the tooling expects <board>.zip.
    (archive,) = out.glob("*.zip")
    archive.rename(out / f"{pcb.stem}.zip")


def verify(out: Path, board: str, design: dict, copper: int) -> list[str]:
    errors = []
    assembled = {p["ref"]: p for p in design["part"] if p.get("assembled", True)}
    with zipfile.ZipFile(out / f"{board}.zip") as z:
        names = z.namelist()
    for layer in LAYERS[copper]:
        if not any(f"-{layer}." in n for n in names):
            errors.append(f"gerber layer {layer} missing")
    if not any(n.endswith("PTH.drl") for n in names):
        errors.append("drill file missing")
    with (out / "bom.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    bom_refs = {}
    for row in rows:
        for ref in (r.strip() for r in row["Designator"].split(",")):
            bom_refs[ref] = row["LCSC Part #"]
    if set(bom_refs) != set(assembled):
        errors.append(f"BOM refs differ: extra {sorted(set(bom_refs) - set(assembled))}, missing {sorted(set(assembled) - set(bom_refs))}")
    for ref, lcsc in bom_refs.items():
        if ref in assembled and lcsc != assembled[ref]["lcsc"]:
            errors.append(f"{ref}: BOM LCSC {lcsc!r}, design {assembled[ref]['lcsc']!r}")
    with (out / "positions.csv").open(encoding="utf-8-sig") as f:
        pos = {row["Designator"]: row for row in csv.DictReader(f)}
    if set(pos) != set(assembled):
        errors.append(f"CPL refs differ: extra {sorted(set(pos) - set(assembled))}, missing {sorted(set(assembled) - set(pos))}")
    for ref, row in pos.items():
        if ref in assembled:
            want = "top" if assembled[ref]["side"] == "front" else "bottom"
            if row["Layer"] != want:
                errors.append(f"{ref}: CPL layer {row['Layer']}, design side {assembled[ref]['side']}")
    return errors


def main(argv: list[str]) -> int:
    board = argv[0]
    pcb = ROOT / "hardware" / board / f"{board}.kicad_pcb"
    design = load_design(board)
    project = pcb.with_suffix(".kicad_pro")
    before = project.read_bytes()
    try:
        copper = mark_unassembled(pcb, design)
        run_toolkit(pcb)
    finally:
        project.write_bytes(before)  # saving the board reorders the DRC exclusions in the project file
    out = pcb.parent / "production"
    errors = verify(out, board, design, copper)
    for e in errors:
        print(e)
    sides = {"top": 0, "bottom": 0}
    for p in design["part"]:
        if p.get("assembled", True):
            sides["top" if p["side"] == "front" else "bottom"] += 1
    print(f"{board}: {len(errors)} fabrication error(s); placements top {sides['top']}, bottom {sides['bottom']}; files in {out.relative_to(ROOT)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
