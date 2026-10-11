# Rev A design review

Two sections: the perch dock board (written, 11 October 2026) and the main board (written after the
main board is routed, in task 12 part B).

## Perch dock board (perch-dock, 2 layers, 34.0 x 29.0 mm with the dock-pad section)

Verdict: ready to order, subject to the placement preview rotation check at order time
(listed in the private order notes). Blockers: none.

### Blockers

| Finding | Status |
|---|---|
| none | |

### Checks run

| Check | Result |
|---|---|
| ERC (`hw_kicad.py perch-dock`) | 0 violations |
| DRC with schematic parity | 0 violations, 0 unconnected, 0 parity |
| `hw_fab.py perch-dock` | 0 fabrication errors; 15 placements, all top; BOM 14 rows, 15 designators; CPL equals `design.toml` |
| Gerber analysis (`analyze_gerbers.py`) | complete: F/B Cu, F/B mask, F/B silkscreen, F/B paste, Edge.Cuts, PTH and NPTH drills; board 34.0 x 29.0 mm; layers aligned; 0 findings |
| kicad-happy schematic analysis | 13 findings, none blocking (see below) |
| kicad-happy PCB analysis (`--full`) | 28 findings, none blocking (see below) |
| kicad-happy cross analysis | 0 findings |
| kicad-happy EMC analysis | 8 findings, none blocking (see below) |
| kicad-happy thermal analysis | 0 findings |

### Findings accepted, with the reason

| Rule | Finding | Reason |
|---|---|---|
| KO-001 (error) | MB1 and MB2 inside the neck keep-out | False positive. The keep-out forbids tracks, vias and copper pours; footprints and pads are allowed. The mouse-bite holes are the footprints meant to sit in the neck. |
| FD-001 (error) | No fiducials on F.Cu | Accepted. 15 parts, none finer than 0402 and no fine-pitch IC, so placement accuracy does not depend on fiducials. |
| GP-001 (error and warning) | Reference plane gaps on PAD_DET and DOCK_ID | Accepted. Both are DC detect levels, no switching edges; the board carries 5 V power and a few mA. |
| GP-005, BE-001, BE-002, RP-001, SU-001, EE-001 | Ground domain, edge, stitching and resonance notes | Accepted. Two-layer power-only board, no signal above DC; the second ground domain is the isolated pad section ground (PAD_GND) which reaches the board only through the owl's own cabling. |
| UC-001 | No capacitor on VBUS_IN at J1 | Accepted. C1 (10 uF) and C2 (100 nF) sit on VBUS_OUT behind the 1.1 A fuse F1; the board has no USB data and no downstream regulator. |
| UC-002 | No TVS on VBUS_IN at J1 | False positive. D1 (SMF5.0A, unidirectional TVS) is on VBUS_IN to GND; the detector does not know the SMF series. |
| RS-001 | VBUS_OUT has no declared source | False positive. VBUS_OUT is fed from VBUS_IN through the fuse F1 (a passive); ERC passes. |
| PM-002 | F1 0.87 mm from the board edge | Accepted. The edge is a plain outline edge with no depanel cut near the fuse; DRC edge clearance passes. |
| TE-001 | No test points | Accepted. Every net is on a pad, connector pin or pogo contact. |
| DS-002 | No datasheets directory | Review gap, see below. |
| TB-001 | Tombstoning risk medium on R1, R2, R3, C2 | Accepted. Symmetric pads, standard 0402 land pattern; JLCPCB reflow. |
| LA-AUD | LED1 current | Accepted. About 0.7 mA through R4 (4.7 k from about 5 V), a dim indicator, chosen to keep the dock idle draw low. |

### Analyses not run, and why

| Analysis | Reason |
|---|---|
| Datasheet cross-verification (`datasheets/`) | Not synced. The perch board has no IC; the passive values and the USB-C CC resistors (5.1 k pull-downs on CC1 and CC2) were checked against the USB Type-C specification by hand. |
| SPICE | ngspice is installed, but the board is a fuse, a TVS, an ESD diode and an LED; there is no analog behavior to simulate beyond the LED current above. |
| Lifecycle audit | Needs network access; stock is re-checked with `hw_stock.py` on the day of the order. |
| Prior review delta | This is the first review. |

### Fabrication output notes

- The Fabrication Toolkit names the archive after the title block; `hw_fab.py` renames it to
  `perch-dock.zip` and restores `perch-dock.kicad_pro`, which pcbnew reorders when it saves the
  board.
- Parts with `assembled = false` (H1, H2, PAD1 to PAD3, MB1, MB2) are excluded from the BOM and the
  position file on the board and on the symbols, so schematic parity stays at 0.
- No rotation table entry of the toolkit matches a perch footprint, so the CPL rotation is the
  KiCad rotation. Polarised parts to check in the placement preview: J1, J2, D1, D2, LED1, P1 to P3.

## Main board (owl-mainboard)

To be written in task 12 part B, after the main board is routed.
