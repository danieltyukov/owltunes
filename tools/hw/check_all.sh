#!/usr/bin/env bash
# Every hardware check CI runs. Needs kicad-cli 10.0.6 and KiCad's pcbnew Python module.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
python3 -m unittest discover -s tools/tests -p "test_hw_*.py"
python3 tools/hw/hw_kicad.py
flag() {
    python3 -c "import sys, tomllib; b = {x['name']: x for x in tomllib.load(open('hardware/boards.toml', 'rb'))['board']}; print('yes' if b['$1'].get('$2', False) else 'no')"
}
for board in owl-mainboard perch-dock; do
    python3 tools/hw/hw_titleblock.py --check "$board"
    if [ "$(flag "$board" netlist)" = yes ]; then
        python3 tools/hw/hw_netlist.py "$board"
        python3 tools/hw/hw_bom.py "$board"
    fi
    if [ "$(flag "$board" contract)" = yes ]; then
        python3 tools/hw/hw_contract.py check "$board"
    fi
done
if [ -f firmware/main/board_owltunes_reva.h ]; then
    python3 tools/hw/hw_pinmap.py
fi
