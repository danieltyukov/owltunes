#!/usr/bin/env python3
"""Generate and verify the JLCPCB files for a board.

1. Marks every footprint with assembled = false in design.toml (test points, holes, dock pads)
   as excluded from the BOM and the position file, and saves the board. This tool never edits
   schematics: it reports as a fabrication error every such part whose schematic symbol is not
   excluded from the BOM ((in_bom no) in the board's .kicad_sch files, set "Exclude from BOM"
   on the symbol) or whose footprint lacks either exclusion. The symbol exclusion is also what
   keeps the DRC schematic parity check quiet.
2. Runs the Fabrication Toolkit CLI (~/tools/Fabrication-Toolkit or $FT_DIR) with automatic
   rotation fixes; it writes hardware/<board>/production/ (not tracked).
3. Checks the outputs: every gerber layer present, BOM designators and LCSC numbers equal to the
   assembled parts in design.toml (each designator once, quantities matching), position file
   designators and sides equal to design.toml (each designator once). The MPN is not in the
   JLC BOM; it is checked in design.toml only.

Usage: python3 tools/hw/hw_fab.py owl-mainboard
"""

from __future__ import annotations

import csv
import os
import re
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


def symbol_errors(sheets: list[str], refs: list[str]) -> list[str]:
    """Name each ref whose schematic symbol is missing or not excluded from the BOM."""
    in_bom: dict[str, bool] = {}
    for text in sheets:
        for chunk in text.split("\n\t(symbol\n")[1:]:
            ref = re.search(r'\(property "Reference" "([^"]+)"', chunk)
            flag = re.search(r"\(in_bom (yes|no)\)", chunk)
            if ref and flag:
                in_bom[ref.group(1)] = flag.group(1) == "yes"
    errors = []
    for ref in refs:
        if ref not in in_bom:
            errors.append(f"{ref}: no schematic symbol found")
        elif in_bom[ref]:
            errors.append(f"{ref}: schematic symbol is in the BOM, set (in_bom no) (Exclude from BOM)")
    return errors


def exclusion_errors(pcb: Path, design: dict) -> list[str]:
    skip = [p["ref"] for p in design["part"] if not p.get("assembled", True)]
    sheets = [f.read_text(encoding="utf-8") for f in sorted(pcb.parent.glob("*.kicad_sch"))]
    errors = symbol_errors(sheets, skip)
    board = pcbnew.LoadBoard(str(pcb))
    for ref in skip:
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            errors.append(f"{ref}: no footprint on the board")
            continue
        attrs = fp.GetAttributes()
        if not attrs & pcbnew.FP_EXCLUDE_FROM_BOM:
            errors.append(f"{ref}: footprint is in the BOM, set Exclude from bill of materials")
        if not attrs & pcbnew.FP_EXCLUDE_FROM_POS_FILES:
            errors.append(f"{ref}: footprint is in the position files, set Exclude from position files")
    return errors


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
    for ref, part in assembled.items():
        if not part.get("lcsc"):
            errors.append(f"{ref}: assembled part has no lcsc in design.toml")
    with zipfile.ZipFile(out / f"{board}.zip") as z:
        names = z.namelist()
    for layer in LAYERS[copper]:
        if not any(f"-{layer}." in n for n in names):
            errors.append(f"gerber layer {layer} missing")
    if not any(n.endswith("-PTH.drl") for n in names):
        errors.append("drill file missing")
    with (out / "bom.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    bom_refs = {}
    bom_list = []
    for row in rows:
        refs = [r.strip() for r in row["Designator"].split(",")]
        if int(row["Quantity"]) != len(refs):
            errors.append(f"BOM row {row['Designator']!r} has quantity {row['Quantity']} for {len(refs)} designator(s)")
        for ref in refs:
            bom_list.append(ref)
            bom_refs[ref] = row["LCSC Part #"]
    for ref in sorted({r for r in bom_list if bom_list.count(r) > 1}):
        errors.append(f"BOM lists {ref} more than once")
    if set(bom_refs) != set(assembled):
        errors.append(f"BOM refs differ: extra {sorted(set(bom_refs) - set(assembled))}, missing {sorted(set(assembled) - set(bom_refs))}")
    for ref, lcsc in bom_refs.items():
        if ref in assembled and assembled[ref].get("lcsc") and lcsc != assembled[ref]["lcsc"]:
            errors.append(f"{ref}: BOM LCSC {lcsc!r}, design {assembled[ref]['lcsc']!r}")
    with (out / "positions.csv").open(encoding="utf-8-sig") as f:
        pos_rows = list(csv.DictReader(f))
    pos_list = [row["Designator"] for row in pos_rows]
    for ref in sorted({r for r in pos_list if pos_list.count(r) > 1}):
        errors.append(f"CPL lists {ref} more than once")
    pos = {row["Designator"]: row for row in pos_rows}
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
    errors = exclusion_errors(pcb, design) + verify(out, board, design, copper)
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
