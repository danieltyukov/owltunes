#!/usr/bin/env python3
"""Set a board's stackup, origins, JLCPCB minimum rules and net classes.

Reads hardware/<board>/setup.toml and applies it to <board>.kicad_pcb (pcbnew) and
<board>.kicad_pro (JSON). Run it again after editing setup.toml; it is idempotent.

Usage: python3 tools/hw/hw_setup.py owl-mainboard
"""

from __future__ import annotations

import json
import sys
import tomllib

import pcbnew

from hw_netlist import ROOT


def main(argv: list[str]) -> int:
    board_name = argv[0]
    folder = ROOT / "hardware" / board_name
    cfg = tomllib.loads((folder / "setup.toml").read_text())
    pcb_path = folder / f"{board_name}.kicad_pcb"
    board = pcbnew.LoadBoard(str(pcb_path))
    board.SetCopperLayerCount(cfg["copper_layers"])
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(pcbnew.FromMM(cfg["thickness_mm"]))
    origin = pcbnew.VECTOR2I(pcbnew.FromMM(cfg["origin_mm"][0]), pcbnew.FromMM(cfg["origin_mm"][1]))
    ds.SetAuxOrigin(origin)
    ds.SetGridOrigin(origin)
    pcbnew.SaveBoard(str(pcb_path), board)

    pro_path = folder / f"{board_name}.kicad_pro"
    pro = json.loads(pro_path.read_text())
    pro["board"]["design_settings"]["rules"].update(cfg["rules"])
    template = pro["net_settings"]["classes"][0]
    classes = []
    for name, values in cfg["netclass"].items():
        cls = dict(template)
        cls.update({k: v for k, v in values.items() if k != "nets"})
        cls["name"] = name
        cls["priority"] = 2147483647 if name == "Default" else len(classes)
        classes.append(cls)
    pro["net_settings"]["classes"] = classes
    pro["net_settings"]["netclass_patterns"] = [
        {"netclass": name, "pattern": net}
        for name, values in cfg["netclass"].items()
        for net in values.get("nets", [])
    ]
    pro_path.write_text(json.dumps(pro, indent=2) + "\n")
    print(f"{board_name}: {cfg['copper_layers']} layers, {cfg['thickness_mm']} mm, {len(classes)} net classes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
