# OwlTunes hardware

KiCad 10 projects for the owl main board (`owl-mainboard/`, 4 layers) and the perch board with its
snap-off owl dock-pad section (`perch-dock/`, 2 layers). Shared symbols and footprints are in
`lib/`. Licence: CERN-OHL-P-2.0 (`LICENSE-HARDWARE`).

Documentation: docs/hardware/README.md.

Each board has a `design.toml` that lists every part, its LCSC number and its pin-to-net map. The
schematic must match it exactly:

| Command | Checks |
|---|---|
| `tools/hw/check_all.sh` | Everything below, as CI runs it |
| `python3 tools/hw/hw_titleblock.py --check owl-mainboard` | Title blocks (title, Rev A, company, licence, date) of every schematic and the PCB; without `--check` it writes them |
| `python3 tools/hw/hw_netlist.py owl-mainboard` | Connectivity against `design.toml` |
| `python3 tools/hw/hw_bom.py owl-mainboard` | `LCSC Part #` and `MPN` fields |
| `python3 tools/hw/hw_kicad.py` | ERC (and DRC once enabled in `boards.toml`), reports in `build/hardware/` |
| `python3 tools/hw/hw_contract.py check owl-mainboard` | Outline and fixed parts against the enclosure contract |
| `python3 tools/hw/hw_stock.py owl-mainboard --boards 5` | JLCPCB stock (needs network) |

`tools/hw/hw_setup.py <board>` applies `setup.toml` (stackup, origins, JLCPCB rules, net classes).
The stackup in `setup.toml` is written into each PCB by `hw_setup.py`. Main board: JLCPCB 4-layer
1.0 mm, modelled on JLC04101H-7628 (35 um outer copper, 7628 prepreg 0.2104 mm, 15.2 um inner
copper); the core thickness (0.4788 mm) is chosen so the stack adds up to 1.0 mm and is to be
confirmed against https://jlcpcb.com/impedance on the order day. Perch board: 2-layer 1.6 mm FR-4.
A test checks that each stack adds up to the board thickness.

`hw_stock.py` writes prices only below the main checkout's `private/` folder.

Coordinates: the display centre is at (100, 100) on the board page, with X right and Y down.
Fabrication outputs (`production/`) are generated, not tracked; releases carry them.
